# Audio Pipeline Configuration

## TTS Pipeline

See [pipelines/audio_production.md](../pipelines/audio_production.md) for detailed pipeline flow.

## Broadcast Scheduler

Broadcast generation and playback scheduling:

```python
class BroadcastScheduler:
    """Schedule broadcast generation and playback."""
    
    def __init__(self, audio_queue: AudioQueue, graph: GraphStore):
        self.audio_queue = audio_queue
        self.graph = graph
        self.last_broadcast_at = 0.0
        self.min_interval = 900  # 15 minutes
        
    async def tick(self):
        """Check if a new broadcast should be generated."""
        if time.monotonic() - self.last_broadcast_at >= self.min_interval:
            if self.audio_queue.needs_pregeneration:
                # Generate next broadcast
                await self._trigger_generation()
    
    async def _trigger_generation(self):
        """Trigger broadcast generation."""
        # This is handled by the scheduler daemon
        self.last_broadcast_at = time.monotonic()
```

## Queue System

See [pipelines/audio_production.md](../pipelines/audio_production.md) for queue implementation.

## Atmospheric Transitions

```python
def create_atmospheric_intro(duration: float = 5.0, 
                              config: dict = None) -> np.ndarray:
    """Generate atmospheric intro audio."""
    sample_rate = 22050
    t = np.linspace(0, duration, int(sample_rate * duration))
    
    # Low drone (50Hz + harmonics)
    drone = np.sin(2 * np.pi * 50 * t) * 0.1
    drone += np.sin(2 * np.pi * 100 * t) * 0.05
    drone += np.sin(2 * np.pi * 150 * t) * 0.025
    
    # Subtle noise floor
    noise = np.random.randn(len(t)) * 0.01
    
    # Fade in
    fade = np.minimum(1.0, t / 1.0)
    
    return (drone + noise) * fade
```

## Interrupt Handling

```python
class InterruptHandler:
    """Handle interruptions during audio playback."""
    
    def __init__(self, player: ContinuousPlayer):
        self.player = player
        self.interrupt_queue: list[QueuedBroadcast] = []
    
    def insert_breaking_broadcast(self, broadcast: QueuedBroadcast):
        """Insert a high-priority broadcast (breaking news)."""
        # Mark current as interrupted
        if self.player.current:
            self.interrupt_queue.insert(0, self.player.current)
        
        # Play breaking broadcast next
        self.player.queue.queue.insert(0, broadcast)
```

## Recurring Narrative Callbacks

```python
class RecurringCallback:
    """Manage recurring narrative callbacks in audio."""
    
    def __init__(self, graph: GraphStore):
        self.graph = graph
    
    def get_callbacks(self) -> list[dict]:
        """Get callbacks to previous broadcasts for recurring narratives."""
        return self.graph.execute("""
            MATCH (n:Narrative)
            WHERE n.active = true
              AND n.last_updated > datetime() - duration('P3D')
            OPTIONAL MATCH (b:Broadcast)-[:REFERENCES]->(n)
            WITH n, b
            ORDER BY b.aired_at DESC
            RETURN n.label, n.drift_score, b.aired_at, b.script[:200] AS snippet
        """)
```

## Stitching Pipeline

```python
class AudioStitcher:
    """Stitch audio segments together with transitions."""
    
    def __init__(self, ambient: AmbientManager, sample_rate: int = 22050):
        self.ambient = ambient
        self.sample_rate = sample_rate
    
    def stitch(self, segments: list[tuple[str, float]], 
               output_path: str) -> str:
        """Stitch WAV files with crossfade transitions."""
        
        # Build FFmpeg concat command
        files = [s[0] for s in segments]
        
        # Create temp concat file
        concat_file = output_path + ".concat"
        with open(concat_file, "w") as f:
            for path in files:
                f.write(f"file '{path}'\n")
        
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            output_path,
        ], check=True)
        
        os.unlink(concat_file)
        return output_path
```
