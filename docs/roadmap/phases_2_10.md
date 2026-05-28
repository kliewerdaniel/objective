# Roadmap Phases

## Phase 2: Claim Extraction (Weeks 2-4)
- LLM client with llama.cpp GPU acceleration
- Claim extraction prompt with structured JSON output
- Entity extraction sub-module (Qwen 3B)
- Stance classification (support/neutral/oppose/uncertain)
- Confidence scoring calibration
- Semantic claim deduplication

## Phase 3: Graph Memory (Weeks 3-5)
- KuzuDB schema and connection management
- Cypher query library for CRUD
- Entity resolution (alias merging, coreference)
- Event clustering (embedding + temporal)
- Embedding generation (BGE-small via Qdrant)
- Temporal graph updater agent

## Phase 4: Contradiction Tracking (Weeks 5-6)
- Embedding + LLM hybrid contradiction detection
- Contradiction edge schema in KuzuDB
- Contradiction indexing in SQLite
- Confidence evolution tracking
- Contradiction metrics pipeline

## Phase 5: Narrative Analysis (Weeks 6-8)
- Claim-to-narrative clustering
- Multi-dimension drift measurement
- Political framing classification
- Linguistic trajectory tracking
- Source reliability scoring

## Phase 6: Broadcast Generation (Weeks 8-10)
- Broadcast writer agent (Qwen 14B)
- Script structure templates
- Recurring thread callbacks
- Uncertainty presentation module
- Script validation pipeline

## Phase 7: Audio Pipeline (Weeks 10-12)
- Piper TTS integration
- FFmpeg audio stitching
- Audio queue with pre-generation
- Atmospheric transitions
- Continuous playback

## Phase 8: Autonomous Runtime (Weeks 12-14)
- Daemon orchestrator
- Scheduler with task management
- Health monitoring and degraded modes
- Signal handling (graceful shutdown)
- Terminal UI (Textual)

## Phase 9: Optimization (Weeks 14-16)
- Model quantization profiling (Q4 vs Q5 vs Q8)
- Inference batching and context management
- Memory consolidation and graph pruning
- Caching layer (LLM outputs, TTS, embeddings)

## Phase 10: Research (Week 16+)
- Crisis detection mode
- Multiple synthetic anchors
- Adversarial verification
- Continuous evaluation benchmarks
