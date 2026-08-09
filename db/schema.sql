-- Voice agent schema. Run in the Supabase SQL editor (or via migration tool).
-- Requires the pgvector extension, which Supabase enables per-project under
-- Database > Extensions > vector.

create extension if not exists vector;

create table if not exists calls (
    id uuid primary key default gen_random_uuid(),
    room_name text not null,
    caller_number text,
    started_at timestamptz not null default now(),
    ended_at timestamptz,
    end_state text, -- e.g. 'booked', 'escalated', 'abandoned'
    escalated boolean not null default false
);

create table if not exists turns (
    id uuid primary key default gen_random_uuid(),
    call_id uuid not null references calls(id) on delete cascade,
    turn_index int not null,
    caller_transcript text,
    agent_reply text,
    asr_provider text,
    asr_latency_ms int,
    llm_provider text,
    llm_latency_ms int,
    tts_provider text,
    tts_latency_ms int,
    fallback_used boolean not null default false,
    created_at timestamptz not null default now()
);

create table if not exists appointments (
    id uuid primary key default gen_random_uuid(),
    call_id uuid references calls(id) on delete set null,
    customer_name text,
    service text,
    scheduled_for timestamptz not null,
    status text not null default 'booked', -- booked | rescheduled | cancelled
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists kb_documents (
    id uuid primary key default gen_random_uuid(),
    title text not null,
    source text,
    created_at timestamptz not null default now()
);

create table if not exists kb_chunks (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null references kb_documents(id) on delete cascade,
    content text not null,
    embedding vector(1536), -- matches OpenAI text-embedding-3-small dimensionality
    created_at timestamptz not null default now()
);

create index if not exists kb_chunks_embedding_idx
    on kb_chunks using hnsw (embedding vector_cosine_ops);

create table if not exists eval_runs (
    id uuid primary key default gen_random_uuid(),
    run_at timestamptz not null default now(),
    scenario_count int not null,
    task_completion_rate numeric,
    hallucination_rate numeric,
    latency_p50_ms int,
    latency_p95_ms int
);

create table if not exists eval_results (
    id uuid primary key default gen_random_uuid(),
    run_id uuid not null references eval_runs(id) on delete cascade,
    scenario_name text not null,
    passed boolean not null,
    end_to_end_latency_ms int,
    notes text
);

-- Every table below is written to and read by the FastAPI orchestrator only,
-- using the Supabase service_role key (which bypasses RLS by design). RLS is
-- enabled with no policies added, so the anon/authenticated keys -- the kind
-- that could end up in browser-side code -- get zero access by default,
-- including to caller phone numbers, transcripts, and customer names.
alter table calls enable row level security;
alter table turns enable row level security;
alter table appointments enable row level security;
alter table kb_documents enable row level security;
alter table kb_chunks enable row level security;
alter table eval_runs enable row level security;
alter table eval_results enable row level security;
