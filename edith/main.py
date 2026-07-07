"""
E.D.I.T.H. — text-only entry point.

Run this, type a message. Real tools (ELP roadmap: add/view/update
milestones; durable memory: remember/view/forget facts) work here exactly
as they do in the voice entry points — main.py, main_voice.py,
main_voice_local.py, and live_explore.py all share the same Brain and
tool registry (edith/setup.py's build_registry()), so nothing is
voice-exclusive.

This is the harness doc's "keep the text path alive forever" principle in
practice: a graceful fallback whenever voice isn't the right tool for the
moment (noisy environment, sensitive info, or simply not wanting to talk
out loud while other parts of the project are still being built) — not a
lesser or older version of E.D.I.T.H., just a different front door into
the exact same brain.

Usage:
    python -m edith.main
"""

import sys

from dotenv import load_dotenv

from edith.brain import Brain, BrainError
from edith.setup import build_registry

# Load .env before anything reads os.environ. If there's no .env file this
# is a harmless no-op — real deployments can still set the env var directly.
load_dotenv()


BANNER = """\
E.D.I.T.H. — text-only (same brain, tools, and memory as the voice entry points)
Type a message and press enter. Ctrl+C or 'exit' to quit.
"""


def run():
    print(BANNER)

    try:
        registry = build_registry()
        brain = Brain(tools=registry)
    except BrainError as e:
        # Fail loudly but cleanly at startup if we can't even construct a
        # client (e.g. missing API key) — no point starting the loop.
        print(f"Couldn't start E.D.I.T.H.: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"{brain.config.name} is online. ({len(registry)} tools available)\n")

    while True:
        try:
            user_text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nShutting down. (Roadmap and memory are saved; this conversation's chat history is not.)")
            break

        if not user_text:
            continue
        if user_text.lower() in ("exit", "quit"):
            print("Shutting down. (Roadmap and memory are saved; this conversation's chat history is not.)")
            break

        print(f"{brain.config.name}> ", end="", flush=True)
        try:
            for piece in brain.send(user_text):
                if piece.startswith("[") and piece.endswith("]"):
                    # A tool-use status marker, not reply text — show it on
                    # its own line so it's visually distinct, then restore
                    # the name label since reply text (or another marker)
                    # is coming next either way.
                    print(f"\n  {piece}")
                    print(f"{brain.config.name}> ", end="", flush=True)
                else:
                    print(piece, end="", flush=True)
            print()  # newline after the streamed reply finishes
        except BrainError as e:
            # This is the case the doc calls out explicitly: the model is
            # slow or unreachable. Show a clear message and loop back to the
            # next prompt rather than crashing.
            print(f"\n[trouble reaching the model: {e}]")


if __name__ == "__main__":
    run()
