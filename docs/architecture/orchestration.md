# Orchestration Strategy

## Philosophy

objective03 uses deterministic orchestration. "Agents" are not autonomous LLM loops making independent decisions. They are well-defined pipeline stages with clear inputs, outputs, and success criteria. Each stage is a pure function (or as close to pure as possible) that transforms data deterministically.

This is not an "AI agent framework." It is a data pipeline where some stages happen to use LLMs for specific sub-tasks.

## Orchestrator Design

The orchestrator is the central coordinator. Its responsibilities:

1. **Component lifecycle** — Start, stop, restart components
2. **Pipeline execution** — Sequence pipeline stages in the correct order
3. **Error handling** — Classify errors, trigger degradation or recovery
4. **State management** — Track system state, expose to UI
5. **Signal handling** — Graceful shutdown on SIGINT/SIGTERM

```python
class Orchestrator:
    def __init__(self, config: Config):
        self.config = config
        self.state = SystemState.STARTING
        self.components: dict[str, Component] = {}
        self.degradation = DegradationManager()
        self.stats = SystemStats()
    
    async def bootstrap(self):
        """Initialize all components in dependency order."""
        self.components["metadata_store"] = SQLiteStore(self.config.databases.metadata)
        self.components["graph_store"] = GraphStore(self.config.databases.graph)
        self.components["vector_store"] = VectorStore(self.config.databases.vector)
        self.components["model_registry"] = ModelRegistry(self.config.models)
        self.components["audio_engine"] = AudioEngine(self.config.audio)
        self.components["scheduler"] = Scheduler(self.config.scheduler)
        self.components["ingestion_coordinator"] = IngestionCoordinator(self.config.sources)
        self.components["claim_extractor"] = ClaimExtractor(self.components["model_registry"])
        self.components["entity_extractor"] = EntityExtractor(self.components["model_registry"])
        self.components["contradiction_detector"] = ContradictionDetector(self.components["model_registry"])
        self.components["narrative_analyzer"] = NarrativeAnalyzer(self.components["model_registry"])
        self.components["broadcast_writer"] = BroadcastWriter(self.components["model_registry"])
        self.components["audio_producer"] = AudioProducer(self.components["audio_engine"])
        self.components["dashboard"] = Dashboard()
        
        # Register background tasks
        self.components["scheduler"].register_many([
            self.components["ingestion_coordinator"],
            self.components["contradiction_detector"],
            self.components["narrative_analyzer"],
            self.components["broadcast_writer"],
            self.components["audio_producer"],
        ])
        
        # Start all components
        for name, component in self.components.items():
            await component.start()
    
    async def run(self):
        """Main orchestrator loop."""
        await self.bootstrap()
        self.state = SystemState.RUNNING
        
        while self.state != SystemState.SHUTDOWN:
            # Check health of all components
            for name, component in self.components.items():
                if component.health() != Health.OK:
                    self.degradation.report_failure(name, component.last_error())
                    self.state = SystemState.DEGRADED
            
            # Attempt recovery for degraded components
            if self.state == SystemState.DEGRADED:
                for name in list(self.degradation.degraded.keys()):
                    if self.degradation.recovery_check(name):
                        await self._recover_component(name)
                
                if not self.degradation.degraded:
                    self.state = SystemState.RUNNING
            
            await asyncio.sleep(self.config.daemon.health_check_interval)
    
    async def _recover_component(self, name: str):
        """Attempt to restart a component."""
        component = self.components[name]
        try:
            await component.restart()
            self.degradation.clear(name)
            emit_event("component.recovered", component=name)
        except Exception as e:
            self.degradation.record_retry(name)
            emit_event("component.recovery.failed", component=name, error=str(e))
    
    async def shutdown(self):
        """Graceful shutdown."""
        self.state = SystemState.SHUTDOWN
        # Reverse bootstrap order
        for name in reversed(list(self.components.keys())):
            await self.components[name].stop()
    
    def handle_signal(self, sig):
        """Signal handler."""
        if sig in (signal.SIGINT, signal.SIGTERM):
            asyncio.create_task(self.shutdown())
```

## Component Interface

Every component implements a standard interface:

```python
class Component(ABC):
    @abstractmethod
    async def start(self): ...
    
    @abstractmethod
    async def stop(self): ...
    
    @abstractmethod
    async def restart(self): ...
    
    @abstractmethod
    def health(self) -> Health: ...
    
    @abstractmethod
    def last_error(self) -> Optional[str]: ...
    
    @property
    def name(self) -> str: ...
```

## Pipeline Orchestration

Pipeline stages are orchestrated as follows:

```python
async def ingestion_cycle(self):
    """Full ingestion + extraction pipeline cycle."""
    coordinator = self.components["ingestion_coordinator"]
    extractor = self.components["claim_extractor"]
    entity_extractor = self.components["entity_extractor"]
    
    documents = await coordinator.poll_all()
    
    for doc in documents:
        try:
            claims = await extractor.extract(doc)
            entities = await entity_extractor.extract(doc)
            
            await self.components["graph_store"].insert_document(doc)
            for claim in claims:
                await self.components["graph_store"].insert_claim(claim)
            for entity in entities:
                await self.components["graph_store"].insert_entity(entity)
            
            self.stats.records_ingested += 1
            self.stats.claims_extracted += len(claims)
        except Exception as e:
            self.stats.errors.append({"doc": doc.id, "error": str(e)})
```

## Agent Coordination

Agents communicate through the shared graph database rather than direct method calls:

```
                    ┌────────────────────────────┐
                    │       KUZUDB GRAPH          │
                    │                            │
                    │  events ─── claims         │
                    │     │          │            │
                    │     ▼          ▼            │
                    │  entities   contradictions  │
                    │     │          │            │
                    │     ▼          ▼            │
                    │  narratives   broadcasts    │
                    └────────────────────────────┘
                           ▲            ▲
                           │            │
               ┌───────────┴────────────┴───────────┐
               │         AGENT LAYER                 │
               │                                     │
               │  Extractor ──▶ Graph Updater        │
               │  Detector  ──▶ Graph Updater        │
               │  Analyzer  ──▶ Graph Updater        │
               │  Writer    ◀── Graph Reader         │
               └─────────────────────────────────────┘
```

This design:
- Decouples agents from each other
- Enables independent scheduling
- Makes the data flow explicit
- Allows agents to be tested in isolation
- Makes the system observable (read the graph to understand state)

## Why Not a Message Bus?

A message bus (RabbitMQ, Kafka, Redis pub/sub) would add:
- A running server process
- Serialization/deserialization overhead
- Network latency (even on localhost)
- Operational complexity
- Failure modes (message loss, broker crash)

For a single-machine system, the overhead of a message bus exceeds its benefit. Agents communicate through the shared graph and the shared state. If the system needs to be distributed in the future, a message bus can be introduced at that point.

## Why Not an Event Sourcing Framework?

Event sourcing would be architecturally correct — the system is fundamentally event-driven. However, frameworks for event sourcing add significant complexity. The system uses a simpler approach:

1. Every mutation to the graph is logged to the audit table (SQLite)
2. The graph itself is a materialized view of the current state
3. If replay is needed, the audit log enables reconstruction

This provides the benefits of event sourcing (audit trail, replay) without the framework overhead.
