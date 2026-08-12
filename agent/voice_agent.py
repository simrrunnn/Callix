"""
Step 2: the real conversation pipeline.

Stage 1 (proven working) was a single generic Agent with STT (Deepgram) ->
LLM (OpenRouter, via the OpenAI-compatible plugin) -> TTS (Cartesia) -> VAD
(Silero), to confirm the conversation pipeline itself works before adding
any complexity on top of it.

Stage 2 swapped that single Agent for the state machine in
pipeline_agents.py (IntentAgent <-> BookingAgent, via LiveKit's handoff
mechanism) -- same providers, same session wiring, just real conversation
structure instead of one open-ended agent.

Stage 3 (this version) adds Supabase persistence: a `calls` row per call,
a `turns` row per conversation item (one side of an exchange -- see
db.record_turn's docstring for why it's not a caller+reply pair), and
`db.CallState` shared via AgentSession(userdata=...) so pipeline_agents.py
can create the `appointments` row from inside confirm_booking without
threading call_id through every function signature.
"""

import asyncio
import logging
import os

from dotenv import load_dotenv
from livekit import agents
from livekit.plugins import cartesia, deepgram, openai, silero

import db
from pipeline_agents import IntentAgent

load_dotenv()

logger = logging.getLogger("voice-agent")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODEL = "openai/gpt-4o-mini"


async def entrypoint(ctx: agents.JobContext) -> None:
    await ctx.connect()
    logger.info("connected to room %s", ctx.room.name)

    call_id = await db.create_call(ctx.room.name)

    session = agents.AgentSession(
        stt=deepgram.STT(),
        llm=openai.LLM(
            model=OPENROUTER_MODEL,
            api_key=os.environ["OPENROUTER_API_KEY"],
            base_url=OPENROUTER_BASE_URL,
        ),
        tts=cartesia.TTS(),
        vad=silero.VAD.load(),
        # Default is 3.0s, and the first live test showed the initial
        # greeting waits for this to finish before speaking at all --
        # confirmed in logs (aec warmup start/expire timestamps lined up
        # exactly with the greeting firing). Shortened for a snappier
        # start; tradeoff is less time for echo-cancellation calibration.
        aec_warmup_duration=1.0,
        userdata=db.CallState(call_id=call_id),
    )

    turn_index = 0

    @session.on("conversation_item_added")
    def _on_conversation_item(event: agents.ConversationItemAddedEvent) -> None:
        nonlocal turn_index
        item = event.item
        if not isinstance(item, agents.ChatMessage) or item.role not in (
            "user",
            "assistant",
        ):
            return
        turn_index += 1
        text = item.text_content
        if item.role == "user":
            asyncio.create_task(
                db.record_turn(call_id, turn_index, caller_transcript=text)
            )
        else:
            asyncio.create_task(
                db.record_turn(call_id, turn_index, agent_reply=text)
            )

    @session.on("close")
    def _on_close(event: agents.CloseEvent) -> None:
        asyncio.create_task(db.end_call(call_id, event.reason.value))

    await session.start(agent=IntentAgent(), room=ctx.room)
    logger.info("session started (call_id=%s)", call_id)


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    agents.cli.run_app(
        agents.WorkerOptions(entrypoint_fnc=entrypoint, host="0.0.0.0", port=7860)
    )


if __name__ == "__main__":
    run()
