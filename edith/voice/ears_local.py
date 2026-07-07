"""
E.D.I.T.H.'s ears — LOCAL/OFFLINE alternative using Vosk.

This is a PARALLEL alternative to ears.py (Deepgram), not a replacement.
ears.py is untouched and still works exactly as before. This file exists
so the two approaches can be tried and compared before committing to
either — per the explicit ask: "always free" as a goal, weighed against
Deepgram's real but revocable/limited free tier.

REAL TRADEOFF, stated plainly: Vosk is genuinely free forever (it's a
local model, no API, no account, no credits to run out) — but multiple
independent sources describe it as less accurate than Deepgram,
especially with background noise or unclear speech. Given the cloud
pipeline's transcripts were already "a bit messy," this is worth going in
with open eyes about, not discovering after the fact.

GENUINE, UN-RESOLVED RISK, same shape as today's pydantic_core saga:
PyPI's vosk wheels are tagged for standard glibc Linux
(manylinux2014_aarch64), not Termux's actual android_*_arm64_v8a tag
family (confirmed via this project's own `pip debug --verbose` output
earlier today). This MAY fail to install on Termux for the exact same
reason pydantic_core did. Not glossed over — this is the first real test
before anything else here matters. If `pip install vosk` fails with a
platform-tag error, that's this exact risk materializing, and the
resolution path (Termux-native build tooling, or accepting the wheel
genuinely isn't available) would need its own investigation, the same way
pydantic_core did.

Uses the same termux-microphone-record -> ffmpeg pipeline as ears.py for
capture and format conversion (that part is proven, on-device, working —
no reason to change it), then swaps Deepgram's WebSocket call for a local
Vosk recognizer instead.
"""

import json
import subprocess
import time
import uuid
import wave
from pathlib import Path

from vosk import Model, KaldiRecognizer, SetLogLevel


AUDIO_TMP_DIR = Path(__file__).resolve().parent.parent.parent / "voice_tmp"

# Suppress Vosk's default verbose logging (Kaldi-level debug output) —
# same instinct as ffmpeg's capture_output=True elsewhere in this project,
# keep noisy tool output out of the way unless something's actually wrong.
SetLogLevel(-1)

# Loaded lazily, once, and reused across calls — a Vosk Model load reads a
# real model directory from disk and isn't free; doing it once per
# listen() call the way ffmpeg/termux-microphone-record calls are made
# fresh each time would be wasteful for something this is.
_model = None


class HearingError(Exception):
    """Raised when listen_local() can't produce a transcript, for any
    reason. Matches HearingError in ears.py in spirit — same contract for
    a caller to catch and continue, not crash."""
    pass


def _get_model() -> Model:
    global _model
    if _model is None:
        try:
            # lang="en-us" auto-downloads the right model on first use —
            # confirmed as the current, simpler pattern via Vosk's own
            # official example files, rather than requiring a manual
            # separate model-download step.
            _model = Model(lang="en-us")
        except Exception as e:
            raise HearingError(
                f"Couldn't load/download the Vosk model: {e}. This needs "
                f"a real internet connection the FIRST time it runs (to "
                f"download the model); after that it's fully offline."
            ) from e
    return _model


def _record_and_convert(seconds: int) -> Path:
    """Reuses the exact same proven capture+conversion approach as
    ears.py's _record_audio/_convert_to_pcm — that part isn't in question,
    only the transcription step is being swapped. Returns the path to a
    real WAV file (Vosk's KaldiRecognizer wants a proper WAV, not
    headerless raw PCM the way Deepgram's URL did — see the wave.open()
    usage below)."""
    call_id = uuid.uuid4().hex[:8]
    m4a_path = AUDIO_TMP_DIR / f"rec_{call_id}.m4a"
    wav_path = AUDIO_TMP_DIR / f"rec_{call_id}.wav"
    AUDIO_TMP_DIR.mkdir(exist_ok=True)

    try:
        subprocess.run(
            ["termux-microphone-record", "-l", str(seconds), "-f", str(m4a_path)],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError as e:
        raise HearingError(
            "termux-microphone-record isn't available (needs Termux:API, "
            "pkg install termux-api)."
        ) from e
    except subprocess.CalledProcessError as e:
        raise HearingError(f"Recording failed: {e.stderr.decode(errors='replace')}") from e

    # Same async-command lesson as ears.py: wait the real duration, then
    # explicitly stop, rather than trust -l alone.
    time.sleep(seconds + 0.5)
    try:
        subprocess.run(["termux-microphone-record", "-q"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        pass
    time.sleep(1)

    if not m4a_path.exists() or m4a_path.stat().st_size == 0:
        raise HearingError("Recording finished but produced no audio file.")

    # Convert to a REAL WAV file this time (not headerless raw PCM) —
    # Vosk's wave.open() usage (per its own official examples) expects an
    # actual WAV container, unlike Deepgram's URL-declared-format approach.
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(m4a_path), "-ar", "16000", "-ac", "1", str(wav_path)],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        raise HearingError(
            f"ffmpeg couldn't convert the recording: {e.stderr.decode(errors='replace')}"
        ) from e
    finally:
        m4a_path.unlink(missing_ok=True)

    return wav_path


def listen_local(seconds: int = 5) -> str:
    """
    Local/offline equivalent of ears.py's listen(). Same contract: record
    for a fixed duration, return the transcribed text, raise HearingError
    on failure, return an empty string (not an error) if nothing
    intelligible was captured.
    """
    wav_path = _record_and_convert(seconds)

    try:
        model = _get_model()

        wf = wave.open(str(wav_path), "rb")
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
            raise HearingError(
                "Converted audio isn't mono 16-bit as expected — "
                "something in the ffmpeg conversion step didn't match "
                "what Vosk needs."
            )

        rec = KaldiRecognizer(model, wf.getframerate())
        rec.SetWords(True)

        full_text_parts = []
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                if result.get("text"):
                    full_text_parts.append(result["text"])

        final_result = json.loads(rec.FinalResult())
        if final_result.get("text"):
            full_text_parts.append(final_result["text"])

        return " ".join(full_text_parts).strip()

    except HearingError:
        raise
    except Exception as e:
        raise HearingError(f"Vosk transcription failed: {e}") from e
    finally:
        wav_path.unlink(missing_ok=True)
