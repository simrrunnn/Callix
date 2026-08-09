"""
Day-1 spike: prove that a bare LiveKit agent, running in this container,
can join a LiveKit Cloud room and pass audio in both directions.

Deliberately has zero dependency on ASR/LLM/TTS providers so it isolates
exactly one question: does the network path (this container -> LiveKit
Cloud) actually carry live audio? Everything else gets layered on only
after this is confirmed working from the real deployment target (a
Hugging Face Space), not just from a local machine.

What it does:
  - Joins whatever room it's dispatched to.
  - Publishes a continuous 440Hz test tone as its own audio track, so a
    human joining the room with a mic/speakers can confirm they hear it.
  - Subscribes to any other participant's audio track and logs a message
    every ~1s of received audio, so we can confirm inbound audio (e.g. a
    caller's voice) is actually arriving.
"""

import asyncio
import logging
import math

import numpy as np
from dotenv import load_dotenv
from livekit import agents, rtc

# WorkerOptions reads LIVEKIT_URL/LIVEKIT_API_KEY/LIVEKIT_API_SECRET straight
# from the process environment, not from .env -- this is what actually
# populates them from the .env file before WorkerOptions is constructed.
load_dotenv()

logger = logging.getLogger("connectivity-spike")

SAMPLE_RATE = 48_000
NUM_CHANNELS = 1
FRAME_MS = 10
SAMPLES_PER_FRAME = SAMPLE_RATE * FRAME_MS // 1000
TONE_HZ = 440.0
TONE_AMPLITUDE = 3000  # int16 headroom, ~10% of full scale


async def _play_test_tone(source: rtc.AudioSource) -> None:
    phase = 0
    while True:
        frame = rtc.AudioFrame.create(SAMPLE_RATE, NUM_CHANNELS, SAMPLES_PER_FRAME)
        samples = np.frombuffer(frame.data, dtype=np.int16)
        for i in range(SAMPLES_PER_FRAME):
            samples[i] = int(TONE_AMPLITUDE * math.sin(2 * math.pi * TONE_HZ * phase / SAMPLE_RATE))
            phase += 1
        await source.capture_frame(frame)
        await asyncio.sleep(FRAME_MS / 1000)


async def _log_incoming_audio(track: rtc.Track, participant_identity: str) -> None:
    stream = rtc.AudioStream(track, sample_rate=SAMPLE_RATE, num_channels=NUM_CHANNELS)
    frame_count = 0
    frames_per_log = 1000 // FRAME_MS  # roughly once per second
    async for event in stream:
        frame_count += 1
        if frame_count % frames_per_log == 0:
            logger.info(
                "received ~%ss of audio from %s (%d frames total)",
                frame_count // frames_per_log,
                participant_identity,
                frame_count,
            )


async def entrypoint(ctx: agents.JobContext) -> None:
    await ctx.connect()
    logger.info("connected to room %s", ctx.room.name)

    source = rtc.AudioSource(SAMPLE_RATE, NUM_CHANNELS)
    track = rtc.LocalAudioTrack.create_audio_track("spike-tone", source)
    publish_options = rtc.TrackPublishOptions()
    publish_options.source = rtc.TrackSource.SOURCE_MICROPHONE
    await ctx.room.local_participant.publish_track(track, publish_options)
    logger.info("publishing test tone (%.0fHz)", TONE_HZ)

    asyncio.create_task(_play_test_tone(source))

    @ctx.room.on("track_subscribed")
    def on_track_subscribed(
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info("subscribed to audio track from %s", participant.identity)
            asyncio.create_task(_log_incoming_audio(track, participant.identity))

    logger.info("spike agent ready, waiting for a participant to join and speak")


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    # host/port here matter for deployment: the worker exposes its own
    # GET / health check ("OK" once connected to LiveKit, 503 otherwise)
    # on this address, which is what satisfies Hugging Face Spaces'
    # requirement that the container answer on its exposed port -- no
    # separate web server needed.
    agents.cli.run_app(
        agents.WorkerOptions(entrypoint_fnc=entrypoint, host="0.0.0.0", port=7860)
    )


if __name__ == "__main__":
    run()
