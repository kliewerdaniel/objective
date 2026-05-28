# Audio Producer Agent

## Overview

The audio producer converts broadcast scripts into synthesized speech audio. It manages TTS engine, audio queue, and playback coordination.

## Responsibility

- Convert script text to audio via Piper TTS
- Manage audio segment queue
- Apply atmospheric transitions
- Handle playback scheduling
- Cache frequently used phrases

## Interface

```python
class AudioProducer(BaseAgent):
    name = "audio_producer"
    timeout_seconds = 120.0
    
    async def run(self, context: AgentContext) -> AgentResult:
        """Generate audio from a script and queue for playback."""
        script: Script = context.state.get("script")
        
        if not script:
            return AgentResult(success=False, data=None, metrics={},
                             error="No script provided")
        
        # Generate audio segments
        audio_segments = []
        total_duration = 0.0
        
        for segment in script.segments:
            wav_path = await self._synthesize(segment.text, context)
            if wav_path:
                duration = self._get_duration(wav_path)
                audio_segments.append(AudioSegment(
                    id=generate_uuid(),
                    script_segment_type=segment.segment_type,
                    wav_path=wav_path,
                    duration=duration,
                ))
                total_duration += duration
        
        # Stitch with transitions
        final_path = await self._stitch_with_transitions(
            audio_segments, context
        )
        
        # Queue for playback
        context.state["audio_queue"].append(QueuedBroadcast(
            id=script.id,
            audio_path=final_path,
            duration=total_duration,
            generated_at=datetime.utcnow(),
        ))
        
        return AgentResult(
            success=True,
            data={"segments": len(audio_segments), "total_duration": total_duration,
                  "path": final_path},
            metrics={"segment_count": len(audio_segments), "duration_s": total_duration},
        )
    
    async def _synthesize(self, text: str, context: AgentContext) -> Optional[str]:
        """Synthesize text to speech using Piper."""
        # Check cache first
        cache_key = hashlib.sha256(text.encode()).hexdigest()
        cached = context.audio_cache.get(cache_key)
        if cached:
            return cached
        
        # Generate via Piper
        output_path = context.config.audio_dir / f"segment_{cache_key[:12]}.wav"
        
        # Piper is called as a subprocess (Piper has no stable Python API)
        proc = await asyncio.create_subprocess_exec(
            "piper",
            "--model", context.config.tts_model,
            "--output_file", str(output_path),
            "--length_scale", "1.0",  # Normal pace
            "--sentence_silence", "0.5",  # 0.5s between sentences
            input=text.encode(),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        
        _, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            context.logger.error("tts.failed", error=stderr.decode())
            return None
        
        # Cache the result
        context.audio_cache.set(cache_key, str(output_path))
        
        return str(output_path)
    
    async def _stitch_with_transitions(self, segments: list[AudioSegment],
                                        context: AgentContext) -> str:
        """Stitch audio segments with atmospheric transitions."""
        output_path = context.config.audio_dir / f"broadcast_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.wav"
        
        # Build FFmpeg filter complex
        filter_parts = []
        input_parts = []
        
        for i, segment in enumerate(segments):
            input_parts.append(f"-i {segment.wav_path}")
            filter_parts.append(f"[{i}:a]")
        
        # Crossfade between segments
        if len(segments) > 1:
            # FFmpeg crossfade filter
            crossfade_duration = 0.5  # 500ms crossfade
            filter_str = ""
            for i in range(len(segments) - 1):
                if filter_str:
                    # Chain crossfades
                    pass
            
            # Simplified: use concat with short crossfade
            cmd = [
                "ffmpeg",
                "-y",
            ]
            for seg in segments:
                cmd.extend(["-i", seg.wav_path])
            cmd.extend([
                "-filter_complex", f"concat=n={len(segments)}:v=0:a=1",
                "-c:a", "pcm_s16le",
                str(output_path),
            ])
        else:
            cmd = ["cp", segments[0].wav_path, output_path]
        
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        
        return str(output_path)
    
    def validate(self, result: AgentResult) -> bool:
        if not result.success:
            return False
        data = result.data
        return data and data.get("segments", 0) > 0 and data.get("total_duration", 0) > 0
```

## TTS Model Configuration

```yaml
audio:
  tts:
    engine: "piper"
    model: "models/piper/en_US-lessac-medium.onnx"
    voice: "en_US-lessac-medium"
    rate: 1.0
    length_scale: 1.0
    sentence_silence: 0.5
    
  output:
    device: "default"
    sample_rate: 22050
    channels: 1
    
  atmosphere:
    enabled: true
    intro: "audio/ambient/intro.wav"
    outro: "audio/ambient/outro.wav"
    transition_duration: 3.0
    background_gain: -20.0  # dB below speech
```

## TTS Engine Comparison

| Engine | Quality | Latency | RAM | macOS Support | Recommendation |
|--------|---------|---------|-----|---------------|----------------|
| Piper | Good | Low | Low | Native | Primary choice |
| Kokoro | Very Good | Low | Low | via Python | Evaluation candidate |
| Coqui TTS | Excellent | High | High | via Python | Only if quality critical |
| macOS NSSpeech | Moderate | Very Low | None | Native | Fallback only |

## Audio Cache

```python
class AudioCache:
    def __init__(self, cache_dir: Path, max_gb: float = 2.0):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_bytes = int(max_gb * 1024**3)
        self.index: dict[str, Path] = {}
        self._load_index()
    
    def get(self, key: str) -> Optional[str]:
        path = self.index.get(key)
        if path and path.exists():
            return str(path)
        return None
    
    def set(self, key: str, path: str):
        self.index[key] = Path(path)
        self._prune_if_needed()
    
    def _prune_if_needed(self):
        total = sum(f.stat().st_size for f in self.cache_dir.glob("*.wav"))
        if total > self.max_bytes:
            # Remove oldest accessed files
            files = sorted(self.cache_dir.glob("*.wav"), key=lambda f: f.stat().st_atime)
            while total > self.max_bytes * 0.8 and files:
                f = files.pop(0)
                total -= f.stat().st_size
                f.unlink()
```

## Continuous Playback

```python
class AudioPlayer:
    def __init__(self, queue: list, config: AudioConfig):
        self.queue = queue
        self.config = config
        self.current: Optional[QueuedBroadcast] = None
        self.running = False
    
    async def play_loop(self):
        """Continuous playback loop."""
        self.running = True
        
        # Initialize audio device
        import sounddevice as sd
        sd.default.samplerate = self.config.sample_rate
        sd.default.channels = self.config.channels
        
        while self.running:
            if not self.queue:
                # Play ambient during silence
                await self._play_ambient(30.0)
                continue
            
            broadcast = self.queue.pop(0)
            self.current = broadcast
            
            # Load and play audio
            data, samplerate = sf.read(broadcast.audio_path)
            sd.play(data, samplerate)
            sd.wait()
            
            self.current = None
        
        sd.stop()
    
    async def _play_ambient(self, duration: float):
        """Play ambient audio when broadcast queue is empty."""
        if not self.config.atmosphere.enabled:
            await asyncio.sleep(5.0)
            return
        
        ambient_path = self.config.atmosphere.background
        if not os.path.exists(ambient_path):
            await asyncio.sleep(5.0)
            return
        
        # Loop ambient for duration
        data, samplerate = sf.read(ambient_path)
        repeats = int(duration / (len(data) / samplerate)) + 1
        looped = np.tile(data, repeats)[:int(duration * samplerate)]
        
        sd.play(looped, samplerate)
        sd.wait()
```

## Performance

| Metric | Expected | Notes |
|--------|----------|-------|
| TTS latency | 0.5-2x realtime | Piper is fast |
| Audio quality | 7/10 | Piper medium models |
| File size | ~1MB/min | WAV at 22050Hz |
| Cache hit rate | ~40% | Repeated phrases |
| Pre-generation time | 30-90s per broadcast | Before current segment ends |
