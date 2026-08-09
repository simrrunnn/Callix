# AI Voice Agent for Inbound Call Handling

A phone-in voice agent: caller dials in, agent verifies intent, answers
questions via RAG over a small knowledge base, and books/reschedules an
appointment or escalates to a human — in real time over a phone call.

## Stack

| Layer | Choice |
|---|---|
| Media/SIP (call ingress) | LiveKit Cloud (free tier) |
| Telephony trunk | Twilio |
| Agent worker + orchestrator compute | Hugging Face Space (Gradio SDK — Docker Spaces require billing details on file, Gradio doesn't), kept warm via UptimeRobot |
| Backend | FastAPI |
| Database + vector store | Supabase (Postgres + pgvector) |
| ASR | Deepgram (primary), AssemblyAI (fallback) |
| LLM | GPT-4o-mini / Claude Haiku (primary/fallback pair) |
| TTS | Cartesia (primary), ElevenLabs (fallback) |
| Dashboard | React/TypeScript |
| Observability | OpenTelemetry + Langfuse |

## Current status: Day-1 connectivity spike

Before building the full ASR/LLM/TTS pipeline, we're validating one thing in
isolation: can a LiveKit agent running on a Hugging Face Space actually join
a LiveKit Cloud room and pass audio both ways? This matters because the
agent worker is meant to run there, and Hugging Face restricts outbound
network traffic to ports 80/443/8080 — everything else here builds on the
assumption that this works. **Confirmed working when run locally** (both
directions: the tone was heard, inbound mic audio was logged); still needs
confirming from the actual Hugging Face deployment, which is the real test
since local dev runs on an unrestricted network.

`agent/connectivity_spike.py` has no ASR/LLM/TTS dependency on purpose. It
joins a room, plays a continuous 440Hz test tone (so a human in the room can
confirm they hear it), and logs whenever it receives audio from another
participant (so we can confirm inbound audio, e.g. your voice, is arriving).

### What you need to do first (accounts I can't create for you)

1. **LiveKit Cloud** — sign up free at https://cloud.livekit.io, create a
   project, and grab the WebSocket URL + API key + API secret from
   Settings > Keys.
2. **Supabase** — sign up free at https://supabase.com, create a project,
   and grab the project URL + service role key from Settings > API, plus the
   direct Postgres connection string from Settings > Database. Once created,
   run `db/schema.sql` in the Supabase SQL editor and enable the `vector`
   extension if it isn't already (Database > Extensions > vector).
3. Copy `.env.example` to `.env` and fill in the LiveKit + Supabase values
   (the ASR/LLM/TTS/Twilio keys aren't needed yet for this spike).

### Running the spike locally

```bash
cd agent
python -m venv ../.venv        # if you haven't already
source ../.venv/Scripts/activate
pip install -r requirements.txt
python connectivity_spike.py dev
```

`dev` mode auto-connects to a LiveKit Cloud "sandbox" test room — LiveKit
Cloud's dashboard has a browser-based test client under your project so you
can join the same room, speak into your mic, and both hear the tone and see
transcribed log lines confirming your audio arrived.

### Running it in Docker (optional, still useful for local testing)

`agent/Dockerfile` still works for a local Docker test run and isn't part of
the Hugging Face deploy path below:

```bash
docker build -t voice-agent-spike ./agent
docker run --env-file .env -p 7860:7860 voice-agent-spike
```

### Deploying to Hugging Face Spaces (Gradio SDK)

Docker-SDK Spaces currently require a payment method on file to create,
even on the free CPU tier — Gradio-SDK Spaces don't. `agent/app.py` wraps
the same agent logic (`entrypoint` from `connectivity_spike.py`, unchanged)
so it starts under Gradio's runtime instead of our own Dockerfile: Gradio
serves a placeholder page on the one port Hugging Face routes traffic to
(satisfying its health check), and the LiveKit worker runs alongside it in
the same process.

1. Create a Space at huggingface.co with SDK = **Gradio**.
2. In its Settings → Variables and secrets, add `LIVEKIT_URL`,
   `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` as secrets.
3. Push this repo's `agent/` folder as that Space's git repo root:
   ```bash
   git remote add hf-space <your-space-git-url>
   git subtree push --prefix=agent hf-space main
   ```

### The actual test we care about

Local dev runs on an unrestricted network, so it doesn't test the thing
we're actually unsure about. The real spike is: once deployed, confirm the
Space's page loads (Gradio's server responding is the health signal here),
then join the LiveKit test room again and confirm audio still flows both
ways from that deployment. If it does, the HF Spaces + LiveKit Cloud
combination is validated and we build the rest of the pipeline on top of
it. If it doesn't, we find out in an hour instead of after a week of
building on a broken assumption.

### A note on the CLI

`connectivity_spike.py`'s `start`/`dev` subcommands come from
`livekit-agents`' current CLI, which the library itself flags as the
"legacy" interface in favor of the newer `lk agent` CLI /
`livekit.agents.__main__`. It works as of `livekit-agents==1.6.9`; if a
future upgrade removes it, the fix is switching the entrypoint invocation,
not rewriting the agent logic.

## Repo layout

```
agent/
  connectivity_spike.py   # Day-1 spike: LiveKit connectivity only, no AI providers yet
  app.py                   # Gradio-wrapped startup for the Hugging Face Space deploy
  requirements.txt
  Dockerfile               # optional local testing only, not used by the HF deploy
  README.md                # Hugging Face Space frontmatter + description
db/
  schema.sql               # Supabase/Postgres schema: calls, turns, appointments, kb_chunks, evals
```

Orchestrator (FastAPI), the provider abstraction layer, RAG, the eval
harness, and the React dashboard come after the spike is confirmed working
from the actual Hugging Face Space deployment.
