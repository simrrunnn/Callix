"""
Concept: naive (blocking) voice pipeline vs. streaming/pipelined voice pipeline.
Everything here is simulated with asyncio.sleep — no ASR/LLM/TTS API keys needed.
The point is to *see* why TTFA (time to first audio) matters, not total time.
"""

import asyncio
import time

# Fake per-chunk latencies (seconds). Pretend the user said a 4-word sentence,
# so we get 4 transcript chunks, and the LLM replies with 6 tokens/chunks.
ASR_CHUNK_LATENCY = 0.15   # time for ASR to emit each transcript chunk
LLM_CHUNK_LATENCY = 0.25   # time for LLM to emit each response chunk (token/word group)
TTS_CHUNK_LATENCY = 0.20   # time for TTS to synthesize each audio chunk

TRANSCRIPT_CHUNKS = ["how", "do", "I", "reschedule"]
LLM_CHUNKS = ["Sure,", "I can", "help you", "reschedule", "your", "appointment."]


def log(t0, msg):
    print(f"[{time.monotonic() - t0:6.2f}s] {msg}")


# ---------- NAIVE: fully sequential, wait for each stage to completely finish ----------
async def naive_pipeline(t0):
    log(t0, "NAIVE pipeline start")

    # ASR must finish the whole utterance before LLM even starts
    for chunk in TRANSCRIPT_CHUNKS:
        await asyncio.sleep(ASR_CHUNK_LATENCY)
    log(t0, "ASR finished full transcript")

    # LLM must finish the whole response before TTS starts
    for chunk in LLM_CHUNKS:
        await asyncio.sleep(LLM_CHUNK_LATENCY)
    log(t0, "LLM finished full response")

    # TTS must finish the whole audio before playback starts
    for chunk in LLM_CHUNKS:
        await asyncio.sleep(TTS_CHUNK_LATENCY)
    log(t0, "TTS finished full audio -> FIRST AUDIO PLAYS HERE")


# ---------- STREAMING: each stage starts consuming as soon as upstream produces ----------
async def asr_stream(t0, queue):
    for chunk in TRANSCRIPT_CHUNKS:
        await asyncio.sleep(ASR_CHUNK_LATENCY)
        log(t0, f"ASR emits chunk: {chunk!r}")
        await queue.put(chunk)
    await queue.put(None)  # end of stream


async def llm_stream(t0, in_queue, out_queue):
    # naive "endpointing": start generating once we've seen ALL transcript chunks.
    # (real systems often start earlier, on a detected pause / semantic endpoint —
    # that's the next concept.)
    buffer = []
    while True:
        chunk = await in_queue.get()
        if chunk is None:
            break
        buffer.append(chunk)
    log(t0, f"LLM sees full transcript: {' '.join(buffer)!r} -> starts generating")

    for chunk in LLM_CHUNKS:
        await asyncio.sleep(LLM_CHUNK_LATENCY)
        log(t0, f"LLM emits chunk: {chunk!r}")
        await out_queue.put(chunk)
    await out_queue.put(None)


async def tts_stream(t0, in_queue):
    first_audio_logged = False
    while True:
        chunk = await in_queue.get()
        if chunk is None:
            break
        await asyncio.sleep(TTS_CHUNK_LATENCY)
        if not first_audio_logged:
            log(t0, f"TTS produces first audio chunk (for {chunk!r}) -> FIRST AUDIO PLAYS HERE")
            first_audio_logged = True
        else:
            log(t0, f"TTS produces audio chunk for {chunk!r}")


async def streaming_pipeline(t0):
    log(t0, "STREAMING pipeline start")
    transcript_q = asyncio.Queue()
    response_q = asyncio.Queue()
    await asyncio.gather(
        asr_stream(t0, transcript_q),
        llm_stream(t0, transcript_q, response_q),
        tts_stream(t0, response_q),
    )


async def main():
    print("=== NAIVE (fully sequential) ===")
    t0 = time.monotonic()
    await naive_pipeline(t0)

    print("\n=== STREAMING (pipelined) ===")
    t0 = time.monotonic()
    await streaming_pipeline(t0)


if __name__ == "__main__":
    asyncio.run(main())
