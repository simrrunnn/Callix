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

`confirm_booking` now persists to Supabase (via db.create_appointment)
instead of just logging. That needs an actual timestamp, not free text
like "tomorrow at 5 PM" -- so the tool asks the model for ISO 8601
specifically, and BookingAgent's instructions include today's real date
(computed fresh each time the class is instantiated, never hardcoded) so
the model can resolve "tomorrow" correctly instead of guessing -- a live
test showed it once hallucinate an appointment dated 2023 with no date
grounding at all. If the model still sends something unparseable,
confirm_booking raises ToolError so the model sees the failure and can
retry/ask again, instead of silently corrupting or dropping the booking.

`answer_question` grounds Q&A in the real knowledge base (rag.py:
Hugging Face Inference API embeddings + pgvector cosine search in
Supabase) instead of the LLM improvising from its own general knowledge.
Instructions tell the model to answer ONLY from what the tool returns and
say so honestly if the answer isn't in there, rather than guessing --
that's what keeps hallucination rate measurable/low later in evals,
instead of the model quietly making up plausible-sounding business
details.

Two more real issues found live, since the RAG layer:

- `confirm_booking` now checks db.find_active_appointment() first and
  raises ToolError if the name already has one booked, instead of
  silently creating a duplicate -- confirmed live: booking a second
  appointment under a name that already had a 3pm booking created a
  second one with zero warning.
- The spoken confirmation uses a human-friendly date format
  (strftime("%B %d, %Y at %I:%M %p")), not the raw ISO string passed to
  confirm_booking -- confirmed live the model sometimes read the machine
  format back verbatim ("the appointment time in ISO 8601 format is
  2026-08-13T15:00:00"), which is both a bad listening experience and
  wastes TTS characters on a long string nobody wants spoken aloud. This
  fixed the *final* confirmation, but a follow-up live test showed the
  same problem earlier in the conversation too -- BookingAgent's own
  mid-booking dialogue said "tomorrow is 2026-08-13" out loud, because the
  instruction telling it to *think* in ISO format leaked into its natural
  speech. Instructions now explicitly separate the two: always speak
  dates naturally to the caller, only convert to ISO internally when
  actually calling confirm_booking.

A live test of the conflict path itself then surfaced a worse bug:
`cancel_booking` was never meant for resolving a conflict with an
existing appointment (it was built for "caller abandons this booking
attempt entirely") -- confirmed live, when told to replace the
conflicting appointment, the model called cancel_booking anyway, which
does nothing to the database at all. The agent then told the caller
"your booking has been successfully cancelled" -- false; the original
appointment was untouched and no replacement was ever created. Fixed by
giving confirm_booking a real conflict_resolution parameter
("keep_both" / "replace_existing") that actually calls
db.cancel_appointment() on the conflicting row when replacing, plus
instructions and both tools' docstrings now explicitly say cancel_booking
must never be used for this.

Tried caching the default greeting as pre-rendered audio (skip LLM +
Cartesia for the one sentence every call repeats identically) via
session.say(audio=...). Reverted: a live test showed a silent ~3s gap
between AEC warmup finishing and the greeting registering, with zero log
output in between -- no clear latency win, and root-causing it further
would need per-stage instrumentation we don't have yet (the future
latency-waterfall work). Not worth the added complexity until that
exists to actually measure whether it helps.
"""

import logging
from datetime import date, datetime, timezone

from livekit import agents

import db
import rag

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
async def answer_question(context: agents.RunContext, query: str) -> str:
    """Look up information from the knowledge base to answer a caller's
    question about business hours, services, pricing, policies, location,
    or other business details. Always call this for such questions instead
    of answering from general knowledge. Base your spoken answer ONLY on
    what this returns -- if it doesn't contain a relevant answer, say
    honestly that you don't have that information and offer to escalate,
    rather than guessing."""
    chunks = await rag.retrieve_chunks(query, k=3)
    if not chunks:
        return "Nothing relevant found in the knowledge base."
    return "\n\n".join(chunks)


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
                "Figure out what the caller needs: answering a question "
                "about the business, or booking/rescheduling an "
                "appointment. Keep responses short and conversational -- "
                "this is a live phone call, not a chat window. If they "
                "ask about hours, services, pricing, policies, or "
                "location, call answer_question. If they want to book or "
                "reschedule an appointment, call book_appointment. If you "
                "can't help with something yourself, call escalate. If the "
                "caller says they don't need anything else, call end_call "
                "-- don't say your own goodbye first, the tool handles "
                "that."
            ),
            tools=[escalate, end_call, answer_question],
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
        today = date.today().isoformat()
        super().__init__(
            instructions=(
                "You are collecting details for an appointment booking. "
                f"Today's date is {today}. Ask one question at a time to "
                "get: what service they need, their preferred date/time, "
                "and their name. When you speak to the caller, always use "
                "natural, human phrasing for dates and times (e.g. "
                "'tomorrow at 5pm', 'August 13th') -- NEVER say a date in "
                "ISO 8601 or any machine-readable format out loud, that's "
                "only for the confirm_booking tool call itself, internally. "
                "Once you have all three details, call confirm_booking -- "
                "only there, convert whatever date/time they said into ISO "
                "8601 format (YYYY-MM-DDTHH:MM:SS) using today's date as "
                "the reference point; never guess a year. If an answer is "
                "unclear, garbled, or cut off, ask the caller to repeat it "
                "-- do NOT call cancel_booking just because something was "
                "hard to understand. Only call cancel_booking if the "
                "caller explicitly says they no longer want to book "
                "anything at all right now. If confirm_booking reports "
                "that this name already has a conflicting appointment, "
                "that is a DIFFERENT situation -- do not call "
                "cancel_booking for it. Instead ask the caller whether to "
                "keep both or replace the existing one, then call "
                "confirm_booking again with conflict_resolution set "
                "accordingly. If "
                "they ask an unrelated question about the business "
                "mid-booking, call answer_question, then continue "
                "collecting booking details. Keep responses short -- this "
                "is a live phone call."
            ),
            tools=[escalate, end_call, answer_question],
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
        conflict_resolution: str | None = None,
    ) -> agents.Agent:
        """Call once you have the service, date/time, and customer name.
        date_time MUST be ISO 8601 (YYYY-MM-DDTHH:MM:SS) -- convert
        whatever the caller said using today's date, given in your
        instructions, as the reference point.

        If this raises a conflict error (the name already has an active
        appointment), ask the caller whether to keep both or replace the
        existing one, then call this again with the SAME details plus
        conflict_resolution set to exactly "keep_both" or
        "replace_existing" -- do not call cancel_booking for this, it does
        not touch the existing appointment at all and will falsely claim
        success (confirmed live: it said "booking successfully cancelled"
        while leaving the original appointment untouched and never
        creating a replacement). Only omit conflict_resolution on the
        first attempt."""
        try:
            scheduled_for = datetime.fromisoformat(date_time)
            if scheduled_for.tzinfo is None:
                # fromisoformat() on a bare "YYYY-MM-DDTHH:MM:SS" (no
                # offset) returns a naive datetime. Passing that straight
                # to asyncpg for a timestamptz column gets it silently
                # reinterpreted using the SERVER's local system timezone
                # -- confirmed live: "3 PM" got stored as "9:30 UTC" on a
                # machine set to IST (UTC+5:30), a silent 5.5h shift with
                # no error. Pinning it to UTC here makes storage
                # deterministic instead of dependent on whatever machine
                # happens to run this code. This still doesn't know what
                # timezone the caller actually meant by "3 PM" -- that
                # needs a real business-timezone setting, which doesn't
                # exist yet.
                scheduled_for = scheduled_for.replace(tzinfo=timezone.utc)
        except ValueError as exc:
            # Surfaces back to the model as this tool call's result, so it
            # can retry with a corrected value instead of silently
            # dropping or corrupting the booking.
            raise agents.ToolError(
                f"date_time {date_time!r} isn't valid ISO 8601 "
                "(YYYY-MM-DDTHH:MM:SS). Re-derive it from today's date and "
                "call confirm_booking again."
            ) from exc

        existing = await db.find_active_appointment(customer_name)
        if existing is not None and conflict_resolution is None:
            # Confirmed live: booking a second appointment under a name
            # that already had one silently created a duplicate, no
            # warning at all. Raising here instead of creating anything
            # lets the model ask the caller how to proceed rather than
            # deciding for them.
            raise agents.ToolError(
                f"{customer_name} already has a {existing['service']} "
                f"appointment booked for {existing['scheduled_for']:%B %d, %Y at %I:%M %p}. "
                "Tell the caller this, and ask whether they want to keep "
                "both appointments, or if this new one should replace the "
                "existing one. Then call confirm_booking again with the "
                "same details plus conflict_resolution set to "
                "'keep_both' or 'replace_existing'."
            )

        if (
            existing is not None
            and conflict_resolution == "replace_existing"
        ):
            await db.cancel_appointment(existing["id"])
            logger.info("cancelled conflicting appointment %s", existing["id"])

        call_state: db.CallState = context.session.userdata
        call_id = await call_state.get_call_id()
        await db.create_appointment(call_id, customer_name, service, scheduled_for)
        logger.info(
            "booking confirmed and persisted: service=%r scheduled_for=%s name=%r",
            service,
            scheduled_for,
            customer_name,
        )
        # Human-friendly format for the spoken confirmation, not the raw
        # ISO string -- confirmed live the model sometimes read the raw
        # "2026-08-13T15:00:00" back verbatim, which is both a bad
        # listening experience and wastes TTS characters on a long
        # machine-formatted string nobody wants to hear spoken aloud.
        friendly_time = scheduled_for.strftime("%B %d, %Y at %I:%M %p")
        return IntentAgent(
            entry_context=(
                f"Confirm to the caller that their {service} appointment is "
                f"booked for {friendly_time} under the name {customer_name}. "
                "Then ask if there's anything else you can help with."
            )
        )

    @agents.function_tool
    async def cancel_booking(self, context: agents.RunContext) -> agents.Agent:
        """Call ONLY if the caller explicitly says they no longer want to
        book ANY appointment right now -- abandoning this booking attempt
        entirely. Do not call this just because an answer was unclear --
        ask them to repeat it instead. This does NOT cancel or touch any
        existing appointment already in the system -- if confirm_booking
        reported a conflict with an existing appointment, use
        confirm_booking's conflict_resolution parameter instead, not this
        tool."""
        logger.info("handoff: BookingAgent -> IntentAgent (booking cancelled)")
        return IntentAgent(
            entry_context=(
                "Acknowledge that the booking was cancelled, and ask how "
                "else you can help."
            )
        )
