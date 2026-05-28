# Scheduler Architecture

## Overview

The scheduler is the heartbeat of objective03. It manages the timing and coordination of all periodic operations: ingestion, analysis, broadcast generation, memory consolidation, and health checks. It is not a cron replacement — it is an application-level scheduler tuned for the system's specific needs.

## Design

The scheduler operates on a fixed-tick model. Every `tick_interval` (default: 1 second), it checks whether any tasks are due for execution. This avoids the complexity of timer-based scheduling while providing sufficient precision.

```python
class Scheduler:
    def __init__(self, config: SchedulerConfig):
        self.tasks: list[ScheduledTask] = []
        self.running = False
        self.tick_interval = 1.0  # seconds
        self._loop_task: Optional[asyncio.Task] = None
    
    def register(self, task: ScheduledTask):
        self.tasks.append(task)
    
    async def run(self):
        self.running = True
        self._loop_task = asyncio.create_task(self._tick_loop())
    
    async def _tick_loop(self):
        while self.running:
            now = time.monotonic()
            for task in self.tasks:
                if task.is_due(now):
                    asyncio.create_task(self._run_task(task))
            await asyncio.sleep(self.tick_interval)
    
    async def _run_task(self, task: ScheduledTask):
        task.last_run = time.monotonic()
        try:
            await task.coro()
            task.failures = 0
        except Exception as e:
            task.failures += 1
            logger.error("task.failed", task=task.name, error=str(e), failures=task.failures)
            if task.failures >= task.max_failures:
                logger.critical("task.disabled", task=task.name)
                task.disabled = True

    def stop(self):
        self.running = False
        if self._loop_task:
            self._loop_task.cancel()
```

## Scheduled Tasks

| Task | Default Interval | Priority | Max Runtime | Max Failures | Description |
|------|-----------------|----------|-------------|--------------|-------------|
| `ingestion.poll` | 300s (5 min) | High | 120s | ∞ | Poll all sources for new content |
| `analysis.contradictions` | 600s (10 min) | Medium | 60s | 3 | Detect contradictions among new claims |
| `analysis.narrative` | 1800s (30 min) | Medium | 120s | 3 | Run narrative drift analysis |
| `analysis.framing` | 1800s (30 min) | Low | 120s | 3 | Run political framing analysis |
| `broadcast.generate` | 900s (15 min) | High | 180s | 3 | Generate next broadcast segment |
| `audio.pregenerate` | 300s (5 min) | Medium | 120s | 3 | Pre-generate audio for queued scripts |
| `memory.consolidate` | 86400s (24h) | Low | 300s | 2 | Archive/prune old data |
| `health.check` | 60s (1 min) | Critical | 10s | ∞ | Verify component health |
| `database.backup` | 86400s (24h) | Low | 60s | 2 | Create DB backup |

## Task Configuration

```python
@dataclass
class ScheduledTask:
    name: str
    coro: Callable
    interval: float          # seconds between runs
    max_runtime: float       # watchdog timeout
    max_failures: int        # before auto-disable
    run_immediately: bool    # run on startup?
    depends_on: list[str]    # tasks that must have run first
    allowed_states: list[SystemState]  # which states permit this task
```

## Task Dependencies

Some tasks have ordering requirements:

```
ingestion.poll ─────────────────────────────────────────────────┐
    │                                                            │
    ├──▶ analysis.contradictions  (needs new claims in graph)    │
    │       │                                                    │
    │       └──▶ analysis.narrative (needs contradiction data)   │
    │               │                                            │
    │               └──▶ analysis.framing (no dependency)        │
    │                                                            │
    └──────────────────────────────────────────────────▶ broadcast.generate
                                                                    │
                                                                    └──▶ audio.pregenerate
                                                                        │
                                                                        └──▶ (playback)
```

## Scheduling Conflicts

When multiple tasks are due simultaneously, priority order determines execution:

1. `health.check` (always runs first)
2. `ingestion.poll` (fresh data is priority)
3. `broadcast.generate` (keep the broadcast flowing)
4. `analysis.contradictions` (contradictions inform broadcast)
5. `analysis.narrative`
6. `analysis.framing`
7. `audio.pregenerate`
8. `memory.consolidate`
9. `database.backup`

If a high-priority task is still running when the next tick arrives, the scheduler checks whether the running task has exceeded its `max_runtime`. If so, it is cancelled and restarted. Otherwise, the new task waits.

## Ingestion-Specific Scheduling

Each source type has its own scheduling profile:

```yaml
sources:
  rss:
    feeds:
      - url: "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"
        poll_interval: 600       # 10 minutes
        respect_etag: true
        timeout: 30
      - url: "https://feeds.bbci.co.uk/news/world/rss.xml"
        poll_interval: 600
        respect_etag: true
        timeout: 30
  reddit:
    subreddits:
      - name: "worldnews"
        poll_interval: 900       # 15 minutes
        rate_limit_delay: 2.0    # seconds between API calls
        max_posts_per_poll: 25
  youtube:
    channels:
      - id: "UC..."
        poll_interval: 3600      # 1 hour (transcripts are slow)
```

## State Persistence

The scheduler persists its state to SQLite to survive restarts:

```sql
CREATE TABLE scheduler_state (
    task_name TEXT PRIMARY KEY,
    last_run REAL NOT NULL,       -- unix timestamp
    failures INTEGER DEFAULT 0,
    disabled INTEGER DEFAULT 0,
    last_duration REAL,           -- seconds
    last_error TEXT
);
```

## Graceful Degradation of Scheduling

If the scheduler itself encounters errors:

1. **Single task failure** → Log, increment failure count, continue scheduling
2. **Task disabled** → After max_failures, mark disabled, alert via UI
3. **All tasks failing** → This is a fatal error; transition to DEGRADED
4. **Scheduler crash** → Guard process restarts the daemon

## Broadcast Timing

The broadcast scheduler is designed to maintain continuous audio:

```
t=0s     t=15min  t=30min  t=45min  t=60min
│────────│────────│────────│────────│──►
▲        ▲        ▲        ▲        ▲
B1       B2       B3       B4       B5
(15min)  (15min)  (15min)  (15min)  (15min)
```

Broadcast segments are pre-generated. At any time, the audio queue contains at least the next segment. If generation falls behind, the system loops ambient audio or replays a recent segment until generation catches up.
