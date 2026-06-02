"""Qwen3-TTS voice cloning engine using mlx_audio."""

import asyncio
import hashlib
import threading
import numpy as np
from pathlib import Path
from src.config import AudioConfig


class QwenTTS:
    """TTS engine using Qwen3-TTS with voice cloning via reference audio."""

    MODEL_ID = "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-8bit"
    DEFAULT_VOICE = "chris"

    def __init__(self, config: AudioConfig):
        self.config = config
        self._model = None
        self._stt_model = None
        self._ref_text = None
        self._ref_audio_path = None
        self._sample_rate = 24000
        self._lock = threading.Lock()

        # Resolve voice reference audio
        voice_name = getattr(config.tts, "voice", self.DEFAULT_VOICE)
        voices_dir = Path(config.tts.model).parent if config.tts.model else Path("custom_voices")
        from src.config import DATA_DIR
        # Try multiple locations
        for candidate in [
            voices_dir / f"{voice_name}.wav",
            Path("custom_voices") / f"{voice_name}.wav",
            DATA_DIR / "custom_voices" / f"{voice_name}.wav",
            Path(__file__).parent.parent.parent / "custom_voices" / f"{voice_name}.wav",
        ]:
            if candidate.exists():
                self._ref_audio_path = str(candidate)
                break

    def _ensure_loaded(self):
        if self._model is not None:
            return
        from mlx_audio.tts.utils import load_model
        self._model = load_model(self.MODEL_ID)

        # Transcribe reference audio for voice cloning
        if self._ref_audio_path:
            try:
                from mlx_audio.stt import load as load_stt
                stt_model = load_stt("mlx-community/whisper-large-v3-turbo-asr-fp16")
                self._ref_text = stt_model.generate(self._ref_audio_path).text
                print(f"[QwenTTS] Voice reference loaded: {self._ref_audio_path}")
                print(f"[QwenTTS] Reference text: {self._ref_text[:80]}...")
            except Exception as e:
                print(f"[QwenTTS] Warning: could not transcribe reference audio: {e}")

    def synthesize_sync(self, text: str, output_path: str) -> bool:
        """Synchronous TTS generation. Returns True on success."""
        with self._lock:
            self._ensure_loaded()

            import soundfile as sf

            all_audio = []
            speed = getattr(self.config.tts, "speed", 1.0)

            for result in self._model.generate(
                text=text,
                ref_audio=self._ref_audio_path,
                ref_text=self._ref_text,
                speed=speed,
                verbose=False,
                max_tokens=2048,
                temperature=0.5,
            ):
                all_audio.append(np.array(result.audio))
                self._sample_rate = getattr(result, 'sample_rate', self._sample_rate)

            if not all_audio:
                return False

            audio = np.concatenate(all_audio) if len(all_audio) > 1 else all_audio[0]
            # Add small silence padding at start/end to reduce boundary artifacts
            pad_samples = int(self._sample_rate * 0.1)  # 100ms
            silence = np.zeros(pad_samples, dtype=audio.dtype)
            audio = np.concatenate([silence, audio, silence])
            # Normalize and convert to int16 for afplay compatibility
            if audio.dtype != np.int16:
                audio = np.clip(audio, -1.0, 1.0)
                audio = (audio * 32767).astype(np.int16)
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            sf.write(output_path, audio, self._sample_rate, subtype='PCM_16')
            return True

    async def synthesize(self, text: str, output_path: str) -> bool:
        """Async TTS generation. Runs sync code in executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.synthesize_sync, text, output_path)


class AudioCache:
    def __init__(self, cache_dir: Path, max_mb: float = 2000):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_bytes = int(max_mb * 1024 * 1024)
        self._index: dict[str, Path] = {}
        for f in self.cache_dir.glob("*.wav"):
            self._index[f.stem] = f

    def get(self, text: str) -> str:
        key = hashlib.sha256(text.encode()).hexdigest()[:16]
        path = self._index.get(key)
        if path and path.exists():
            return str(path)
        return None

    def set(self, text: str, path: str):
        key = hashlib.sha256(text.encode()).hexdigest()[:16]
        self._index[key] = Path(path)
        self._prune()

    def _prune(self):
        total = sum(f.stat().st_size for f in self.cache_dir.glob("*.wav"))
        if total > self.max_bytes:
            files = sorted(self.cache_dir.glob("*.wav"), key=lambda f: f.stat().st_atime)
            while total > self.max_bytes * 0.8 and files:
                f = files.pop(0)
                total -= f.stat().st_size
                f.unlink()
