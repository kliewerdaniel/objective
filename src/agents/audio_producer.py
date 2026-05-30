"""Audio producer — converts scripts to speech and queues audio."""

import re
import structlog
from pathlib import Path
from src.agents.base import BaseAgent, AgentContext, AgentResult
from src.audio.player import QueuedBroadcast
from src.audio.preprocessor import TTSProcessor
from src.models.types import Script, generate_uuid

logger = structlog.get_logger()

MAX_CHUNK_WORDS = 100


def _split_into_chunks(text: str, max_words: int = MAX_CHUNK_WORDS) -> list[str]:
    """Split text into chunks at paragraph/sentence boundaries."""
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
        import asyncio
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
        queue = context.state.get("audio_queue")
        stitcher = context.state.get("audio_stitcher")

        if not tts or not queue:
            return AgentResult(success=True, data={"note": "Audio components unavailable"})

        processor = TTSProcessor()

        async def _synthesize_chunk(chunk: str) -> str | None:
            processed = processor.preprocess(chunk)
            cached = audio_cache.get(processed) if audio_cache else None
            if cached:
                return cached
            out = str(Path(str(context.state.get("audio_dir", "/tmp"))) / "queue" / f"seg_{generate_uuid()[:8]}.wav")
            try:
                ok = await tts.synthesize(processed, out)
                if ok:
                    if audio_cache:
                        audio_cache.set(processed, out)
                    return out
            except Exception as e:
                logger.warning("audioProducer.segment.failed", error=str(e))
            return None

        segment_paths = []
        for segment in script.segments:
            chunks = _split_into_chunks(segment.text)
            tasks = [_synthesize_chunk(chunk) for chunk in chunks]
            results = await asyncio.gather(*tasks)
            segment_paths.extend(r for r in results if r is not None)

        if not segment_paths:
            return AgentResult(success=False, error="No audio segments produced")

        output_path = str(Path(str(context.state.get("audio_dir", "/tmp"))) / "queue" / f"bcast_{generate_uuid()[:8]}.wav")
        if len(segment_paths) == 1:
            import shutil
            shutil.copy2(segment_paths[0], output_path)
        else:
            stitcher.stitch(segment_paths, output_path)

        duration = script.estimated_duration()
        try:
            import soundfile as sf
            data, sr = sf.read(output_path)
            duration = len(data) / sr
        except Exception:
            pass

        queue.enqueue(QueuedBroadcast(
            id=generate_uuid(), audio_path=output_path,
            duration=duration, script_id=script.id,
        ))
        logger.info("audioProducer.complete", segments=len(segment_paths), duration=duration)
        return AgentResult(success=True, data={"segments": len(segment_paths), "duration": duration},
                           metrics={"segments": len(segment_paths), "duration_s": round(duration, 1)})

    def validate(self, result: AgentResult) -> bool:
        return result.success
