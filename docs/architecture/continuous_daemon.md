# Continuous Daemon Runtime

## Overview

objective03 runs as a continuous daemon process. It is designed for autonomous operation with minimal human intervention. The daemon manages component lifecycle, scheduling, health monitoring, and graceful degradation.

## Daemon Lifecycle

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DAEMON LIFECYCLE                              │
│                                                                      │
│  START ──▶ INIT ──▶ BOOT ──▶ RUN ──▶ SHUTDOWN ──▶ EXIT              │
│   │          │        │        │          │          │               │
│   │          ├─ Config│        ├─ Sched   ├─ Flush   │               │
│   │          ├─ Logs  │        ├─ Process ├─ Save    │               │
│   │          ├─ Model │        ├─ Monitor ├─ Close   │               │
│   │          ├─ DB    │        ├─ React   │          │               │
│   │          └─ Audio │        └─ UI      │          │               │
│   │                   │                   │          │               │
│   └──(failure)────────┴──(degraded)───────┴──────────┘               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Entry Point

```python
# src/main.py
import asyncio
import signal
from daemon.orchestrator import Orchestrator
from config import load_config

async def main():
    config = load_config()
    orchestrator = Orchestrator(config)
    
    # Signal handling
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(orchestrator.shutdown()))
    
    try:
        await orchestrator.bootstrap()
        await orchestrator.run()
    except Exception as e:
        logger.critical("daemon.crash", error=str(e))
        raise
    finally:
        await orchestrator.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
```

## Process Model

The daemon runs as a single process with:

- **Main async loop** — Scheduler, health checks, pipeline coordination
- **Thread pool** — CPU-bound LLM inference (concurrent.futures)
- **Dedicated audio thread** — Continuous playback (must not block)
- **UI thread** — Textual terminal interface (async-compatible)

```
┌──────────────────────────────────────────┐
│              SINGLE PROCESS              │
│                                          │
│  asyncio Event Loop                      │
│  ┌────────────────────────────────────┐  │
│  │ Scheduler Tasks                     │  │
│  │   • ingestion_poll                  │  │
│  │   • analysis_cycle                  │  │
│  │   • broadcast_cycle                 │  │
│  │   • health_check                    │  │
│  │   • consolidation                   │  │
│  └────────────────────────────────────┘  │
│                                          │
│  ThreadPoolExecutor                      │
│  ┌────────────────────────────────────┐  │
│  │ LLM Inference Workers (4 threads)   │  │
│  │   • claim extraction                │  │
│  │   • entity resolution               │  │
│  │   • contradiction detection         │  │
│  │   • narrative analysis              │  │
│  │   • broadcast writing               │  │
│  └────────────────────────────────────┘  │
│                                          │
│  Audio Thread                            │
│  ┌────────────────────────────────────┐  │
│  │ TTS + Playback                     │  │
│  │   • text-to-speech pipeline        │  │
│  │   • audio queue management         │  │
│  │   • sounddevice output             │  │
│  └────────────────────────────────────┘  │
│                                          │
│  UI Thread (Textual)                     │
│  ┌────────────────────────────────────┐  │
│  │ Dashboard Render                   │  │
│  │   • live metrics                   │  │
│  │   • feed logs                      │  │
│  │   • graph state                    │  │
│  │   • broadcast status               │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

## Execution Profile

```python
class DaemonRuntime:
    def __init__(self, config: Config):
        self.config = config
        self.state = DaemonState()
        self.components: dict[str, Component] = {}
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=config.daemon.thread_pool_size or 4
        )
        self.audio_thread = AudioThread(config.audio)
        self.ui_task: Optional[asyncio.Task] = None
    
    async def bootstrap(self):
        """Initialize all components in dependency order."""
        # Phase 1: Core infrastructure
        await self._init_logging()
        await self._init_databases()
        
        # Phase 2: Models
        await self._init_model_registry()
        
        # Phase 3: Application components
        await self._init_ingestion()
        await self._init_agents()
        
        # Phase 4: Output
        await self._init_audio()
        await self._init_ui()
        
        # Phase 5: Scheduler
        await self._init_scheduler()
    
    async def run_forever(self):
        """Main runtime loop."""
        self.state.status = "running"
        
        while self.state.status != "shutdown":
            # Health check
            health = await self._check_health()
            self.state.last_health = health
            
            if not health.all_ok:
                await self._handle_degradation(health.failures)
            
            await asyncio.sleep(self.config.daemon.health_check_interval)
    
    async def shutdown(self):
        """Graceful shutdown sequence."""
        self.state.status = "shutdown"
        
        # Stop accepting new work
        await self._drain_pipelines()
        
        # Stop audio
        self.audio_thread.stop()
        
        # Stop scheduler
        if "scheduler" in self.components:
            await self.components["scheduler"].stop()
        
        # Save state
        await self._save_state()
        
        # Close databases
        await self._close_databases()
        
        # Unload models
        if "model_registry" in self.components:
            await self.components["model_registry"].unload_all()
        
        # Stop UI
        if self.ui_task:
            self.ui_task.cancel()
``` 

## Daemonization

For production operation, the daemon is managed by launchd (macOS):

```xml
<!-- ~/Library/LaunchAgents/com.objective03.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.objective03</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>/Users/username/objective03/src/main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/username/objective03</string>
    <key>StandardOutPath</key>
    <string>/Users/username/.objective03/logs/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/username/.objective03/logs/stderr.log</string>
    <key>KeepAlive</key>
    <true/>
    <key>RunAtLoad</key>
    <true/>
    <key>ThrottleInterval</key>
    <integer>10</integer>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONUNBUFFERED</key>
        <string>1</string>
    </dict>
</dict>
</plist>
```

Load with: `launchctl load ~/Library/LaunchAgents/com.objective03.plist`

## Resource Monitoring

```python
class ResourceMonitor:
    def __init__(self):
        self.process = psutil.Process()
    
    def get_usage(self) -> ResourceUsage:
        return ResourceUsage(
            cpu_percent=self.process.cpu_percent(),
            memory_rss=self.process.memory_info().rss,
            memory_percent=self.process.memory_percent(),
            threads=len(self.process.threads()),
            open_files=len(self.process.open_files()),
            disk_usage=psutil.disk_usage(self.data_dir),
            gpu_usage=self._get_gpu_usage(),  # Via py3nvml or similar
        )
    
    def _get_gpu_usage(self) -> Optional[dict]:
        """Get Apple Silicon GPU usage if available."""
        try:
            result = subprocess.run(
                ["powermetrics", "--samplers", "gpu_power", "-n", "1", "-i", "100"],
                capture_output=True, text=True, timeout=5,
            )
            return parse_powermetrics(result.stdout)
        except Exception:
            return None
```

## Logging

Structured logging via structlog:

```python
import structlog

logger = structlog.get_logger()

# In pipeline stages:
logger.info("pipeline.ingestion.completed",
    documents_processed=len(docs),
    claims_extracted=total_claims,
    duration_ms=elapsed_ms,
    errors=error_count,
)

logger.warning("pipeline.contradiction.detection.slow",
    duration_ms=elapsed_ms,
    threshold_ms=config.max_duration_ms,
)

logger.error("component.failure",
    component="claim_extractor",
    error=str(e),
    traceback=traceback.format_exc(),
)
```
