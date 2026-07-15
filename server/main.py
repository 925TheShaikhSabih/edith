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

NEW: /ws/live — VOICE over the browser, via Gemini Live (added after the
text-only /ws endpoint above; that endpoint is completely untouched).
Chosen over adding Deepgram/ElevenLabs to the browser specifically
because Live was already the most functionally complete, fully proven
voice path (real audio in, real audio out, tool-calling, all confirmed
working end-to-end via Termux in live_explore.py) — and because it's
free under the same Gemini key already in use, matching an explicit
"always free" priority, rather than adding a third/fourth paid-adjacent
provider into the browser specifically.

HOW THIS WORKS, concretely: live_explore.py's run_voice_turn() function
gets its audio bytes from Termux commands (_record_audio,
_convert_to_pcm) and plays the reply via termux-media-player — both
Termux-specific. The actual Gemini Live logic underneath (open a
session, send_client_content with raw PCM bytes, handle tool_call,
send_tool_response, collect reply audio bytes) is otherwise plain
Python bytes in/bytes out — nothing Termux-specific about the Live
protocol itself. This endpoint reuses that exact same Live logic, but
swaps the I/O source: audio bytes come from the BROWSER's mic (sent as
binary WebSocket frames) instead of a Termux recording, and reply audio
goes back to the BROWSER (also binary frames) instead of
termux-media-player. The Live session itself, the tool registry, the
system instruction, and the "gemini-3.1-flash-live-preview" model are
all copied directly from live_explore.py's confirmed-working config —
not re-derived, to avoid re-introducing any of the real bugs that took
real debugging to resolve there (the 1007 error, the
send_client_content-vs-send_realtime_input distinction, etc.).

Message protocol on /ws/live:
  Client -> Server: BINARY frames = raw 16-bit PCM audio, 16kHz mono
                     (the exact format Live's Blob expects — see
                     live_explore.py's confirmed pipeline). A TEXT frame
                     containing exactly "END_TURN" signals "I'm done
                     speaking, process what I sent" (turn-based, matching
                     live_explore.py's architecture — NOT continuous
                     streaming; see live_explore.py's own architecture
                     note for why true continuous streaming doesn't fit
                     this project's proven tools).
  Server -> Client: JSON control messages ({"type": "tool_used", ...},
                     {"type": "transcript", ...}, {"type": "turn_done"})
                     interleaved with BINARY frames = raw 16-bit PCM
                     audio, 24kHz mono (Live's OUTPUT rate — different
                     from the 16kHz INPUT rate; this distinction caused
                     real confusion earlier in this project, called out
                     explicitly here so it isn't relearned).

NOT YET DONE / genuinely untested: this endpoint has NOT been run for
real — no network access in the environment that wrote it. The
EdithHUD.jsx browser-side changes needed to actually USE this endpoint
(MediaRecorder for capture, Web Audio API for playback) are ALSO not
yet written — this is server-side plumbing only, built to match
live_explore.py's proven logic as closely as possible, but "closely
matches something proven" is not the same claim as "itself proven."
Test on a real device before trusting this the way live_explore.py
itself is trusted.
"""

import asyncio
import io
import uuid
import wave

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

from edith.brain import Brain, BrainError
from edith.setup import build_registry
from edith.tools.roadmap import add_milestone_tool, view_roadmap_tool, update_milestone_tool
from edith.tools.memory import remember_fact_tool, view_memory_tool, forget_fact_tool

load_dotenv()

app = FastAPI()

# One Brain per active connection, keyed by a random session id. See the
# module docstring above for why this matters — this is what keeps
# different people's conversations from bleeding into each other.
active_sessions: dict[str, Brain] = {}

# --- Live voice setup, copied directly from live_explore.py's confirmed-
# working configuration (NOT re-derived) to avoid reintroducing bugs that
# took real debugging to resolve there. ---

LIVE_MODEL_NAME = "gemini-3.1-flash-live-preview"

_LIVE_TOOL_FUNCS = [
    add_milestone_tool, view_roadmap_tool, update_milestone_tool,
    remember_fact_tool, view_memory_tool, forget_fact_tool,
]

live_tool_registry = {t.name: t.run for t in _LIVE_TOOL_FUNCS}

live_tools = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(name=t.name, description=t.description, parameters=t.parameters)
            for t in _LIVE_TOOL_FUNCS
        ]
    )
]

LIVE_SYSTEM_INSTRUCTION = (
    "You are E.D.I.T.H., the 8th founding member of ELP (ESports "
    "League Pakistan). Professional but playful. You have tools "
    "for the ELP roadmap (add/view/update milestones) and for "
    "durable memory across conversations (remember_fact, "
    "view_memory, forget_fact) — use them naturally when relevant, "
    "including checking view_memory before saying you can't "
    "remember something."
)


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


@app.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket):
    """
    Voice over the browser via Gemini Live — see the module docstring's
    "NEW: /ws/live" section for the full protocol and reasoning.

    Structurally this is live_explore.py's run_voice_turn() ported to
    receive audio from a browser instead of Termux commands. The actual
    Live session lifecycle, tool-calling loop, and audio format handling
    are copied as directly as possible from that confirmed-working
    reference, specifically to avoid re-introducing bugs that took real
    debugging to resolve there (see module docstring).
    """
    await websocket.accept()
    session_id = str(uuid.uuid4())[:8]
    print(f"[live session {session_id}] connected")

    try:
        client = genai.Client()  # picks up GEMINI_API_KEY from env, same as elsewhere
    except Exception as e:
        await websocket.send_json({"type": "error", "text": f"Couldn't start Live client: {e}"})
        await websocket.close()
        return

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=LIVE_SYSTEM_INSTRUCTION,
        tools=live_tools,
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
            )
        ),
    )

    try:
        async with client.aio.live.connect(model=LIVE_MODEL_NAME, config=config) as session:
            await websocket.send_json({"type": "live_ready"})

            try:
                while True:
                    # One turn: accumulate binary audio chunks from the
                    # browser until the client sends the "END_TURN" text
                    # signal — matching live_explore.py's turn-based
                    # architecture (record a full utterance, then send),
                    # NOT continuous streaming. See the module docstring's
                    # protocol section for why this shape was chosen.
                    audio_chunks = []
                    while True:
                        message = await websocket.receive()
                        if message.get("bytes") is not None:
                            audio_chunks.append(message["bytes"])
                        elif message.get("text") == "END_TURN":
                            break
                        # Any other text during recording is ignored here —
                        # this loop is specifically for accumulating one
                        # turn's audio, not a general message router.

                    if not audio_chunks:
                        # Client signaled end-of-turn with no audio sent —
                        # nothing to do, wait for the next turn rather than
                        # send an empty turn to Gemini.
                        continue

                    all_audio_bytes = b"".join(audio_chunks)

                    # Ported directly from live_explore.py's run_voice_turn:
                    # send_client_content with turn_complete=True — NOT
                    # send_realtime_input, per the documented-but-actually-
                    # working exception recorded in live_explore.py's own
                    # docstring (bypasses a real VAD-hanging issue with
                    # batch-sent audio).
                    await session.send_client_content(
                        turns=[
                            types.Content(
                                role="user",
                                parts=[
                                    types.Part(
                                        inline_data=types.Blob(
                                            data=all_audio_bytes,
                                            mime_type="audio/pcm;rate=16000",
                                        )
                                    )
                                ],
                            )
                        ],
                        turn_complete=True,
                    )

                    reply_audio_buffer = bytearray()

                    async for response in session.receive():
                        if response.tool_call:
                            function_responses = []
                            for fc in response.tool_call.function_calls:
                                await websocket.send_json({"type": "tool_used", "name": fc.name})
                                tool_fn = live_tool_registry.get(fc.name)
                                kwargs = getattr(fc, "args", getattr(fc, "arguments", {})) or {}
                                if tool_fn is None:
                                    result = {"ok": False, "error": f"no tool named {fc.name!r}"}
                                else:
                                    try:
                                        result = tool_fn(**kwargs)
                                    except Exception as e:
                                        result = {"ok": False, "error": str(e)}
                                function_responses.append(
                                    types.FunctionResponse(name=fc.name, id=fc.id, response={"result": result})
                                )
                            await session.send_tool_response(function_responses=function_responses)

                        content = response.server_content
                        if content:
                            if content.input_transcription and content.input_transcription.text:
                                await websocket.send_json({
                                    "type": "input_transcript",
                                    "text": content.input_transcription.text,
                                })
                            if content.model_turn:
                                for part in content.model_turn.parts:
                                    if part.inline_data:
                                        # Reply audio: 24kHz, per Live's
                                        # OUTPUT rate — deliberately
                                        # different from the 16kHz INPUT
                                        # rate above. Buffered here and
                                        # sent as ONE binary frame at the
                                        # end (see below) rather than
                                        # streamed chunk-by-chunk, since
                                        # this matches live_explore.py's
                                        # turn-based, not continuous,
                                        # architecture.
                                        reply_audio_buffer.extend(part.inline_data.data)
                                    if part.text:
                                        await websocket.send_json({"type": "output_transcript", "text": part.text})

                        if content and content.turn_complete:
                            break

                    if reply_audio_buffer:
                        # Send the complete reply audio as ONE binary
                        # frame. The browser side needs to know this is
                        # raw 16-bit PCM, 24kHz, mono — same as
                        # live_explore.py's ffmpeg conversion step
                        # expects, just handed to the browser instead of
                        # ffmpeg/termux-media-player.
                        await websocket.send_bytes(bytes(reply_audio_buffer))

                    await websocket.send_json({"type": "turn_done"})

            except WebSocketDisconnect:
                pass

    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "text": f"Live session error: {e}"})
        except Exception:
            pass  # connection may already be gone

@app.websocket("/ws/live-stream")
async def websocket_live_stream_endpoint(websocket: WebSocket):
    """
    TRUE real-time streaming voice, via Gemini Live — the way Live is
    actually meant to be used, per explicit request after /ws/live's
    turn-based approach (record fully, then send) worked correctly.

    THE STRUCTURAL DIFFERENCE FROM /ws/live, stated plainly: /ws/live has
    ONE sequential loop — accumulate audio until END_TURN, THEN send,
    THEN wait for the full reply. This endpoint has NO such sequence.
    Audio flows to Gemini continuously the instant it's captured, via
    send_realtime_input (NOT send_client_content/turn_complete — a
    different, genuinely continuous-streaming-oriented call, confirmed
    via Google's own current docs and multiple independent working
    examples, e.g. a Reachy Mini robot project's identical pattern).
    Because sending and receiving now need to happen AT THE SAME TIME
    (you can be still talking while Gemini has already started replying,
    or interrupting it), this uses asyncio.gather to run two tasks
    concurrently, not one bigger sequential loop:
      - _forward_browser_to_gemini: browser binary frames -> Gemini,
        continuously, no buffering, no turn concept.
      - _forward_gemini_to_browser: Gemini's responses -> browser,
        including a NEW signal /ws/live never needed: interruption.
        Confirmed via Google's own Vertex docs: server_content.interrupted
        fires when the user starts talking over an in-progress reply —
        the client is expected to immediately flush/stop whatever
        reply audio it was playing. Without forwarding this signal,
        real-time voice would still be TECHNICALLY continuous but would
        keep talking over you, defeating the actual point.

    /ws/live is left completely untouched — this is a genuinely separate
    endpoint/mode, not a replacement, matching the pattern of every other
    addition in this project (ears.py/ears_local.py, mouth.py/
    mouth_local.py, etc.) so the proven turn-based fallback stays intact.

    Protocol on /ws/live-stream:
      Client -> Server: BINARY frames = raw 16-bit PCM, 16kHz mono,
                         sent continuously, no END_TURN signal at all —
                         there is no "turn" on this endpoint.
      Server -> Client: JSON control messages ({"type": "tool_used",...},
                         {"type": "input_transcript",...},
                         {"type": "output_transcript",...},
                         {"type": "interrupted"} <- NEW, not present on
                         /ws/live, tells the browser to immediately stop
                         playing whatever reply audio is queued)
                         interleaved with BINARY frames = raw 16-bit PCM,
                         24kHz mono, sent as SMALL chunks as they arrive
                         from Gemini (NOT buffered into one big frame at
                         turn-end the way /ws/live does — there is no
                         turn-end here to buffer until).

    VERIFICATION STATUS: genuinely untested — no network access in the
    environment that wrote this. This is a bigger, riskier change than
    /ws/live was: two concurrent tasks instead of one sequential loop,
    a new interruption-handling path that /ws/live never needed, and a
    fundamentally different client-side audio strategy (continuous
    small-chunk playback instead of one buffered reply). Expect this to
    need real debugging on first attempt, likely more than one round,
    the same as nearly every other new capability in this project.
    """
    await websocket.accept()
    session_id = str(uuid.uuid4())[:8]
    print(f"[live-stream session {session_id}] connected")

    try:
        client = genai.Client()
    except Exception as e:
        await websocket.send_json({"type": "error", "text": f"Couldn't start Live client: {e}"})
        await websocket.close()
        return

    # REAL FIX for a documented, known issue (confirmed via a matching
    # GitHub bug report: googleapis/python-genai#1224 — "session stops
    # responding after first turn_complete... the receive() coroutine
    # never yields another message even though the client keeps sending
    # more audio. The WebSocket remains open, but the session is
    # effectively dead") — this is NOT something this code did wrong;
    # it's a known limitation/bug in how the SDK's AUTOMATIC voice
    # activity detection (VAD) handles ending a turn cleanly in
    # continuous-streaming mode. The documented mitigation (Google's own
    # Best Practices page): disable automatic VAD and send EXPLICIT
    # activity_start/activity_end markers around each utterance instead
    # of relying on Gemini to detect end-of-speech itself. The mic still
    # streams continuously — this doesn't reintroduce turn-based
    # buffering — it just tells Gemini precisely when one utterance
    # begins/ends, rather than trusting automatic detection that this
    # project's testing showed goes silent after the first cycle.
    # REAL FIX for likely root cause of BOTH reported errors (1011
    # Internal error, 1007 Precondition failed): confirmed via Google's
    # own current docs (Session Management guide + Troubleshooting guide,
    # both dated 2026) that a single Live WebSocket connection has a
    # hard, documented lifetime of ~10 minutes, and audio-only sessions
    # are capped around 15 minutes of context — the server sends a
    # GoAway warning first, but terminates regardless if nothing handles
    # it. This server had ZERO handling for this (confirmed via direct
    # grep: no go_away or session_resumption references anywhere) —a
    # natural, DOCUMENTED session expiry during a longer test session is
    # a strong, better-fitting explanation for both errors together than
    # either in isolation: an unhandled termination (1011) followed by
    # this server's local activity_open tracking being out of sync with
    # a session that no longer exists (1007) is a coherent single story,
    # not two unrelated bugs.
    # session_resumption=types.SessionResumptionConfig() (empty config)
    # enables the server to periodically send resumption handles, which
    # get captured below and used to reconnect seamlessly if the
    # connection is terminated — rather than the previous behavior of
    # just surfacing an error and stopping.
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=LIVE_SYSTEM_INSTRUCTION,
        tools=live_tools,
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Aoede")
            )
        ),
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(disabled=True)
        ),
        session_resumption=types.SessionResumptionConfig(transparent=True),
    )

    # Shared mutable state: _forward_gemini_to_browser writes the latest
    # resumption handle here as it arrives; the outer reconnection loop
    # (below, replacing the old single `async with` block) reads it when
    # deciding how to reconnect after a go_away/termination. A plain dict
    # (not a local variable) since it needs to be visible across the
    # async function boundary and survive being read after
    # _forward_gemini_to_browser returns.
    resumption_state = {"handle": None}

    async def _forward_browser_to_gemini(session):
        """Continuously reads binary audio frames from the browser and
        forwards each one to Gemini immediately via send_realtime_input —
        no accumulation of audio bytes, but WITH explicit activity_start/
        activity_end markers wrapping each utterance (see the endpoint's
        docstring for why: automatic VAD was found to silently break
        after the first turn in continuous mode — a real, documented SDK
        issue, not a guess). The browser signals utterance boundaries via
        text control frames ("UTTERANCE_START"/"UTTERANCE_END") based on
        its OWN silence detection — the mic itself never stops streaming,
        only these boundary markers are discrete."""
        activity_open = False
        while True:
            message = await websocket.receive()
            if message.get("bytes") is not None:
                if not activity_open:
                    # Defensive: if audio arrives without an explicit
                    # UTTERANCE_START (shouldn't normally happen given
                    # the browser's own logic, but real bugs happen),
                    # open one now rather than silently drop the audio
                    # or send it into a closed activity window.
                    await session.send_realtime_input(activity_start=types.ActivityStart())
                    activity_open = True
                await session.send_realtime_input(
                    audio=types.Blob(data=message["bytes"], mime_type="audio/pcm;rate=16000")
                )
            elif message.get("text") == "UTTERANCE_START":
                if not activity_open:
                    await session.send_realtime_input(activity_start=types.ActivityStart())
                    activity_open = True
            elif message.get("text") == "UTTERANCE_END":
                if activity_open:
                    await session.send_realtime_input(activity_end=types.ActivityEnd())
                    activity_open = False

    async def _forward_gemini_to_browser(session):
        """Continuously reads Gemini's responses (tool calls, transcripts,
        reply audio chunks, and interruption signals) and forwards each
        to the browser AS IT ARRIVES.

        THE ACTUAL ROOT CAUSE FIX, found via Google's own official
        Session Management guide (not the VAD explanation tried
        earlier — that was grounded in real research but was solving an
        adjacent problem): session.receive() is an async generator that
        naturally completes after ONE logical exchange — this is
        DOCUMENTED, INTENDED behavior, not a bug. Google's own
        recommended pattern for multi-turn sessions explicitly shows
        `receive()` called INSIDE an outer `while True` loop, fresh for
        each new exchange:
            while True:
                await session.send_client_content(...)
                async for message in session.receive():
                    ...
        The original version of this function called `async for response
        in session.receive()` exactly ONCE, with no outer loop — meaning
        after Gemini's first reply naturally finished, this generator
        completed and the function RETURNED. asyncio.gather's other task
        (_forward_browser_to_gemini) kept running and kept sending audio
        into Gemini, but nothing was left consuming responses back out —
        explaining precisely the reported symptom: first command works,
        nothing registers after.
        The outer `while True` here re-calls session.receive() every
        time the inner loop completes, so the server keeps listening
        indefinitely across the whole streaming session, not just the
        first exchange."""
        while True:
            async for response in session.receive():
                # Capture the resumption handle as it's periodically sent
                # by the server (confirmed via Google's own Session
                # Management guide) — stored in resumption_state, a
                # mutable dict the OUTER reconnection loop (below) reads
                # from, so a future reconnect can resume this exact
                # session with its context intact rather than starting
                # fresh.
                if response.session_resumption_update:
                    update = response.session_resumption_update
                    if update.resumable and update.new_handle:
                        resumption_state["handle"] = update.new_handle

                # A GoAway signal means the server will terminate this
                # connection soon (documented: ~60 seconds' notice).
                # Rather than let this surface as an unhandled 1011/1007
                # later when the connection actually drops, break out of
                # BOTH loops cleanly now — the outer reconnection wrapper
                # (below) will reconnect using the resumption handle
                # captured above.
                if response.go_away:
                    await websocket.send_json({"type": "reconnecting"})
                    return

                if response.tool_call:
                    function_responses = []
                    for fc in response.tool_call.function_calls:
                        await websocket.send_json({"type": "tool_used", "name": fc.name})
                        tool_fn = live_tool_registry.get(fc.name)
                        kwargs = getattr(fc, "args", getattr(fc, "arguments", {})) or {}
                        if tool_fn is None:
                            result = {"ok": False, "error": f"no tool named {fc.name!r}"}
                        else:
                            try:
                                result = tool_fn(**kwargs)
                            except Exception as e:
                                result = {"ok": False, "error": str(e)}
                        function_responses.append(
                            types.FunctionResponse(name=fc.name, id=fc.id, response={"result": result})
                        )
                    await session.send_tool_response(function_responses=function_responses)

                content = response.server_content
                if not content:
                    continue

                # NEW vs. /ws/live: real-time streaming means the user can
                # start talking again while Gemini is still replying.
                # Confirmed via Google's own Vertex docs: this is the signal
                # to tell the browser to immediately stop/flush whatever
                # reply audio it has queued, rather than keep talking over
                # the user. /ws/live never needed this since it always
                # waited for one full reply before allowing the next turn.
                if content.interrupted:
                    await websocket.send_json({"type": "interrupted"})
                    continue

                if content.input_transcription and content.input_transcription.text:
                    await websocket.send_json({
                        "type": "input_transcript",
                        "text": content.input_transcription.text,
                    })
                if content.output_transcription and content.output_transcription.text:
                    await websocket.send_json({
                        "type": "output_transcript",
                        "text": content.output_transcription.text,
                    })
                if content.model_turn:
                    for part in content.model_turn.parts:
                        if part.inline_data:
                            # Sent AS A SMALL CHUNK immediately, NOT buffered
                            # until some turn-end signal — there is no
                            # turn-end concept here, so buffering would just
                            # mean waiting arbitrarily and defeating the
                            # entire point of streaming.
                            await websocket.send_bytes(part.inline_data.data)
            # Inner `async for` completed (Gemini finished one logical
            # exchange) — loop back to the top of `while True` and call
            # session.receive() again, fresh, per the documented pattern.
            # Without this outer loop, the function would return here and
            # silently stop listening for anything further.

    # Reconnection loop, replacing the previous single-shot `async with`.
    # This is the actual structural fix for the reported errors: Gemini
    # Live connections have a hard, documented ~10 minute lifetime (see
    # the config block's comment above for sources) — the server warns
    # via go_away, but WILL terminate regardless. Previously, that
    # termination surfaced as an unhandled error (1011, and a follow-on
    # 1007 from this server's local state being out of sync with a
    # session that no longer existed) and stopped the whole endpoint.
    # Now: a go_away causes _forward_gemini_to_browser to return cleanly
    # (see its go_away check above), and this outer loop reconnects using
    # the resumption handle captured along the way — continuing the
    # conversation with its context intact rather than erroring out.
    MAX_RECONNECT_ATTEMPTS = 5
    attempt = 0
    while attempt < MAX_RECONNECT_ATTEMPTS:
        attempt += 1
        try:
            connect_config = config
            if resumption_state["handle"]:
                # Reconnecting after a go_away — pass the saved handle so
                # Gemini resumes this exact session's context rather than
                # starting a brand new one. Everything else in config
                # (tools, system instruction, voice, etc.) stays the same;
                # only session_resumption's handle changes.
                connect_config = types.LiveConnectConfig(
                    response_modalities=config.response_modalities,
                    system_instruction=config.system_instruction,
                    tools=config.tools,
                    input_audio_transcription=config.input_audio_transcription,
                    output_audio_transcription=config.output_audio_transcription,
                    speech_config=config.speech_config,
                    realtime_input_config=config.realtime_input_config,
                    session_resumption=types.SessionResumptionConfig(
                        handle=resumption_state["handle"], transparent=True
                    ),
                )

            async with client.aio.live.connect(model=LIVE_MODEL_NAME, config=connect_config) as session:
                await websocket.send_json({"type": "live_ready"})
                # Run both directions CONCURRENTLY — this is the actual
                # structural change from /ws/live's one sequential loop.
                # asyncio.gather with return_exceptions=False (default)
                # means if EITHER task raises (e.g. the browser
                # disconnects, which surfaces as a WebSocketDisconnect
                # from the receive() call inside _forward_browser_to_gemini),
                # the whole gather stops.
                await asyncio.gather(
                    _forward_browser_to_gemini(session),
                    _forward_gemini_to_browser(session),
                )
            # If we reach here, _forward_gemini_to_browser returned on
            # its own (the go_away path) rather than the gather raising —
            # loop back and reconnect using the handle captured above.
            # If neither task ever returns/raises normally (the ongoing,
            # healthy-connection case), this line is simply never reached
            # until a real disconnect or go_away happens.
        except WebSocketDisconnect:
            break
        except Exception as e:
            try:
                await websocket.send_json({"type": "error", "text": f"Live stream session error: {e}"})
            except Exception:
                pass
            break

    print(f"[live-stream session {session_id}] disconnected")
