# E.D.I.T.H. server — persistent deployment (Oracle Cloud, or any real VM)
#
# WHY THIS EXISTS: Vercel's serverless model was flagged as a real,
# confirmed risk once true continuous streaming (server/main.py's
# /ws/live-stream) started working — a mid-conversation instance recycle
# would silently drop the live Gemini session, its conversation context,
# and all utterance-boundary state, with no clean recovery. A real,
# always-running container removes this class of risk entirely: one
# process, staying up, holding state for as long as it needs to.
#
# Uses requirements-server.txt (NOT the project's main requirements.txt)
# deliberately — excludes vosk/piper-tts, which this server never imports
# at all (they're only used by main_voice_local.py, an unrelated
# phone-native experiment). See requirements-server.txt's own comments.

FROM python:3.12-slim

WORKDIR /app

# System-level build tools, in case any dependency needs to compile from
# source on this platform (a normal Linux VM should mostly get prebuilt
# wheels, unlike Termux's aarch64-linux-android situation documented
# elsewhere in this project — but not assuming that without a fallback).
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt

# Only what the server actually needs at runtime — the edith/ package
# (Brain, tools, setup) and the server code itself. NOT the frontend/,
# not vercel.json (irrelevant here), not the local-voice-only pieces.
COPY edith/ ./edith/
COPY server/ ./server/

# Real secrets (GEMINI_API_KEY, DEEPGRAM_API_KEY, ELEVENLABS_API_KEY,
# ELEVENLABS_VOICE_ID) are NOT baked into the image — set them as real
# environment variables on the Oracle instance itself (or via `docker run
# -e ...` / a .env file mounted at runtime), same "secrets never in code"
# principle as everywhere else in this project.

EXPOSE 8000

# Runs server/main.py's `app` object directly — the same FastAPI app
# already confirmed working, unchanged. --host 0.0.0.0 so it's reachable
# from outside the container (matching the same reasoning Vercel's own
# deployment needed: listen on any address, not just localhost).
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
