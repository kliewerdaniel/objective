# System Overview

objective03 is a local-first autonomous AI news broadcast system designed around epistemic uncertainty, temporal memory, and contradiction preservation. It operates as a continuous daemon that transforms raw information streams into an evolving geopolitical knowledge graph and renders that graph into infinite audio broadcasts.

## Core Concepts

### The Broadcast is a Side Effect

The audio broadcast is not the product. It is the visible surface of a much deeper system:

```
  SOURCES
     │
     ▼
  CLAIMS              ← atomic factoid extraction
     │
     ▼
  EVENT GRAPH         ← temporal property graph with contradictions
     │
     ▼
  NARRATIVE ANALYSIS  ← drift, framing, confidence evolution
     │
     ▼
  BROADCAST SCRIPT    ← synthesis from graph state
     │
     ▼
  AUDIO               ← TTS rendering
```

The real system is the graph, the memory, and the continuous evolution.

### Contradiction as a First-Class Citizen

Most systems attempt to reconcile conflicting information into a single coherent narrative. objective03 does the opposite:

- Conflicting claims are linked via explicit contradiction edges
- Contradictions are tracked over time and their evolution is measured
- The broadcast can report on uncertainty, conflicting sourcing, and narrative divergence
- Confidence scores decay and shift as new evidence arrives

This produces broadcasts that sound like:

> "Across 14 independent reports, confidence in the official narrative has declined 23% over the last 48 hours."
> "State media sources continue converging on identical linguistic framing."
> "Contradictions persist regarding casualty estimates."

### Temporal Memory

The system exhibits memory-like behavior:

- Previous broadcasts are stored and referenced
- Recurring threads receive callbacks ("as we reported 72 hours ago...")
- Unresolved contradictions persist across broadcast cycles
- Entity histories are maintained
- Narratives evolve and the system tracks their evolution

This creates the eerie sensation of an AI that remembers history.

## System Boundaries

| Aspect | Included | Out of scope |
|--------|----------|--------------|
| Ingestion | RSS, Reddit, YouTube, gov feeds | Twitter/X, PDFs, arbitrary APIs (phase 2) |
| Inference | Local llama.cpp quantized models | Cloud API inference |
| Storage | KuzuDB, Qdrant, SQLite (local) | Distributed databases, cloud sync |
| UI | Terminal (Textual) | Web UI, mobile apps |
| Audio | Piper TTS, FFmpeg stitching | Real-time streaming, live radio |
| Deployment | Apple Silicon MacBook Pro | Server clusters, cloud deployment |

## System Characteristics

| Property | Value |
|----------|-------|
| Runtime model | Continuous daemon |
| Primary storage | Temporal property graph (KuzuDB) |
| Vector storage | Qdrant (local) |
| Metadata storage | SQLite |
| Inference engine | llama.cpp via Python bindings |
| Audio engine | Piper TTS + FFmpeg |
| Terminal UI | Textual |
| Language | Python 3.11+ |
| Target hardware | MacBook Pro M4 Pro, 48GB RAM |
| Expected memory usage | 8-16GB for models + graph |
| Expected disk usage | 10-100GB (growing) |

## Architectural Philosophy

1. **Graph-native, not graph-wrapped** — The data model is a graph from the ground up, not a document store with a graph layer bolted on.

2. **Deterministic orchestration** — Agents are not autonomous LLM loops. They are deterministic pipeline stages that happen to use LLMs for specific reasoning tasks.

3. **Observability as infrastructure** — Every pipeline stage emits structured events. The terminal UI and log system consume the same event stream.

4. **Fail-degraded operation** — If a model is unavailable, if ingestion is down, if TTS fails, the system continues operating in a degraded mode rather than crashing.

5. **Local-first by necessity** — Running on consumer hardware forces discipline: small models, efficient batching, aggressive caching, and careful resource management.

## The Dystopian Aesthetic

The system is deliberately designed to feel:

- **Cold** — Detached analytical tone, not warm and friendly
- **Synthetic** — Obviously machine-generated, not pretending to be human
- **Eerie** — The memory of past broadcasts creates a sense of persistent observation
- **Hypnotic** — Long-form continuous generation with atmospheric audio layering
- **Archival** — The voice of a machine cataloging civilization's information flows

This is not a bug. It is the point.

## Relation to Existing Systems

| System | Approach | Difference |
|--------|----------|------------|
| Google News | Algorithmic aggregation | No memory, no narrative tracking, no temporal graph |
| Bloomberg Terminal | Real-time financial data | Domain-specific, no AI synthesis, no contradictions |
| OSINT aggregators | Human-curated intelligence | No autonomous generation, no narrative analysis |
| AI podcast generators | Summarization + TTS | No contradiction preservation, no temporal memory |
| Radio news | Human-produced | Not autonomous, not continuous, not synthetic |

objective03 occupies a space no existing system fills: an autonomous epistemic observatory that tracks uncertainty over time.
