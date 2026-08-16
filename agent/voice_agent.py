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

Stage 3 adds Supabase persistence: a `calls` row per call, a `turns` row
per conversation item (one side of an exchange -- see db.record_turn's
docstring for why it's not a caller+reply pair), and `db.CallState` shared
via AgentSession(userdata=...) so pipeline_agents.py can create the
`appointments` row from inside confirm_booking without threading call_id
through every function signature.

`db.create_call()` is kicked off here but NOT awaited before starting the
session -- confirmed live that awaiting it first added ~5.5s to the
critical path (first DB connection pool setup), delaying the greeting by
that much for no real reason, since nothing about greeting the caller
actually depends on the call_id existing yet.
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

    call_id_task = asyncio.create_task(db.create_call(ctx.room.name))
    call_state = db.CallState(call_id_task=call_id_task)

    session = agents.AgentSession(
        stt=deepgram.STT(
            # Nova-3 keyterm prompting: biases recognition toward this
            # vocabulary. Added after a live test where "waxing" got
            # misheard as "vaccine" repeatedly, causing several costly
            # extra back-and-forth turns (each one paying for another
            # LLM call + TTS synthesis) before the caller finally spelled
            # it out letter by letter.
            keyterm=[
                "haircut",
                "beard trim",
                "hair coloring",
                "blowout",
                "styling",
                "waxing",
                "kids haircut",
                "appointment",
                "reschedule",
                "cancel",
                "Willow Lane",
            ],
        ),
        llm=openai.LLM(
            model=OPENROUTER_MODEL,
            api_key=os.environ["OPENROUTER_API_KEY"],
            base_url=OPENROUTER_BASE_URL,
        ),
        tts=cartesia.TTS(),
        vad=silero.VAD.load(),
        # Default is 3.0s, and an earlier live test showed the initial
        # greeting waits for this to finish before speaking at all --
        # confirmed in logs (aec warmup start/expire timestamps lined up
        # exactly with the greeting firing). Shortened for a snappier
        # start; tradeoff is less time for echo-cancellation calibration.
        aec_warmup_duration=1.0,
        userdata=call_state,
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
        role = item.role

        async def _record() -> None:
            call_id = await call_state.get_call_id()
            if role == "user":
                await db.record_turn(call_id, turn_index, caller_transcript=text)
            else:
                await db.record_turn(call_id, turn_index, agent_reply=text)

        asyncio.create_task(_record())

    # end_call() must run as a shutdown callback, not a fire-and-forget task
    # off session.on("close") -- confirmed live that a plain
    # asyncio.create_task() there never got a chance to run: the job process
    # exits right after the close event fires, with no guarantee the event
    # loop schedules the task before that happens (every turn during the
    # call persisted fine, since there was always time between them, but
    # ended_at/end_state stayed NULL on every call). Shutdown callbacks
    # registered via ctx.add_shutdown_callback(), by contrast, are awaited
    # by the worker before the job process exits.
    async def _end_call(reason: str) -> None:
        call_id = await call_state.get_call_id()
        await db.end_call(call_id, reason)

    ctx.add_shutdown_callback(_end_call)

    await session.start(agent=IntentAgent(), room=ctx.room)
    logger.info("session started")


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    agents.cli.run_app(
        agents.WorkerOptions(entrypoint_fnc=entrypoint, host="0.0.0.0", port=7860)
    )


if __name__ == "__main__":
    run()
