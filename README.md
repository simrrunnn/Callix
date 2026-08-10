# AI Voice Agent for Inbound Call Handling

A phone-in voice agent: caller dials in, agent verifies intent, answers
questions via RAG over a small knowledge base, and books/reschedules an
appointment or escalates to a human — in real time over a phone call.

## Stack

| Layer | Choice |
|---|---|
| Media/SIP (call ingress) | LiveKit Cloud (free tier) |
| Telephony trunk | Twilio |
| Agent worker + orchestrator compute | Hugging Face Space (Gradio SDK, ZeroGPU hardware — free accounts can no longer run CPU-basic compute Spaces of any SDK without PRO), kept warm via UptimeRobot |
| Backend | FastAPI |
| Database + vector store | Supabase (Postgres + pgvector) |
| ASR | Deepgram (primary), AssemblyAI (fallback) |
| LLM | GPT-4o-mini / Claude Haiku (primary/fallback pair) |
| TTS | Cartesia (primary), ElevenLabs (fallback) |
| Dashboard | React/TypeScript |
| Observability | OpenTelemetry + Langfuse |

## Current status: Day-1 connectivity spike — confirmed working end-to-end

The one thing everything else was waiting on: can a LiveKit agent actually
running on a Hugging Face Space join a LiveKit Cloud room and pass audio
both ways? **Confirmed, from the real deployment, not just locally** — the
Space registered with LiveKit Cloud, a human joined the room, heard the
agent's test tone, and the agent logged clean, continuous inbound audio
(8s, evenly spaced frames, no gaps) from that human's mic. Hugging Face's
network restrictions (80/443/8080 only) do not block LiveKit's WebRTC media
path in practice.

Two real bugs surfaced and got fixed along the way, worth knowing about if
touching `agent/app.py` again:
- `.env` was never actually loaded into the process (missing `load_dotenv()`
  call) — silent until the worker failed with a missing-URL error.
- The LiveKit worker spawns subprocesses per job, and Python's
  multiprocessing re-imports `app.py` in each one; unguarded top-level
  `demo.launch()` calls re-ran in every subprocess and crash-looped the
  whole worker fighting over the same port. Fixed by guarding everything
  behind `if __name__ == "__main__":`.

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

### The actual test we cared about — passed

Local dev runs on an unrestricted network, so it didn't test the thing we
were actually unsure about. The real test was from the deployed Space
itself, and it passed: audio flows both ways through HF Spaces + LiveKit
Cloud. The rest of the pipeline (ASR/LLM/TTS, state machine, RAG, provider
failover, dashboard, evals) can now be built on top of this without that
assumption hanging over it.

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
