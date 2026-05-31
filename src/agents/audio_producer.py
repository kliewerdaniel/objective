"""Audio producer — converts scripts to speech and streams chunks for playback."""

import re
import asyncio
import structlog
from pathlib import Path
from src.agents.base import BaseAgent, AgentContext, AgentResult
from src.audio.player import AudioChunk, BroadcastEnd
from src.audio.preprocessor import TTSProcessor
from src.models.types import generate_uuid

logger = structlog.get_logger()

MAX_CHUNK_WORDS = 40


def _split_into_chunks(text: str, max_words: int = MAX_CHUNK_WORDS) -> list[str]:
    """Split text into small chunks at paragraph/sentence boundaries."""
    paragraphs = re.split(r'\n\s*\n', text.strip())
    chunks = []
    current = ""
    for para in paragraphs:
        words = current.split()
        para_words = para.split()
        if len(words) + len(para_words) > max_words and current:
            chunks.append(current.strip())
            current = para
        else:
            current = (current + "\n\n" + para).strip() if current else para
    if current.strip():
        chunks.append(current.strip())
    return chunks if chunks else [text]


class AudioProducer(BaseAgent):
    name = "audio_producer"
    timeout_seconds = 900.0

    async def run(self, context: AgentContext) -> AgentResult:
        # Wait briefly for broadcast_writer to populate script
        for _ in range(10):
            script = context.state.get("script")
            if script:
                break
            await asyncio.sleep(2)
        if not script:
            return AgentResult(success=True, data={"note": "No script yet"})

        tts = context.state.get("tts")
        audio_cache = context.state.get("audio_cache")
        streaming_queue = context.state.get("streaming_queue")

        if not tts or not streaming_queue:
            return AgentResult(success=True, data={"note": "Audio components unavailable"})

        processor = TTSProcessor()
        broadcast_id = generate_uuid()
        streaming_queue.register_broadcast(broadcast_id)

        audio_dir = Path(str(context.state.get("audio_dir", "/tmp"))) / "queue"
        audio_dir.mkdir(parents=True, exist_ok=True)

        total_chunks = 0
        for segment in script.segments:
            chunks = _split_into_chunks(segment.text)
            for i, chunk in enumerate(chunks):
                processed = processor.preprocess(chunk)
                cached = audio_cache.get(processed) if audio_cache else None

                if cached:
                    await streaming_queue.enqueue_chunk(AudioChunk(
                        audio_path=cached,
                        broadcast_id=broadcast_id,
                        chunk_index=total_chunks,
                    ))
                    total_chunks += 1
                    continue

                out = str(audio_dir / f"seg_{generate_uuid()[:8]}.wav")
                try:
                    ok = await tts.synthesize(processed, out)
                    if ok:
                        if audio_cache:
                            audio_cache.set(processed, out)
                        await streaming_queue.enqueue_chunk(AudioChunk(
                            audio_path=out,
                            broadcast_id=broadcast_id,
                            chunk_index=total_chunks,
                        ))
                        total_chunks += 1
                        logger.info("audioProducer.chunk.done",
                                    chunk=total_chunks, text=chunk[:60])
                except Exception as e:
                    logger.warning("audioProducer.chunk.failed", error=str(e))
                # Yield to event loop between chunks
                await asyncio.sleep(0)

        if total_chunks == 0:
            return AgentResult(success=False, error="No audio chunks produced")

        # Signal broadcast end
        await streaming_queue.enqueue_end(BroadcastEnd(broadcast_id=broadcast_id))

        duration = script.estimated_duration()
        logger.info("audioProducer.complete",
                     broadcast_id=broadcast_id, chunks=total_chunks, duration=duration)
        return AgentResult(
            success=True,
            data={"broadcast_id": broadcast_id, "chunks": total_chunks, "duration": duration},
            metrics={"chunks": total_chunks, "duration_s": round(duration, 1)},
        )

    def validate(self, result: AgentResult) -> bool:
        return result.success
