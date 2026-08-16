"""
Read-only REST API for the dashboard -- a FastAPI APIRouter mounted onto
the same Gradio-created FastAPI app in app.py (confirmed live: routes
added to demo.app after launch() are immediately reachable), so this rides
along on the existing Hugging Face Space instead of needing its own
separate deployment.

Historical browsing only for this MVP (call list, a call's transcript,
appointments) -- no live/real-time updates, which would need
WebSockets/polling infra this doesn't have.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import db

router = APIRouter(prefix="/api")


class Call(BaseModel):
    id: UUID
    room_name: str
    caller_number: str | None
    started_at: datetime
    ended_at: datetime | None
    end_state: str | None
    escalated: bool


class Turn(BaseModel):
    turn_index: int
    caller_transcript: str | None
    agent_reply: str | None
    asr_provider: str | None
    asr_latency_ms: int | None
    llm_provider: str | None
    llm_latency_ms: int | None
    tts_provider: str | None
    tts_latency_ms: int | None
    fallback_used: bool
    created_at: datetime


class CallDetail(BaseModel):
    call: Call
    turns: list[Turn]


class Appointment(BaseModel):
    id: UUID
    call_id: UUID | None
    customer_name: str | None
    service: str | None
    scheduled_for: datetime
    status: str
    created_at: datetime


@router.get("/calls", response_model=list[Call])
async def get_calls() -> list[dict]:
    return await db.list_calls()


@router.get("/calls/{call_id}", response_model=CallDetail)
async def get_call_detail(call_id: UUID) -> dict:
    call = await db.get_call(call_id)
    if call is None:
        raise HTTPException(status_code=404, detail="call not found")
    turns = await db.list_turns(call_id)
    return {"call": call, "turns": turns}


@router.get("/appointments", response_model=list[Appointment])
async def get_appointments() -> list[dict]:
    return await db.list_appointments()
