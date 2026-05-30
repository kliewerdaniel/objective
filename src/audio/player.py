"""Audio stitching and playback."""

import asyncio
import subprocess
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
