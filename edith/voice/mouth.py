"""
E.D.I.T.H.'s mouth — text-to-speech, behind a seam.

Per AGENT.md and the harness doc: "give me text, play it aloud," one
function, swappable later. Everything else calls into this module and
never touches the elevenlabs SDK directly.

Provider: ElevenLabs (per the original design doc). Free tier confirmed
directly against the user's own dashboard: 10,000 credits/month, API
access included, non-commercial only. Roughly 1 credit per character on
standard models; eleven_flash_v2_5 (used here) costs less per character
on top of being faster — a genuine win on both latency and quota for
this project, not a tradeoff.

Model choice: eleven_flash_v2_5, not eleven_v3. Confirmed (multiple
current sources): Flash targets ~75ms model inference and ~150-300ms
time-to-first-audio-chunk, which matters here because latency compounds
across the whole voice pipeline (record -> convert -> transcribe -> think
-> speak) — v3 sounds richer but there's no expressed need for that yet,
and it costs more credits per character against a real monthly ceiling.

VOICE_ID is deliberately left as a required config value, not hardcoded
to some default I picked myself — per AGENT.md's own Tier 3 notes, this
was meant to be a deliberate choice, kept in config rather than buried.
"""

import os
import subprocess
import time
from pathlib import Path

from elevenlabs.client import ElevenLabs
from elevenlabs import save as save_audio


# Kept as one constant so it's a one-line change later, matching brain.py's
# MODEL_NAME pattern. See module docstring for why Flash over v3.
MODEL_ID = "eleven_flash_v2_5"

# REQUIRED — set this to a real voice_id from your ElevenLabs voice
# library before using speak(). Deliberately left unset rather than
# defaulted, per AGENT.md's note that voice choice should be explicit.
# User selected voice_id "uYXf8XasLslADfZ2MB4u" from their own voice
# library browsing — set ELEVENLABS_VOICE_ID to this value in .env.
VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID")

# Where generated audio files live during a single speak() call — same
# pattern as ears.py's AUDIO_TMP_DIR, throwaway working files, not durable
# data.
AUDIO_TMP_DIR = Path(__file__).resolve().parent.parent.parent / "voice_tmp"


class SpeakingError(Exception):
    """Raised when speak() can't produce or play audio, for any reason —
    missing API key, missing voice ID, network issue reaching ElevenLabs,
    no audio player available on this device, etc. Caught by the caller
    so a failure here doesn't crash the session, matching BrainError and
    HearingError elsewhere in this project."""
    pass


def _build_client() -> ElevenLabs:
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise SpeakingError(
            "No ElevenLabs API key found. Set ELEVENLABS_API_KEY in your "
            "environment (e.g. in .env) before using voice output."
        )
    return ElevenLabs(api_key=api_key)


def speak(text: str) -> Path:
    """
    Convert text to speech and save it as an audio file, returning the
    path. Does NOT play it — playback is a separate concern (see
    play_audio() below), kept apart so a caller could, for instance,
    generate audio without immediately playing it.

    Raises SpeakingError on any failure — missing key, missing voice ID,
    network issue, empty text, etc. — so the caller can show a clean
    message and continue rather than crash.
    """
    if not text or not text.strip():
        raise SpeakingError("nothing to speak — text was empty")

    if not VOICE_ID:
        raise SpeakingError(
            "No ElevenLabs voice selected. Set ELEVENLABS_VOICE_ID in your "
            "environment to a real voice_id from your ElevenLabs voice "
            "library before using voice output."
        )

    client = _build_client()

    try:
        audio = client.text_to_speech.convert(
            text=text,
            voice_id=VOICE_ID,
            model_id=MODEL_ID,
            output_format="mp3_44100_128",
        )
    except Exception as e:
        raise SpeakingError(f"Couldn't reach ElevenLabs: {e}") from e

    AUDIO_TMP_DIR.mkdir(exist_ok=True)
    out_path = AUDIO_TMP_DIR / "reply.mp3"
    try:
        save_audio(audio, str(out_path))
    except Exception as e:
        raise SpeakingError(f"Got audio back but couldn't save it: {e}") from e

    return out_path


def _probe_duration_seconds(audio_path: Path) -> float:
    """Ask ffprobe (part of the ffmpeg install already required by
    ears.py) for the real duration of an audio file, rather than guess.

    This exists specifically because of the lesson from ears.py's
    async-recording bug: trusting a Termux:API-style command's return to
    mean "the real-world audio event is finished" was wrong once already
    (termux-microphone-record returns almost instantly while recording
    continues in the background). termux-media-player's play/pause/stop
    being separate commands — rather than one command that runs and
    completes — is the same structural shape, which is reason to suspect
    (not yet confirmed) it behaves the same asynchronous way. Rather than
    assume either way, get the ACTUAL duration and wait that out
    explicitly, so play_audio() doesn't depend on guessing right about
    something unconfirmed."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(audio_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError) as e:
        raise SpeakingError(f"Couldn't determine audio duration: {e}") from e


def play_audio(audio_path: Path):
    """
    Play an audio file aloud via termux-media-player.

    Waits out the audio's ACTUAL duration (via ffprobe) rather than
    trusting termux-media-player's own return to mean playback finished —
    see _probe_duration_seconds()'s docstring for why: the same command
    shape (separate play/pause/stop commands) that turned out to be
    asynchronous for termux-microphone-record is present here too, and
    this project has already been burned once by assuming a Termux:API
    command blocks when it doesn't. Better to not repeat that specific
    mistake, even though this exact command hasn't been confirmed
    asynchronous the way the recording one was.

    Raises SpeakingError on failure (player not available, file missing,
    etc.) so the caller can continue rather than crash.
    """
    if not audio_path.exists():
        raise SpeakingError(f"audio file not found: {audio_path}")

    duration = _probe_duration_seconds(audio_path)

    try:
        subprocess.run(
            ["termux-media-player", "play", str(audio_path)],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError as e:
        raise SpeakingError(
            "termux-media-player isn't available. This requires Termux "
            "with the Termux:API companion app installed (pkg install "
            "termux-api)."
        ) from e
    except subprocess.CalledProcessError as e:
        raise SpeakingError(f"Playback failed: {e.stderr.decode(errors='replace')}") from e

    # Wait out the real duration, plus a small buffer, rather than trust
    # the command above to have blocked until playback finished.
    time.sleep(duration + 0.5)
