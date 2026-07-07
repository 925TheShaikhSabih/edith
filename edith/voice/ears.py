"""
E.D.I.T.H.'s ears — speech-to-text, behind a seam.

Per AGENT.md and the harness doc: "give me audio, get back text," one
function, swappable later. Everything else (main_voice.py) calls into this
module and never touches termux-microphone-record, ffmpeg, or Deepgram's
WebSocket protocol directly.

This wraps the EXACT pipeline confirmed working live, on-device, via Termux:
    termux-microphone-record (capture, always outputs AAC/M4A)
      -> ffmpeg (decode to genuine headerless 16kHz mono linear16 PCM)
      -> Deepgram WebSocket (batch send, get transcript back)

This is a BATCH pipeline, not a continuously-streaming one — record for a
fixed/bounded duration, then transcribe the whole recording at once. That's
an honest fit for push-to-talk as the harness doc defines it (a deliberate
start/stop action), not a limitation being quietly worked around. A move to
true live-streaming (holding the Deepgram connection open, sending audio as
it's captured rather than after) is a real possible upgrade later, but it's
a change *inside* this seam — nothing that calls listen() needs to change
for it.

TWO REAL BUGS were found and fixed while proving this pipeline out, kept
here as comments since they're easy to reintroduce by "simplifying":
  1. termux-microphone-record ALWAYS outputs AAC audio in an M4A container,
     regardless of what filename/extension you give it — there is no
     WAV/raw-PCM option in its interface at all. Skipping the ffmpeg
     decode step and sending the raw file to Deepgram results in Deepgram
     reporting an audio duration of 0 (it can't interpret compressed AAC
     bytes as literal PCM samples). The ffmpeg step below is REQUIRED, not
     an optional quality improvement.
  2. ffmpeg must be installed via `pkg install ffmpeg` (Termux's system
     package manager), NOT `pip install ffmpeg` or `pip install
     ffmpeg-python` — pip installs Python code, not the actual ffmpeg
     binary, and subprocess calls to "ffmpeg" will fail with
     FileNotFoundError if only the pip package was installed.
"""

import asyncio
import json
import os
import subprocess
import time
import uuid
from pathlib import Path

import websockets


# Where recordings/conversions live during a single listen() call. Kept in
# a dedicated tmp folder (not mixed into the project root like roadmap.json)
# since these are throwaway working files, not durable project data.
AUDIO_TMP_DIR = Path(__file__).resolve().parent.parent.parent / "voice_tmp"

DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen?encoding=linear16&sample_rate=16000"


class HearingError(Exception):
    """Raised when listen() can't produce a transcript, for any reason —
    mic capture failed, ffmpeg isn't installed, Deepgram was unreachable,
    the recording was silence, etc. The caller is expected to catch this
    and let the user try again rather than crash the session, matching
    how BrainError is handled in brain.py/main.py."""
    pass


def _check_ffmpeg_available():
    """Fail fast and clearly if ffmpeg isn't on PATH, rather than let a
    cryptic FileNotFoundError surface later from inside a subprocess call.
    This is exactly the failure this project hit once already during
    testing (pip install ffmpeg vs pkg install ffmpeg) — catch it early
    with a message that says what to actually do about it."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True,
        )
    except FileNotFoundError as e:
        raise HearingError(
            "ffmpeg isn't installed or isn't on PATH. On Termux, run: "
            "pkg install ffmpeg (NOT pip install ffmpeg — that installs "
            "Python code, not the actual ffmpeg program)."
        ) from e
    except subprocess.CalledProcessError as e:
        raise HearingError(f"ffmpeg is present but returned an error: {e}") from e


def _record_audio(seconds: int, m4a_path: Path):
    """Capture audio via termux-microphone-record.

    IMPORTANT, found via real on-device testing (not assumed): this command
    does NOT block until recording finishes. It starts an asynchronous
    background recording and returns to the shell almost immediately — the
    `-l` flag sets a MAXIMUM duration ceiling, not something the command
    waits for. This first became clear from a "moov atom not found" ffmpeg
    error: an MP4/M4A file's index (the moov atom) only gets written when
    the recording is properly finished, and this code was previously
    handing the file to ffmpeg while it was still being actively written by
    a separate, still-running background process — subprocess.run() here
    only waits for the *launch* of that background process, which returns
    in a fraction of a second, nowhere near the actual recording duration.

    The correct pattern (confirmed via Termux:API's own documented usage):
    start the recording, actually wait out the requested duration ourselves
    in Python, then explicitly stop it with `termux-microphone-record -q` —
    which is also what finalizes the file (writes the moov atom) rather
    than just letting `-l` silently expire on its own.

    Always produces AAC in an M4A container regardless of filename — see
    the module docstring's bug #1 for why the extension doesn't matter.
    """
    try:
        subprocess.run(
            ["termux-microphone-record", "-l", str(seconds), "-f", str(m4a_path)],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError as e:
        raise HearingError(
            "termux-microphone-record isn't available. This requires Termux "
            "with the Termux:API companion app installed (pkg install "
            "termux-api), not a generic Python environment."
        ) from e
    except subprocess.CalledProcessError as e:
        raise HearingError(f"Recording failed: {e.stderr.decode(errors='replace')}") from e

    # Actually wait out the recording duration ourselves — the command
    # above returned almost instantly and is recording in the background
    # while this sleep runs. A small buffer (+0.5s) on top of the
    # requested duration gives the background process a moment to
    # naturally reach the point we're about to explicitly stop it at,
    # rather than racing it.
    time.sleep(seconds + 0.5)

    # Explicitly stop the recording. This is what finalizes/flushes the
    # M4A container (writes the moov atom) — waiting for `-l` to expire
    # on its own was the missing step; -q makes the stop explicit and
    # synchronous from termux-microphone-record's own perspective, rather
    # than hoping the file is done by the time we look at it.
    try:
        subprocess.run(
            ["termux-microphone-record", "-q"],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        # If there was nothing to stop (e.g. it already finished on its
        # own right at the -l boundary), this can fail harmlessly — don't
        # treat that as fatal, but do still apply the settle pause below.
        pass

    # A short additional pause for the file to be fully flushed to disk
    # after the stop command, confirmed necessary during testing.
    time.sleep(1)

    if not m4a_path.exists() or m4a_path.stat().st_size == 0:
        raise HearingError(
            "Recording finished but produced no audio file (or an empty "
            "one). Check microphone permissions were granted to Termux:API."
        )


def _convert_to_pcm(m4a_path: Path, pcm_path: Path):
    """Decode AAC/M4A into genuine headerless 16kHz mono linear16 PCM,
    matching what DEEPGRAM_WS_URL declares it's receiving. This is the
    fix for bug #1 in the module docstring — skipping this step is the
    single most likely way to reintroduce the 'duration 0' failure."""
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(m4a_path),
                "-ar", "16000",
                "-ac", "1",
                "-f", "s16le",
                str(pcm_path),
            ],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        raise HearingError(
            f"ffmpeg couldn't convert the recording: {e.stderr.decode(errors='replace')}"
        ) from e


async def _send_to_deepgram(pcm_path: Path) -> str:
    """Stream the converted PCM to Deepgram and collect the transcript.
    Returns the transcript text (possibly empty, if nothing intelligible
    was captured — that's a valid result, not an error)."""
    api_key = os.environ.get("DEEPGRAM_API_KEY")
    if not api_key:
        raise HearingError(
            "No Deepgram API key found. Set DEEPGRAM_API_KEY in your "
            "environment (e.g. in .env) before using voice input."
        )

    with open(pcm_path, "rb") as f:
        audio_data = f.read()

    headers = {"Authorization": f"Token {api_key}"}

    try:
        # NOTE: `additional_headers` is the current (websockets 16.x)
        # parameter name; older installed versions may need `extra_headers`
        # instead. Confirmed correct during live on-device testing with
        # this exact call — if a future websockets upgrade breaks this,
        # that's the first thing to check.
        async with websockets.connect(DEEPGRAM_WS_URL, additional_headers=headers) as ws:
            await ws.send(audio_data)
            await ws.send(json.dumps({"type": "CloseStream"}))

            transcript_parts = []
            async for message in ws:
                data = json.loads(message)
                if data.get("channel"):
                    piece = data["channel"]["alternatives"][0]["transcript"]
                    if piece:
                        transcript_parts.append(piece)
                if data.get("type") == "Metadata":
                    break

            return " ".join(transcript_parts).strip()

    except Exception as e:
        raise HearingError(f"Couldn't reach Deepgram: {e}") from e


def listen(seconds: int = 5) -> str:
    """
    Record from the mic for a fixed duration and return the transcribed
    text. This is the whole seam — the one function everything else calls.

    Raises HearingError on any failure (missing ffmpeg, mic permission
    denied, network issue reaching Deepgram, missing API key, etc.) so the
    caller can show a clean message and let the user try again, matching
    how BrainError is handled elsewhere in this project.

    Returns an empty string (not an error) if recording succeeded but
    nothing intelligible was captured — silence is a valid outcome, not a
    failure, and the caller should decide how to handle that (e.g. "didn't
    catch that, try again").
    """
    _check_ffmpeg_available()

    AUDIO_TMP_DIR.mkdir(exist_ok=True)
    # A unique-per-call filename so overlapping/rapid calls (shouldn't
    # normally happen with push-to-talk, but worth being defensive) can't
    # clobber each other's working files.
    call_id = uuid.uuid4().hex[:8]
    m4a_path = AUDIO_TMP_DIR / f"rec_{call_id}.m4a"
    pcm_path = AUDIO_TMP_DIR / f"rec_{call_id}.pcm"

    try:
        _record_audio(seconds, m4a_path)
        _convert_to_pcm(m4a_path, pcm_path)
        return asyncio.run(_send_to_deepgram(pcm_path))
    finally:
        # Clean up working files regardless of success/failure — these are
        # throwaway, not durable data worth keeping around.
        m4a_path.unlink(missing_ok=True)
        pcm_path.unlink(missing_ok=True)
