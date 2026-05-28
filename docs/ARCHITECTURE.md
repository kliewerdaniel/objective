# Architecture Overview

## High-Level System Architecture

objective03 is organized into seven primary subsystems, each with distinct responsibilities, resource profiles, and failure modes.

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DAEMON ORCHESTRATOR                          │
│  (process supervisor, scheduler, health monitoring, lifecycle mgmt)  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────┬───────────────┼───────────────┬───────────┐
        ▼           ▼               ▼               ▼           ▼
┌──────────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐ ┌──────────┐
│  INGESTION   │ │ CLAIM    │ │ GRAPH    │ │ BROADCAST  │ │ AUDIO    │
│  PIPELINE    │ │ ENGINE   │ │ MEMORY   │ │ SYNTHESIS  │ │ ENGINE   │
│              │ │          │ │          │ │            │ │          │
│ RSS, Reddit, │ │ Extract  │ │ KuzuDB   │ │ Script     │ │ TTS      │
│ YouTube, gov │ │ Entities │ │ Qdrant   │ │ generation │ │ FFmpeg   │
│ feeds        │ │ Claims   │ │ SQLite   │ │            │ │ Queue    │
└──────────────┘ └──────────┘ └──────────┘ └────────────┘ └──────────┘
        │               │               │               │           │
        └───────────────┴───────────────┴───────────────┴───────────┘
                                    │
                    ┌───────────────┘
                    ▼
          ┌──────────────────┐
          │  TERMINAL UI     │
          │  (Textual/Rich)  │
          │  Live dashboard  │
          └──────────────────┘
```

## Event Flow Architecture

```
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ SOURCE   │──▶│ NORMALIZE│──▶│ DEDUP    │──▶│ EXTRACT  │──▶│ RESOLVE  │
│ Poller   │   │ Adapter  │   │ Filter   │   │ Pipeline │   │ Entities │
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
                                                                    │
                                                                    ▼
┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
│ BROADCAST│◀──│ NARRATIVE│◀──│ CLUSTER  │◀──│ LINK     │◀──│ STORE    │
│ Render   │   │ Analyze  │   │ Events   │   │ Claims   │   │ Graph    │
└──────────┘   └──────────┘   └──────────┘   └──────────┘   └──────────┘
     │
     ▼
┌──────────┐   ┌──────────┐   ┌──────────┐
│ WRITE    │──▶│ QUEUE    │──▶│ PLAY     │
│ Script   │   │ Manager  │   │ (Piper)  │
└──────────┘   └──────────┘   └──────────┘
```

## Storage Architecture

Three storage systems, each serving a distinct purpose:

### KuzuDB (Primary — Graph)

- Embedded columnar graph database
- Stores the temporal property graph of events, claims, entities, sources, contradictions, narratives
- Supports Cypher queries for graph traversal
- All relationship types are timestamped
- No separate server process needed

### Qdrant (Secondary — Vector)

- Local vector search service
- Stores embeddings for claims, entities, and broadcast segments
- Enables semantic retrieval for "similar to previous event," "what did we say about X," and narrative drift detection
- Runs as a local HTTP service

### SQLite (Tertiary — Metadata)

- Lightweight relational store
- Pipeline state, ingestion cursors, scheduling metadata, model cache indices, error logs
- Single-file, zero-configuration

## Data Flow Summary

```
Ingestion ──▶ Normalization ──▶ Claim Extraction ──▶ Entity Resolution
                                                           │
                                                           ▼
Entity Linking ──▶ Event Clustering ──▶ Graph Insertion ──▶ Vector Embedding
                                                           │
                                                           ▼
Contradiction Detection ──▶ Narrative Analysis ──▶ Political Framing
                                                           │
                                                           ▼
Broadcast Script Synthesis ──▶ TTS Rendering ──▶ Audio Queue ──▶ Output
```

## Component Communication

All inter-component communication occurs through:

1. **Python function calls** (within-process synchronous operations)
2. **SQLite state tables** (cross-process coordination for future multi-process scaling)
3. **KuzuDB graph updates** (primary data exchange mechanism)
4. **Qdrant vector operations** (semantic similarity queries)
5. **File system** (audio files, cached model outputs, temporary artifacts)

There is NO message broker, NO REST API between components, NO event bus in the initial architecture. Complexity will be added only when justified by measurable bottlenecks.

## Resource Allocation Strategy

| Component | CPU | RAM | GPU | Priority |
|-----------|-----|-----|-----|----------|
| Ingestion polling | Low | Low | None | Background |
| Claim extraction | Medium | Medium | Metal | High |
| Entity resolution | Medium | Medium | Metal | High |
| Embedding generation | Low | Medium | Metal | Medium |
| Contradiction detection | Low | Low | None | Background |
| Narrative analysis | High | High | Metal | Scheduled |
| Broadcast writing | High | High | Metal | Scheduled |
| TTS generation | Medium | Medium | None | Scheduled |
| Terminal UI | Low | Low | None | Continuous |

The system schedules GPU-intensive operations to avoid contention. Extraction pipelines have priority. Narrative analysis and broadcast writing are scheduled during idle periods.

## Design Decisions

### Why Python?

- Mature ecosystem for LLM interaction (llama-cpp-python, transformers)
- Excellent graph database bindings (KuzuDB Python API)
- Rich terminal UI frameworks (Textual)
- Extensive audio processing libraries (FFmpeg bindings)
- Rapid prototyping for complex pipeline logic

### Why not distributed?

The system runs on a single machine. Adding distributed infrastructure (message brokers, container orchestration, distributed databases) would increase complexity without benefit until the system exceeds a single node's capacity.

### Why not web-first?

The terminal interface aligns with the dystopian/detached aesthetic. Textual provides a rich UI without web browser overhead. Web interfaces can be added later as an optional layer.

### Why KuzuDB over Neo4j?

KuzuDB is embedded (no server), columnar (fast analytic queries), and supports temporal relationships natively. Neo4j requires a running server and has higher resource overhead. For a single-machine deployment, KuzuDB is the correct choice.

### Why local models over API calls?

- Complete privacy
- No recurring API costs
- Offline operation
- Deterministic reproducibility
- No rate limiting
- Latency control
- Aesthetic consistency (the entire system is self-contained)
