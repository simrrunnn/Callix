"""
Supabase persistence -- a direct asyncpg connection to Postgres using
SUPABASE_DB_URL, not the Supabase REST client/SDK.

RLS is enabled with no policies on every table (see db/schema.sql), which
blocks the REST API's anon/authenticated roles by default -- but that's
irrelevant here. A direct Postgres connection like this one authenticates
as the `postgres` role itself, which owns the tables and bypasses RLS
entirely, the same way the service_role key does over the REST API.

A connection pool (a small set of already-open connections, reused across
queries) is used instead of opening a fresh connection per call, since
each new connection is a real network round-trip.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg

logger = logging.getLogger("voice-agent")

_pool: asyncpg.Pool | None = None


@dataclass
class CallState:
    """Shared per-call state, passed as AgentSession(userdata=...) so both
    the session-level event hooks (voice_agent.py) and Agent tools
    (pipeline_agents.py) can reach the same call_id without threading it
    through every function signature."""

    call_id: UUID


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            os.environ["SUPABASE_DB_URL"], min_size=1, max_size=5
        )
    return _pool


async def create_call(room_name: str) -> UUID:
    pool = await get_pool()
    call_id: UUID = await pool.fetchval(
        "insert into calls (room_name) values ($1) returning id",
        room_name,
    )
    logger.info("db: created call %s (room=%s)", call_id, room_name)
    return call_id


async def end_call(call_id: UUID, end_state: str, escalated: bool = False) -> None:
    pool = await get_pool()
    await pool.execute(
        "update calls set ended_at = now(), end_state = $2, escalated = $3 "
        "where id = $1",
        call_id,
        end_state,
        escalated,
    )
    logger.info("db: ended call %s (state=%s escalated=%s)", call_id, end_state, escalated)


async def record_turn(
    call_id: UUID,
    turn_index: int,
    *,
    caller_transcript: str | None = None,
    agent_reply: str | None = None,
) -> None:
    # One row per conversation item (one side of an exchange), not a
    # caller+reply pair -- simpler than buffering/pairing turns, and
    # honest about what we're actually capturing right now: no ASR/LLM/TTS
    # provider or latency instrumentation exists yet, so those columns
    # stay NULL regardless of how a "turn" is defined.
    pool = await get_pool()
    await pool.execute(
        "insert into turns (call_id, turn_index, caller_transcript, agent_reply) "
        "values ($1, $2, $3, $4)",
        call_id,
        turn_index,
        caller_transcript,
        agent_reply,
    )


async def create_appointment(
    call_id: UUID, customer_name: str, service: str, scheduled_for: datetime
) -> UUID:
    pool = await get_pool()
    appointment_id: UUID = await pool.fetchval(
        "insert into appointments (call_id, customer_name, service, scheduled_for) "
        "values ($1, $2, $3, $4) returning id",
        call_id,
        customer_name,
        service,
        scheduled_for,
    )
    logger.info(
        "db: created appointment %s (service=%r scheduled_for=%s)",
        appointment_id,
        service,
        scheduled_for,
    )
    return appointment_id
