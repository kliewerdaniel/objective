"""Audio stitching, streaming queue, and playback."""

import asyncio
import os
import subprocess
import time
import soundfile as sf
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class QueuedBroadcast:
    id: str
    audio_path: str
    duration: float
    script_id: str = ""


@dataclass
class AudioChunk:
    """A single audio chunk for streaming playback."""
    audio_path: str
    broadcast_id: str
    chunk_index: int


@dataclass
class BroadcastEnd:
    """Sentinel marking the end of a broadcast's chunks."""
    broadcast_id: str


class AudioStitcher:
    CROSSFADE_MS = 20

    def stitch(self, paths: list[str], output_path: str) -> str:
        if len(paths) == 1:
            import shutil
            shutil.copy2(paths[0], output_path)
            return output_path

        segments = []
        sr = None
        for p in paths:
            data, rate = sf.read(p, dtype='float32')
            if sr is None:
                sr = rate
            if data.ndim > 1:
                data = np.mean(data, axis=1)
            segments.append(data)

        fade_len = int(sr * self.CROSSFADE_MS / 1000)
        result = segments[0]
        for seg in segments[1:]:
            if len(result) >= fade_len and len(seg) >= fade_len:
                fade_out = np.linspace(1, 0, fade_len)
                result[-fade_len:] *= fade_out
                fade_in = np.linspace(0, 1, fade_len)
                seg[:fade_len] *= fade_in
                overlap = result[-fade_len:] + seg[:fade_len]
                result = np.concatenate([result[:-fade_len], overlap, seg[fade_len:]])
            else:
                result = np.concatenate([result, seg])

        # Fade in/out the entire broadcast to prevent click at boundaries
        fade_len = min(fade_len, len(result) // 4)
        result[:fade_len] *= np.linspace(0, 1, fade_len)
        result[-fade_len:] *= np.linspace(1, 0, fade_len)

        sf.write(output_path, result, sr)
        return output_path


class AudioQueue:
    def __init__(self, pregeneration_buffer: int = 2):
        self.queue: list[QueuedBroadcast] = []
        self.buffer = pregeneration_buffer

    def enqueue(self, item: QueuedBroadcast):
        self.queue.append(item)

    def next(self) -> Optional[QueuedBroadcast]:
        return self.queue.pop(0) if self.queue else None

    @property
    def needs_pregeneration(self) -> bool:
        return len(self.queue) < self.buffer

    @property
    def estimated_remaining(self) -> float:
        return sum(b.duration for b in self.queue)


class StreamingAudioQueue:
    """Queue that accepts individual audio chunks for streaming playback.

    Chunks are enqueued as they complete synthesis, allowing the player
    to begin playback immediately without waiting for all chunks.
    Uses a priority queue ordered by (broadcast_order, chunk_index) to
    ensure chunks are played in the correct sequence across broadcasts.
    """

    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._broadcast_counter = 0
        self._active_broadcasts: dict[str, int] = {}

    def register_broadcast(self, broadcast_id: str) -> int:
        """Register a new broadcast and return its priority order."""
        if broadcast_id not in self._active_broadcasts:
            self._active_broadcasts[broadcast_id] = self._broadcast_counter
            self._broadcast_counter += 1
        return self._active_broadcasts[broadcast_id]

    async def enqueue_chunk(self, chunk: AudioChunk):
        """Add a single chunk for immediate playback."""
        await self._queue.put(chunk)

    async def enqueue_end(self, end: BroadcastEnd):
        """Mark that all chunks for a broadcast have been enqueued."""
        await self._queue.put(end)

    async def next_item(self):
        """Get next item (AudioChunk or BroadcastEnd). Blocks with timeout."""
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=1.0)
        except asyncio.TimeoutError:
            return None

    def has_pending(self) -> bool:
        return not self._queue.empty()

    def clear(self):
        """Drop all pending items (e.g. on shutdown)."""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                break


class ContinuousPlayer:
    def __init__(self, queue: AudioQueue, sample_rate: int = 24000):
        self.queue = queue
        self.sample_rate = sample_rate
        self.running = False
        self.current: Optional[QueuedBroadcast] = None

    async def run(self):
        self.running = True
        print("[audioPlayer] Player started — waiting for broadcasts", flush=True)

        while self.running:
            broadcast = self.queue.next()
            if broadcast is None:
                await asyncio.sleep(1)
                continue
            self.current = broadcast
            audio_path = str(Path(broadcast.audio_path).expanduser())
            print(f"[audioPlayer] Playing: {audio_path}", flush=True)
            try:
                proc = await asyncio.create_subprocess_exec(
                    "afplay", audio_path,
                    stdout=subprocess.DEVNULL,
                )
                await proc.wait()
                print(f"[audioPlayer] Done playing", flush=True)
            except Exception as e:
                print(f"[audioPlayer] Error: {e}", flush=True)
            self.current = None

    def stop(self):
        self.running = False


class StreamingPlayer:
    """Plays audio chunks as they arrive via StreamingAudioQueue.

    Instead of waiting for all chunks to be stitched into one file,
    this player picks up chunks as synthesis completes and plays them
    sequentially, giving near-instant time-to-first-audio.
    """

    def __init__(self, queue: StreamingAudioQueue, sample_rate: int = 24000):
        self.queue = queue
        self.sample_rate = sample_rate
        self.running = False
        self.current_broadcast: Optional[str] = None

    async def run(self):
        self.running = True
        print("[streamingPlayer] Player started — waiting for chunks", flush=True)

        while self.running:
            item = await self.queue.next_item()
            if item is None:
                continue

            if isinstance(item, BroadcastEnd):
                print(f"[streamingPlayer] Broadcast {item.broadcast_id} complete", flush=True)
                self.current_broadcast = None
                continue

            if isinstance(item, AudioChunk):
                self.current_broadcast = item.broadcast_id
                audio_path = str(Path(item.audio_path).expanduser())

                # Wait for file to be fully written and flushed to disk
                if not await self._wait_for_file(audio_path):
                    print(f"[streamingPlayer] Chunk {item.chunk_index}: file not ready, skipping", flush=True)
                    continue

                print(f"[streamingPlayer] Playing chunk {item.chunk_index}: {audio_path}", flush=True)
                try:
                    proc = await asyncio.create_subprocess_exec(
                        "afplay", audio_path,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    await proc.wait()
                except Exception as e:
                    print(f"[streamingPlayer] Error playing chunk: {e}", flush=True)

    async def _wait_for_file(self, path: str, timeout: float = 5.0) -> bool:
        """Wait for file to exist and have stable size (fully written)."""
        deadline = time.monotonic() + timeout
        last_size = -1
        while time.monotonic() < deadline:
            try:
                size = os.path.getsize(path)
                if size > 0 and size == last_size:
                    # Size stable — file is fully written
                    return True
                last_size = size
            except OSError:
                pass
            await asyncio.sleep(0.05)
        # Final check
        return os.path.exists(path) and os.path.getsize(path) > 0

    def stop(self):
        self.running = False
        self.queue.clear()
