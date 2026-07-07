"""
E.D.I.T.H.'s mouth — LOCAL/OFFLINE alternative using Piper.

Parallel alternative to mouth.py (ElevenLabs), same reasoning as
ears_local.py: mouth.py is untouched, this exists to let both approaches
be tried before committing.

REAL TRADEOFF, stated plainly: Piper is genuinely free forever (local
model, no API, no account, no credits) — multiple sources describe it as
fast and CPU-friendly (confirmed: real-time on a Raspberry Pi 5 with no
GPU) but less expressive/natural than ElevenLabs' voices. The gap is
described as narrowing, but it's real.

SAME GENUINE, UN-RESOLVED RISK as ears_local.py: PyPI's piper-tts wheels
are tagged for standard glibc Linux/macOS, with no Android/Termux variant
visible. This may hit the identical platform-tag wall pydantic_core did
earlier today. Not glossed over.

LICENSE NOTE, worth knowing even though it doesn't block anything here:
the original MIT-licensed rhasspy/piper repo is archived; the actively
maintained fork (OHF-Voice/piper1-gpl, what `pip install piper-tts` now
installs) is GPL-3.0. This only matters if E.D.I.T.H. were ever
distributed as closed-source software — running it locally for your own
use isn't affected.
"""

import subprocess
import time
import wave
from pathlib import Path

from piper.voice import PiperVoice


AUDIO_TMP_DIR = Path(__file__).resolve().parent.parent.parent / "voice_tmp"

# A real, specific voice, not a vague default — per the same "voice choice
# should be explicit" principle mouth.py follows for its ElevenLabs
# voice_id. en_US-lessac-medium is the voice named as Home Assistant's own
# default and referenced most consistently across the Piper research
# above — a reasonable, well-supported starting point to actually compare
# against ElevenLabs, not a random pick.
VOICE_MODEL_NAME = "en_US-lessac-medium"

_voice = None


class SpeakingError(Exception):
    """Matches SpeakingError in mouth.py in spirit — same contract."""
    pass


def _get_voice() -> PiperVoice:
    global _voice
    if _voice is None:
        try:
            # PiperVoice.load can take a bare model name and handle
            # download/lookup itself in current versions per the Piper
            # research above, but the exact auto-download call shape
            # varies across the sources I found (some show a separate
            # piper.download_voices.download_voice step, others show
            # PiperVoice.load(name) alone handling it) — NOT fully
            # resolved which applies to the currently-pip-installed
            # version. If this raises complaining it can't find a model
            # file, that's the likely reason; the fix is checking piper's
            # actual current download-helper API rather than guessing
            # further here.
            _voice = PiperVoice.load(VOICE_MODEL_NAME)
        except Exception as e:
            raise SpeakingError(
                f"Couldn't load the Piper voice model '{VOICE_MODEL_NAME}': "
                f"{e}. This may need a real internet connection the FIRST "
                f"time it runs to download the model; after that it's "
                f"fully offline. If this error is about finding/downloading "
                f"the model rather than a network issue, Piper's current "
                f"model-download API needs to be checked directly — this "
                f"wasn't fully pinned down during research."
            ) from e
    return _voice


def speak_local(text: str) -> Path:
    """
    Local/offline equivalent of mouth.py's speak(). Same contract:
    convert text to speech, save as a file, return the path, raise
    SpeakingError on failure.
    """
    if not text or not text.strip():
        raise SpeakingError("nothing to speak — text was empty")

    voice = _get_voice()

    AUDIO_TMP_DIR.mkdir(exist_ok=True)
    out_path = AUDIO_TMP_DIR / "reply_local.wav"

    try:
        with wave.open(str(out_path), "w") as wav_file:
            voice.synthesize(text, wav_file)
    except Exception as e:
        raise SpeakingError(f"Piper synthesis failed: {e}") from e

    return out_path


def _probe_duration_seconds(audio_path: Path) -> float:
    """Same approach as mouth.py's identically-named function — get the
    REAL duration via ffprobe rather than guess, for the same reason:
    don't assume a Termux:API-adjacent command's return means playback
    finished, given ears.py's async-recording bug already proved that
    assumption wrong once for a structurally similar command."""
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


def play_audio_local(audio_path: Path):
    """Identical approach to mouth.py's play_audio() — same
    termux-media-player + ffprobe-duration-wait pattern. Not duplicated
    logic by accident; kept deliberately parallel so switching between
    local/cloud mouths is symmetric, not surprising."""
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
            "termux-media-player isn't available (needs Termux:API, "
            "pkg install termux-api)."
        ) from e
    except subprocess.CalledProcessError as e:
        raise SpeakingError(f"Playback failed: {e.stderr.decode(errors='replace')}") from e

    time.sleep(duration + 0.5)
