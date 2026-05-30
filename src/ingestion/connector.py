"""Abstract connector framework for source ingestion."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import time


class RateLimiter:
    def __init__(self, max_calls: int, window_seconds: float):
        self.max_calls = max_calls
        self.window = window_seconds
        self.calls: list[float] = []

    async def acquire(self):
        now = time.monotonic()
        self.calls = [t for t in self.calls if now - t < self.window]
        if len(self.calls) >= self.max_calls:
            sleep_time = self.calls[0] + self.window - now
            if sleep_time > 0:
                import asyncio
                await asyncio.sleep(sleep_time)
        self.calls.append(time.monotonic())


class PollState:
    def __init__(self):
        self.last_poll: dict[str, float] = {}
        self.etags: dict[str, str] = {}
        self.cursors: dict[str, str] = {}

    def get_last_poll(self, name: str) -> Optional[datetime]:
        ts = self.last_poll.get(name)
        return datetime.fromtimestamp(ts) if ts else None

    def update(self, name: str):
        self.last_poll[name] = time.time()

    def get_etag(self, name: str) -> str:
        return self.etags.get(name, "")

    def set_etag(self, name: str, etag: str):
        self.etags[name] = etag


class SourceConnector(ABC):
    """Abstract base for source-specific connectors."""

    def __init__(self, config: dict):
        self.config = config
        self.rate_limiter = RateLimiter(
            config.get("rate_limit", 60), 60
        )

    @abstractmethod
    async def fetch(self) -> list:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    def interval(self) -> int:
        return self.config.get("interval", 600)

    async def poll(self) -> list:
        await self.rate_limiter.acquire()
        return await self.fetch()
