# Audio Broadcast Scheduler

The broadcast scheduler manages when audio segments are generated and played. It operates on a configurable cadence (default: 15 min between broadcasts) and maintains a pre-generation buffer of 2 segments to prevent silence.

**Scheduling algorithm**:
1. After a broadcast is queued, schedule next generation at `last_queued + interval`
2. If queue depth drops below `pregeneration_count`, trigger early generation
3. If generation fails, replay the most recent broadcast as fallback

```python
class BroadcastScheduler:
    def __init__(self, interval=900, pregeneration_buffer=2):
        self.interval = interval
        self.buffer = pregeneration_buffer
        
    def should_generate(self, queue_depth, time_since_last):
        return queue_depth < self.buffer or time_since_last >= self.interval
```
