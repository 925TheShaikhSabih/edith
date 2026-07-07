"""
E.D.I.T.H. — Gemini Live API, turn-based voice (CONFIRMED WORKING ON-DEVICE).

Real audio in, real audio out, tool-calling included, via a single
continuous Gemini Live session. This is a genuinely different thing from
main_voice.py/main_voice_local.py — those wrap separate STT/TTS providers
around the existing Brain; this is one live, bidirectional audio
connection with the model itself.

PROVENANCE, stated honestly: this file's core logic came from the user
working directly with Gemini to debug an earlier, non-working draft of
this same file (which used send_realtime_input for audio and hit a 1007
"invalid frame payload data" error). THIS version uses
send_client_content(turns=[...], turn_complete=True) instead, with the
comment "bypasses VAD hanging issues" — a real, concrete failure mode
(the server's Voice Activity Detection waiting for an end-of-speech
signal that a batch-recorded file can't naturally provide) that the
earlier draft hadn't accounted for. CONFIRMED WORKING END-TO-END
ON-DEVICE by the user: connects, records, transcodes, sends, receives
tool calls AND audio, plays the reply aloud.

A REAL, DOCUMENTED TENSION WORTH KNOWING, not hidden: Google's own
capabilities guide states, specifically for gemini-3.1-flash-live-preview
(the exact model this file uses): "send_client_content is only supported
for seeding initial context history... After the first model turn, use
send_realtime_input... instead" — and three more independent sources
(the official gemini-skills repo, Firebase's AI SDK docs, a third-party
Elixir client's docs) all state the same rule, one as an explicit
warning: "Do not use it to send new user messages during the
conversation." This file does exactly what that rule says not to do, and
it worked. This isn't papered over — Live is Preview-labeled, and preview
API validation sometimes lags stated documentation; this is being kept
as the real, working, on-device-verified approach specifically BECAUSE it
worked, not because it's known to be the documented-correct pattern. If
this ever starts failing after previously working (e.g. after an SDK or
API update), tightened enforcement of this specific documented rule is
the first thing to check.

A second, smaller point of real ambiguity, also worth knowing rather than
hiding: the response={"result": result} wrapping in the tool-response
step matches Google's own official cookbook notebook example exactly —
but a real, open GitHub issue (google-gemini/cookbook#906) shows someone
else reporting this same shape "does not work" for raw WebSocket use
specifically (as opposed to going through the SDK's send_tool_response()
wrapper, which is what this file does — a potentially important
difference in how serialization is handled). Not changed here since this
exact code is confirmed working through the SDK layer on this project's
actual device — flagged for awareness, not treated as a bug.

WHY THIS ISN'T WIRED INTO Brain/ToolRegistry (edith/brain.py,
edith/tools/__init__.py) YET: Live's tool-calling is a different protocol
from chat.send_message's response.function_calls/Part-list pattern (this
file's tool_call/send_tool_response loop, confirmed necessary since Live
"doesn't support automatic tool response handling" per Google's own
docs); Live remains Preview with real, current model-naming
inconsistency across Google's own different doc pages; and this file is
async while brain.py is synchronous. Given all three, and given this
whole path was only just gotten working, it stays a standalone
alternative for now rather than a deeper integration — main.py,
main_voice.py, and main_voice_local.py are all untouched and still work
exactly as before.

ARCHITECTURE NOTE: this is turn-based (record a full utterance, send
it, wait for the full reply), not true continuous streaming with
mid-sentence barge-in — a deliberate, honest simplification, not
something hidden. True continuous streaming would need audio flowing
in and out simultaneously via a different, harder-to-build-on-Termux
capture/playback model (see live_explore's earlier design notes on why
PyAudio-based continuous streaming, as Google's own reference examples
use, doesn't transfer cleanly to Termux's proven, file-based audio
tools). This version's turn-based approach avoided that fight entirely —
reusing ears.py's real, already-proven capture functions directly
(_record_audio, _convert_to_pcm, _check_ffmpeg_available) rather than a
new, separately-built capture path, which is itself a real strength of
this version over an earlier draft that had duplicated that logic.

Usage:
    python -m edith.live_explore
"""

import asyncio
import os
import sys
import subprocess
import traceback
from pathlib import Path
from dotenv import load_dotenv

# Google GenAI SDK Imports
from google import genai
from google.genai import types

load_dotenv()

# Robust local engine imports from E.D.I.T.H. codebase
from edith.tools.roadmap import add_milestone_tool, view_roadmap_tool, update_milestone_tool
from edith.tools.memory import remember_fact_tool, view_memory_tool, forget_fact_tool
from edith.voice.ears import _check_ffmpeg_available, _record_audio, _convert_to_pcm, AUDIO_TMP_DIR
from edith.voice.mouth import _probe_duration_seconds


# Configuration Constants
MODEL_NAME = "gemini-3.1-flash-live-preview"

# Tool Registry Setup
tool_registry = {
    "add_milestone": add_milestone_tool.run,
    "view_roadmap": view_roadmap_tool.run,
    "update_milestone": update_milestone_tool.run,
    "remember_fact": remember_fact_tool.run,
    "view_memory": view_memory_tool.run,
    "forget_fact": forget_fact_tool.run,
}

# Translate your internal custom tool architecture into the schema expected by Gemini's Live API
live_tools = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name=t.name,
                description=t.description,
                parameters=t.parameters
            ) for t in [
                add_milestone_tool, view_roadmap_tool, update_milestone_tool,
                remember_fact_tool, view_memory_tool, forget_fact_tool,
            ]
        ]
    )
]

async def run_voice_turn(session):
    """Executes a single push-to-talk multimodal voice and tool interaction turn."""
    _check_ffmpeg_available()
    AUDIO_TMP_DIR.mkdir(parents=True, exist_ok=True)
    
    call_id = "live_turn"
    m4a_input = AUDIO_TMP_DIR / f"input_{call_id}.m4a"
    pcm_input = AUDIO_TMP_DIR / f"input_{call_id}.pcm"
    pcm_output = AUDIO_TMP_DIR / f"output_{call_id}.pcm"
    mp3_output = AUDIO_TMP_DIR / f"output_{call_id}.mp3"

    try:
        # Step 1: Capture Voice via ears.py primitives
        input("\n🎤 Press [Enter] to start recording your command (5 seconds)...")
        print("[1/5] Listening through device microphone...")
        _record_audio(seconds=5, m4a_path=m4a_input)
        
        print("[2/5] Transcoding local file to 16kHz Mono PCM format...")
        _convert_to_pcm(m4a_path=m4a_input, pcm_path=pcm_input)

        if not pcm_input.exists() or pcm_input.stat().st_size == 0:
            print("❌ Input generation fault: Audio file was not created or is empty.")
            return

        # Step 2: Read whole file and submit atomically to force immediate execution
        print("[3/5] Submitting complete voice turn to E.D.I.T.H....")
        with open(pcm_input, "rb") as f:
            all_audio_bytes = f.read()
            
        # Using send_client_content with turn_complete=True bypasses VAD hanging issues
        await session.send_client_content(
            turns=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            inline_data=types.Blob(
                                data=all_audio_bytes,
                                mime_type="audio/pcm;rate=16000"
                            )
                        )
                    ]
                )
            ],
            turn_complete=True
        )

        # Step 3: Continuously poll the live WebSocket context for incoming data or tool requests
        print("[4/5] Awaiting execution processing from E.D.I.T.H....")
        raw_audio_buffer = bytearray()
        
        async for response in session.receive():
            # Intercept and process any autonomous Function Call triggers requested by Gemini
            if response.tool_call:
                function_responses = []
                for fc in response.tool_call.function_calls:
                    print(f"\n[E.D.I.T.H. executing tool: {fc.name}...]")
                    tool_func = tool_registry.get(fc.name)
                    
                    # Defensively adapt to argument payload keys
                    kwargs = getattr(fc, "args", getattr(fc, "arguments", {}))
                    
                    if tool_func:
                        try:
                            result = tool_func(**kwargs)
                        except Exception as tool_err:
                            result = {"ok": False, "error": str(tool_err)}
                    else:
                        result = {"ok": False, "error": f"Tool '{fc.name}' is unregistered."}
                    
                    function_responses.append(
                        types.FunctionResponse(
                            name=fc.name,
                            id=fc.id,
                            response={"result": result}
                        )
                    )
                
                # Push tool answers back so Gemini can formulate its audio final summary response
                await session.send_tool_response(function_responses=function_responses)

            # Process inbound textual content or transcript chunks
            content = response.server_content
            if content:
                if content.input_transcription:
                    print(f"\n[User Transcribed]: {content.input_transcription.text}")
                
                if content.model_turn:
                    for part in content.model_turn.parts:
                        # Append the 24kHz raw audio chunks to our player payload buffer
                        if part.inline_data:
                            raw_audio_buffer.extend(part.inline_data.data)
                        # Mirror text transcriptions in real time to the screen console
                        if part.text:
                            print(part.text, end="", flush=True)

            # Terminate streaming collection once the server signals completion of the response loop turn
            if content and content.turn_complete:
                print("\n[Turn execution wrapped cleanly by server]")
                break

        if not raw_audio_buffer:
            print("\n⚠️ Notification: Empty audio stream buffer returned from Gemini session.")
            return

        # Step 4: Convert and prepare output stream (Gemini produces 24kHz 16-Bit Little-Endian Mono PCM)
        print(f"\n[5/5] Processing {len(raw_audio_buffer)} bytes of output voice data...")
        with open(pcm_output, "wb") as f:
            f.write(raw_audio_buffer)

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-f", "s16le", "-ar", "24000", "-ac", "1",
                "-i", str(pcm_output),
                str(mp3_output),
            ],
            check=True,
            capture_output=True,
        )

        # Step 5: Deliver playback with programmatic safety delay bounding
        print("[🔊 Playing response voice aloud...]")
        duration = _probe_duration_seconds(mp3_output)
        subprocess.run(["termux-media-player", "play", str(mp3_output)], check=True, capture_output=True)
        await asyncio.sleep(duration + 0.5)

    except Exception as e:
        print(f"\n❌ Error encountered within active run loop: {e}")
        traceback.print_exc()
        
    finally:
        # Guarantee strict workspace decontamination to avoid memory or disk bloat
        m4a_input.unlink(missing_ok=True)
        pcm_input.unlink(missing_ok=True)
        pcm_output.unlink(missing_ok=True)
        mp3_output.unlink(missing_ok=True)

async def main():
    """Validates parameters, opens the continuous background session socket, and loops turns."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("❌ System Exit: The 'GEMINI_API_KEY' environment variable is missing.")
        sys.exit(1)

    # Initialize the client. This handles setup, network bindings, and authentication patterns securely.
    client = genai.Client(api_key=api_key)
    
    # Configure session specifications to demand native vocal feedback via the 'Aoede' voice profile
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=(
            "You are E.D.I.T.H., the 8th founding member of ELP (ESports "
            "League Pakistan). Professional but playful. You have tools "
            "for the ELP roadmap (add/view/update milestones) and for "
            "durable memory across conversations (remember_fact, "
            "view_memory, forget_fact) — use them naturally when relevant, "
            "including checking view_memory before saying you can't "
            "remember something."
        ),
        tools=live_tools,
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Aoede"
                )
            )
        )
    )

    print(f"[Initializing E.D.I.T.H. Voice Pipeline | Engine: {MODEL_NAME} | Voice: Aoede]")
    print("Connecting to live WebSocket streams...")
    
    try:
        async with client.aio.live.connect(model=MODEL_NAME, config=config) as session:
            print("🚀 Connection stabilized! Voice assistant loop running. Press Ctrl+C to terminate.")
            
            while True:
                await run_voice_turn(session)
                
    except KeyboardInterrupt:
        print("\n[Session terminated cleanly by command request. Exiting.]")
    except Exception as connection_fault:
        print(f"\n[Critical connection failure]: {connection_fault}")
        traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
