<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-blue" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT">
  <img src="https://img.shields.io/badge/inference-local-brightgreen" alt="Local Inference">
  <img src="https://img.shields.io/badge/platform-macOS%20ARM64-black" alt="macOS arm64">
  <img src="https://img.shields.io/badge/status-alpha-orange" alt="Alpha">
</p>

<h1 align="center">objective03</h1>
<p align="center">
  <em>A synthetic epistemology engine masquerading as an infinite radio station.</em><br>
  <sub>Ingests news. Extracts claims. Detects contradictions. Generates broadcasts. Entirely offline.</sub>
</p>

---

objective03 is a locally-run desktop application that transforms news consumption from passive scrolling into an autonomous process of claim extraction, contradiction tracking, and synthetic broadcast generation. It polls RSS feeds and Reddit communities, runs each article through a pipeline of local LLMs (Metal GPU accelerated on Apple Silicon), stores everything in an embedded graph database with vector search, and produces TTS-narrated news broadcasts with voice cloning — all without any cloud dependencies, API keys, or internet connectivity after setup.

It ships as a macOS DMG with an Electron + React frontend and a Python backend spawned with a dynamic port, requiring only Python 3.11+ and a few system packages to run.

---

## Features

- **Autonomous Ingestion** — Polls RSS feeds and Reddit subreddits on configurable schedules with ETag support, deduplication, and HTML normalization
- **Claim Extraction** — Local LLM extracts atomic factual claims with confidence scores, stance classification, entity references, and supporting evidence
- **Entity Resolution** — Named entity recognition with alias tracking and fuzzy graph matching
- **Event Clustering** — Claims grouped into events by entity overlap with importance scoring and status tracking (emerging/active/resolved)
- **Contradiction Detection** — Embedding similarity pre-filter (hnswlib, cosine >0.75) + LLM classification into 5 contradiction types: `DIRECT_CONTRADICTION`, `NUMERICAL_DISCREPANCY`, `FRAMING_DIFFERENCE`, `TEMPORAL_DISCREPANCY`, `COMPATIBLE`
- **Narrative Analysis** — Unclustered claims grouped into narrative threads via embedding clustering with drift measurement and framing classification
- **TTS Broadcast Generation** — LLM writes 800–1200 word scripts using `<think>` block reasoning, then synthesizes via Qwen3-TTS (mlx_audio) with voice cloning from reference audio
- **Desktop Application** — Electron + React frontend with Dashboard, Broadcast player, model manager, source editor, voice switcher, and prompt editor
- **First-Run Wizard** — 7-step setup: storage paths, model tier selection, voice choice, source selection, model download or use existing
- **macOS DMG Distribution** — Self-contained .dmg with embedded Python backend, notarization-ready signing, zero configuration required

---

## Quick Start

### Download

Download the latest DMG from the [Releases](https://github.com/yourusername/objective03/releases) page.

### Install

1. Open the `.dmg` and drag `objective03.app` to your Applications folder
2. Double-click `objective03.app`

The first-run wizard will guide you through:

| Step | What You Choose |
|------|----------------|
| Storage | Data and models directory paths (defaults to `~/Library/Application Support/objective03`) |
| Models | Tier: **Minimal** (4 GB, 8 GB RAM), **Balanced** (12 GB, 16 GB RAM), **Full Suite** (25 GB, 32 GB RAM) — or point to existing `.gguf` files |
| Voice | Atlas (deep/slow), Meridian (neutral), Cipher (clipped) — or upload your own `.wav` for voice cloning |
| Sources | Pre-configured categories: World News, US Politics, Science & Technology, Economics & Finance, Community (Reddit) — or add custom RSS URLs |
| Download | Download models automatically or use existing files from disk |

### Prerequisites

- macOS 14+ (Apple Silicon, 8 GB RAM minimum, 48 GB recommended)
- Python 3.11+ installed (`brew install python@3.11` or from python.org)
- Python packages: `pip3 install --break-system-packages mlx mlx-audio`

The backend auto-detects your Python installation and validates that all required packages are available. On first launch, the terminal session includes a `.venv` setup guide if dependencies are missing.

### From Source

```bash
git clone https://github.com/yourusername/objective03.git
cd objective03

# Python backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[tts,dev]"

# Electron frontend
cd electron
npm install

# Development mode
npm run dev

# Production build
npm run electron:build:mac
# Output: electron/release/objective03-0.1.0-arm64.dmg
```

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   objective03.app                         │
│  ┌────────────────────────────────────────────────────┐  │
│  │              Electron Main Process                   │  │
│  │  ┌──────────┐  ┌──────────────┐  ┌──────────────┐  │  │
│  │  │findPython │  │findAvailable │  │   Spawn       │  │  │
│  │  │  ()       │  │  Port ()     │  │  uvicorn      │  │  │
│  │  └──────────┘  └──────────────┘  └──────┬───────┘  │  │
│  └──────────────────────────────────────────┼──────────┘  │
│                                             │               │
│  ┌──────────────────────────────────────────┼──────────┐  │
│  │              React Renderer              │           │  │
│  │  ┌──────────┐  ┌──────────┐  ┌────────┐ │           │  │
│  │  │ Dashboard │  │Broadcast │  │Wizard  │ │           │  │
│  │  │  (stats,  │  │ (pipeline│  │ (7-step│ │           │  │
│  │  │   events) │  │  player) │  │ setup) │ │           │  │
│  │  └──────────┘  └──────────┘  └────────┘ │           │  │
│  │  ┌──────────┐  ┌──────────┐  ┌────────┐ │           │  │
│  │  │  Models  │  │ Sources  │  │  Voice  │ │           │  │
│  │  │ Manager  │  │  Editor  │  │ Switcher│ │           │  │
│  │  └──────────┘  └──────────┘  └────────┘ │           │  │
│  │                    │                     │           │  │
│  └────────────────────┼─────────────────────┘           │  │
│                       │ HTTP + SSE                      │  │
│  ┌────────────────────┼─────────────────────┐           │  │
│  │         Python Backend (uvicorn)          │           │  │
│  │  ┌──────────────────────────────────────┐ │           │  │
│  │  │          FastAPI Server               │ │           │  │
│  │  │  /api/wizard/*  /api/dashboard/*      │ │           │  │
│  │  │  /api/broadcasts/*  /api/models/*     │ │           │  │
│  │  │  /api/sources/*  /api/events (SSE)    │ │           │  │
│  │  └────────────────┬─────────────────────┘ │           │  │
│  │                   │                        │           │  │
│  │  ┌────────────────┴─────────────────────┐ │           │  │
│  │  │         Agent Pipeline                │ │           │  │
│  │  │  Ingestion → Claims → Entities →     │ │           │  │
│  │  │  Clustering → Contradictions →       │ │           │  │
│  │  │  Narratives → Graph Updater →        │ │           │  │
│  │  │  Broadcast Writer → TTS → Stitcher    │ │           │  │
│  │  └────────────────┬─────────────────────┘ │           │  │
│  │                   │                        │           │  │
│  │  ┌────────────────┴─────────────────────┐ │           │  │
│  │  │          Storage Layer                │ │           │  │
│  │  │  ┌─────────┐ ┌──────────┐ ┌────────┐ │ │           │  │
│  │  │  │ KuzuDB  │ │ hnswlib │ │ SQLite │ │ │           │  │
│  │  │  │ (graph) │ │(vector) │ │(meta)  │ │ │           │  │
│  │  │  └─────────┘ └──────────┘ └────────┘ │ │           │  │
│  │  └──────────────────────────────────────┘ │           │  │
│  └───────────────────────────────────────────┘           │  │
└──────────────────────────────────────────────────────────┘
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **hnswlib over Qdrant** | Eliminates external process, network port, and Docker dependency. HNSW index persisted to disk with payload filtering |
| **HashRouter over BrowserRouter** | HashRouter works with `file://` protocol in Electron; BrowserRouter pathname resolves to the full filesystem path |
| **Dynamic port allocation** | `net.createServer()` picks a random free port, avoiding conflicts with other applications |
| **afplay for audio** | macOS built-in player — no additional dependencies, supports WAV playback with position tracking |
| **LLM LRU cache (1 model)** | Maximizes available RAM for other processes; 5-minute idle timeout unloads unused models |
| **KuzuDB + hnswlib + SQLite** | Three specialized stores instead of one general-purpose DB: graph for relationships, vector for similarity, SQLite for key-value metadata |
| **Embedded, no Docker** | Every dependency runs in-process or as a subprocess — no containers, no daemons, no cloud |

---

## Storage Architecture

| Tier | Technology | Schema | Purpose |
|------|-----------|--------|---------|
| **Graph** | KuzuDB (embedded columnar) | 8 node types, 11 edge types | Temporal property graph for claims, entities, events, contradictions, narratives |
| **Vector** | hnswlib (in-process HNSW) | 384-dimensional float vectors | Cosine similarity search over claim embeddings with payload filtering |
| **Metadata** | SQLite (WAL mode) | 8 tables | Ingestion cursors, dedup hashes, scheduler state, provenance tracking, model cache |

Graph node types: Source, Document, Claim, Entity, Event, Narrative, Broadcast, ContradictionSummary.

Edge types: FROM_SOURCE, EXTRACTED_FROM, MENTIONS, ABOUT_EVENT, CONTRADICTS, SUPPORTS, PART_OF_THREAD, APPEARS_IN, REFERENCES, PRECEDES, CALLS_BACK.

The graph tracks the full provenance chain from source document through claim extraction to contradiction detection, enabling queries like "which claims in this broadcast contradict claims from yesterday's BBC feed?"

---

## Models

Models are loaded on demand via an LRU registry (1 model at a time by default) and use llama.cpp with Metal GPU acceleration, flash attention, and mlock.

### Default Configurations

#### Minimal (~4.5 GB total, 8 GB RAM)

| Task | Model | Context | GPU Layers |
|------|-------|---------|------------|
| All LLM tasks | Qwen2.5-7B-Instruct Q4_K_M | 4096 | 32 |
| Embedding | BGE-Small-EN-v1.5 Q4_K_M | 512 | 0 |

#### Balanced (~11.8 GB total, 16 GB RAM) ★ Recommended

| Task | Model | Context | GPU Layers |
|------|-------|---------|------------|
| Extraction, Entity, Classification | Qwen2.5-7B-Instruct Q4_K_M | 4096 | 32 |
| Reasoning, Broadcast | Llama-3.1-8B-Instruct Q4_K_M | 8192 | 32 |
| Contradiction | Llama-3.2-3B-Instruct Q4_K_M | 4096 | 32 |
| Embedding | BGE-Small-EN-v1.5 Q4_K_M | 512 | 0 |

#### Full Suite (~24.6 GB total, 32 GB RAM)

| Task | Model | Context | GPU Layers |
|------|-------|---------|------------|
| Extraction | Qwen2.5-7B-Instruct Q4_K_M | 4096 | 32 |
| Entity, Classification | Qwen2.5-3B-Instruct Q4_K_M | 2048 | 32 |
| Reasoning | Llama-3.1-8B-Instruct Q4_K_M | 8192 | 32 |
| Broadcast | Qwen2.5-14B-Instruct Q4_K_M | 8192 | 32 |
| Contradiction | Llama-3.2-3B-Instruct Q4_K_M | 4096 | 32 |
| Embedding | BGE-Small-EN-v1.5 Q4_K_M | 512 | 0 |

### Custom Assignments

Any GGUF model can be assigned to any task slot via the Model Manager in the app or by editing `config.yaml` directly. The auto-detection feature (triggered during wizard setup with "Use Existing Models") scores each `.gguf` file against task keywords and assigns optimally.

---

## Configuration

The app stores configuration at `~/Library/Application Support/objective03/config.yaml`. Key sections:

```yaml
system:
  data_dir: ~/Library/Application Support/objective03
  models_dir: /path/to/models
  log_level: INFO

audio:
  tts:
    engine: qwen
    voice: atlas        # or meridian, cipher, or custom voice name
    speed: 1.0
  enabled: true

scheduler:
  ingestion_interval: 300       # seconds
  analysis_interval: 1800       # seconds
  broadcast_interval: 900       # seconds

sources:
  rss:
    - url: https://...           # 30+ pre-configured feeds
  reddit:
    - subreddit: worldnews       # 13 pre-configured subreddits
```

Configuration is editable at runtime through the Advanced section in the app sidebar.

---

## Frontend Pages

| Page | Route | Description |
|------|-------|-------------|
| **Dashboard** | `/` | Health bar (daemon status, event/claim/contradiction counts), event feed with expandable cards, epistemic state panel (contradiction density, source reliability, active claims), real-time activity stream |
| **Broadcast** | `/broadcast` | Now-playing player with play/stop and progress bar, 10-stage pipeline visualization (INGEST → CLAIMS → ENTITIES → CLUSTER → CONTRA → NARRATE → SCRIPT → TTS → STITCH → READY), TTS progress, broadcast history grid with play/rename/download/delete |
| **Sources** | `/sources` | Full CRUD for RSS, Reddit, and YouTube sources with URL validation |
| **Models** | `/models` | Browse `.gguf` files, scan folders, assign models to pipeline tasks |
| **Voice** | `/voices` | Select active voice, upload custom `.wav` files for voice cloning |
| **Prompts** | `/prompts` | In-editor for all LLM prompt templates |
| **Advanced** | `/config` | Raw YAML config editor |

All pages receive real-time updates via Server-Sent Events from the backend.

---

## Pipeline

When the user clicks "Generate Broadcast," the following pipeline executes as a background task:

1. **Ingestion** — Polls all configured sources (RSS + Reddit), normalizes HTML, deduplicates via SHA-256, stores documents
2. **Claim Extraction** — Each document is fed to a local LLM that extracts atomic factual claims with confidence scores, stance (for/against/neutral), topic tags, entities, and supporting evidence
3. **Entity Resolution** — LLM extracts named entities and resolves aliases against the graph database
4. **Event Clustering** — Claims are grouped into events by shared entities; importance scores and temporal boundaries are computed
5. **Contradiction Detection** — Each claim is embedded (BGE-Small) and searched against existing claims via hnswlib cosine similarity; pairs above 0.75 are classified by LLM into one of 5 contradiction types
6. **Narrative Analysis** — Ungrouped claims are clustered into narrative threads via embedding similarity (>0.75), labeled by LLM, and tracked for drift over time
7. **Broadcast Writer** — Queries the graph for top events, unresolved contradictions, active narratives, and system metrics, then generates an 800–1200 word TTS-optimized script using `<think>` block reasoning
8. **TTS Synthesis** — Script is split into ~100-word chunks, preprocessed (abbreviation expansion, number spelling, date/dollar/percentage normalization), and synthesized via Qwen3-TTS with voice cloning
9. **Stitching** — Individual segments are merged into a single WAV file with crossfade padding

Progress is streamed to the frontend via SSE at every stage.

---

## Hardware Requirements

| Machine | RAM | Model Config | Notes |
|---------|-----|--------------|-------|
| M4 Pro | 48 GB | Full Suite | Recommended — all 7 task-specific models |
| M3 Pro | 36 GB | Balanced | Works well with 4 models |
| M2 | 24 GB | Balanced or Minimal | Tighter headroom with Balanced |
| M1 Pro | 16 GB | Minimal | Single model handles all tasks |
| M1 | 8 GB | Minimal | Feasible with 7B model, expect slower performance |
| Any + CUDA | 24 GB+ | Any | With CUDA-enabled llama-cpp-python |

Peak memory with all 7 models loaded simultaneously: ~25 GB. The ModelRegistry limits to 1 active model with LRU eviction and 5-minute idle timeout, so typical memory usage is 4–8 GB.

---

## Project Structure

```
objective03/
├── backend/                        # FastAPI backend server
│   ├── server.py                   # 1350+ line API server — all endpoints, pipeline, playback
│   └── events.py                   # SSE event manager for real-time frontend updates
│
├── electron/                       # Electron + React desktop frontend
│   ├── electron/
│   │   ├── main.ts                 # Main process: backend spawning, dynamic port, IPC
│   │   ├── preload.ts              # Context bridge for secure IPC
│   │   └── tsconfig.json
│   ├── src/                        # React renderer
│   │   ├── App.tsx                 # Root: state machine (loading/wizard/ready), HashRouter, ErrorBoundary
│   │   ├── components/
│   │   │   ├── Layout.tsx          # Sidebar nav with drag region, collapsible config menu
│   │   │   └── ErrorBoundary.tsx   # Catches render errors with stack display
│   │   ├── pages/
│   │   │   ├── Dashboard.tsx       # Health bar, event feed, epistemic state
│   │   │   ├── Broadcast.tsx       # Pipeline viz, now-playing player, history grid
│   │   │   ├── SourcesPage.tsx     # Source CRUD with validation
│   │   │   ├── ModelManager.tsx    # Model browsing and task assignment
│   │   │   ├── VoiceSwitcher.tsx   # Voice selection and upload
│   │   │   ├── PromptEditor.tsx    # Prompt template editor
│   │   │   └── ConfigEditor.tsx    # Raw YAML config editor
│   │   ├── wizard/                 # 7-step first-run wizard
│   │   │   ├── Wizard.tsx          # Step orchestrator with navigation
│   │   │   ├── WelcomeStep.tsx
│   │   │   ├── StorageStep.tsx     # Directory picker with native dialog
│   │   │   ├── ModelsStep.tsx      # Tier selection from model catalog
│   │   │   ├── VoiceStep.tsx       # Built-in voices + custom upload
│   │   │   ├── SourcesStep.tsx     # Category-based source selection
│   │   │   ├── DownloadStep.tsx    # Download vs use existing models
│   │   │   ├── CompleteStep.tsx    # Summary + launch
│   │   │   └── types.ts
│   │   ├── data/
│   │   │   ├── model-catalog.json  # 3 tiers: Minimal, Balanced, Full Suite
│   │   │   └── default-sources.json # 5 categories with curated feeds
│   │   └── lib/
│   │       └── api.ts             # Full API client with TypeScript interfaces
│   ├── electron-builder.yml       # DMG packaging config
│   ├── vite.config.ts             # Vite + Electron builder
│   └── scripts/                   # Build and notarization scripts
│
├── src/                            # Python core
│   ├── config.py                   # Pydantic config with model_path() resolution
│   ├── cli.py                      # CLI entry point (dev mode)
│   ├── main.py                     # Async entry point
│   ├── prompts.py                  # Prompt template loader
│   ├── agents/                     # 15 pipeline agents
│   │   ├── base.py                 # BaseAgent ABC
│   │   ├── ingestion_coordinator.py
│   │   ├── claim_extractor.py
│   │   ├── entity_extractor.py
│   │   ├── event_clustering.py
│   │   ├── contradiction_detector.py
│   │   ├── narrative_analyzer.py
│   │   ├── framing_analyzer.py
│   │   ├── source_reliability.py
│   │   ├── broadcast_writer.py
│   │   ├── audio_producer.py
│   │   ├── graph_updater.py
│   │   ├── memory_consolidator.py
│   │   ├── scoring.py
│   │   └── scheduler_daemon.py
│   ├── audio/
│   │   ├── piper.py                # Qwen3-TTS with voice cloning (mlx_audio)
│   │   ├── player.py               # AudioStitcher, AudioQueue, StreamingPlayer
│   │   ├── preprocessor.py         # TTS text normalization
│   │   └── ambient.py              # Procedural drone generation
│   ├── database/
│   │   ├── graph.py                # KuzuDB temporal property graph
│   │   ├── vector.py               # hnswlib vector store with payload filtering
│   │   └── metadata.py             # SQLite metadata store
│   ├── models/
│   │   ├── client.py               # LLMClient (llama.cpp wrapper) + ModelRegistry (LRU)
│   │   ├── types.py                # Document, Claim, Entity, Event, Script, etc.
│   │   └── download.py             # HuggingFace GGUF downloader
│   ├── ingestion/
│   │   ├── connector.py            # Base SourceConnector
│   │   ├── rss.py                  # feedparser + aiohttp with ETag
│   │   ├── reddit.py               # Async PRAW wrapper
│   │   ├── youtube.py              # yt-dlp channel extraction
│   │   └── normalize.py            # HTML strip, NFKC, dedup
│   ├── daemon/
│   │   └── orchestrator.py         # Async lifecycle and scheduler loop
│   ├── evaluation/
│   │   └── engine.py               # Graph metrics and health checks
│   ├── security/
│   │   └── sanitize.py             # Prompt injection detection
│   └── ui/
│       └── dashboard.py            # Rich terminal UI (dev mode)
│
├── prompts/                        # LLM prompt templates (Markdown)
│   ├── broadcast_writer.md
│   ├── claim_extractor.md
│   ├── entity_extractor.md
│   ├── contradiction_detector.md
│   ├── narrative_analyzer.md
│   └── framing_analyzer.md
│
├── custom_voices/                  # Reference audio for voice cloning
├── models/                         # GGUF model files (gitignored)
├── tests/                          # Pytest test suite
├── config.yaml                     # Default configuration
├── pyproject.toml                  # Python package definition
└── com.danielkliewer.objective03.plist  # launchd plist
```

---

## Hardware Notes

| Machine | RAM | Recommended Tier | Notes |
|---------|-----|-----------------|-------|
| M4 Pro | 48 GB | Full Suite | All 7 task-specific models |
| M3 Pro | 36 GB | Balanced | 4 models, good headroom |
| M2 Pro | 32 GB | Balanced | Works well |
| M2 | 24 GB | Balanced or Minimal | Tighter with Balanced |
| M1 Pro | 16 GB | Minimal | Single model handles all |
| M1 | 8 GB | Minimal | 7B Q4 model, expect slower |

Peak memory with all models loaded: ~25 GB. ModelRegistry limits to 1 loaded at a time via LRU eviction (5-minute idle timeout), so typical runtime memory is 4–8 GB.

---

## Development

```bash
# Clone and set up
git clone https://github.com/yourusername/objective03.git
cd objective03
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[tts,dev]"

# Run tests
pytest
pytest --cov=src

# Lint and type check
ruff check src
mypy src

# Run in development mode (terminal UI)
objective03 run --dashboard

# Electron frontend (separate terminal)
cd electron
npm install
npm run dev
```

### Building the DMG

```bash
cd electron
npm run electron:build:mac
# Output: electron/release/objective03-0.1.0-arm64.dmg
```

The build process:
1. Vite bundles the React app + Electron main process
2. electron-builder packages into a `.app` bundle
3. Python source (`src/`, `backend/`, `prompts/`, `config.yaml`) is copied into `Resources/backend/`
4. DMG is created with custom background and `/Applications` symlink
5. Notarization is attempted if a Developer ID certificate is available

### macOS Specifics

- **Data directory**: `~/Library/Application Support/objective03`
- **Setup marker**: `~/Library/Application Support/objective03/setup-complete.json` (delete to re-run wizard)
- **Config**: `~/Library/Application Support/objective03/config.yaml`
- **Broadcasts**: `~/Library/Application Support/objective03/audio/queue/` and `archive/`
- **Auto-migration**: Legacy `~/.objective03/` data is migrated on first run
- **Audio playback**: Uses macOS `afplay` subprocess
- **Python detection**: Probes `.venv/bin/python3`, `/opt/homebrew/bin/python3` (versions 3.11–3.14), `/usr/local/bin/python3`, `python3`

---

## Project Status

**Phase:** Desktop application implementation complete. Python pipeline is stable and deterministic. Electron frontend supports all major workflows: wizard setup, dashboard monitoring, broadcast generation and playback, model management, source editing, voice switching, and prompt editing.

**Stability:** Alpha. Core pipeline logic is tested and deterministic, but hasn't been soak-tested against live feeds for extended periods.

### Roadmap

- **Soak testing** — Extended 7+ day runs against live feeds
- **Code signing** — Re-enable notarization for Gatekeeper-clean installs
- **Universal binary** — arm64 + x86_64 build
- **Auto-updater** — electron-updater integration for seamless updates
- **System tray** — Menu bar icon with background operation
- **Enhanced playback** — Multi-voice TTS, dynamic ambient mixing, crossfade controls
- **Model verification** — SHA-256 checksum validation after download
- **Contradiction tuning** — False-positive reduction through prompt refinement
- **Performance profiling** — Sustained load testing and memory optimization

---

## License

MIT. Models have their own licenses: Qwen (Apache 2.0), Llama (Llama Community License), BGE (MIT).

---

## Acknowledgments

- [llama.cpp](https://github.com/ggerganov/llama.cpp) — Local LLM inference with Metal GPU
- [KuzuDB](https://kuzudb.com/) — Embedded columnar graph database
- [hnswlib](https://github.com/nmslib/hnswlib) — In-process HNSW vector search
- [mlx-audio](https://github.com/ml-explore/mlx-audio) — Qwen3-TTS voice synthesis on Apple Silicon
- [FastAPI](https://fastapi.tiangolo.com/) — Python backend framework
- [Electron](https://www.electronjs.org/) — Desktop application shell
- [React](https://react.dev/) / [React Router](https://reactrouter.com/) — Frontend framework
- [TailwindCSS](https://tailwindcss.com/) — Utility-first CSS
- [Lucide](https://lucide.dev/) — Icons
- [Vite](https://vitejs.dev/) — Build tooling
