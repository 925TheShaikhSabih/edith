import React, { useState, useRef, useEffect, useCallback } from 'react';

// ---------------------------------------------------------------------------
// DESIGN NOTES (per the frontend-design skill's two-pass process)
//
// Brief: E.D.I.T.H. as seen in Spider-Man: Homecoming — a real, specific
// reference, not "futuristic AI UI" in general. Homecoming's HUD reads as:
// dark, cold-metal base; a hot Stark-red used sparingly as an accent/alert
// color, never a background; a cyan-white scanline glow that IS the
// "system is alive" signal; radial/circular data arrangements rather than
// rectangular cards; small rotating/ticking micro-readouts around a calm
// central presence, not a wall of text.
//
// Color (named, not generic "AI-blue"):
//   --void:      #0A0A0C  (near-black base — cold, not warm)
//   --steel:     #3D4147  (inactive borders, dividers, resting-state UI)
//   --glow:      #00D4FF  (the HUD's living color — scanlines, active ring)
//   --stark-red: #C4001A  (accent only — listening state, alerts)
//   --paper:     #E8E8E8  (primary text — off-white, not pure #FFF, so it
//                          doesn't compete with --glow under a real glow effect)
//
// Type: a technical/monospace face for data readouts and labels (system
// voice), a clean sans for the actual spoken transcript (human/AI voice) —
// these should NOT look identical, since a HUD narrates ABOUT the
// conversation as well as showing it.
//
// Layout/signature: NOT a chat app. A central circular "core" that
// physically reacts to voice activity (radius/glow pulsing with amplitude),
// radial status readouts around it (connection, session id, latency-style
// numbers reminiscent of Stark-tech diagnostics), and the transcript
// flowing as a ticking, low-opacity feed beneath — present, but secondary
// to the core, the way Homecoming's HUD keeps Peter's actual view primary
// and data peripheral.
//
// Self-critique pass: the obvious generic version of this brief is a dark
// dashboard with a green "mic active" pill and a chat bubble list — cut
// that entirely. Radial layout + a single glowing reactive ring is the one
// place this design takes a real risk; everything else (spacing, the
// ticker, the status labels) stays quiet and disciplined around it, per
// the skill's "spend your boldness in one place" principle.
// ---------------------------------------------------------------------------

const COLORS = {
  void: '#0A0A0C',
  steel: '#3D4147',
  glow: '#00D4FF',
  starkRed: '#C4001A',
  paper: '#E8E8E8',
};

// Change this to your real deployed WebSocket URL once you're testing
// against the live server rather than a local one.
const DEFAULT_WS_URL = 'wss://edith-flame.vercel.app/ws';

function useRadialTicks(count, radius) {
  // Generates the small tick-mark positions around the core — a real,
  // deliberate HUD device (Homecoming's rings are built from many small
  // radial ticks, not a solid circle), computed once per radius/count.
  return Array.from({ length: count }, (_, i) => {
    const angle = (i / count) * Math.PI * 2 - Math.PI / 2;
    return {
      x: Math.cos(angle) * radius,
      y: Math.sin(angle) * radius,
      angle: (angle * 180) / Math.PI + 90,
    };
  });
}

// Live voice endpoint - same host as the text /ws endpoint, different path.
const LIVE_WS_URL = DEFAULT_WS_URL.replace(/\/ws$/, '/ws/live');

// The AudioWorklet processor that converts the browser's native Float32
// audio samples into 16-bit PCM, matching what Gemini Live's input
// expects. MUST be loaded as a separate module (a real, hard constraint
// of the AudioWorklet API — confirmed via research: worklets can't be
// inline functions the way a normal event handler can), so this is
// created as a Blob URL at runtime rather than a separate served file —
// keeps this workable in a single-file sandbox like PlayCode, not just a
// full multi-file build.
//
// WHY NOT MediaRecorder: confirmed via research that MediaRecorder
// cannot produce raw PCM at all — only compressed/container formats
// (webm, ogg). This is the SAME category of problem ears.py hit with
// termux-microphone-record only producing AAC/M4A, not raw PCM, which
// needed a real ffmpeg conversion step to work around. AudioWorklet is
// the correct, if more involved, browser equivalent — it's the thing
// standing in for ffmpeg's role here, not an optional extra.
const PCM_WORKLET_SOURCE = `
class PCM16Processor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    if (input && input[0]) {
      const float32 = input[0];
      const int16 = new Int16Array(float32.length);
      for (let i = 0; i < float32.length; i++) {
        const s = Math.max(-1, Math.min(1, float32[i]));
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
      }
      this.port.postMessage(int16.buffer, [int16.buffer]);
    }
    return true;
  }
}
registerProcessor('pcm16-processor', PCM16Processor);
`;

export default function EdithHUD() {
  const [wsUrl, setWsUrl] = useState(DEFAULT_WS_URL);
  const [connectionState, setConnectionState] = useState('disconnected'); // disconnected | connecting | connected | error
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState([]);
  const [inputText, setInputText] = useState('');
  const [pulsePhase, setPulsePhase] = useState(0);
  const wsRef = useRef(null);
  const transcriptEndRef = useRef(null);

  // --- Live voice state, kept separate from the text-mode state above ---
  const [voiceMode, setVoiceMode] = useState(false); // false = text /ws, true = voice /ws/live
  const [voiceState, setVoiceState] = useState('idle'); // idle | connecting | ready | recording | processing
  const liveWsRef = useRef(null);
  const audioContextRef = useRef(null);
  const workletNodeRef = useRef(null);
  const micStreamRef = useRef(null);
  const playbackQueueRef = useRef([]); // holds reply audio ArrayBuffers received while one is already playing

  const outerTicks = useRadialTicks(48, 140);
  const innerTicks = useRadialTicks(24, 110);

  // Ambient pulse animation for the core ring — even at rest, a HUD should
  // read as "alive," not static. Speeds up when actively listening/replying.
  useEffect(() => {
    const speed = isListening ? 40 : 90;
    const interval = setInterval(() => {
      setPulsePhase((p) => (p + 1) % 360);
    }, speed);
    return () => clearInterval(interval);
  }, [isListening]);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcript]);

  const connect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    setConnectionState('connecting');
    setTranscript((t) => [...t, { type: 'system', text: `Establishing uplink to ${wsUrl}` }]);

    try {
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        setConnectionState('connected');
        setTranscript((t) => [...t, { type: 'system', text: 'Uplink established. E.D.I.T.H. online.' }]);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'reply_chunk') {
            setTranscript((t) => {
              const last = t[t.length - 1];
              if (last && last.type === 'edith' && last.streaming) {
                const updated = [...t];
                updated[updated.length - 1] = { ...last, text: last.text + data.text };
                return updated;
              }
              return [...t, { type: 'edith', text: data.text, streaming: true }];
            });
          } else if (data.type === 'reply_done') {
            setTranscript((t) => {
              const updated = [...t];
              if (updated.length > 0) updated[updated.length - 1].streaming = false;
              return updated;
            });
            setIsListening(false);
          } else if (data.type === 'error' || data.error) {
            setTranscript((t) => [...t, { type: 'error', text: data.text || data.error }]);
            setIsListening(false);
          }
        } catch {
          setTranscript((t) => [...t, { type: 'system', text: 'Received malformed transmission.' }]);
        }
      };

      ws.onerror = () => {
        setConnectionState('error');
        setTranscript((t) => [...t, { type: 'error', text: 'Uplink error. Signal lost.' }]);
      };

      ws.onclose = () => {
        setConnectionState('disconnected');
        setTranscript((t) => [...t, { type: 'system', text: 'Uplink terminated.' }]);
      };

      wsRef.current = ws;
    } catch (e) {
      setConnectionState('error');
      setTranscript((t) => [...t, { type: 'error', text: `Could not initiate uplink: ${e.message}` }]);
    }
  }, [wsUrl]);

  const sendMessage = useCallback(() => {
    if (!inputText.trim() || connectionState !== 'connected') return;
    setTranscript((t) => [...t, { type: 'user', text: inputText }]);
    setIsListening(true);
    wsRef.current?.send(inputText);
    setInputText('');
  }, [inputText, connectionState]);

  // --- Live voice: connect, capture, playback ---
  //
  // Turn-based, matching server/main.py's /ws/live protocol and
  // live_explore.py's proven architecture: press to start recording,
  // press again to stop and send (an "END_TURN" text signal), then wait
  // for the reply. NOT continuous/always-listening — same honest
  // simplification reasoning as live_explore.py's own turn-based design.

  const playReplyAudio = useCallback(async (arrayBuffer) => {
    // The server sends raw 16-bit PCM, 24kHz, mono — Live's OUTPUT rate
    // (different from the 16kHz INPUT rate used for capture below; this
    // distinction caused real confusion earlier in this project and is
    // deliberately called out here so it isn't relearned). Web Audio's
    // AudioBuffer wants Float32 samples, so convert back the other way
    // from what the worklet did for capture.
    if (!audioContextRef.current) return;
    const int16 = new Int16Array(arrayBuffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / (int16[i] < 0 ? 0x8000 : 0x7fff);
    }
    const audioBuffer = audioContextRef.current.createBuffer(1, float32.length, 24000);
    audioBuffer.copyToChannel(float32, 0);

    const source = audioContextRef.current.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(audioContextRef.current.destination);

    return new Promise((resolve) => {
      source.onended = resolve;
      source.start();
    });
  }, []);

  const connectVoice = useCallback(() => {
    setVoiceState('connecting');
    const ws = new WebSocket(LIVE_WS_URL);
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      setTranscript((t) => [...t, { type: 'system', text: 'Live voice uplink connecting...' }]);
    };

    ws.onmessage = async (event) => {
      if (event.data instanceof ArrayBuffer) {
        // Binary frame = reply audio. Queue it so overlapping arrivals
        // (shouldn't normally happen in this turn-based design, but
        // defensive) don't play on top of each other.
        playbackQueueRef.current.push(event.data);
        if (playbackQueueRef.current.length === 1) {
          while (playbackQueueRef.current.length > 0) {
            const buf = playbackQueueRef.current[0];
            await playReplyAudio(buf);
            playbackQueueRef.current.shift();
          }
        }
        return;
      }

      try {
        const data = JSON.parse(event.data);
        if (data.type === 'live_ready') {
          setVoiceState('ready');
          setTranscript((t) => [...t, { type: 'system', text: 'Live voice uplink established.' }]);
        } else if (data.type === 'tool_used') {
          setTranscript((t) => [...t, { type: 'system', text: `[used ${data.name}]` }]);
        } else if (data.type === 'input_transcript') {
          setTranscript((t) => [...t, { type: 'user', text: data.text }]);
        } else if (data.type === 'output_transcript') {
          setTranscript((t) => [...t, { type: 'edith', text: data.text }]);
        } else if (data.type === 'turn_done') {
          setVoiceState('ready');
          setIsListening(false);
        } else if (data.type === 'error') {
          setTranscript((t) => [...t, { type: 'error', text: data.text }]);
          setVoiceState('ready');
          setIsListening(false);
        }
      } catch {
        // Non-JSON, non-ArrayBuffer text frame — ignore.
      }
    };

    ws.onerror = () => {
      setTranscript((t) => [...t, { type: 'error', text: 'Live voice uplink error.' }]);
      setVoiceState('idle');
    };

    ws.onclose = () => {
      setVoiceState('idle');
      setTranscript((t) => [...t, { type: 'system', text: 'Live voice uplink closed.' }]);
    };

    liveWsRef.current = ws;
  }, [playReplyAudio]);

  const startRecording = useCallback(async () => {
    if (voiceState !== 'ready') return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      micStreamRef.current = stream;

      const audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
      audioContextRef.current = audioContext;

      // AudioWorklet, loaded from a Blob URL (see PCM_WORKLET_SOURCE's
      // comment for why this specific approach — worklets must be
      // separate modules, can't be inline functions, but this keeps the
      // whole component self-contained for single-file environments).
      const blob = new Blob([PCM_WORKLET_SOURCE], { type: 'application/javascript' });
      const workletUrl = URL.createObjectURL(blob);
      await audioContext.audioWorklet.addModule(workletUrl);

      const source = audioContext.createMediaStreamSource(stream);
      const workletNode = new AudioWorkletNode(audioContext, 'pcm16-processor');
      workletNodeRef.current = workletNode;

      workletNode.port.onmessage = (event) => {
        // event.data is an Int16Array's underlying ArrayBuffer — raw
        // 16-bit PCM, matching what server/main.py's /ws/live expects.
        if (liveWsRef.current?.readyState === WebSocket.OPEN) {
          liveWsRef.current.send(event.data);
        }
      };

      source.connect(workletNode);
      // Deliberately NOT connecting workletNode to audioContext.destination
      // — we don't want to hear our own mic input played back locally.

      setVoiceState('recording');
      setIsListening(true);
      setTranscript((t) => [...t, { type: 'system', text: '[recording — speak now]' }]);
    } catch (e) {
      setTranscript((t) => [...t, { type: 'error', text: `Microphone access failed: ${e.message}` }]);
    }
  }, [voiceState]);

  const stopRecording = useCallback(() => {
    if (voiceState !== 'recording') return;

    // Tear down capture first, then signal END_TURN — matches the
    // server's protocol (accumulate binary frames until a text
    // "END_TURN" arrives, then process the whole turn).
    workletNodeRef.current?.disconnect();
    micStreamRef.current?.getTracks().forEach((track) => track.stop());
    audioContextRef.current?.close();

    if (liveWsRef.current?.readyState === WebSocket.OPEN) {
      liveWsRef.current.send('END_TURN');
    }

    setVoiceState('processing');
    setTranscript((t) => [...t, { type: 'system', text: '[processing your message]' }]);
  }, [voiceState]);

  const statusColor =
    connectionState === 'connected'
      ? COLORS.glow
      : connectionState === 'connecting'
      ? COLORS.starkRed
      : COLORS.steel;

  const coreGlowIntensity = isListening ? 0.9 : connectionState === 'connected' ? 0.5 : 0.2;
  const corePulseScale = 1 + Math.sin((pulsePhase * Math.PI) / 180) * (isListening ? 0.06 : 0.02);

  return (
    <div
      style={{
        minHeight: '100vh',
        background: `radial-gradient(ellipse at center, #111318 0%, ${COLORS.void} 70%)`,
        color: COLORS.paper,
        fontFamily: "'JetBrains Mono', 'Courier New', monospace",
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '2rem 1rem',
        boxSizing: 'border-box',
      }}
    >
      {/* Top status bar - quiet, technical, radial-diagnostic in tone */}
      <div
        style={{
          width: '100%',
          maxWidth: 600,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '0.7rem',
          letterSpacing: '0.15em',
          color: COLORS.steel,
          textTransform: 'uppercase',
          marginBottom: '1rem',
        }}
      >
        <span>E.D.I.T.H. // ELP Ops Interface</span>
        <span style={{ color: statusColor }}>
          ● {connectionState.toUpperCase()}
        </span>
      </div>

      {/* The signature element: the reactive HUD core */}
      <div
        style={{
          position: 'relative',
          width: 320,
          height: 320,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '1.5rem 0',
        }}
      >
        <svg width="320" height="320" style={{ position: 'absolute', overflow: 'visible' }}>
          <defs>
            <path id="labelArc" d="M 48,160 A 112,112 0 0 1 272,160" fill="none" />
            <filter id="edithGlow" x="-100%" y="-100%" width="300%" height="300%">
              <feGaussianBlur stdDeviation="5" result="b1" />
              <feGaussianBlur stdDeviation="12" result="b2" />
              <feMerge>
                <feMergeNode in="b2" />
                <feMergeNode in="b1" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="edithGlowSoft" x="-100%" y="-100%" width="300%" height="300%">
              <feGaussianBlur stdDeviation="8" />
            </filter>
          </defs>

          <g transform="translate(160, 160)">
            {/* Outer tick ring - the "many small radial marks" HUD device */}
            {outerTicks.map((tick, i) => (
              <line
                key={`outer-${i}`}
                x1={tick.x * 0.92}
                y1={tick.y * 0.92}
                x2={tick.x}
                y2={tick.y}
                stroke={i % 4 === 0 ? COLORS.glow : COLORS.steel}
                strokeWidth={i % 4 === 0 ? 2 : 1}
                opacity={connectionState === 'connected' ? 0.85 : 0.3}
              />
            ))}
            {/* Inner tick ring, offset rotation for a layered-instrument feel */}
            {innerTicks.map((tick, i) => (
              <line
                key={`inner-${i}`}
                x1={tick.x * 0.9}
                y1={tick.y * 0.9}
                x2={tick.x}
                y2={tick.y}
                stroke={COLORS.steel}
                strokeWidth={0.75}
                opacity={0.4}
                transform={`rotate(${pulsePhase / 3})`}
              />
            ))}

            {/* Main reactive core ring - real glow via SVG filter, NOT css
                text-shadow/box-shadow: confirmed via direct visual testing
                (rendered and screenshotted both approaches) that box-shadow/
                text-shadow read as a barely-visible thin outline, while an
                feGaussianBlur+feMerge filter produces a genuine light bloom.
                Don't swap this back to a CSS-shadow approach without
                re-checking against a real screenshot first. */}
            <circle
              r={70}
              fill="none"
              stroke={isListening ? COLORS.starkRed : COLORS.glow}
              strokeWidth={2}
              filter="url(#edithGlow)"
              opacity={connectionState === 'connected' ? 1 : 0.3}
              transform={`scale(${corePulseScale})`}
              style={{ transition: 'opacity 0.3s ease, stroke 0.3s ease' }}
            />
            <circle
              r={70}
              fill="none"
              stroke={isListening ? COLORS.starkRed : COLORS.glow}
              strokeWidth={0.5}
              strokeDasharray="4 8"
              opacity={connectionState === 'connected' ? 0.6 : 0.2}
              transform={`rotate(${-pulsePhase})`}
            />
            {/* Core glow fill */}
            <circle
              r={55}
              fill={isListening ? COLORS.starkRed : COLORS.glow}
              opacity={coreGlowIntensity * 0.1}
              filter="url(#edithGlowSoft)"
              transform={`scale(${corePulseScale})`}
            />
          </g>

          {/* Arc-integrated label - sits ON the ring geometry as real HUD
              instrumentation, rather than centered like a logo lockup
              (an earlier version did this; direct visual review showed it
              read as an afterthought/logo, not part of the instrument). */}
          <text
            fontSize="11"
            letterSpacing="4"
            fill={isListening ? COLORS.starkRed : COLORS.glow}
            filter="url(#edithGlow)"
            fontWeight="bold"
            opacity={connectionState === 'connected' ? 1 : 0.4}
          >
            <textPath href="#labelArc" startOffset="50%" textAnchor="middle">
              E · D · I · T · H
            </textPath>
          </text>
        </svg>

        {/* Center readout - what E.D.I.T.H. is doing right now, plus a
            small diagnostic line beneath it. Direct visual review of an
            earlier version (label alone, no second line) showed the core's
            center reading as too empty once the main label moved to the
            arc above — this second line fills that space with real HUD
            instrument density rather than leaving a void. */}
        <div style={{ textAlign: 'center', zIndex: 1, marginTop: 8 }}>
          <div
            style={{
              fontSize: '0.6rem',
              letterSpacing: '0.25em',
              color: COLORS.steel,
              textTransform: 'uppercase',
            }}
          >
            {isListening ? 'Processing' : connectionState === 'connected' ? 'Standing By' : 'Offline'}
          </div>
          <div
            style={{
              fontSize: '0.55rem',
              letterSpacing: '0.12em',
              color: isListening ? COLORS.starkRed : COLORS.glow,
              opacity: 0.55,
              marginTop: 8,
            }}
          >
            {connectionState === 'connected' ? 'LINK STABLE' : 'AWAITING UPLINK'}
          </div>
        </div>
      </div>

      {/* Uplink configuration - quiet, technical, not a prominent form */}
      <div
        style={{
          width: '100%',
          maxWidth: 600,
          display: 'flex',
          gap: 8,
          marginBottom: '1rem',
        }}
      >
        <input
          value={wsUrl}
          onChange={(e) => setWsUrl(e.target.value)}
          placeholder="wss://your-deployment.vercel.app/ws"
          style={{
            flex: 1,
            background: 'transparent',
            border: `1px solid ${COLORS.steel}`,
            color: COLORS.paper,
            fontFamily: 'inherit',
            fontSize: '0.75rem',
            padding: '0.5rem 0.75rem',
            outline: 'none',
          }}
        />
        <button
          onClick={connect}
          style={{
            background: 'transparent',
            border: `1px solid ${COLORS.glow}`,
            color: COLORS.glow,
            fontFamily: 'inherit',
            fontSize: '0.7rem',
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            padding: '0.5rem 1rem',
            cursor: 'pointer',
          }}
        >
          Connect
        </button>
      </div>

      {/* Transcript - ticker-style, secondary to the core, per the design plan */}
      <div
        style={{
          width: '100%',
          maxWidth: 600,
          height: 220,
          overflowY: 'auto',
          border: `1px solid ${COLORS.steel}`,
          padding: '0.75rem 1rem',
          fontSize: '0.8rem',
          fontFamily: "'Inter', -apple-system, sans-serif",
          lineHeight: 1.6,
        }}
      >
        {transcript.length === 0 && (
          <div style={{ color: COLORS.steel, fontStyle: 'italic', fontSize: '0.75rem' }}>
            No transmissions yet. Connect the uplink to begin.
          </div>
        )}
        {transcript.map((line, i) => (
          <div
            key={i}
            style={{
              marginBottom: 6,
              color:
                line.type === 'edith'
                  ? COLORS.glow
                  : line.type === 'user'
                  ? COLORS.paper
                  : line.type === 'error'
                  ? COLORS.starkRed
                  : COLORS.steel,
              opacity: line.type === 'system' ? 0.6 : 1,
            }}
          >
            <span
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '0.65rem',
                letterSpacing: '0.1em',
                marginRight: 8,
                opacity: 0.7,
              }}
            >
              {line.type === 'edith' ? 'E.D.I.T.H.' : line.type === 'user' ? 'YOU' : line.type === 'error' ? 'ALERT' : 'SYS'}
            </span>
            {line.text}
            {line.streaming && <span style={{ opacity: 0.5 }}>▍</span>}
          </div>
        ))}
        <div ref={transcriptEndRef} />
      </div>

      {/* Input */}
      <div style={{ width: '100%', maxWidth: 600, display: 'flex', gap: 8, marginTop: '1rem' }}>
        <input
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
          placeholder={connectionState === 'connected' ? 'Speak, or type your query...' : 'Uplink required'}
          disabled={connectionState !== 'connected'}
          style={{
            flex: 1,
            background: 'transparent',
            border: `1px solid ${isListening ? COLORS.starkRed : COLORS.steel}`,
            color: COLORS.paper,
            fontFamily: "'Inter', -apple-system, sans-serif",
            fontSize: '0.85rem',
            padding: '0.65rem 1rem',
            outline: 'none',
            transition: 'border-color 0.3s ease',
          }}
        />
        <button
          onClick={sendMessage}
          disabled={connectionState !== 'connected'}
          style={{
            background: connectionState === 'connected' ? COLORS.glow : 'transparent',
            border: `1px solid ${COLORS.glow}`,
            color: connectionState === 'connected' ? COLORS.void : COLORS.steel,
            fontFamily: 'inherit',
            fontSize: '0.7rem',
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            padding: '0 1.25rem',
            cursor: connectionState === 'connected' ? 'pointer' : 'not-allowed',
          }}
        >
          Send
        </button>
      </div>

      {/* Live voice panel — separate uplink from the text /ws above,
          talks to /ws/live. Turn-based: connect once, then press to
          record, press again to stop and send — matching
          server/main.py's END_TURN protocol and live_explore.py's
          proven turn-based architecture (not continuous/always-on). */}
      <div
        style={{
          width: '100%',
          maxWidth: 600,
          display: 'flex',
          gap: 8,
          marginTop: '0.75rem',
          alignItems: 'center',
        }}
      >
        <span style={{ fontSize: '0.65rem', letterSpacing: '0.1em', color: COLORS.steel, textTransform: 'uppercase' }}>
          Live Voice:
        </span>
        {voiceState === 'idle' ? (
          <button
            onClick={connectVoice}
            style={{
              background: 'transparent',
              border: `1px solid ${COLORS.glow}`,
              color: COLORS.glow,
              fontFamily: 'inherit',
              fontSize: '0.7rem',
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              padding: '0.4rem 1rem',
              cursor: 'pointer',
            }}
          >
            Connect Live
          </button>
        ) : (
          <button
            onClick={voiceState === 'recording' ? stopRecording : startRecording}
            disabled={voiceState === 'connecting' || voiceState === 'processing'}
            style={{
              background: voiceState === 'recording' ? COLORS.starkRed : 'transparent',
              border: `1px solid ${voiceState === 'recording' ? COLORS.starkRed : COLORS.glow}`,
              color: voiceState === 'recording' ? COLORS.paper : COLORS.glow,
              fontFamily: 'inherit',
              fontSize: '0.7rem',
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              padding: '0.4rem 1.25rem',
              cursor: voiceState === 'ready' || voiceState === 'recording' ? 'pointer' : 'not-allowed',
              opacity: voiceState === 'connecting' || voiceState === 'processing' ? 0.5 : 1,
            }}
          >
            {voiceState === 'connecting' && 'Connecting...'}
            {voiceState === 'ready' && 'Press to Speak'}
            {voiceState === 'recording' && 'Stop & Send'}
            {voiceState === 'processing' && 'Processing...'}
          </button>
        )}
      </div>
    </div>
  );
}
