"""
E.D.I.T.H. — Tier 3, LOCAL/OFFLINE variant: voice IN via Vosk, voice OUT
via Piper. No Deepgram, no ElevenLabs, no API keys for voice at all
(Gemini is still cloud — that's the brain, a separate question from the
ears/mouth being explored here).

This is a PARALLEL alternative to main_voice.py, which is untouched and
still works exactly as before with the cloud providers. Structurally
identical to main_voice.py — same Brain, same tool registry, same
control flow — only the ears/mouth imports differ. This mirroring is
deliberate: comparing the two should be an apples-to-apples comparison
of the voice layer, not confounded by unrelated structural differences.

GENUINE, UNRESOLVED RISK: both vosk and piper-tts's PyPI wheels are
tagged for standard glibc Linux, not Termux's actual android_*_arm64_v8a
tag family. `pip install vosk piper-tts` may fail with the same kind of
platform-tag error pydantic_core hit earlier today. That would need its
own investigation (same shape as the pydantic_core saga) before this file
can even run — this is genuinely untested on-device as of being written.

Usage:
    python -m edith.main_voice_local
"""

import sys

from dotenv import load_dotenv

from edith.brain import Brain, BrainError
from edith.setup import build_registry
from edith.voice.ears_local import listen_local, HearingError
from edith.voice.mouth_local import speak_local, play_audio_local, SpeakingError

load_dotenv()

RECORD_SECONDS = 5

BANNER = f"""\
E.D.I.T.H. — Tier 3 LOCAL (voice IN via Vosk, voice OUT via Piper — fully offline)
Press Enter to record ({RECORD_SECONDS}s), then speak. Ctrl+C to quit.
Type 'text' + Enter instead of just Enter to send a typed message this turn.
NOTE: first run downloads the Vosk and Piper models — needs real internet
for that one time only; fully offline after.
"""


def run():
    print(BANNER)

    try:
        registry = build_registry()
        brain = Brain(tools=registry)
    except BrainError as e:
        print(f"Couldn't start E.D.I.T.H.: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"{brain.config.name} is online. ({len(registry)} tools available)\n")

    while True:
        try:
            first_line = input("[Enter to speak, or type a message] ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nShutting down. (Nothing is saved yet — that's Tier 4.)")
            break

        if first_line.lower() in ("exit", "quit"):
            print("Shutting down. (Nothing is saved yet — that's Tier 4.)")
            break

        if first_line:
            user_text = first_line
            print("(typed message, not transcribed)")
        else:
            print(f"[recording for {RECORD_SECONDS}s — speak now]", flush=True)
            try:
                user_text = listen_local(seconds=RECORD_SECONDS)
            except HearingError as e:
                print(f"[couldn't hear that: {e}]")
                continue

            if not user_text:
                print("[didn't catch anything — try again]")
                continue

            print(f"you (transcribed)> {user_text}")

        print(f"{brain.config.name}> ", end="", flush=True)
        reply_pieces = []
        try:
            for piece in brain.send(user_text):
                if piece.startswith("[") and piece.endswith("]"):
                    print(f"\n  {piece}")
                    print(f"{brain.config.name}> ", end="", flush=True)
                else:
                    print(piece, end="", flush=True)
                    reply_pieces.append(piece)
            print()
        except BrainError as e:
            print(f"\n[trouble reaching the model: {e}]")
            continue

        full_reply = "".join(reply_pieces)
        if full_reply.strip():
            try:
                audio_path = speak_local(full_reply)
                play_audio_local(audio_path)
            except SpeakingError as e:
                print(f"[couldn't speak that: {e}]")


if __name__ == "__main__":
    run()
