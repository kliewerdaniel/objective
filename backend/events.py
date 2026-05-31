"""SSE event manager for real-time frontend updates."""

import asyncio
import json
from typing import AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Event:
    type: str
    data: dict
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_sse(self) -> str:
        payload = json.dumps({"type": self.type, "data": self.data, "timestamp": self.timestamp})
        return f"data: {payload}\n\n"


class EventManager:
    """Manages SSE connections and broadcasts events to all subscribers."""

    def __init__(self):
        self._subscribers: list[asyncio.Queue[Event]] = []
        self._lock = asyncio.Lock()

    async def subscribe(self) -> AsyncGenerator[Event, None]:
        """Subscribe to the event stream. Yields events as they arrive."""
        queue: asyncio.Queue[Event] = asyncio.Queue()
        async with self._lock:
            self._subscribers.append(queue)
        try:
            while True:
                event = await queue.get()
                yield event
        except asyncio.CancelledError:
            pass
        finally:
            async with self._lock:
                self._subscribers.remove(queue)

    async def publish(self, event: Event):
        """Publish an event to all subscribers."""
        async with self._lock:
            for queue in self._subscribers:
                await queue.put(event)

    async def emit(self, event_type: str, data: dict):
        """Shorthand to publish an event."""
        await self.publish(Event(type=event_type, data=data))


# Global event manager instance
event_manager = EventManager()
