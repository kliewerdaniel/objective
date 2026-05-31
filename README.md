<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT">
  <img src="https://img.shields.io/badge/inference-local-brightgreen" alt="Local Inference">
  <img src="https://img.shields.io/badge/status-pre--alpha-orange" alt="Pre-alpha">
</p>

<h1 align="center">objective03</h1>
<p align="center">
  <em>Autonomous news ingestion, claim extraction, contradiction tracking, and TTS broadcast — entirely on your laptop.</em>
</p>

---

objective03 is a locally-run daemon that polls RSS, Reddit, and YouTube sources, extracts factual claims and entities using local LLMs (llama.cpp with Metal GPU), stores everything in a KuzuDB temporal property graph with Qdrant vector search, detects contradictions between claims across sources, clusters them into events and narratives, and generates TTS audio broadcasts — all without any cloud dependencies.

---

## What It Does

### Ingestion
Polls RSS feeds (with ETag support), Reddit subreddits (OAuth2), and YouTube channel uploads (yt-dlp) on a configurable schedule. Documents are normalized (HTML strip, Unicode NFKC, SHA-256 dedup) and stored as nodes in a KuzuDB graph with edges to their source.

### Claim Extraction
Each document is fed to a local LLM that extracts atomic factual claims with confidence scores, stance classification, topic tags, and supporting evidence text via structured JSON output with GBNF grammar enforcement.

### Entity Resolution
A local LLM extracts named entities (people, organizations, locations, events) and resolves them against existing graph nodes via fuzzy matching and alias tracking.

### Event Clustering
Claims are assigned to events by entity overlap. New claims with shared entities create or join existing event nodes. Events track importance scores, status (emerging/active/resolved), and temporal boundaries.

### Contradiction Detection
New claims are embedded (BGE-Small-EN-v1.5) and searched against existing claims via Qdrant cosine similarity. Pairs above 0.75 threshold are classified by an LLM into typed contradictions: `DIRECT_CONTRADICTION`, `NUMERICAL_DISCREPANCY`, `FRAMING_DIFFERENCE`, `TEMPORAL_DISCREPANCY`, or `COMPATIBLE`. Contradictions are persisted as graph edges and never automatically resolved.

### Narrative Analysis
Unclustered claims are grouped into narrative threads via embedding cosine similarity clustering (>0.75 threshold). Each cluster gets an LLM-generated label. Active narratives track drift scores and framing classifications over time.

### Broadcast Generation
A local LLM queries the graph for top events, unresolved contradictions, active narratives, and system metrics, then writes an 800–1200 word TTS-optimized broadcast script. The model uses `<think>` blocks for internal reasoning before outputting spoken content.

### Audio Production
Scripts are split into ~100-word chunks, preprocessed (abbreviation expansion, number spelling, date normalization, dollar/percentage formatting), then synthesized via Qwen3-TTS (mlx_audio) with voice cloning from reference audio. Segments are stitched with crossfades and queued for playback via `afplay` on macOS. An ambient generator produces procedural drone audio (55Hz/110Hz sine waves, atmospheric noise) mixed beneath speech.

### Scheduling
A daemon scheduler runs five task groups on independent intervals:
- **Ingestion** (default: 60s)
- **Analysis pipeline** (default: 120s) — extraction → entity resolution → event clustering → contradiction detection → narrative analysis → framing analysis → source reliability → graph update
- **Broadcast** (default: 90s)
- **Audio production** (default: 90s)
- **Maintenance** (default: 24h) — memory consolidation, evaluation

Tasks have configurable max runtime, failure limits, and circuit-breaking.

---

## Storage Architecture

| Tier | Technology | Content |
|------|-----------|---------|
| **Graph** | KuzuDB (embedded) | 8 node types (Source, Document, Claim, Entity, Event, Narrative, Broadcast, ContradictionSummary), 10 edge types (FROM_SOURCE, EXTRACTED_FROM, MENTIONS, ABOUT_EVENT, CONTRADICTS, SUPPORTS, PART_OF_THREAD, APPEARS_IN, REFERENCES, PRECEDES) |
| **Vector** | Qdrant (local HTTP) | HNSW cosine similarity search over claim embeddings (384d) with payload filtering |
| **Metadata** | SQLite (WAL mode) | Ingestion cursors, dedup hashes, scheduler state, evaluation history, audit log |

---

## Models

7 specialized GGUF model slots loaded on demand via LRU (max 1 loaded at a time by default):

| Task | Default Model | Context | GPU Layers |
|------|--------------|---------|------------|
| extraction | LFM2.5-8B-A1B Q4 | 8192 | 32 |
| entity | LFM2.5-8B-A1B Q4 | 8192 | 32 |
| reasoning | LFM2.5-8B-A1B Q4 | 8192 | 32 |
| broadcast | LFM2.5-8B-A1B Q4 | 8192 | 32 |
| contradiction | LFM2.5-8B-A1B Q4 | 8192 | 32 |
| classification | LFM2.5-8B-A1B Q4 | 4096 | 32 |
| embedding | LFM2.5-8B-A1B Q4 | 8192 | 0 |

Models use llama.cpp with Metal GPU offload, flash attention, and mlock. Chat format is auto-detected from GGUF metadata with broken Jinja2 template patching. Any GGUF model can be assigned to any slot via `config.yaml`.

---

## Quick Start

### Prerequisites
- macOS 15+ (Apple Silicon with 48GB+ RAM ideal)
- Python 3.11+
- [FFmpeg](https://ffmpeg.org/) (`brew install ffmpeg`)
- [Qdrant](https://qdrant.tech/) (`brew install qdrant && brew services start qdrant`)

### Install
```bash
git clone https://github.com/yourusername/objective03.git
cd objective03
pip install -e ".[dev]"

# Download models (~25GB total)
objective03 download

# Verify setup
objective03 check
```

### Configure
Edit `~/.objective03/config.yaml` to set sources. Defaults pre-configure RSS feeds from NYT World/US/Politics/Tech/Science, BBC World/Politics/Tech/Science, The Guardian World/US/Tech/Science, and NPR News/Politics/World, plus Reddit r/worldnews and r/politics, and YouTube Associated Press.

### Run
```bash
objective03 run              # Daemon with log output
objective03 run --dashboard  # With Rich terminal UI dashboard
```

### Commands
| Command | Description |
|---------|-------------|
| `objective03 run` | Start the daemon |
| `objective03 run --dashboard` | Start with terminal UI dashboard |
| `objective03 download [models...]` | Download GGUF models and voices |
| `objective03 check` | Verify dependencies and config |

---

## Project Structure

```
objective03/
├── src/                        # Core Python backend
│   ├── ingestion/              # RSS, Reddit, YouTube source connectors
│   │   ├── connector.py        # Base SourceConnector, RateLimiter
│   │   ├── rss.py              # feedparser + aiohttp with ETag support
│   │   ├── reddit.py           # OAuth2 Reddit JSON API
│   │   ├── youtube.py          # yt-dlp channel extraction
│   │   └── normalize.py        # HTML strip, NFKC, SHA-256 dedup
│   │
│   ├── models/                 # LLM client + data types
│   │   ├── client.py           # llama-cpp-python wrapper (Metal, GBNF, chat format detection)
│   │   ├── types.py            # Document, Claim, Entity, Event, Narrative, Contradiction, Script
│   │   └── download.py         # HuggingFace GGUF model downloader
│   │
│   ├── database/               # Three-tier storage
│   │   ├── graph.py            # KuzuDB temporal property graph
│   │   ├── vector.py           # Qdrant HNSW vector search
│   │   └── metadata.py         # SQLite pipeline state + dedup
│   │
│   ├── agents/                 # 13 pipeline agents
│   │   ├── base.py                     # AgentContext, AgentResult, BaseAgent ABC
│   │   ├── ingestion_coordinator.py    # Polls all sources, creates Source/Document nodes
│   │   ├── claim_extractor.py          # LLM-based atomic claim extraction
│   │   ├── entity_extractor.py         # NER with graph-based resolution
│   │   ├── event_clustering.py         # Claim → event grouping by entity overlap
│   │   ├── contradiction_detector.py   # Vector pre-filter + LLM classification
│   │   ├── narrative_analyzer.py       # Embedding clustering + drift measurement
│   │   ├── framing_analyzer.py         # Per-claim framing classification
│   │   ├── source_reliability.py       # Trust scoring by source type
│   │   ├── broadcast_writer.py         # Script generation from graph state
│   │   ├── graph_updater.py            # Node/edge persistence
│   │   ├── audio_producer.py           # TTS synthesis + queuing
│   │   ├── memory_consolidator.py      # Orphan claim pruning
│   │   ├── scoring.py                  # Claim scoring utilities
│   │   └── scheduler_daemon.py         # Interval-based task execution
│   │
│   ├── audio/                  # Synthesis pipeline
│   │   ├── piper.py            # Qwen3-TTS voice cloning (mlx_audio)
│   │   ├── player.py           # AudioStitcher, AudioQueue, ContinuousPlayer (afplay)
│   │   ├── preprocessor.py     # TTS text normalization
│   │   └── ambient.py          # Procedural drone + atmosphere generation
│   │
│   ├── daemon/
│   │   └── orchestrator.py     # Async lifecycle, bootstrap, scheduler loop
│   │
│   ├── ui/
│   │   └── dashboard.py        # Rich 4-panel terminal dashboard
│   │
│   ├── evaluation/
│   │   └── engine.py           # Graph metrics, health checks
│   │
│   ├── security/
│   │   └── sanitize.py         # Prompt injection detection + feed sanitization
│   │
│   ├── config.py               # Pydantic config from YAML
│   ├── prompts.py              # Prompt template loader
│   ├── cli.py                  # CLI entry point
│   └── main.py                 # Signal handling + async entry point
│
├── electron/                   # Electron + React desktop frontend
│   ├── src/                    # React components (TypeScript)
│   ├── dist-electron/          # Electron main process
│   ├── package.json            # Node dependencies (React, Radix UI, TailwindCSS, Recharts)
│   └── vite.config.ts          # Vite + Electron builder config
│
├── prompts/                    # LLM prompt templates (Markdown)
│   └── broadcast_writer.md
│
├── tests/                      # pytest test suite
│   ├── test_end_to_end.py
│   ├── test_models.py
│   ├── test_graph.py
│   └── dashboard.py
│
├── docs/                       # Project documentation
│
├── custom_voices/              # Reference audio for TTS voice cloning (gitignored)
├── models/                     # GGUF model files (gitignored)
│
├── config.yaml                 # Default runtime configuration
├── pyproject.toml              # Python package definition
├── requirements.txt            # Supplementary Python dependencies
└── com.danielkliewer.objective03.plist  # macOS launchd daemon plist
```

---

## Hardware Notes

| Machine | RAM | Model Load | Notes |
|---------|-----|------------|-------|
| M4 Pro | 48GB | 1 at a time (LRU) | Recommended |
| M3 Pro | 36GB | 1 at a time | Works, tighter headroom |
| M2 | 24GB | 1 at a time | May need smaller models |
| M1 | 16GB | Not recommended | Insufficient RAM |
| Any + CUDA | 24GB+ | 1 at a time | With CUDA-llamacpp |

Peak memory with all models: ~25GB. ModelRegistry loads 1 model at a time with LRU eviction and 5-minute idle timeout.

---

## Development

```bash
pip install -e ".[dev]"
pytest
pytest --cov=src
mypy src
ruff check src
```

---

## Project Status

**Phase:** Core implementation complete. 47 Python source files, ~9,300 lines of code.

**Stability:** Pre-alpha. Pipeline logic is deterministic and tested, but hasn't run for extended periods against live feeds.

**Remaining:**
- Extended soak testing (7+ days)
- Contradiction detection false-positive tuning
- Multi-voice TTS and dynamic ambient mixing
- Model download + verification pipeline
- Sustained load profiling

---

## License

MIT. Models have their own licenses (Qwen: Apache 2.0, Llama: Llama Community License).

---

## Acknowledgments

- [llama.cpp](https://github.com/ggerganov/llama.cpp) — Local LLM inference
- [KuzuDB](https://kuzudb.com/) — Embedded graph database
- [Qdrant](https://qdrant.tech/) — Vector search
- [mlx-audio](https://github.com/ml-explore/mlx-audio) — Qwen3-TTS voice synthesis
- [Textual](https://textual.textualize.io/) / [Rich](https://rich.readthedocs.io/) — Terminal UI
- [Electron](https://www.electronjs.org/) / [React](https://react.dev/) / [TailwindCSS](https://tailwindcss.com/) — Desktop frontend
