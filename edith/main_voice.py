"""
E.D.I.T.H. — Tier 3: voice IN, voice OUT.

Press Enter to start recording, speak, and E.D.I.T.H. transcribes what you
said and runs it through the EXACT SAME Brain and tool registry as
main.py's typed loop — per the harness doc, voice is an adapter around the
existing brain, not a fork of it. The reply is both printed AND spoken
aloud.

This is an HONEST simplification of "push-to-talk" as the harness doc
describes it (hold a key, release when done): true held-key capture needs
raw terminal input handling, which is real, separate work not yet built.
What's here instead: press Enter to START a fixed-duration recording. Not
a fake version of push-to-talk — a real, simpler, deliberate interface
that's still "you decide when to speak," just not "you decide exactly
when to stop." Worth upgrading to true hold-to-record later; not silently
pretended to be that now.

SAME HONESTY APPLIES TO SPEECH OUTPUT: brain.send() streams text
chunk-by-chunk, but this accumulates the full reply before speaking it —
NOT true incremental streaming TTS (start speaking the first sentence
while the rest is still being generated, which the original design doc
describes as the ideal). That's a real, more advanced pattern this
doesn't attempt yet. What's here is simpler and correct: wait for the
complete reply, then speak all of it once. Upgrading to true streaming
speech is a reasonable next step, not something silently pretended to
already be done.

Usage:
    python -m edith.main_voice
"""

import sys

from dotenv import load_dotenv

from edith.brain import Brain, BrainError
from edith.setup import build_registry
from edith.voice.ears import listen, HearingError
from edith.voice.mouth import speak, play_audio, SpeakingError

load_dotenv()

RECORD_SECONDS = 5

BANNER = f"""\
E.D.I.T.H. — Tier 3 (voice IN via Termux+Deepgram, voice OUT via ElevenLabs)
Press Enter to record ({RECORD_SECONDS}s), then speak. Ctrl+C to quit.
Type 'text' + Enter instead of just Enter to send a typed message this turn.
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
            # A blank Enter starts a recording; typing something first
            # (e.g. "text") falls back to the typed path for this turn —
            # keeps the doc's "keep the text path alive forever" principle
            # true even inside the voice entry point itself, since voice
            # recognition WILL sometimes be the wrong tool for a given
            # moment (noisy room, sensitive info you'd rather type, etc.).
            first_line = input("[Enter to speak, or type a message] ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nShutting down. (Nothing is saved yet — that's Tier 4.)")
            break

        if first_line.lower() in ("exit", "quit"):
            print("Shutting down. (Nothing is saved yet — that's Tier 4.)")
            break

        if first_line:
            # Non-empty input on the "press Enter to speak" prompt — treat
            # it as a typed message instead of triggering a recording.
            user_text = first_line
            print("(typed message, not transcribed)")
        else:
            print(f"[recording for {RECORD_SECONDS}s — speak now]", flush=True)
            try:
                user_text = listen(seconds=RECORD_SECONDS)
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
                audio_path = speak(full_reply)
                play_audio(audio_path)
            except SpeakingError as e:
                # A speech-output failure shouldn't erase the fact that
                # the reply already printed successfully above — just note
                # it and keep going, same "don't crash the session"
                # principle as every other error path in this project.
                print(f"[couldn't speak that: {e}]")


if __name__ == "__main__":
    run()
