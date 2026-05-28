# Scheduler Daemon Agent

## Overview

The scheduler daemon manages the timing and coordination of all periodic operations. It is the heartbeat of the autonomous runtime.

## Responsibility

- Schedule pipeline cycles on configured intervals
- Manage task concurrency and prioritization
- Track task execution and failures
- Handle graceful degradation of scheduling
- Expose scheduler state for UI

## Interface

```python
class SchedulerDaemon(BaseAgent):
    name = "scheduler_daemon"
    timeout_seconds = 1.0  # Tick interval
    
    async def run(self, context: AgentContext) -> AgentResult:
        """Execute one scheduler tick."""
        now = time.monotonic()
        triggered = []
        
        for task in context.state["tasks"]:
            if task.is_due(now):
                asyncio.create_task(self._execute_task(task, context))
                triggered.append(task.name)
        
        return AgentResult(
            success=True,
            data={"tasks_triggered": triggered},
            metrics={"tasks_triggered": len(triggered)},
        )
    
    async def _execute_task(self, task: ScheduledTask, context: AgentContext):
        """Execute a scheduled task with monitoring."""
        task.last_run = time.monotonic()
        task.status = "running"
        
        try:
            result = await asyncio.wait_for(
                task.coro(), timeout=task.max_runtime
            )
            task.status = "completed"
            task.failures = 0
            task.last_duration = time.monotonic() - task.last_run
        except asyncio.TimeoutError:
            task.status = "timeout"
            task.failures += 1
            context.logger.warning("task.timeout", task=task.name, 
                                 max_runtime=task.max_runtime)
        except Exception as e:
            task.status = "failed"
            task.failures += 1
            context.logger.error("task.failed", task=task.name, error=str(e))
        
        if task.failures >= task.max_failures:
            task.status = "disabled"
            context.logger.critical("task.disabled", task=task.name)
```

## Task Scheduler

```python
class ScheduledTask:
    def __init__(self, name: str, coro: Callable, interval: float, 
                 max_runtime: float = 60.0, max_failures: int = 3):
        self.name = name
        self.coro = coro
        self.interval = interval
        self.max_runtime = max_runtime
        self.max_failures = max_failures
        self.last_run = 0.0
        self.failures = 0
        self.status = "idle"
        self.last_duration = 0.0
        self.run_immediately = True
    
    def is_due(self, now: float) -> bool:
        if self.status == "disabled":
            return False
        if self.run_immediately:
            self.run_immediately = False
            return True
        return (now - self.last_run) >= self.interval
```

## Task Registration

```python
def register_default_tasks(scheduler: SchedulerDaemon, agents: dict):
    """Register all default scheduled tasks."""
    tasks = [
        ScheduledTask("ingestion", agents["ingestion_coordinator"].run,
                     interval=300, max_runtime=120, max_failures=999),
        ScheduledTask("contradiction", agents["contradiction_detector"].run,
                     interval=600, max_runtime=60, max_failures=3),
        ScheduledTask("narrative", agents["narrative_analyzer"].run,
                     interval=1800, max_runtime=120, max_failures=3),
        ScheduledTask("framing", agents["framing_analyzer"].run,
                     interval=1800, max_runtime=60, max_failures=3),
        ScheduledTask("broadcast", agents["broadcast_writer"].run,
                     interval=900, max_runtime=180, max_failures=3),
        ScheduledTask("audio", agents["audio_producer"].run,
                     interval=900, max_runtime=120, max_failures=3),
        ScheduledTask("consolidation", agents["memory_consolidator"].run,
                     interval=86400, max_runtime=300, max_failures=2),
        ScheduledTask("health", agents.get("evaluation_engine", lambda: None).run,
                     interval=60, max_runtime=30, max_failures=999),
    ]
    
    scheduler.state["tasks"] = tasks
```

## Scheduler State

The scheduler exposes its state for the terminal UI:

```python
def get_scheduler_state(scheduler: SchedulerDaemon) -> dict:
    """Get current scheduler state for UI display."""
    return {
        "tasks": [
            {
                "name": t.name,
                "status": t.status,
                "last_run": t.last_run,
                "last_duration": t.last_duration,
                "failures": t.failures,
                "interval": t.interval,
            }
            for t in scheduler.state["tasks"]
        ],
        "next_events": [
            {
                "task": t.name,
                "next_run": t.last_run + t.interval,
                "due_in_s": max(0, t.last_run + t.interval - time.monotonic()),
            }
            for t in scheduler.state["tasks"]
            if t.status != "disabled"
        ],
    }
```
