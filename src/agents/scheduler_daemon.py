"""Scheduler daemon — manages task timing and execution."""

import time
import asyncio
from dataclasses import dataclass, field
from typing import Callable, Optional
from src.agents.base import BaseAgent, AgentContext, AgentResult


@dataclass
class ScheduledTask:
    name: str
    coro: Callable
    interval: float
    max_runtime: float = 60.0
    max_failures: int = 3
    last_run: float = 0.0
    failures: int = 0
    status: str = "idle"
    run_immediately: bool = True

    def is_due(self, now: float) -> bool:
        if self.status == "disabled":
            return False
        if self.run_immediately:
            self.run_immediately = False
            self.last_run = now
            return True
        if self.last_run <= 0.0:
            self.last_run = now
            return False
        return (now - self.last_run) >= self.interval


class SchedulerDaemon(BaseAgent):
    name = "scheduler_daemon"
    timeout_seconds = 1.0

    def __init__(self):
        self.tasks: list[ScheduledTask] = []

    def register(self, task: ScheduledTask):
        self.tasks.append(task)

    async def run(self, context: AgentContext) -> AgentResult:
        now = time.monotonic()
        triggered = []

        for task in self.tasks:
            if task.is_due(now):
                asyncio.create_task(self._execute(task, context))
                triggered.append(task.name)

        return AgentResult(success=True, data={"tasks_triggered": triggered},
                           metrics={"tasks_triggered": len(triggered)})

    async def _execute(self, task: ScheduledTask, context: AgentContext):
        task.last_run = time.monotonic()
        task.status = "running"
        try:
            result = await asyncio.wait_for(task.coro(context), timeout=task.max_runtime)
            task.status = "completed"
            task.failures = 0
        except asyncio.TimeoutError:
            task.status = "timeout"
            task.failures += 1
        except Exception:
            task.status = "failed"
            task.failures += 1
        if task.failures >= task.max_failures:
            task.status = "disabled"

    def validate(self, result: AgentResult) -> bool:
        return result.success

    def get_state(self) -> dict:
        return {
            "tasks": [
                {"name": t.name, "status": t.status, "interval": t.interval,
                 "failures": t.failures}
                for t in self.tasks
            ]
        }
