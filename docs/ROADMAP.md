# Roadmap

## Overview

objective03 is developed in ten phases over approximately 16+ weeks. Each phase builds on the prior phases and introduces measurable, testable capabilities.

## Phase Summary

| Phase | Focus | Duration | Deliverable |
|-------|-------|----------|-------------|
| 1 | Ingestion | 2 weeks | Working source pollers, dedup, normalization |
| 2 | Claim Extraction | 2 weeks | Atomic claims from raw documents |
| 3 | Graph Memory | 2 weeks | Persistent temporal graph with entity resolution |
| 4 | Contradiction | 1 week | Contradiction detection and preservation |
| 5 | Narrative Analysis | 2 weeks | Drift, framing, confidence evolution |
| 6 | Broadcast Generation | 2 weeks | Script synthesis from graph state |
| 7 | Temporal/Audio | 2 weeks | TTS, queue, continuous playback |
| 8 | Autonomous Runtime | 2 weeks | Daemon, scheduler, terminal UI |
| 9 | Optimization | 2 weeks | Performance, resource, cache tuning |
| 10 | Research | Ongoing | Advanced capabilities |

## Dependency Chain

```
Phase 1 ───▶ Phase 2 ───▶ Phase 3 ───▶ Phase 4
                                  │            │
                                  ▼            ▼
                              Phase 5 ───▶ Phase 6 ───▶ Phase 7 ───▶ Phase 8
                                                                         │
                                                                    ┌────┘
                                                                    ▼
                                                               Phase 9
                                                                   │
                                                                   ▼
                                                              Phase 10
```

## Detailed Phase Plan

### Phase 1: Ingestion Infrastructure

**Goal**: Reliable, continuous ingestion from multiple source types.

**Key decisions**:
- SQLite cursor state for resumable polling
- SHA-256 content deduplication
- Configurable poll intervals per source
- Structured document model (normalized before storage)

**Deliverables**:
- RSS feed poller with ETag/If-Modified-Since support
- Reddit poller with PRAW (configurable subreddits + sorting)
- YouTube transcript fetcher via yt-dlp
- Content normalization (HTML stripping, encoding fixing)
- Content deduplication (exact + fuzzy via MinHash)
- Source configuration in YAML
- SQLite cursor/polling state store
- Connector framework for adding new source types
- `src/ingestion/` module complete with tests

**Tests**:
- Feed parsing with known XML fixtures
- Dedup correctly identifies identical/similar documents
- Polling resumes from correct cursor after restart
- All connector types produce identical output schema

---

### Phase 2: Claim Extraction

**Goal**: Transform raw documents into atomic claims with confidence, stance, and entity annotations.

**Key decisions**:
- Small fast instruct model for extraction (Qwen2.5-7B-Instruct-Q4)
- Atomic claims only — no summaries
- Structured JSON output via constrained decoding
- Confidence scores calibrated per model run

**Deliverables**:
- LLM client abstraction for llama.cpp
- Claim extraction prompt template with structured output
- Entity extraction sub-module
- Stance classification (support/neutral/oppose/uncertain)
- Confidence scoring calibration
- Claim deduplication via semantic similarity
- `src/agents/claim_extractor.py` with tests

**Tests**:
- Extract known claims from test documents
- Confidence scores are well-calibrated (calibration curve)
- Entity extraction correctly identifies people, orgs, locations
- Stance classification accuracy >80%

---

### Phase 3: Graph Memory

**Goal**: Persistent temporal knowledge graph with entity resolution, event clustering, and vector search.

**Key decisions**:
- KuzuDB as primary graph store
- Qdrant for vector similarity
- SQLite for pipeline metadata
- Event clustering via temporal + entity co-occurrence

**Deliverables**:
- KuzuDB schema initialization and connection management
- Cypher query library for all CRUD operations
- Entity resolution (aliases, coreference)
- Event clustering algorithm
- Embedding generation for claims and entities
- Qdrant index population and query
- SQLite metadata tables for pipeline state
- Temporal graph updater agent
- `src/database/` module complete

**Tests**:
- Schema validation (all node types, edge constraints)
- Entity resolution correctly merges known aliases
- Event clustering groups related claims
- Vector search returns semantically similar claims
- Temporal queries respect time bounds

---

### Phase 4: Contradiction Tracking

**Goal**: Detect, store, and surface contradictions between claims.

**Key decisions**:
- Contradictions are explicit graph edges with type + confidence
- Contradictions are never automatically resolved
- Contradiction types: direct, contextual, sourcing, temporal

**Deliverables**:
- Contradiction detection via LLM + embedding hybrid
- Contradiction edge type in graph schema
- Contradiction indexing for efficient query
- Confidence evolution tracking per contradiction
- Contradiction metrics (count, density, resolution rate)
- `src/agents/contradiction_detector.py` with tests

**Tests**:
- Detects known contradictions in test corpus
- Does not flag unrelated claims as contradictory
- Contradiction edges correctly stored in graph
- Confidence evolution correctly tracks over time

---

### Phase 5: Narrative Analysis

**Goal**: Track narrative drift, political framing, linguistic evolution.

**Key decisions**:
- Narrative analysis is scheduled, not continuous
- Drift measured via embedding cosine distance over time
- Framing analysis via LLM classification

**Deliverables**:
- Narrative analyzer (clusters claims into narrative threads)
- Political framing analyzer (left/right/establishment/alternative)
- Linguistic drift measurement via embedding trajectories
- Narrative evolution tracking (per-thread state over time)
- Source reliability scoring
- `src/agents/narrative_analyzer.py` with tests

**Tests**:
- Correctly identifies narrative threads
- Drift measurement monotonic over time with conflicting sources
- Framing classification accuracy >75%
- Source reliability scores converge with evidence

---

### Phase 6: Broadcast Generation

**Goal**: Synthesize the graph state into cold, analytical broadcast scripts.

**Key decisions**:
- Larger reasoning model for synthesis (Llama-3.1-8B or Qwen-2.5-14B)
- Structured script format with sections
- Templates for recurring segments
- Uncertainty explicitly surfaced

**Deliverables**:
- Broadcast writer agent with prompt templates
- Script structure: intro, segments, transitions, outro
- Recurring thread system (callbacks to prior broadcasts)
- Uncertainty presentation module
- Queue management for scripts
- `src/agents/broadcast_writer.py` with tests

**Tests**:
- Scripts reference prior broadcasts correctly
- Uncertainty is surfaced in every script
- Recurring threads are tracked and referenced
- Scripts are syntactically valid (no broken segments)

---

### Phase 7: Audio Pipeline

**Goal**: Render scripts to spoken audio with atmospheric transitions.

**Key decisions**:
- Piper TTS for voice synthesis
- FFmpeg for audio stitching and processing
- Audio queue with pre-generation for low latency
- Atmospheric background tracks for transitions

**Deliverables**:
- Piper TTS integration with voice model loading
- FFmpeg audio stitching pipeline
- Broadcast scheduler (when to generate, when to play)
- Audio queue with pre-generation
- Atmospheric transition generation
- Continuous playback with sounddevice
- `src/audio/` module complete

**Tests**:
- TTS produces valid WAV output
- Audio stitching has no audible glitches at seams
- Queue pre-generates before depletion
- Scheduler respects configured intervals
- Transitions are smooth and appropriate

---

### Phase 8: Autonomous Runtime

**Goal**: The system runs as a daemon with terminal UI, health monitoring, and graceful degradation.

**Key decisions**:
- Single-process orchestrator with async scheduling
- Textual for terminal UI
- Degraded modes for component failures
- Structured logging to file + UI

**Deliverables**:
- Daemon orchestrator with lifecycle management
- Scheduler daemon (ingestion, analysis, broadcast cycles)
- Health monitoring (component status, model availability)
- Graceful degradation (disable failed components)
- Signal handling (SIGINT, SIGTERM, SIGHUP reload)
- Terminal dashboard with live metrics
- `src/daemon/` and `src/ui/` modules complete

**Tests**:
- All components handle graceful shutdown
- Degraded mode activates correctly on failures
- Health checks detect component failure within 30s
- Scheduler respects configured cycles
- Terminal UI renders without errors

---

### Phase 9: Optimization

**Goal**: Performance, memory, and quality optimization.

**Key decisions**:
- Profile before optimizing
- Cache everything that can be cached
- Prune aggressively

**Deliverables**:
- Model quantization profiling (Q4 vs Q5 vs Q8)
- Inference batching optimization
- Context window management strategies
- Memory consolidation (archive old data, prune low-confidence claims)
- Graph pruning (remove orphaned nodes, archive resolved contradictions)
- Caching layer for LLM outputs
- Performance benchmarks

**Tests**:
- Throughput benchmarks for each pipeline stage
- Memory usage under load
- Cache hit rates >60%
- Pruning does not remove referenced data

---

### Phase 10: Research Extensions

**Goal**: Advanced capabilities and speculative features.

See [docs/roadmap/phase_10_research.md](docs/roadmap/phase_10_research.md).

## Decision Tracking

Significant architectural decisions are recorded with:

- Date
- Context
- Decision
- Consequences
- Alternatives considered

## Success Criteria

The system is successful when:

1. It runs continuously for 7+ days without human intervention
2. It ingests from 10+ sources across 3+ source types
3. The graph contains 10,000+ claims with <1% false contradiction rate
4. Broadcasts sound coherent, eerie, and analytically useful
5. The system recovers from component failures autonomously
6. Memory usage stays under 32GB
7. Disk usage is bounded by configured limits
