# Autonomous Runtime Lifecycle

## System States

objective03 operates in a finite state machine with the following states:

```
                  ┌──────────────┐
                  │   STARTING   │
                  └──────┬───────┘
                         │
                         ▼
                  ┌──────────────┐
         ┌───────▶│   RUNNING    │◀──────────────────────┐
         │        └──────┬───────┘                       │
         │               │                               │
         │               ├──────────────────────┐        │
         │               ▼                      ▼        │
         │        ┌──────────────┐      ┌──────────────┐ │
         │        │  DEGRADED    │──────▶│ RECOVERING   │ │
         │        └──────┬───────┘      └──────┬───────┘ │
         │               │                     │         │
         │               ▼                     │         │
         │        ┌──────────────┐              │         │
         └────────│ HEALTH_CHECK │◀─────────────┘         │
                  └──────┬───────┘                        │
                         │                                │
                         ▼                                │
                  ┌──────────────┐                         │
                  │  SHUTDOWN    │─────────────────────────┘
                  └──────────────┘
```

### State Descriptions

| State | Description | Actions |
|-------|-------------|---------|
| `STARTING` | Initializing all components | Load config, init DBs, load models, check resources |
| `RUNNING` | Full operation | All components operational, normal cycles |
| `DEGRADED` | Component(s) failed | Disable failed components, continue with available |
| `RECOVERING` | Attempting component restart | Try restart, if success → RUNNING, if fail → DEGRADED |
| `HEALTH_CHECK` | Active component verification | Run diagnostics, report status |
| `SHUTDOWN` | Graceful termination | Flush buffers, close DBs, stop audio, save state |

## Startup Sequence

```
[STARTING]
     │
     ├── 1. Load configuration
     │     └── Parse config.yaml, validate schema, merge env overrides
     │
     ├── 2. Initialize logging
     │     └── Configure structlog, open log files, set log level
     │
     ├── 3. Initialize databases
     │     ├── KuzuDB: Open graph database, run schema migrations
     │     ├── Qdrant: Connect to local instance, verify collection
     │     └── SQLite: Open metadata store, create tables if needed
     │
     ├── 4. Load models
     │     ├── Extraction model: Load Q4 quantized GGUF
     │     ├── Reasoning model: Load Q4 quantized GGUF
     │     ├── Embedding model: Load Q4 quantized GGUF
     │     └── Verify GPU layers, check context size
     │
     ├── 5. Initialize audio subsystem
     │     ├── Load Piper TTS model
     │     ├── Initialize audio device
     │     └── Pre-generate ambient/atmosphere tracks
     │
     ├── 6. Start scheduler
     │     └── Register tasks: ingestion, analysis, broadcast, consolidation
     │
     ├── 7. Start terminal UI
     │     └── Launch Textual app in dedicated thread
     │
     └── 8. Transition to RUNNING or DEGRADED
           ├── All OK → RUNNING
           └── Non-critical failure → DEGRADED
```

## Normal Operation (RUNNING)

In RUNNING state:

1. **Scheduler executes tasks on their configured intervals**
2. **Pipeline cycles run without errors**
3. **Audio plays continuously** (new segments queued before current ends)
4. **UI updates in real-time**
5. **Health checks pass**

## Degraded Operation (DEGRADED)

Degradations are indexed by severity:

| Degradation | Effect | Recovery |
|-------------|--------|----------|
| Single source offline | Continue with other sources | Retry on next poll cycle |
| Extraction model hung | Skip extraction, use cached | Restart model subprocess |
| Reasoning model OOM | Skip analysis/broadcast | Reduce context, retry |
| TTS engine fail | Output scripts to log | Restart TTS process |
| Qdrant unavailable | Skip vector operations | Retry connection |
| KuzuDB corruption | Restore from backup | Manual intervention |
| Disk space low | Skip new ingestion, consolidate | Alert user |

Pseudocode:

```python
class DegradationManager:
    def __init__(self):
        self.degraded: dict[str, Degradation] = {}
        self.severity: dict[str, Severity] = {}
    
    def report_failure(self, component: str, error: Exception):
        self.degraded[component] = Degradation(
            component=component,
            error=str(error),
            timestamp=time.time(),
            retry_count=0,
        )
        self.severity[component] = self._classify(error)
        emit_event("component.degraded", component=component, error=str(error))
    
    def _classify(self, error: Exception) -> Severity:
        if isinstance(error, TemporaryError):
            return Severity.TEMPORARY
        if isinstance(error, ResourceError):
            return Severity.RESOURCE
        if isinstance(error, PermanentError):
            return Severity.PERMANENT
        return Severity.UNKNOWN
    
    def should_skip(self, component: str) -> bool:
        return component in self.degraded
    
    def recovery_check(self, component: str) -> bool:
        deg = self.degraded.get(component)
        if not deg:
            return True
        if deg.retry_count >= config.max_restarts:
            return False
        # Exponential backoff
        if time.time() - deg.timestamp < (config.restart_delay * 2 ** deg.retry_count):
            return False
        return True
```

## Shutdown Sequence

```
[SHUTDOWN]
     │
     ├── 1. Signal scheduler to stop
     │     └── Cancel all pending tasks, wait for running tasks (with timeout)
     │
     ├── 2. Stop audio playback
     │     ├── Fade out current segment
     │     └── Flush audio queue
     │
     ├── 3. Close databases
     │     ├── KuzuDB: Close connection
     │     ├── Qdrant: Close client
     │     └── SQLite: Flush WAL, close connection
     │
     ├── 4. Save state
     │     ├── Ingestion cursors
     │     ├── Scheduler state
     │     └── UI state (if persistent)
     │
     ├── 5. Unload models
     │     └── Release GPU memory, clear model caches
     │
     ├── 6. Stop terminal UI
     │
     └── 7. Exit
```

## Restart Policy

| Failure | Action | Max Retries | Cooldown |
|---------|--------|-------------|----------|
| Model crash | Restart model subprocess | 3 | 30s exponential |
| Source poll failure | Log and skip | ∞ | N/A |
| DB connection failure | Reconnect | 5 | 10s exponential |
| OOM | Reduce model size or context | 2 | 60s |
| Hang (watchdog timeout) | Force restart component | 2 | 30s |

## Watchdog Timer

Every pipeline stage registers a watchdog timer:

```python
class Watchdog:
    def __init__(self, timeout: float):
        self.timeout = timeout
        self.deadline = time.monotonic() + timeout
    
    def pet(self):
        self.deadline = time.monotonic() + self.timeout
    
    def expired(self) -> bool:
        return time.monotonic() > self.deadline

# Usage
async def safe_extraction(doc, model):
    watchdog = Watchdog(timeout=30.0)
    result = None
    
    async def extract():
        nonlocal result
        result = await model.extract_claims(doc)
    
    task = asyncio.create_task(extract())
    while not watchdog.expired():
        await asyncio.sleep(0.1)
        if task.done():
            return result
    
    # Watchdog expired - kill and restart
    task.cancel()
    raise TimeoutError("Claim extraction timed out")
```
