---
title: Voice Agent Connectivity Spike
emoji: 📞
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 6.22.0
app_file: app.py
pinned: false
---

Day-1 connectivity spike for the inbound voice agent project. Joins a
LiveKit Cloud room, plays a test tone, and logs received audio -- validates
that this Space's network path can carry live call audio before any
ASR/LLM/TTS logic is built on top of it.

Runs as a Gradio Space (see `app.py`) rather than a Docker Space: Docker
Spaces currently require a payment method on file even on the free tier,
Gradio Spaces don't. The Gradio UI itself is just a placeholder page --
the real work is the LiveKit agent worker running alongside it in the same
process.

Requires these repository secrets to be set in the Space's settings:
`LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`.
