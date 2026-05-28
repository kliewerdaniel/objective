# Roadmap Documentation

## Phase Summaries

### Phase 1: Ingestion Infrastructure
**Duration**: Weeks 1-2 | **Goal**: Reliable source polling

Key deliverables:
- RSS, Reddit, YouTube connectors
- Normalization and deduplication
- SQLite cursor state
- Connector framework
- Tests: feed parsing, dedup, cursor recovery

### Phase 2: Claim Extraction
**Duration**: Weeks 2-4 | **Goal**: Atomic claim extraction

Key deliverables:
- LLM client abstraction
- Claim extraction prompt
- Entity extraction
- Confidence scoring
- Stance detection
- Tests: extraction accuracy, calibration

### Phase 3: Graph Memory
**Duration**: Weeks 3-5 | **Goal**: Persistent temporal graph

Key deliverables:
- KuzuDB schema and CRUD
- Entity resolution
- Event clustering
- Embedding generation
- Qdrant integration
- Tests: schema, traversal, temporal queries

### Phase 4: Contradiction Tracking
**Duration**: Weeks 5-6 | **Goal**: Contradiction detection and preservation

Key deliverables:
- Contradiction detector (LLM + embedding)
- Contradiction graph edges
- Contradiction indexing
- Confidence evolution tracking
- Tests: detection accuracy, false positive rate

### Phase 5: Narrative Analysis
**Duration**: Weeks 6-8 | **Goal**: Narrative drift and framing

Key deliverables:
- Narrative analyzer
- Political framing analyzer
- Linguistic drift measurement
- Source reliability scoring
- Tests: drift monotonicity, framing accuracy

### Phase 6: Broadcast Generation
**Duration**: Weeks 8-10 | **Goal**: Script synthesis

Key deliverables:
- Broadcast writer agent
- Script structure templates
- Recurring thread system
- Uncertainty presentation
- Tests: script structure, callback accuracy

### Phase 7: Audio Pipeline
**Duration**: Weeks 10-12 | **Goal**: TTS rendering

Key deliverables:
- Piper TTS integration
- FFmpeg audio stitching
- Broadcast scheduler
- Audio queue
- Continuous playback
- Tests: audio quality, queue management

### Phase 8: Autonomous Runtime
**Duration**: Weeks 12-14 | **Goal**: Continuous daemon

Key deliverables:
- Daemon orchestrator
- Scheduler daemon
- Health monitoring
- Graceful degradation
- Terminal UI
- Tests: lifecycle, degradation, recovery

### Phase 9: Optimization
**Duration**: Weeks 14-16 | **Goal**: Performance tuning

Key deliverables:
- Model quantization profiling
- Inference batching
- Context window management
- Memory consolidation
- Graph pruning
- Caching layer

### Phase 10: Research
**Duration**: Week 16+ | **Goal**: Advanced capabilities

Speculative features:
- Real-time crisis mode
- Synthetic multiple anchors
- Voice cloning
- Live streaming
- Federated instances
