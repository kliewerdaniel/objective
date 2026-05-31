# Frontend Architecture Plan

## Overview

Transform objective03 from a terminal-only daemon into a desktop app with a graphical control surface using Electron + React + FastAPI.

## Architecture

```
┌──────────────────────────────────────────────────┐
│              Electron Main Process               │
│  - Creates BrowserWindow                          │
│  - Manages app lifecycle                          │
│  - Spawns Python backend as child process         │
│  - Proxies health checks                          │
└──────────────┬───────────────────────────────────┘
               │ BrowserWindow (Renderer)
┌──────────────▼───────────────────────────────────┐
│              React App (Vite + TypeScript)        │
│                                                   │
│  ┌─────────────┐ ┌───────────┐ ┌──────────────┐  │
│  │  Dashboard   │ │  Voice    │ │  Prompts     │  │
│  │  - Status    │ │  Switcher │ │  Editor      │  │
│  │  - Metrics   │ │  - List   │ │  - Monaco    │  │
│  │  - Activity  │ │  - Select │ │  - Tree nav  │  │
│  │  - SSE feed  │ │  - Preview│ │  - Save      │  │
│  ├─────────────┤ ├───────────┤ ├──────────────┤  │
│  │  Models     │ │  Config   │ │  Audio       │  │
│  │  Manager    │ │  Editor   │ │  Monitor     │  │
│  │  - Browse   │ │  - Form   │ │  - Queue     │  │
│  │  - Assign   │ │  - YAML   │ │  - Now       │  │
│  │  - Grid     │ │  - Save   │ │    playing   │  │
│  └─────────────┘ └───────────┘ └──────────────┘  │
│                                                   │
│  UI: Tailwind CSS, shadcn/ui, Recharts            │
└──────────────┬───────────────────────────────────┘
               │ HTTP + SSE (localhost:8510)
┌──────────────▼───────────────────────────────────┐
│          Python Backend (FastAPI + Uvicorn)        │
│                                                   │
│  ┌──────────────────────────────────────────────┐ │
│  │  API Routes                                  │ │
│  │  GET  /api/status          — system state    │ │
│  │  GET  /api/metrics         — graph metrics    │ │
│  │  GET  /api/activity        — activity log     │ │
│  │  GET  /api/config          — full config      │ │
│  │  PUT  /api/config          — update config    │ │
│  │  GET  /api/voices          — list voices      │ │
│  │  PUT  /api/config/voice    — set voice        │ │
│  │  GET  /api/models          — list .gguf files │ │
│  │  GET  /api/models/folder   — scan custom dir  │ │
│  │  PUT  /api/models/assign   — assign to task   │ │
│  │  GET  /api/prompts         — list prompts     │ │
│  │  GET  /api/prompts/{name}  — get prompt text  │ │
│  │  PUT  /api/prompts/{name}  — update prompt    │ │
│  │  SSE  /api/events          — real-time stream │ │
│  └──────────────────────────────────────────────┘ │
│           ↕ in-process shared state                │
│  ┌──────────────────────────────────────────────┐ │
│  │      Main Daemon Process                     │ │
│  │  - Orchestrator with all components          │ │
│  │  - Graph store, vector store, metadata       │ │
│  │  - Model registry, TTS, audio pipeline       │ │
│  │  - Scheduler with all agents                 │ │
│  └──────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

## Directory Structure (new files)

```
objective03/
├── backend/                       # Python backend
│   ├── __init__.py
│   ├── server.py                  # FastAPI app + routes
│   └── events.py                  # SSE event manager
│
├── prompts/                       # Externalized prompt files
│   ├── broadcast_writer.md
│   ├── claim_extractor.md
│   ├── entity_extractor.md
│   ├── contradiction_detector.md
│   ├── framing_analyzer.md
│   ├── narrative_analyzer.md
│   └── source_reliability.md
│
├── electron/                      # Electron app
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── postcss.config.js
│   ├── index.html
│   ├── electron/
│   │   ├── main.ts               # Electron main process
│   │   └── preload.ts            # Preload script
│   └── src/
│       ├── main.tsx              # React entry
│       ├── App.tsx               # Router + layout
│       ├── lib/
│       │   └── api.ts            # API client
│       ├── components/
│       │   ├── layout.tsx        # Sidebar + main
│       │   └── ui/               # shadcn/ui components
│       └── pages/
│           ├── Dashboard.tsx
│           ├── VoiceSwitcher.tsx
│           ├── PromptEditor.tsx
│           ├── ModelManager.tsx
│           └── ConfigEditor.tsx
```

## Key Implementation Details

### 1. Prompt Externalization
- Each agent gets a prompt file in `prompts/<agent_name>.md`
- Agent code loads prompt from file at runtime, falls back to compiled-in string
- Backend reads/writes files directly
- Prompt files are tracked in git (they're configuration, not generated)

### 2. Voice Switching
- `QwenTTS` resolves voice at synthesis time from `_ref_audio_path`
- Switching voice = update `config.tts.voice` + re-init `_ref_audio_path` and `_ref_text`
- Backend handles TTS re-initialization transparently

### 3. Model Management
- `ModelRegistry.get(task)` loads model by `config.models[task].path`
- Assigning a new model = update `config.models[task].path` + invalidate cache
- GPU layers and context size editable per-task

### 4. Real-time Updates
- SSE endpoint streams: system state changes, metrics, activity log entries
- React frontend uses EventSource to consume stream
- Dashboard updates automatically without polling

### 5. Electron Packaging
- `electron-builder` creates distributable `.dmg` (macOS) / `.AppImage` (Linux)
- Python backend bundled as a PyInstaller binary or launched from system Python
- On first launch, setup script installs Python deps if needed
