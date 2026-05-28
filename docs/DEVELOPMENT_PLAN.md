# Development Plan

## Engineering Priorities

### Tier 1: Foundation (Must Work First)

1. **Ingestion pipeline** — Without sources, the system is empty
2. **Graph schema** — Without storage, nothing persists
3. **Claim extraction** — Without claims, there is nothing to graph

### Tier 2: Core Intelligence

4. **Entity resolution and event clustering** — Making sense of raw claims
5. **Contradiction detection** — The novel capability
6. **Narrative analysis** — Drift and framing

### Tier 3: Production

7. **Broadcast generation** — The visible output
8. **Audio pipeline** — The audible output
9. **Terminal UI** — The observable interface

### Tier 4: Maturity

10. **Continuous daemon runtime** — Autonomous operation
11. **Optimization** — Performance and resource tuning
12. **Research extensions** — Advanced capabilities

## Dependency Graph

```
Phase 1 (Ingestion): No dependencies
    │
    ▼
Phase 2 (Claim Extraction): Depends on Phase 1
    │
    ▼
Phase 3 (Graph Memory): Depends on Phase 2
    │
    ├──────────────┐
    ▼              ▼
Phase 4 (Contra)  Phase 5 (Narrative)
    │              │
    └──────┬───────┘
           ▼
    Phase 6 (Broadcast)
           │
           ▼
    Phase 7 (Temporal)
           │
           ▼
    Phase 8 (Autonomous)
           │
           ├──────────────┐
           ▼              ▼
    Phase 9 (Optimize)  Phase 10 (Research)
```

## Implementation Ordering

### Phase 1: Ingestion (Week 1-2)

| Task | Files | Dependencies |
|------|-------|-------------|
| RSS feed poller | `src/ingestion/rss.py` | None |
| Reddit API poller | `src/ingestion/reddit.py` | PRAW |
| YouTube transcript fetcher | `src/ingestion/youtube.py` | yt-dlp |
| Source configuration | `src/ingestion/config.py` | YAML config |
| Normalization layer | `src/ingestion/normalize.py` | None |
| Deduplication filter | `src/ingestion/dedup.py` | None |
| SQLite cursor store | `src/ingestion/state.py` | SQLite |
| Connector framework | `src/ingestion/connector.py` | ABC |

### Phase 2: Claim Extraction (Week 2-4)

| Task | Files | Dependencies |
|------|-------|-------------|
| LLM client abstraction | `src/models/client.py` | llama-cpp-python |
| Claim extraction prompt | `src/agents/claim_extractor.py` | Phase 1 |
| Entity extraction | `src/agents/entity_extractor.py` | Phase 1 |
| Confidence scoring | `src/agents/scoring.py` | None |
| Stance detection | `src/agents/stance.py` | Phase 1 |

### Phase 3: Graph Memory (Week 3-5)

| Task | Files | Dependencies |
|------|-------|-------------|
| KuzuDB schema initialization | `src/database/graph.py` | None |
| KuzuDB CRUD operations | `src/database/graph_ops.py` | Phase 3 |
| Qdrant client setup | `src/database/vector.py` | Qdrant |
| Embedding generation | `src/database/embeddings.py` | Model |
| SQLite metadata | `src/database/metadata.py` | None |
| Temporal graph updater | `src/agents/graph_updater.py` | Phase 2 + Phase 3 |
| Event clustering | `src/agents/event_clustering.py` | Phase 2 + Phase 3 |

### Phase 4: Contradiction Tracking (Week 5-6)

| Task | Files | Dependencies |
|------|-------|-------------|
| Contradiction detector | `src/agents/contradiction_detector.py` | Phase 2 + Phase 3 |
| Contradiction graph edges | `src/agents/contradiction.py` | Phase 3 |
| Contradiction indexing | `src/database/contradictions.py` | Phase 3 |
| Contradiction metrics | `src/agents/contradiction_metrics.py` | Phase 4 |
| Confidence evolution tracking | `src/agents/confidence.py` | Phase 4 |

### Phase 5: Narrative Analysis (Week 6-8)

| Task | Files | Dependencies |
|------|-------|-------------|
| Narrative analyzer | `src/agents/narrative_analyzer.py` | Phase 3 + Phase 4 |
| Political framing analyzer | `src/agents/framing_analyzer.py` | Phase 3 |
| Linguistic drift measurement | `src/agents/drift.py` | Qdrant |
| Narrative evolution tracking | `src/agents/narrative_evolution.py` | Phase 5 |
| Source reliability evaluator | `src/agents/source_reliability.py` | Phase 3 |

### Phase 6: Broadcast Generation (Week 8-10)

| Task | Files | Dependencies |
|------|-------|-------------|
| Broadcast writer | `src/agents/broadcast_writer.py` | Phase 5 |
| Script structure | `src/agents/script.py` | None |
| Recurring thread system | `src/agents/threads.py` | Phase 3 |
| Uncertainty presentation | `src/agents/uncertainty.py` | Phase 4 + Phase 5 |
| Queue management | `src/agents/queue.py` | None |

### Phase 7: Audio Pipeline (Week 10-12)

| Task | Files | Dependencies |
|------|-------|-------------|
| Piper TTS integration | `src/audio/piper.py` | Piper binary + models |
| FFmpeg audio stitching | `src/audio/stitch.py` | FFmpeg |
| Broadcast scheduler | `src/audio/scheduler.py` | Phase 6 |
| Audio queue | `src/audio/queue.py` | Phase 6 |
| Atmospheric transitions | `src/audio/atmos.py` | FFmpeg |
| Continuous playback | `src/audio/player.py` | SDL/sounddevice |

### Phase 8: Autonomous Runtime (Week 12-14)

| Task | Files | Dependencies |
|------|-------|-------------|
| Daemon orchestrator | `src/daemon/orchestrator.py` | All phases |
| Scheduler daemon | `src/agents/scheduler_daemon.py` | Phase 7 |
| Health monitoring | `src/daemon/health.py` | Phase 8 |
| Graceful degradation | `src/daemon/degradation.py` | Phase 8 |
| Signal handling | `src/daemon/signals.py` | Phase 8 |
| Terminal UI | `src/ui/dashboard.py` | Phase 8 |
| Live metrics | `src/ui/metrics.py` | Phase 8 |

### Phase 9: Optimization (Week 14-16)

| Task | Files | Dependencies |
|------|-------|-------------|
| Model quantization tuning | `src/models/quantization.py` | Phase 2+ |
| Batching strategy optimization | `src/models/batching.py` | Phase 8 |
| Context window management | `src/models/context.py` | Phase 8 |
| Memory consolidation | `src/agents/memory_consolidator.py` | Phase 3 |
| Graph pruning | `src/database/pruning.py` | Phase 3 |
| Caching strategy | `src/database/cache.py` | Phase 8 |

### Phase 10: Research (Week 16+)

See [docs/roadmap/phase_10_research.md](docs/roadmap/phase_10_research.md).

## Engineering Standards

### Code Organization

```
src/
├── __init__.py
├── config.py              # Global configuration
├── main.py                # Entry point / orchestrator
│
├── ingestion/
│   ├── __init__.py
│   ├── connector.py       # Abstract base connector
│   ├── rss.py             # RSS feed poller
│   ├── reddit.py          # Reddit API poller
│   ├── youtube.py         # YouTube transcript fetcher
│   ├── normalize.py       # Document normalization
│   ├── dedup.py           # Deduplication engine
│   ├── config.py          # Source configuration
│   └── state.py           # Ingestion state (SQLite cursors)
│
├── models/
│   ├── __init__.py
│   ├── client.py          # LLM client abstraction
│   ├── batching.py        # Inference batching
│   ├── context.py         # Context window management
│   ├── quantization.py    # Quantization strategy
│   └── registry.py        # Model registry
│
├── database/
│   ├── __init__.py
│   ├── graph.py           # KuzuDB schema + connection
│   ├── graph_ops.py       # KuzuDB CRUD operations
│   ├── vector.py          # Qdrant client
│   ├── embeddings.py      # Embedding generation
│   ├── metadata.py        # SQLite metadata store
│   ├── contradictions.py  # Contradiction indexing
│   ├── cache.py           # Result caching
│   └── pruning.py         # Graph maintenance
│
├── agents/
│   ├── __init__.py
│   ├── base.py            # Base agent class
│   ├── ingestion_coordinator.py
│   ├── claim_extractor.py
│   ├── entity_extractor.py
│   ├── contradiction_detector.py
│   ├── narrative_analyzer.py
│   ├── framing_analyzer.py
│   ├── event_clustering.py
│   ├── source_reliability.py
│   ├── graph_updater.py
│   ├── memory_consolidator.py
│   ├── broadcast_writer.py
│   ├── audio_producer.py
│   ├── scheduler_daemon.py
│   ├── evaluation_engine.py
│   ├── scoring.py
│   ├── stance.py
│   ├── contradiction_metrics.py
│   ├── confidence.py
│   ├── drift.py
│   ├── narrative_evolution.py
│   ├── script.py
│   ├── threads.py
│   ├── uncertainty.py
│   ├── queue.py
│   └── deployment_agent.py
│
├── audio/
│   ├── __init__.py
│   ├── piper.py           # Piper TTS integration
│   ├── stitch.py          # FFmpeg audio stitching
│   ├── scheduler.py       # Broadcast scheduling
│   ├── queue.py           # Audio queue management
│   ├── atmos.py           # Atmospheric transitions
│   ├── player.py          # Audio playback
│   └── cache.py           # Audio cache
│
├── daemon/
│   ├── __init__.py
│   ├── orchestrator.py    # Main orchestrator
│   ├── health.py          # Health monitoring
│   ├── degradation.py     # Degraded mode handling
│   └── signals.py         # Signal handling
│
├── ui/
│   ├── __init__.py
│   ├── dashboard.py       # Main dashboard
│   ├── panels.py          # UI panels
│   ├── metrics.py         # Metrics display
│   ├── feed_view.py       # Ingestion feed view
│   └── graph_view.py      # Graph visualization
│
├── evaluation/
│   ├── __init__.py
│   ├── metrics.py         # Evaluation metrics
│   ├── claim_quality.py   # Claim quality evaluation
│   ├── narrative_coherence.py
│   ├── contradiction_preservation.py
│   └── broadcast_quality.py
│
└── security/
    ├── __init__.py
    ├── sanitize.py        # Input sanitization
    ├── provenance.py      # Provenance verification
    └── audit.py           # Audit logging
```

### Testing Strategy

| Level | Tool | Scope |
|-------|------|-------|
| Unit tests | pytest | Individual agent logic |
| Integration tests | pytest | Pipeline stages |
| Graph tests | pytest + KuzuDB | Schema validation |
| End-to-end tests | pytest | Full pipeline |
| Load tests | Locust (if needed) | Ingestion throughput |

### Code Review Standards

- Every agent must have a corresponding test file
- Every database operation must be tested with a throwaway instance
- Every prompt template must be a constant, not inline string
- Every model call must have timeout + retry
- Every pipeline stage must emit structured log events

### Configuration Management

Configuration is managed through:

1. `config.yaml` — User-editable settings (sources, polling intervals, model paths)
2. `config.schema.yaml` — JSON Schema for validation
3. Environment variables — Oversides for secrets (API tokens) and paths
4. Runtime state — SQLite tables for dynamic state

## Risk Management

| Risk | Impact | Mitigation |
|------|--------|------------|
| llama.cpp crash | Lost inference state | Wrap in subprocess, restart automatically |
| Memory exhaustion | OOM kill | Memory limits, streaming models, aggressive GC |
| Disk full | DB corruption | Disk usage monitoring, automated pruning |
| Malicious feed content | Prompt injection | Sanitization layer, output validation |
| Infinite loop | CPU burnout | Timeout on every pipeline stage, watchdog timer |
| Model degradation | Quality loss | Evaluation hooks, benchmark tracking |
| Source goes offline | Data gap | Configurable retry, grace period, alerting |
