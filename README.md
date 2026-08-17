# Callix

An AI voice agent for inbound call handling, built as a portfolio project and
themed as a salon receptionist. A caller talks to it over the browser (no
phone line yet), and it can answer questions grounded in a small knowledge
base, and book, reschedule, or cancel appointments. Every call and its
transcript are saved, with a read-only API over that history.

Built entirely on free-tier infrastructure.

## What actually works right now

- Real-time voice conversation: greeting, intent handling, and a handoff
  between an intent agent and a booking agent
- Question answering grounded in a small knowledge base (RAG over Supabase
  pgvector)
- Appointment booking with a basic conflict check (same name, not already
  booked in the past)
- Escalation to a human is acknowledged in conversation and logged, though
  the escalated flag isn't persisted correctly yet (see Known limitations)
- Every call's transcript, and any appointment created, is saved to Postgres
- A read-only REST API over calls, transcripts, and appointments
- A browser-based landing page and a live call demo page

## What isn't built yet

- No real phone number. Calls happen through the browser via LiveKit, not
  through an actual telephony line.
- No fallback providers. One ASR provider, one LLM, one TTS provider, no
  automatic failover if one goes down.
- No observability or eval suite. The database has tables reserved for both,
  nothing writes to them yet.
- No dashboard UI. The API for call history exists; there's no page for it.
- No authentication on the API, and CORS is wide open. Fine for a demo with
  synthetic data, not fine for real customer data.

## Stack

| Layer | Choice |
|---|---|
| Voice orchestration | livekit-agents, running as a LiveKit Cloud worker |
| ASR | Deepgram |
| LLM | OpenRouter (gpt-4o-mini) |
| TTS | Cartesia |
| VAD | Silero |
| Backend hosting | Hugging Face Spaces (Gradio SDK), FastAPI routes mounted on the same app |
| Database | Supabase (Postgres + pgvector) |
| Embeddings | Hugging Face Inference API |
| Frontend | React, TypeScript, Vite, Tailwind |
| Frontend hosting | Vercel |

## Repo layout

```
agent/
  app.py             Gradio-wrapped entrypoint used for the Hugging Face Space deploy
  voice_agent.py      Session wiring: STT/LLM/TTS, persistence hooks
  pipeline_agents.py  The actual conversation logic: intent handling, booking, escalation
  rag.py              Embedding + retrieval for the knowledge base
  db.py                Supabase persistence layer
  api/                 REST API for call history (mounted on the same app)
  connectivity_spike.py  Early spike, kept for reference, not part of the current deploy
db/
  schema.sql          Postgres schema: calls, turns, appointments, kb_chunks, eval tables
frontend/
  Landing page and live call demo, deployed separately to Vercel
```

## Running it locally

1. Sign up for free accounts: LiveKit Cloud, Supabase, OpenRouter, Deepgram,
   Cartesia, Hugging Face.
2. Run `db/schema.sql` in the Supabase SQL editor, and enable the `vector`
   extension under Database > Extensions if it isn't already on.
3. Copy `.env.example` to `.env` in the repo root and fill in the values.
4. From `agent/`:

```bash
python -m venv ../.venv
source ../.venv/Scripts/activate
pip install -r requirements.txt
python app.py
```

5. For the frontend, copy `frontend/.env.example` to `frontend/.env`, then:

```bash
cd frontend
npm install
npm run dev
```

## Deploying

The backend deploys to a Hugging Face Space (Gradio SDK) as a separate git
remote:

```bash
git remote add hf-space <your-space-git-url>
git subtree push --prefix=agent hf-space main
```

The Space needs to be set to Public, and needs `ssr_mode=False` passed to
`demo.launch()` in `app.py`, since Hugging Face's Space runtime otherwise
enables Gradio's SSR mode by default, which breaks the custom API routes.

The frontend deploys to Vercel from `frontend/`, using `frontend/vercel.json`
for the build settings. Root Directory and the `VITE_API_URL` environment
variable are set in the Vercel project dashboard, not in a committed file.
