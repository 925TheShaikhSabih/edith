"""
E.D.I.T.H. — the hosting layer (the "door" into Brain).

WHAT THIS FILE IS: the smallest possible bridge between a website (or any
WebSocket client) and the EXACT SAME Brain class every other entry point
(main.py, main_voice.py, live_explore.py) already uses. This file does
NOT reimplement any brain/tool logic — it only exposes what already
exists to the internet.

WHY A SEPARATE PROCESS PER CONNECTION MATTERS (read this before adding
multiple users): each WebSocket connection gets its OWN Brain() instance,
stored in a plain Python dict keyed by a random session id. This is
deliberate and important — Brain holds a live Gemini chat session with
its own conversation history. If two people shared one Brain instance,
their conversations would bleed into each other (person A's messages
would show up in person B's chat history). One Brain per connection
keeps conversations separate, the same way two people running main.py in
two separate terminals on two separate phones would never interfere with
each other.

WHAT THIS DOES NOT YET SOLVE, on purpose — flagged, not hidden:
- NO AUTHENTICATION. Anyone who finds this server's URL can connect and
  talk to E.D.I.T.H., using YOUR Gemini/Deepgram/ElevenLabs API keys and
  YOUR quota. This is fine for a first private test with a URL only you
  know, genuinely not fine once this is a real, public, shared tool — see
  AGENT.md's "hosted web app" section for why auth becomes unavoidable at
  that point, not optional.
- Text only, matching main.py — this does NOT yet handle voice
  (Deepgram/ElevenLabs/Live), which would need its own, separate wiring
  on top of this same pattern. Get text working and understood first.
- roadmap.json and memory.json are SHARED across every connection to
  this server (they're just files on the server's disk) — unlike your
  phone, where you're the only user, multiple people connecting to this
  hosted server would all read/write the SAME roadmap and memory. This
  might be exactly what you want (a shared team brain) or might not —
  worth being aware it's the current, real behavior.

HOW TO RUN THIS LOCALLY FIRST (before deploying anywhere):
    pip install fastapi uvicorn[standard]
    uvicorn server.main:app --reload
Then connect with any WebSocket client to ws://localhost:8000/ws
Confirming this works on your own machine BEFORE deploying to Render is
the same "verify the small thing before the big thing" discipline this
whole project has used throughout.
"""

import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from edith.brain import Brain, BrainError
from edith.setup import build_registry

load_dotenv()

app = FastAPI()

# One Brain per active connection, keyed by a random session id. See the
# module docstring above for why this matters — this is what keeps
# different people's conversations from bleeding into each other.
active_sessions: dict[str, Brain] = {}


@app.get("/")
def health_check():
    """
    A plain, ordinary web page (not a WebSocket) at the server's root
    URL. Visiting this in a normal browser is the very first, simplest
    test that the server is running and reachable at all — before
    testing anything about WebSockets or Brain itself. If this doesn't
    load, nothing else will either; check this first, always.
    """
    return {"status": "E.D.I.T.H. server is running", "active_sessions": len(active_sessions)}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    The actual door. A client (eventually your web app; for now, any
    plain WebSocket testing tool) connects here, and from that point on,
    messages flow back and forth freely over one open connection — the
    "phone call, not a letter" pattern described in the chat explanation
    above.
    """
    await websocket.accept()

    session_id = str(uuid.uuid4())[:8]
    try:
        registry = build_registry()
        brain = Brain(tools=registry)
    except BrainError as e:
        # If Brain can't even start (e.g. a missing API key on the
        # server), tell the client clearly and close, rather than accept
        # a connection that can never actually work.
        await websocket.send_json({"error": f"E.D.I.T.H. couldn't start: {e}"})
        await websocket.close()
        return

    active_sessions[session_id] = brain
    print(f"[session {session_id}] connected. ({len(active_sessions)} active)")

    try:
        while True:
            # Wait for the next message from the client. This line
            # PAUSES here until a message arrives — that's what "the
            # connection stays open" actually means in code: this loop
            # just waits, patiently, for as long as the connection is
            # open, instead of running once and finishing like a normal
            # web request would.
            user_text = await websocket.receive_text()

            try:
                # THIS is the entire point of this file: take whatever
                # text arrived over the internet, and hand it to the
                # EXACT SAME brain.send() that main.py already calls when
                # you type into your phone. Nothing about Brain itself
                # changes based on where the text came from.
                for piece in brain.send(user_text):
                    await websocket.send_json({"type": "reply_chunk", "text": piece})
                await websocket.send_json({"type": "reply_done"})
            except BrainError as e:
                await websocket.send_json({"type": "error", "text": str(e)})

    except WebSocketDisconnect:
        # The client closed the connection (closed the browser tab,
        # etc.) — this is normal, expected, not an error to alarm over.
        pass
    finally:
        # Clean up this session's Brain instance regardless of how the
        # connection ended, so active_sessions doesn't grow forever with
        # dead entries from people who've long since disconnected.
        active_sessions.pop(session_id, None)
        print(f"[session {session_id}] disconnected. ({len(active_sessions)} active)")
