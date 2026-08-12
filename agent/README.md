---
title: Voice Agent
emoji: 📞
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 6.22.0
app_file: app.py
pinned: false
---

Inbound voice agent for a fictional small business (Willow Lane Hair
Studio): callers can ask questions grounded in a real knowledge base
(RAG), and book/reschedule appointments through a state machine
(Intent/Booking agents, LiveKit's Agent handoff mechanism). Calls, turns,
and appointments persist to Supabase.

Runs as a Gradio Space (see `app.py`) rather than a Docker Space: Docker
Spaces currently require a payment method on file even on the free tier,
Gradio Spaces don't. The Gradio UI itself is just a placeholder page --
the real work is the LiveKit agent worker (`voice_agent.py` +
`pipeline_agents.py`) running alongside it in the same process.

Requires these repository secrets to be set in the Space's settings:
`LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `OPENROUTER_API_KEY`,
`DEEPGRAM_API_KEY`, `CARTESIA_API_KEY`, `SUPABASE_DB_URL`, `HF_TOKEN`.

`agent/connectivity_spike.py` is the original Day-1 spike (LiveKit
connectivity only, no AI providers) -- still in the repo for reference,
no longer what this Space deploys.
