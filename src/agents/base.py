"""Base agent interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AgentContext:
    trace_id: str = ""
    config: dict = field(default_factory=dict)
    state: dict = field(default_factory=dict)
    models: Any = None
    graph: Any = None
    vector: Any = None
    metadata: Any = None
    logger: Any = None


@dataclass
class AgentResult:
    success: bool = True
    data: Any = None
    error: Optional[str] = None
    metrics: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


class BaseAgent(ABC):
    @abstractmethod
    async def run(self, context: AgentContext) -> AgentResult:
        ...

    @abstractmethod
    def validate(self, result: AgentResult) -> bool:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    def timeout_seconds(self) -> float:
        return 30.0

    @property
    def max_retries(self) -> int:
        return 2
