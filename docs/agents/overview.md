# Agent System Overview

## Philosophy

objective03 uses a deterministic agent architecture. "Agents" are not autonomous LLM loops making independent decisions. They are well-defined pipeline stages with clear inputs, outputs, success criteria, and failure modes. Each agent is a Python class that implements a standard interface.

This design choice is deliberate:
- **Predictability** — Agents always produce the same output for the same input
- **Testability** — Agents can be unit-tested with mock data
- **Observability** — Every agent call is logged with input/output/error
- **Debuggability** — Pipeline traces let you see exactly what each agent did
- **Replaceability** — Any agent can be replaced with a different implementation

## Agent Interface

```python
class BaseAgent(ABC):
    """Base class for all pipeline agents."""
    
    @abstractmethod
    async def run(self, context: AgentContext) -> AgentResult:
        """Execute the agent's primary function."""
        ...
    
    @abstractmethod
    def validate(self, result: AgentResult) -> bool:
        """Validate that the agent's output meets quality criteria."""
        ...
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable agent name."""
        ...
    
    @property
    def version(self) -> str:
        """Agent version for provenance tracking."""
        return "1.0.0"
    
    @property
    def timeout_seconds(self) -> float:
        """Maximum runtime before watchdog fires."""
        return 30.0
    
    @property
    def max_retries(self) -> int:
        """Number of retries on transient failure."""
        return 2
```

## Agent Context

```python
@dataclass
class AgentContext:
    trace_id: str                    # Pipeline correlation ID
    config: dict                     # Agent-specific configuration
    state: MutableMapping            # Shared state for this pipeline cycle
    models: ModelRegistry            # Access to inference models
    graph: GraphStore                # KuzuDB access
    vector: VectorStore              # Qdrant access
    metadata: SQLiteStore            # Metadata store
    logger: structlog.BoundLogger   # Structured logger
```

## Agent Result

```python
@dataclass
class AgentResult:
    success: bool
    data: Any                        # Agent-specific output
    error: Optional[str] = None
    metrics: Optional[dict] = None   # Performance metrics
    warnings: list[str] = field(default_factory=list)
```

## Agent Lifecycle

```
AGENT LIFECYCLE

[IDLE]
   │
   ├── scheduler triggers
   │
   ▼
[INITIALIZE]
   │  Load config, prepare context
   │
   ▼
[EXECUTE] ──retry──▶ [EXECUTE]
   │                    │
   ├── success          ├── max retries exceeded
   ▼                    ▼
[VALIDATE]           [FAILED]
   │                    │
   ├── valid            ├── log error
   ▼                    ▼
[STORE RESULT]      [DEGRADE]
   │                    │
   ├── log success      ├── disable agent
   ▼                    ▼
[IDLE]              [ALERT]
```

## Agent Registry

```python
class AgentRegistry:
    def __init__(self):
        self.agents: dict[str, BaseAgent] = {}
    
    def register(self, agent: BaseAgent):
        self.agents[agent.name] = agent
    
    def get(self, name: str) -> BaseAgent:
        return self.agents[name]
    
    def list_by_priority(self) -> list[BaseAgent]:
        """Return agents in execution priority order."""
        priority = [
            "ingestion_coordinator",
            "claim_extractor",
            "entity_extractor",
            "source_reliability",
            "event_clustering",
            "graph_updater",
            "contradiction_detector",
            "narrative_analyzer",
            "framing_analyzer",
            "memory_consolidator",
            "broadcast_writer",
            "audio_producer",
            "evaluation_engine",
        ]
        return [self.agents[name] for name in priority if name in self.agents]
```

## Agent Summary Table

| Agent | Phase | Model | Latency | Frequency | Input | Output |
|-------|-------|-------|---------|-----------|-------|--------|
| ingestion_coordinator | Ingestion | None | 5-30s | Every 5-15min | Sources config | Normalized documents |
| claim_extractor | Extraction | Qwen 7B Q4 | 15-60s/doc | Per document | Document | Claim list |
| entity_extractor | Extraction | Qwen 3B Q4 | 5-15s/doc | Per document | Document | Entity list |
| contradiction_detector | Analysis | Llama 3.2 3B | 5-15s/pair | Per new claim | Claims | Contradiction edges |
| narrative_analyzer | Analysis | Llama 3.1 8B | 30-120s | Every 30min | Graph state | Drift report |
| framing_analyzer | Analysis | Qwen 3B Q4 | 10-30s | Every 30min | Claims | Framing labels |
| event_clustering | Graph | Embedding model | 5-30s | Per claim batch | Claims | Event clusters |
| source_reliability | Analysis | None (heuristic) | 1-5s | Per analysis | Trust log | Trust scores |
| graph_updater | Graph | None (logic) | 1-10s | Per claim | Claims, entities | Graph mutations |
| memory_consolidator | Maintenance | Llama 8B | 60-300s | Every 24h | Graph state | Archival actions |
| broadcast_writer | Output | Qwen 14B Q4 | 60-180s | Every 15-30min | Graph state | Broadcast script |
| audio_producer | Output | Piper TTS | 30-120s | Per script | Script | Audio file |
| scheduler_daemon | Runtime | None (timer) | 1s tick | Continuous | Scheduler config | Task triggers |
| evaluation_engine | Quality | Various | 30-120s | Per cycle | Pipeline results | Quality metrics |

## Retry Strategy

| Agent | Max Retries | Backoff | Retry Conditions |
|-------|-------------|---------|------------------|
| ingestion_coordinator | 3 | Exponential 2^n * 5s | Network timeout, rate limit |
| claim_extractor | 2 | Fixed 10s | Model OOM, GPU crash |
| entity_extractor | 2 | Fixed 10s | Model OOM, GPU crash |
| contradiction_detector | 1 | Fixed 5s | Model timeout |
| narrative_analyzer | 2 | Fixed 30s | Model OOM |
| framing_analyzer | 2 | Fixed 10s | Model timeout |
| event_clustering | 3 | Fixed 2s | Vector store unavailable |
| source_reliability | 0 (heuristic) | N/A | N/A |
| graph_updater | 3 | Fixed 1s | KuzuDB contention |
| memory_consolidator | 2 | Fixed 60s | Resource exhaustion |
| broadcast_writer | 2 | Fixed 30s | Model OOM, timeout |
| audio_producer | 2 | Fixed 30s | TTS engine failure |

## Agent Dependencies

```
ingestion_coordinator
    │
    ├── claim_extractor
    │       └── entity_extractor
    │               └── event_clustering
    │                       └── graph_updater
    │                               ├── contradiction_detector
    │                               │       └── narrative_analyzer
    │                               │               └── framing_analyzer
    │                               ├── source_reliability
    │                               └── memory_consolidator (daily)
    │
    └── broadcast_writer
            └── audio_producer
                    └── (audio playback)

scheduler_daemon (controls all)
evaluation_engine (observes all)
```
