"""
State-machine layer for the voice pipeline: each conversation stage is its
own Agent with focused instructions, transitioning via tool calls that
return a new Agent instance -- LiveKit's built-in handoff mechanism (a tool
returning an Agent switches the session to it; confirmed against the
installed package's tool_executor.py before relying on it).

Three real bugs surfaced across live tests and are fixed below, not just
tuned:

1. Handing off to a new Agent does NOT make it say anything on its own.
   Each Agent overrides `on_enter` (called automatically on activation,
   confirmed against agent_activity.py) to proactively call
   `session.generate_reply(...)`.

2. That proactive greeting is interruptible by default, and LLM+TTS
   latency means there's a real window where it's "in progress" but not
   yet audible -- a live test showed the caller saying "hi" during that
   window silently cancelled the greeting before a single word played,
   leaving true dead air. `on_enter` replies are now generated with
   `allow_interruptions=False` so they always finish playing.

3. `end_call` isn't reliably invoked by the model just because the
   instructions ask for it -- confirmed live: the model wrote "goodbye
   *ending call*" as plain text, twice, without ever calling the tool, and
   the call never ended. `end_call` now generates and speaks its own
   goodbye internally (so it doesn't depend on the model pairing text with
   the call correctly) and its docstring is written as a hard requirement
   with the failure mode spelled out, since a soft suggestion demonstrably
   wasn't enough.

4. Every proactive `generate_reply` call above (on_enter, end_call's own
   goodbye) is meant to speak one scripted line, not make a decision -- but
   by default it still has the full toolset available. Confirmed live:
   right after confirm_booking handed off to IntentAgent to speak the
   booking confirmation, the model instead called book_appointment again
   (nonsensical) and then end_call, hanging up without ever telling the
   caller their appointment was confirmed. All of these calls now pass
   `tool_choice="none"` to force plain text, no tool calls possible.

Also: BookingAgent now explicitly asks the caller to repeat unclear
answers instead of treating confusing input as a reason to cancel -- a
live test showed a garbled/cut-off name ("It's in an") caused the model to
call cancel_booking rather than ask again.

Deliberately no RAG or database writes yet -- those are the next two
layers, added only after this handoff mechanism is proven reliable. For
now, `confirm_booking` just logs instead of persisting, and general
questions are answered directly from the LLM's own knowledge instead of a
real knowledge base.
"""

import logging

from livekit import agents

logger = logging.getLogger("voice-agent")


@agents.function_tool
async def escalate(context: agents.RunContext, reason: str) -> str:
    """Escalate the call to a human when the caller explicitly asks for one,
    or when their request can't be handled by this agent."""
    logger.info("escalation requested: %s", reason)
    return (
        "I'm sorry, I'm not able to help with that myself. I've flagged "
        "this call for a team member to follow up with you."
    )


@agents.function_tool
async def end_call(context: agents.RunContext) -> None:
    """MUST be called whenever the call is ending -- e.g. the caller says
    they don't need anything else, says goodbye, or wants to hang up. This
    is the ONLY way to actually end the call. Writing a goodbye as plain
    text does NOT hang up -- confirmed live: the model said 'goodbye
    *ending call*' as text twice without ever invoking this tool, and the
    call never actually ended either time. Always invoke this tool itself;
    never just narrate ending the call. This tool speaks its own goodbye,
    so don't say your own goodbye first -- just call it."""
    logger.info("ending call")
    handle = context.session.generate_reply(
        instructions="Say a brief, warm goodbye to the caller.",
        allow_interruptions=False,
        tool_choice="none",
    )
    await handle.wait_for_playout()
    job_ctx = agents.get_job_context()
    if job_ctx is not None:
        # shutdown() alone only ends *our* job -- the caller's client is
        # left connected to a now-empty room. Confirmed live: after
        # shutdown, the LiveKit playground still accepted mic input, it
        # just went nowhere. delete_room() actually disconnects everyone,
        # which is the difference between a call properly hanging up and
        # the line just going dead while the caller doesn't know it.
        await job_ctx.delete_room()
        job_ctx.shutdown(reason="call ended by agent")


class IntentAgent(agents.Agent):
    def __init__(self, entry_context: str | None = None) -> None:
        super().__init__(
            instructions=(
                "You are a friendly phone assistant for a small business. "
                "Figure out what the caller needs: answering a general "
                "question, or booking/rescheduling an appointment. Keep "
                "responses short and conversational -- this is a live "
                "phone call, not a chat window. If they want to book or "
                "reschedule an appointment, call book_appointment. If you "
                "can't help with something yourself, call escalate. If the "
                "caller says they don't need anything else, call end_call "
                "-- don't say your own goodbye first, the tool handles "
                "that."
            ),
            tools=[escalate, end_call],
        )
        self._entry_context = entry_context

    async def on_enter(self) -> None:
        self.session.generate_reply(
            instructions=self._entry_context
            or "Greet the caller warmly and ask how you can help them today.",
            allow_interruptions=False,
            tool_choice="none",
        )

    @agents.function_tool
    async def book_appointment(self, context: agents.RunContext) -> agents.Agent:
        """Call this as soon as the caller wants to book, schedule, or
        reschedule an appointment."""
        logger.info("handoff: IntentAgent -> BookingAgent")
        return BookingAgent()


class BookingAgent(agents.Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are collecting details for an appointment booking. "
                "Ask one question at a time to get: what service they need, "
                "their preferred date/time, and their name. Once you have "
                "all three, call confirm_booking. If an answer is unclear, "
                "garbled, or cut off, ask the caller to repeat it -- do NOT "
                "call cancel_booking just because something was hard to "
                "understand. Only call cancel_booking if the caller "
                "explicitly says they no longer want to book. Keep "
                "responses short -- this is a live phone call."
            ),
            tools=[escalate, end_call],
        )

    async def on_enter(self) -> None:
        self.session.generate_reply(
            instructions=(
                "Acknowledge that you'll help them book an appointment, "
                "then ask what service they need."
            ),
            allow_interruptions=False,
            tool_choice="none",
        )

    @agents.function_tool
    async def confirm_booking(
        self,
        context: agents.RunContext,
        service: str,
        date_time: str,
        customer_name: str,
    ) -> agents.Agent:
        """Call once you have the service, date/time, and customer name."""
        # NOTE: no persistence yet -- Supabase writes are the next layer.
        logger.info(
            "booking confirmed (not yet persisted): service=%r date_time=%r name=%r",
            service,
            date_time,
            customer_name,
        )
        return IntentAgent(
            entry_context=(
                f"Confirm to the caller that their {service} appointment is "
                f"booked for {date_time} under the name {customer_name}. "
                "Then ask if there's anything else you can help with."
            )
        )

    @agents.function_tool
    async def cancel_booking(self, context: agents.RunContext) -> agents.Agent:
        """Call ONLY if the caller explicitly says they no longer want to
        book an appointment. Do not call this just because an answer was
        unclear -- ask them to repeat it instead."""
        logger.info("handoff: BookingAgent -> IntentAgent (booking cancelled)")
        return IntentAgent(
            entry_context=(
                "Acknowledge that the booking was cancelled, and ask how "
                "else you can help."
            )
        )
