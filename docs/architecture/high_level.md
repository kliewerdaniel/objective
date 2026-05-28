# High-Level Architecture

## System Boundaries

objective03 is a single-machine, multi-process system designed for Apple Silicon. All components run locally. No cloud dependencies.

```
┌────────────────────────────────────────────────────────────────────┐
│                     objective03 SYSTEM BOUNDARY                     │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                     DAEMON ORCHESTRATOR                       │  │
│  │  (process lifecycle, scheduling, health, signal handling)    │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐│
│  │INGESTION │ │  CLAIM   │ │  GRAPH   │ │BROADCAST │ │  AUDIO   ││
│  │ MODULE   │ │  ENGINE  │ │  MEMORY  │ │ ENGINE   │ │  ENGINE  ││
│  │          │ │          │ │          │ │          │ │          ││
│  │ RSS      │ │ Extract  │ │ KuzuDB   │ │ Script   │ │ TTS      ││
│  │ Reddit   │ │ Entities │ │ Qdrant   │ │ Writer   │ │ FFmpeg   ││
│  │ YouTube  │ │ Claims   │ │ SQLite   │ │ Queue    │ │ Player   ││
│  │ Gov      │ │ Stance   │ │          │ │          │ │          ││
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘│
│                                                                    │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                    TERMINAL DASHBOARD                         │  │
│  │  (Textual live view: metrics, feeds, graph stats, status)    │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

## Process Architecture

The system runs as a single process with async task scheduling. The main process manages:

1. **Orchestrator** — Lifecycle manager, starts/stops components, handles signals
2. **Scheduler** — Periodic task runner with configurable cadences
3. **Pipeline workers** — Sequential execution of ingestion → extraction → graph update → analysis → broadcast
4. **Audio player** — Separate thread for continuous audio output
5. **Terminal UI** — Async Textual application rendering live state

### Thread Model

```
┌──────────────────────────────────────────────────────────────────┐
│                        MAIN PROCESS                              │
│                                                                  │
│  ┌────────────────────┐  ┌────────────────────┐                  │
│  │   Event Loop        │  │   Scheduler        │                 │
│  │   (asyncio)         │  │   (asyncio)        │                 │
│  │   • Pipeline tasks  │  │   • Ingestion tick │                 │
│  │   • Health checks   │  │   • Analysis tick  │                 │
│  │   • UI updates      │  │   • Broadcast tick │                 │
│  └────────────────────┘  └────────────────────┘                  │
│                                                                  │
│  ┌────────────────────┐  ┌────────────────────┐                  │
│  │   LLM Thread Pool   │  │   Audio Thread     │                 │
│  │   (concurrent.futures)│  │   (dedicated)      │                │
│  │   • Model inference │  │   • TTS generation │                 │
│  │   • Embeddings      │  │   • Playback       │                 │
│  │   • Classification  │  │   • Queue mgmt     │                 │
│  └────────────────────┘  └────────────────────┘                  │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │                   Shared State                              │   │
│  │  (thread-safe in-memory state + SQLite + KuzuDB + Qdrant)  │   │
│  └───────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

### Orchestrator (`src/daemon/orchestrator.py`)

- Loads configuration
- Initializes all database connections
- Starts the scheduler
- Manages component lifecycle
- Handles SIGINT/SIGTERM for graceful shutdown
- Restarts failed components

### Scheduler (`src/agents/scheduler_daemon.py`)

- Runs ingestion on configurable intervals (default: every 5-15 minutes)
- Runs analysis on configurable intervals (default: every 30-60 minutes)
- Runs broadcast generation on configurable intervals (default: every 15-30 minutes)
- Runs memory consolidation on configurable intervals (default: every 24 hours)
- Runs health checks on configurable intervals (default: every 60 seconds)

### Pipeline Workers

Executed sequentially per cycle:
1. **Ingestion Poll** — Check all sources for new content
2. **Document Processing** — Normalize, dedup, extract
3. **Graph Update** — Insert extracted claims, entities, relationships
4. **Contradiction Detection** — Identify contradictions among new claims
5. **Analysis** — Narrative drift, framing, source reliability
6. **Broadcast Generation** — Synthesize scripts from graph
7. **Audio Production** — Render scripts to audio

### Audio Player

- Separate thread with its own event loop
- Manages audio queue
- Pre-generates upcoming segments during idle time
- Handles playback via sounddevice or PyAudio

### Terminal UI

- Textual async application
- Reads shared state (metrics, status, logs)
- Updates display on configurable interval (default: every 1 second)

## Configuration Model

```yaml
# config.yaml — top-level system configuration
system:
  name: "objective03"
  data_dir: "~/.objective03"
  log_level: "INFO"

daemon:
  health_check_interval: 60
  restart_delay: 5
  max_restarts: 3

scheduler:
  ingestion_interval: 300        # 5 minutes
  analysis_interval: 1800        # 30 minutes
  broadcast_interval: 900        # 15 minutes
  consolidation_interval: 86400  # 24 hours

databases:
  graph:
    path: "~/.objective03/graph.db"   # KuzuDB file
  vector:
    host: "localhost"
    port: 6333
    collection: "objective03"
  metadata:
    path: "~/.objective03/metadata.db" # SQLite file

models:
  extraction:
    path: "models/qwen2.5-7b-instruct-q4.gguf"
    context: 4096
    gpu_layers: 32
  reasoning:
    path: "models/llama-3.1-8b-instruct-q4.gguf"
    context: 8192
    gpu_layers: 32
  embedding:
    path: "models/bge-small-en-v1.5-q4.gguf"
    context: 512
    gpu_layers: 0
  classification:
    path: "models/qwen2.5-3b-instruct-q4.gguf"
    context: 2048
    gpu_layers: 32

audio:
  tts:
    engine: "piper"
    model: "models/piper/en_US-lessac-medium.onnx"
    voice: "en_US-lessac-medium"
    rate: 1.0
  output:
    device: "default"
    sample_rate: 22050
    channels: 1
  atmosphere:
    enabled: true
    background: "ambient/cold_hum.wav"
    transition_duration: 3.0

ui:
  refresh_interval: 1.0
  theme: "dark"
  panels:
    - "ingestion"
    - "graph"
    - "broadcast"
    - "metrics"
    - "log"

sources:
  rss:
    feeds:
      - url: "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"
        name: "NYT World"
        interval: 600
      - url: "https://feeds.bbci.co.uk/news/world/rss.xml"
        name: "BBC World"
        interval: 600
      # ... additional feeds
  reddit:
    subreddits:
      - name: "worldnews"
        sort: "hot"
        limit: 25
        interval: 900
      - name: "geopolitics"
        sort: "new"
        limit: 25
        interval: 900
  youtube:
    channels:
      - id: "UC..."  # Channel ID
        interval: 3600
```

## Data Directory Structure

```
~/.objective03/
├── config.yaml              # Main configuration (user-editable)
├── graph.db                 # KuzuDB database file
├── metadata.db              # SQLite database file
├── audio/
│   ├── cache/               # Cached TTS output
│   ├── queue/               # Queued broadcast segments
│   └── archive/             # Historical broadcasts
├── models/
│   ├── qwen2.5-7b-instruct-q4.gguf
│   ├── llama-3.1-8b-instruct-q4.gguf
│   ├── bge-small-en-v1.5-q4.gguf
│   ├── piper/
│   │   ├── en_US-lessac-medium.onnx
│   │   └── en_US-lessac-medium.onnx.json
│   └── ambient/
│       └── cold_hum.wav
├── logs/
│   ├── objective03.log
│   └── audit.log
└── state/
    ├── ingestion_cursors.json
    └── scheduler_state.json
```
