# Audio Production Pipeline

## Pipeline Flow

```
Script (parsed segments)
    │
    ▼
Segment Text Extraction
    │
    ▼
Pre-processing for TTS
    │
    ├── Abbreviation expansion
    ├── Number normalization
    ├── SSML annotation (prosody, pauses)
    └── Phrase chunking for natural breaks
    │
    ▼
TTS Synthesis (Piper)
    │
    ├── Check audio cache
    ├── Piper subprocess call
    └── WAV output
    │
    ▼
Audio Stitching (FFmpeg)
    │
    ├── Crossfade between segments
    ├── Add atmospheric intro/outro
    ├── Apply background ambience
    └── Normalize volume
    │
    ▼
Completed Broadcast WAV
    │
    ▼
Audio Queue
    │
    ▼
Playback (sounddevice)
```

## TTS Pre-Processing

```python
class TTSProcessor:
    def __init__(self):
        self.abbreviation_map = {
            "e.g.": "for example",
            "i.e.": "that is",
            "vs.": "versus",
            "approx.": "approximately",
            "dept.": "department",
            "govt.": "government",
            "est.": "estimated",
            "cont.": "continued",
        }
    
    def preprocess(self, text: str) -> str:
        """Prepare text for TTS synthesis."""
        # Expand abbreviations
        for abbr, expansion in self.abbreviation_map.items():
            text = re.sub(r'\b' + re.escape(abbr) + r'\b', expansion, text)
        
        # Normalize numbers
        text = re.sub(r'(\d+)(?:st|nd|rd|th)\b', r'\1', text)  # Remove ordinals
        
        # Normalize percentages
        text = re.sub(r'(\d+)%', r'\1 percent', text)
        
        # Add SSML prosody markers for longer pauses between segments
        text = text.replace("...", '<break time="1.5s"/>')
        text = text.replace(". ", '.<break time="0.3s"/> ')
        
        return text
```

## Piper Integration

```python
class PiperTTS:
    def __init__(self, model_path: str, config: dict):
        self.model_path = model_path
        self.config = config
        self._ensure_model_exists()
    
    async def synthesize(self, text: str, output_path: str) -> bool:
        """Synthesize text to WAV file."""
        processor = TTSProcessor()
        processed_text = processor.preprocess(text)
        
        proc = await asyncio.create_subprocess_exec(
            "piper",
            "--model", self.model_path,
            "--output_file", output_path,
            "--length_scale", str(self.config.get("length_scale", 1.0)),
            "--sentence_silence", str(self.config.get("sentence_silence", 0.5)),
            input=processed_text.encode(),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        
        _, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            logger.error("piper.error", error=stderr.decode())
            return False
        
        return True
```

## Ambient Audio

```python
class AmbientManager:
    def __init__(self, config: dict):
        self.intro = config.get("intro")
        self.outro = config.get("outro")
        self.background = config.get("background")
        self.transition_duration = config.get("transition_duration", 3.0)
    
    def generate_transition(self, duration: float) -> np.ndarray:
        """Generate a transition (fade) effect."""
        if not self.background:
            return np.zeros(int(22050 * duration))
        
        bg, sr = sf.read(self.background)
        fade_in = np.linspace(0, 1, int(sr * duration))
        return bg[:int(sr * duration)] * fade_in
```

## Audio Queue

```python
class AudioQueue:
    def __init__(self, pregeneration_count: int = 2):
        self.queue: list[QueuedBroadcast] = []
        self.pregeneration_count = pregeneration_count
    
    def enqueue(self, broadcast: QueuedBroadcast):
        self.queue.append(broadcast)
    
    def next(self) -> Optional[QueuedBroadcast]:
        if self.queue:
            return self.queue.pop(0)
        return None
    
    @property
    def needs_pregeneration(self) -> bool:
        return len(self.queue) < self.pregeneration_count
    
    @property
    def estimated_remaining(self) -> float:
        return sum(b.duration for b in self.queue)
```

## Continuous Playback

```python
class ContinuousPlayer:
    def __init__(self, queue: AudioQueue, ambient: AmbientManager):
        self.queue = queue
        self.ambient = ambient
        self.running = False
    
    async def run(self):
        """Continuous playback loop."""
        self.running = True
        import sounddevice as sd
        sd.default.samplerate = 22050
        sd.default.channels = 1
        
        while self.running:
            broadcast = self.queue.next()
            
            if broadcast is None:
                # Play ambient while waiting
                ambient_data = self.ambient.generate_transition(10.0)
                sd.play(ambient_data, 22050)
                sd.wait()
                continue
            
            data, sr = sf.read(broadcast.audio_path)
            sd.play(data, sr)
            sd.wait()
    
    def stop(self):
        self.running = False
        import sounddevice as sd
        sd.stop()
```

## Performance

| Metric | Expected | Notes |
|--------|----------|-------|
| TTS speed | ~2x realtime | Piper medium model |
| Audio quality | 7/10 | Comparable to good TTS |
| File size | ~1MB/min WAV | 22050 Hz, 16-bit mono |
| Cache hit rate | ~40% | Repeated phrases |
| Pre-generation window | 30-90s | Before current segment ends |
| Stitching overhead | 1-2s per broadcast | FFmpeg concat |
