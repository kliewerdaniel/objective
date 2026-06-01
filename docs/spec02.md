Looking at this codebase, I'll write a comprehensive spec for transforming objective03 into a polished, distributable macOS desktop application.

---

# objective03 — Desktop Distribution & UX Transformation Spec

## Executive Summary

objective03 is architecturally complete but operationally hostile to anyone who didn't write it. The Python daemon, Electron frontend, manual Qdrant setup, GGUF model downloads, and scattered config files create a barrier that makes the project inaccessible to its intended audience: technically curious people who want a self-hosted AI broadcast system, not a devops project.

This spec defines the full transformation of objective03 from a developer-only system into a distributable, self-contained macOS desktop application delivered as a signed `.dmg`. The resulting app should be installable by dragging to `/Applications`, launchable by double-clicking, and operational within a guided first-run wizard — without any terminal interaction required.

The architecture remains local-first and privacy-preserving. No cloud dependencies are introduced. The aesthetic character of the system — cold, detached, synthetic — is preserved and elevated in the UI.

---

## Part 1: Distribution Format & Platform Targets

### 1.1 Primary Target: macOS Universal DMG

The primary distribution artifact is a notarized, signed macOS `.dmg` containing a universal binary application bundle (`objective03.app`) that runs natively on both Apple Silicon (arm64) and Intel (x86_64).

**File structure of the DMG:**
```
objective03 1.0.0.dmg
├── objective03.app/
│   └── Contents/
│       ├── Info.plist
│       ├── MacOS/
│       │   └── objective03          (Electron main binary, universal)
│       ├── Resources/
│       │   ├── app.asar             (React frontend code)
│       │   ├── backend/             (Python source)
│       │   ├── python/              (embedded Python runtime)
│       │   ├── bin/                 (ffmpeg, bundled binaries)
│       │   └── assets/
│       │       ├── icons/
│       │       └── sounds/          (ambient WAV files)
│       └── _CodeSignature/
└── Applications (alias → /Applications)
```

**DMG visual design:** Dark background matching the app's color scheme (`#0a0a0a`), custom volume icon, drag-target arrow animation. The DMG window opens at 660×400 with the app icon and Applications alias visible.

### 1.2 Platform Matrix

| Platform | Format | Priority | Notes |
|----------|--------|----------|-------|
| macOS 14+ arm64 | `.dmg` (primary) | P0 | Apple Silicon, Metal GPU |
| macOS 13+ x86_64 | `.dmg` (universal) | P0 | Intel fallback |
| macOS 12 | `.dmg` | P1 | Reduced feature set (no Qwen3-TTS) |
| Windows 11 | `.exe` NSIS installer | P2 | Phase 2, CUDA GPU path |
| Linux x86_64 | `.AppImage` | P2 | Phase 2, no audio |

This spec focuses entirely on P0: the macOS DMG.

### 1.3 Version Naming Convention

Releases follow semantic versioning: `MAJOR.MINOR.PATCH`. Pre-release builds append `-beta.N` or `-alpha.N`. The DMG filename is `objective03-{version}-{arch}.dmg`, e.g. `objective03-1.0.0-universal.dmg`.

---

## Part 2: Python Runtime Bundling

The single most complex aspect of distribution is eliminating the requirement for a system Python. The app must carry its own Python runtime.

### 2.1 Embedded Python Strategy

Use `python-build-standalone` (the same runtime used by Rye, uv, and Astral's toolchain) to embed a fully self-contained Python 3.12 runtime inside the app bundle. This avoids the brittleness of PyInstaller and the complexity of Conda.

**Build process:**
1. Download `cpython-3.12.x+{build}-{arch}-apple-darwin-install_only.tar.gz` from `github.com/indygreg/python-build-standalone/releases`
2. Extract into `Contents/Resources/python/`
3. Install all Python dependencies into that embedded runtime's `site-packages` using `pip install --target`
4. Patch shebangs and `.pth` files
5. Sign the Python runtime before code-signing the app

**Dependencies installed into embedded runtime:**
```
kuzu>=0.7
qdrant-client>=1.9
llama-cpp-python>=0.2 (compiled with Metal support)
textual>=0.52
rich>=13.7
structlog>=24.1
aiohttp>=3.9
feedparser>=6.0
asyncpraw>=7.7
yt-dlp>=2024.4
pydantic>=2.6
pyyaml>=6.0
sounddevice>=0.4
soundfile>=0.12
numpy>=1.26
scipy>=1.12
psutil>=5.9
fastapi>=0.109
uvicorn>=0.27
mlx-audio>=0.4.2
huggingface-hub>=0.23
```

**Critical:** `llama-cpp-python` must be compiled with `CMAKE_ARGS="-DGGML_METAL=on"` and linked against the system's Metal framework. This produces `.so` files that must be re-signed with the app's certificate.

### 2.2 llama.cpp Metal Compilation

`llama-cpp-python` compiles a C++ extension at install time. For bundling:

1. Build on a clean arm64 macOS machine (or GitHub Actions macOS runner)
2. Set `MACOSX_DEPLOYMENT_TARGET=13.0`
3. Use `CMAKE_ARGS="-DGGML_METAL=on -DGGML_METAL_EMBED_LIBRARY=on"` to embed the Metal shaders into the binary (critical — avoids runtime shader compilation that fails in sandboxed apps)
4. Strip debug symbols
5. Verify `otool -L` shows only system library dependencies (no homebrew paths)
6. Re-sign with `codesign --deep --force --options runtime --sign "Developer ID Application: ..."` before packaging

### 2.3 Qdrant Bundling

Qdrant is a Rust binary. The current architecture requires a running Qdrant HTTP service. For the bundled app, two options exist:

**Option A (Recommended): Replace Qdrant with hnswlib + SQLite**

For the bundled app, replace the Qdrant dependency entirely with a pure-Python in-process vector index using `hnswlib`. This eliminates a separate process, a network connection, and a Rust binary. Performance at the scale objective03 operates (tens of thousands of vectors) is identical.

The `VectorStore` interface in `src/database/vector.py` remains the same. Swap the implementation:

```python
class VectorStore:
    """hnswlib-backed in-process vector store."""
    
    def __init__(self, vector_size: int = 384, **kwargs):
        import hnswlib
        self.vector_size = vector_size
        self._index = hnswlib.Index(space='cosine', dim=vector_size)
        self._index.init_index(max_elements=100000, ef_construction=200, M=16)
        self._id_map: dict[str, int] = {}  # str id -> int label
        self._reverse_map: dict[int, str] = {}
        self._payloads: dict[int, dict] = {}
        self._next_label = 0
        self._persist_path = kwargs.get('persist_path')
        self._load()
```

This completely eliminates the Qdrant subprocess and port dependency.

**Option B: Bundle Qdrant binary**

Include the `qdrant` binary (signed and notarized) in `Contents/MacOS/qdrant` and launch it as a child process from the Electron main process, using a random available port, storing data in `~/Library/Application Support/objective03/qdrant/`.

Option A is recommended for the initial distribution. Option B can be used if the llama.cpp integration requires semantic similarity at scale that hnswlib cannot match.

### 2.4 Build Script Architecture

A `scripts/build-macos.sh` script orchestrates the entire build:

```bash
#!/usr/bin/env bash
# 1. Build Electron/React frontend (npm run build)
# 2. Download python-build-standalone
# 3. Install Python deps into embedded runtime
# 4. Compile llama-cpp-python with Metal
# 5. Bundle ffmpeg (static build from evermeet.cx/ffmpeg)
# 6. Run electron-builder
# 7. Sign app bundle (codesign)
# 8. Notarize with notarytool
# 9. Staple notarization ticket
# 10. Create DMG (electron-builder or create-dmg)
# 11. Sign DMG
```

This script runs in CI (GitHub Actions) and locally.

---

## Part 3: First-Run Wizard

The single biggest UX improvement is eliminating the requirement to manually download models, configure YAML, install Qdrant, and run shell commands before seeing anything work.

### 3.1 Wizard Architecture

The first-run wizard is a multi-step React component rendered in the main Electron window, replacing the normal app UI until setup is complete. It writes to `~/Library/Application Support/objective03/` (not `~/.objective03/` — proper macOS convention for bundled apps).

State is persisted in `~/Library/Application Support/objective03/setup-complete.json`. If this file exists and is valid, the wizard is skipped on subsequent launches.

### 3.2 Wizard Steps

**Step 0: Welcome**

Full-screen dark panel. The objective03 wordmark. Tagline: *"A synthetic epistemology engine masquerading as an infinite radio station."* Single button: **Begin Setup**. No choices yet.

**Step 1: Storage Location**

Show where data will be stored:
- Graph database: `~/Library/Application Support/objective03/graph.db` 
- Audio cache: `~/Library/Application Support/objective03/audio/`
- Models: user-selectable (default: `~/Library/Application Support/objective03/models/`)

The models directory is user-configurable because models are large (4–25 GB) and users may want them on an external drive. A folder picker opens a native macOS file dialog. The selected path is validated for available disk space.

Show estimated disk usage:
- Minimum (single model): ~4 GB
- Recommended (broadcast-quality): ~12 GB  
- Full suite (all 7 slots): ~25 GB

**Step 2: Model Selection**

This is the most important step. Present model tiers as cards:

---
**Tier 1: Minimal** — 4.2 GB download  
*One model handles all tasks. Slower. Lower quality. Works on 8 GB RAM Macs.*  
Model: Qwen2.5-7B-Instruct Q4_K_M

**Tier 2: Balanced** ⭐ Recommended — 11.8 GB download  
*Separate extraction and broadcast models. Good quality on 16 GB RAM Macs.*  
Models: Qwen2.5-7B Q4 (extraction) + Llama-3.1-8B Q4 (broadcast/reasoning) + BGE-Small (embedding)

**Tier 3: Full Suite** — 24.6 GB download  
*All seven task-specific models. Best quality. Requires 32 GB+ RAM.*  
All models from the existing config

---

Each tier shows:
- Download size
- Minimum RAM requirement
- Estimated quality rating (1-5 stars, shown as radio towers)
- Estimated broadcast generation time

The system auto-detects available RAM and highlights the appropriate tier with a "Recommended for your Mac" badge.

**Step 3: Voice Selection**

Play audio samples for each bundled voice. The app ships with 3 reference voices included in the bundle (licensed CC0 or synthesized):

- **Atlas** — Deep, slow, authoritative
- **Meridian** — Mid-range, neutral, flat
- **Cipher** — Slightly higher, clipped, synthetic

Each has a "Preview" button that plays a 10-second demo clip without requiring model download (pre-rendered).

The user can also click "Import Voice" to drop in a custom `.wav` file (minimum 10 seconds of clear speech), which will be used for voice cloning via Qwen3-TTS.

**Step 4: News Sources**

A categorized checklist of pre-configured RSS sources:

**World News**
- [ ] BBC World (https://feeds.bbci.co.uk/news/world/rss.xml)
- [ ] NPR World (https://feeds.npr.org/1004/rss.xml)
- [ ] Reuters World (https://feeds.reuters.com/reuters/worldNews)
- [ ] Al Jazeera English (https://www.aljazeera.com/xml/rss/all.xml)

**US News & Politics**
- [ ] NYT US (https://rss.nytimes.com/services/xml/rss/nyt/US.xml)
- [ ] NPR Politics (https://feeds.npr.org/1014/rss.xml)

**Science & Technology**
- [ ] BBC Science (https://feeds.bbci.co.uk/news/science_and_environment/rss.xml)
- [ ] Ars Technica (https://feeds.arstechnica.com/arstechnica/index)

**Community**
- [ ] r/worldnews (requires no API key, uses JSON API)
- [ ] r/geopolitics

Custom RSS URLs can be added via a text field at the bottom. At least one source must be selected to proceed.

Reddit OAuth is optional. If enabled, a collapsible section explains how to create a Reddit API application (with a direct link to reddit.com/prefs/apps) and fields for client ID and secret.

**Step 5: Download & Setup**

A progress view showing the download and installation of selected models. Each model downloads independently with its own progress bar. Download resumes if interrupted (models are large; resumable downloads are non-negotiable).

Download UI:
```
Downloading models to ~/Library/Application Support/objective03/models/

● Qwen2.5-7B-Instruct Q4_K_M
  ████████████████████░░░░ 78% — 3.2 GB / 4.1 GB — 12 MB/s — 1m 23s remaining

● BGE-Small-EN-v1.5
  ████████████████████████ Done — 91 MB

○ Llama-3.1-8B-Instruct Q4_K_M
  Queued

Initializing graph database...        ✓
Initializing metadata store...        ✓
```

Downloads use the HuggingFace Hub API with proper resume support via HTTP Range requests. Failed downloads show a retry button per-model.

**Step 6: Complete**

Confirmation screen:
- Summary of what was configured
- Estimated time to first broadcast: "Your first broadcast will generate in approximately 3-5 minutes after ingestion begins"
- **Launch objective03** button

The wizard writes `setup-complete.json` with the configuration choices and transitions to the main app.

### 3.3 Wizard State Persistence

If the user quits mid-wizard, their progress is saved. On relaunch, they return to the step they were on. This is important because model downloads take time.

---

## Part 4: Main Application UX Redesign

The current Electron frontend is functional but sparse. This section defines a comprehensive UX redesign that surfaces the system's capabilities clearly.

### 4.1 Navigation Restructure

Replace the current 5-item sidebar with a 4-section structure:

```
● LIVE          (pulsing when playing)
─────────────
  Dashboard
  Broadcast
─────────────
  Configure
    Sources
    Models  
    Voice
    Prompts
    Advanced
─────────────
  History
─────────────
```

The sidebar is 200px wide, collapsible to 48px (icon-only mode), with keyboard shortcut `⌘\` to toggle.

### 4.2 Dashboard Page (Redesign)

The dashboard is the primary status view. It should communicate the system's state at a glance without requiring the user to interpret raw numbers.

**Layout: Three-row design**

**Row 1: System Health Bar (60px)**

A thin full-width bar at the top with:
- Left: Status indicator — `● RUNNING` (green) / `● DEGRADED` (amber) / `● IDLE` (gray)
- Center: Activity pulse — a small animated waveform that reflects ingestion activity, brightening when new documents arrive
- Right: Quick stats — `127 events · 892 contradictions · 43 narratives`

**Row 2: Primary Content (flex, ~60% height)**

Split into two columns:

*Left column: "What the system is thinking"*

A scrollable feed of the most recent significant events detected by the pipeline. Each entry:
```
┌─────────────────────────────────────────┐
│  ▲ EMERGING  Eastern Mediterranean      │
│  Maritime Dispute                       │
│  12 claims · 3 sources · 2 contradicts │
│  Confidence: 74% · Drift: +0.12        │
│  47 min ago                             │
└─────────────────────────────────────────┘
```

Color-coded left border: green (high confidence), amber (contradicted), red (rapidly drifting).

Clicking an event expands a detail panel showing:
- All claims sorted by confidence
- Contradictions with both sides displayed side-by-side
- Source trust scores
- Entity mentions
- Narrative thread assignment

*Right column: "Epistemic state"*

A compact view of the system's current uncertainty profile:
```
CONTRADICTION DENSITY
██████████░░░░░░  62% of events contested

NARRATIVE DRIFT  (last 24h)
↑ Accelerating in 3 threads
→ Stable in 7 threads  
↓ Resolving in 1 thread

SOURCE RELIABILITY
BBC World      ████████░░  0.79
NPR News       ███████░░░  0.71
r/worldnews    ████░░░░░░  0.41
Al Jazeera     ██████░░░░  0.65

ACTIVE CLAIMS
14,892  (+247 last hour)
```

**Row 3: Activity Stream (20% height, collapsible)**

Live log of pipeline events, replacing the current "Event Log" panel. Filterable by category (ingestion, extraction, analysis, broadcast, error). Shows timestamps, event type, and brief description. Scrolls automatically but can be paused.

### 4.3 Broadcast Page (Complete Redesign)

The broadcast page is the primary user-facing feature — this is where the system's output becomes tangible. It deserves the most design attention.

**Full redesign: Four-quadrant layout**

```
┌──────────────────────┬─────────────────────┐
│                      │                     │
│   NOW PLAYING        │   PIPELINE STATUS   │
│   (40% width)        │   (60% width)       │
│                      │                     │
├──────────────────────┴─────────────────────┤
│                                            │
│   BROADCAST HISTORY                        │
│   (full width, scrollable)                 │
│                                            │
└────────────────────────────────────────────┘
```

**Now Playing Panel**

When a broadcast is playing:

```
▶ BROADCAST #142
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  objective03. System time: 14:30 UTC.

  Across fourteen independent sources,
  confidence in the official narrative 
  surrounding the Eastern Mediterranean
  maritime incident has declined twenty-
  three percent over the last forty-eight
  hours...

  [rolling text, synchronized to audio]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  2:14 ████████████████████░░░░ 4:37

  [■ STOP]    [↩ REPLAY]    [⬇ SAVE]
```

The rolling text display shows the current sentence being spoken, highlighted in the full script context. This is the most ambitious feature: synchronize TTS playback position with script text display. Implementation uses the duration of each sentence (estimated at 150 words/minute) to advance a cursor through the script segments.

When nothing is playing:
```
○ NO BROADCAST PLAYING

  The system is monitoring 127 active events.
  Next broadcast generates in 8 minutes.

  [▶ GENERATE NOW]
```

**Pipeline Status Panel**

Replace the current stage list with a visual pipeline diagram:

```
INGESTION      ANALYSIS       OUTPUT
─────────      ────────       ──────
[BBC World] ─→ [Claims]   ─→ [Script]
[NPR News]  ─→ [Entities] ─→ [TTS]
[r/world]   ─→ [Events]   ─→ [Audio]
            ─→ [Contras]
            ─→ [Narrat.]

Last cycle: 47 docs → 312 claims → 3m 24s ago
Next cycle: 13m 16s
```

Each node in the diagram pulses briefly when active. Failed nodes show red with an error count badge. Clicking any node opens a detail popover with the last 10 operations and their outcomes.

The "Generate Now" button triggers the full pipeline. It should be prominent but not disruptive — place it at the top right of the pipeline panel with a keyboard shortcut `⌘G`.

**Broadcast History Panel**

The existing broadcast list, significantly improved:

- Group by date (Today, Yesterday, This Week, Earlier)
- Each entry shows: waveform thumbnail (computed from audio), duration, title (editable), claim count, contradiction count
- Filter bar: All / Today / Favorites
- Sort: Newest first / Oldest first / By duration
- Batch select + delete
- Export selection as ZIP containing WAV files

The waveform thumbnail is a 120×32px SVG generated by sampling the audio file's amplitude at 120 points. This can be computed lazily (on hover or in background after recording).

### 4.4 Sources Page (New)

A dedicated, full-featured source management page replacing the YAML-based config for sources.

**Three sections:**

*Active Sources:*
A live table with columns: Name | Type | Last Polled | Documents Today | Trust Score | Status | Actions

Each row has inline controls:
- Toggle on/off (affects scheduler)
- Edit (opens inline editing)
- Delete

*Add Source:*
A form with type selector (RSS / Reddit / YouTube / Custom) that dynamically shows the relevant fields. For RSS: URL field with live validation (fetch and parse the feed on blur, show feed title and first 3 items as preview). For Reddit: subreddit name field with a "Test connection" button. For YouTube: channel URL or handle field.

*Recommended Sources:*
A curated list of additional sources the user hasn't added yet, grouped by category. Each has an "+ Add" button. The list is bundled with the app (not fetched remotely) and updated with each app release.

### 4.5 Models Page (Redesign)

The current models page is functional but requires knowing model paths. The redesigned version abstracts this away.

**Layout: Three tabs**

*Installed:*
Grid of task cards, one per slot (extraction, entity, reasoning, broadcast, contradiction, classification, embedding). Each card:
```
┌─────────────────────────────────────┐
│  EXTRACTION                         │
│  Qwen2.5-7B-Instruct Q4_K_M        │
│  ████████████████████ 4.1 GB        │
│                                     │
│  Context: 4096    GPU Layers: 32    │
│  Last used: 12m ago                 │
│  [Replace]                          │
└─────────────────────────────────────┘
```

*Available (Download):*
A catalog of supported models, organized by task slot and tier. Each entry shows model name, parameter count, quantization, size, estimated quality (stars), RAM requirement, and a download button. The catalog is bundled with the app.

*Custom:*
A file drop zone for `.gguf` files. Drop a model, see its metadata parsed from the GGUF header (model name, architecture, context length, embedding dimension), then assign it to a task slot.

### 4.6 Voice Page (Redesign)

The voice page currently shows a grid of cards. The redesigned version adds a proper preview and recording capability.

**Layout:**

*Current Voice:*
Large card showing the active voice with a waveform visualization and a "Preview" button that generates a 10-second test clip using the current news summary. The test clip generation runs through the full TTS pipeline in the background.

*Available Voices:*
Grid of voice cards with:
- Waveform thumbnail
- Duration of reference audio
- Preview button (plays pre-rendered demo)
- A/B compare button (plays two voices back-to-back with the same text)

*Import Voice:*
Drag-and-drop zone for `.wav`, `.mp3`, `.flac` files. After import:
1. Show audio waveform
2. Show detected duration (must be ≥10 seconds, recommend 30-60 seconds)
3. "Test synthesis" — generates a 20-second clip using this voice
4. "Save as voice" — prompts for a name

*Record Voice:*
A microphone recording interface (uses native macOS audio input). Records up to 60 seconds, shows a live waveform, has start/stop/review controls. After recording, follows the same flow as Import.

### 4.7 Advanced Config Page

Replace the raw YAML editor with a structured form. The YAML editor remains accessible as a tab for power users, but the primary interface is form-based.

**Sections:**

*Scheduler Intervals:*
Sliders with sensible min/max/default:
- Ingestion interval: 1m — 60m (default 5m)
- Analysis interval: 5m — 4h (default 30m)
- Broadcast interval: 5m — 2h (default 15m)

*Broadcast Settings:*
- Broadcast length: Short (3-5min) / Standard (8-12min) / Long (15-20min)
- Language: English only (v1.0), more in future
- Tone: Analytical (current) / Archival / Cold

*Storage:*
- Models directory: path picker
- Audio archive: path picker
- Graph database: path picker (not recommended to change)
- Clear audio cache button (shows cache size)
- Export graph data button (writes JSON)

*Advanced (collapsible):*
- Raw YAML editor (with syntax highlighting via CodeMirror lite)
- Log level selector
- Restart daemon button

---

## Part 5: System Tray Integration

A macOS menu bar extra provides always-accessible controls without requiring the main window to be open.

### 5.1 Menu Bar Icon

A custom icon: a minimalist radio tower with a pulsing dot at the top. The dot pulses green when a broadcast is playing, amber when the pipeline is running, gray when idle. The icon is 18×18px, rendered as a template image (adapts to light/dark menu bar automatically).

### 5.2 Menu Bar Menu

```
objective03
─────────────
● PLAYING: Broadcast #142 (2:14 / 4:37)
  [■ Stop]

─────────────
Next broadcast: 8 minutes

─────────────
Events tracked: 127
Claims: 14,892
Last update: 3 minutes ago

─────────────
[▶ Generate Broadcast]
[○ Open objective03]
[⚙ Preferences]
─────────────
[Quit]
```

The "Playing" section only appears when audio is active. Clicking "Open objective03" brings the main window to focus, creating it if needed.

### 5.3 Notifications

Use macOS UserNotifications framework (via Electron) for:
- **First broadcast ready** (on initial setup): "Your first broadcast is ready. Click to listen."
- **Significant event detected** (optional, user-controlled): "Significant narrative drift detected in [topic]."
- **Contradiction found** (optional): "New contradiction: [truncated claim A] vs [truncated claim B]"
- **Error** (non-dismissible): "Pipeline error: [brief description]. Click to view."

Notification frequency is configurable. Default: only "first broadcast ready" and errors.

---

## Part 6: Launch & Lifecycle Management

### 6.1 App Launch Sequence

When the user double-clicks `objective03.app`:

1. Electron main process starts
2. Check for `setup-complete.json` — if missing, launch wizard
3. If setup complete: start the Python backend subprocess
4. Show a loading splash screen (the wordmark, animated) while the backend initializes
5. Backend emits a ready signal via its `/api/status` endpoint
6. Hide splash screen, show main app

The splash screen has a timeout: if the backend doesn't respond within 30 seconds, show an error with diagnostic information.

### 6.2 Backend Process Management

The Python backend (`uvicorn backend.server:app`) runs as a child process of the Electron main process. Critical details:

- **Port assignment:** The backend picks a random available port on startup (not hardcoded 8510) to avoid conflicts. The port is written to a temp file that the Electron process reads.
- **Stdio:** stdout and stderr are captured by Electron and shown in the app's log viewer (accessible via Help > Show Logs)
- **Crash recovery:** If the backend process exits unexpectedly, Electron restarts it automatically (up to 3 times, then shows an error)
- **Graceful shutdown:** When the user quits the app, Electron sends SIGTERM to the backend and waits up to 5 seconds for it to flush state before SIGKILL

The backend process is launched with:
```javascript
const backendProcess = spawn(
  embeddedPython, 
  ['-m', 'uvicorn', 'backend.server:app', '--host', '127.0.0.1', '--port', String(port)],
  {
    cwd: resourcesPath,
    env: {
      ...process.env,
      PYTHONPATH: resourcesPath,
      OBJECTIVE03_DATA_DIR: userDataPath,
      OBJECTIVE03_MODELS_DIR: modelsPath,
      OBJECTIVE03_CONFIG: configPath,
      PYTHONUNBUFFERED: '1',
    }
  }
)
```

### 6.3 Auto-Launch on Login

The app offers to enable auto-launch on login during the final wizard step. This uses `app.setLoginItemSettings()` in Electron. When auto-launched, the app starts minimized (no main window, only menu bar icon) and begins the pipeline immediately.

### 6.4 Update Mechanism

Use `electron-updater` with a self-hosted update server (or GitHub Releases). On startup, the app checks for updates in the background. When an update is available, a non-intrusive banner appears at the top of the dashboard:

```
objective03 1.1.0 is available — [View release notes] [Update and restart]
```

Updates download in the background. Installation requires a restart but does not wipe data or models.

The update check pings `https://updates.objective03.app/latest.json` (a static JSON file). If the server is unavailable, the check fails silently.

---

## Part 7: Data Directory Structure

The macOS-conventional data directory replaces `~/.objective03/`:

```
~/Library/Application Support/objective03/
├── setup-complete.json
├── config.yaml
├── graph.db                 (KuzuDB)
├── metadata.db              (SQLite)
├── models/                  (user-configurable location)
│   ├── qwen2.5-7b-instruct-q4_k_m.gguf
│   ├── llama-3.1-8b-instruct-q4_k_m.gguf
│   └── bge-small-en-v1.5-q4.gguf
├── voices/
│   ├── atlas.wav            (bundled, extracted on first run)
│   ├── meridian.wav
│   ├── cipher.wav
│   └── custom/              (user-imported)
├── audio/
│   ├── cache/
│   ├── queue/
│   └── archive/
├── logs/
│   ├── backend.log          (rotating, max 50MB)
│   └── electron.log
└── backups/
    └── graph-{date}.db.gz
```

~/Library/Caches/objective03/ holds downloaded-but-not-yet-installed model files (safe to delete):
```
~/Library/Caches/objective03/
└── downloads/
    ├── qwen2.5-7b.gguf.partial
    └── manifest.json
```

### 7.1 Migration from `~/.objective03/`

On first launch, if `~/.objective03/` exists but `~/Library/Application Support/objective03/` does not, offer to migrate:

```
Found existing objective03 data at ~/.objective03/

[Migrate to ~/Library/Application Support/objective03/]
[Start fresh]
[Use existing location]   ← keeps old path, not recommended
```

Migration copies graph.db, metadata.db, models/, voices/, and config.yaml. Audio files are not migrated (large, regenerable).

---

## Part 8: Permissions & Entitlements

### 8.1 macOS Sandbox

The app is NOT sandboxed (App Sandbox is disabled). Sandboxing would prevent:
- Reading/writing to arbitrary model directories
- Spawning the uvicorn subprocess
- Metal GPU access from child processes

The app's `entitlements.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "...">
<plist version="1.0">
<dict>
    <key>com.apple.security.cs.allow-jit</key><true/>
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key><true/>
    <key>com.apple.security.cs.disable-library-validation</key><true/>
    <key>com.apple.security.cs.allow-dyld-environment-variables</key><true/>
    <key>com.apple.security.device.audio-input</key><true/>
    <key>com.apple.security.network.client</key><true/>
</dict>
</plist>
```

The `allow-unsigned-executable-memory` and `disable-library-validation` entitlements are required for llama.cpp's JIT Metal shader compilation and for loading unsigned dylibs (compiled Python extensions).

### 8.2 Privacy Permissions

The app requests microphone access (for voice recording). The usage description in `Info.plist`:
> "objective03 uses your microphone to record reference audio for voice cloning. Recordings are processed locally and never transmitted."

Network access is used for RSS polling and model downloads only. No telemetry, no analytics, no cloud sync.

### 8.3 Gatekeeper & Notarization

All binaries must be signed and notarized. Process:
1. Code sign with `Developer ID Application` certificate
2. Submit to Apple's notary service via `xcrun notarytool submit`
3. Wait for approval (typically 1-5 minutes)
4. Staple the notarization ticket to the app and DMG

Without notarization, users see "Apple cannot check it for malicious software" and must right-click > Open, which is too high a barrier.

---

## Part 9: CI/CD Pipeline

### 9.1 GitHub Actions Workflow

`.github/workflows/build-macos.yml`:

```yaml
name: Build macOS DMG

on:
  push:
    tags: ['v*']
  workflow_dispatch:

jobs:
  build:
    runs-on: macos-14  # M1 runner (Apple Silicon)
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          
      - name: Import signing certificate
        env:
          MACOS_CERTIFICATE: ${{ secrets.MACOS_CERTIFICATE }}
          MACOS_CERTIFICATE_PWD: ${{ secrets.MACOS_CERTIFICATE_PWD }}
        run: |
          # Import certificate to keychain
          
      - name: Build Python runtime
        run: |
          scripts/build-python-runtime.sh
          
      - name: Build Electron app
        env:
          APPLE_ID: ${{ secrets.APPLE_ID }}
          APPLE_APP_SPECIFIC_PASSWORD: ${{ secrets.APPLE_APP_SPECIFIC_PASSWORD }}
          APPLE_TEAM_ID: ${{ secrets.APPLE_TEAM_ID }}
        run: |
          cd electron && npm ci && npm run build
          npx electron-builder --mac --universal
          
      - name: Notarize
        run: scripts/notarize.sh
        
      - name: Upload DMG
        uses: actions/upload-artifact@v4
        with:
          name: objective03-dmg
          path: electron/dist/*.dmg
```

### 9.2 Release Pipeline

Tags of the form `v1.2.3` trigger the build. After successful notarization:
1. Upload to GitHub Releases with auto-generated changelog
2. Update `latest.json` on the update server
3. Send notification to a Discord webhook (optional)

---

## Part 10: Error Handling & Diagnostics

### 10.1 Crash Reporter

When the backend crashes or becomes unresponsive, show a modal:

```
objective03 encountered a problem

The analysis engine stopped responding.

[Show diagnostic information]
[Restart engine]
[Quit]
```

"Show diagnostic information" opens a panel with:
- Last 50 lines of backend log
- System information (macOS version, RAM, disk space)
- A "Copy to clipboard" button (for pasting into a bug report)
- A "Send crash report" button (optional, explicitly opt-in, posts to a GitHub issue template)

### 10.2 Model Loading Errors

If a model fails to load (wrong format, corrupted, insufficient RAM):

```
Failed to load broadcast model

Model: qwen2.5-14b-instruct-q4_k_m.gguf
Error: insufficient memory (required: 10.2 GB, available: 7.1 GB)

[Try with fewer GPU layers]     ← auto-reduces gpu_layers
[Select a different model]
[Continue without this model]   ← fallback to a smaller model
```

### 10.3 Graceful Degradation Messages

When the app is running in degraded mode (e.g., Qdrant unavailable, vector search replaced with hnswlib fallback, or a model slot unfilled), show a non-blocking status indicator in the sidebar:

```
⚠ Running in reduced mode
  • Vector search: in-memory (Qdrant unavailable)
  Click to view details
```

### 10.4 Help & Documentation

**Help > objective03 Help** opens an in-app documentation viewer (rendered Markdown, loaded from bundled files). Sections:
- Getting started
- Understanding the broadcast
- Managing sources
- Managing models
- Troubleshooting
- About the data model

**Help > Show Logs** opens a floating window with the backend log, filterable by level, searchable, and with export capability.

---

## Part 11: Performance & Startup Time

### 11.1 Startup Time Targets

| Milestone | Target | P95 |
|-----------|--------|-----|
| Dock icon appears | <1s | <2s |
| Splash screen visible | <2s | <3s |
| Backend ready | <15s | <25s |
| First render | <16s | <26s |

### 11.2 Lazy Loading

Models are not loaded at startup. They load on first use (when a task actually requires them). The model registry already supports this via LRU eviction. The app shows a loading indicator in the relevant pipeline stage when a model is being loaded for the first time.

### 11.3 Database Startup

KuzuDB startup is synchronous and can be slow (~2-5 seconds) for large databases. Move the database initialization to a background thread and show the UI immediately with a "Connecting to database..." indicator in the status bar.

---

## Part 12: Accessibility

### 12.1 Keyboard Navigation

All interactive elements are keyboard-accessible. Tab order is logical and visible (focus ring uses `outline: 2px solid #00ff88; outline-offset: 2px;`). Custom keyboard shortcuts:

| Shortcut | Action |
|----------|--------|
| `⌘G` | Generate broadcast now |
| `Space` | Play/pause current broadcast |
| `⌘1` | Dashboard |
| `⌘2` | Broadcast |
| `⌘3` | Sources |
| `⌘,` | Preferences |
| `⌘\` | Toggle sidebar |

### 12.2 VoiceOver

All custom SVG elements have `aria-label` attributes. Dynamic content (pipeline progress, now playing) uses `aria-live` regions. The app is not a VoiceOver-first experience, but it should not be hostile to screen reader users.

### 12.3 Reduced Motion

Respect `prefers-reduced-motion`. When set:
- Remove all CSS animations (pulsing dots, waveform animations, transition effects)
- Replace animated pipeline indicators with static text

---

## Part 13: Testing Requirements for Distribution

Before any DMG can be considered release-ready, the following tests must pass:

### 13.1 Fresh Install Test

1. Create a new macOS user account
2. Install the DMG by dragging to Applications
3. Launch the app — wizard appears
4. Complete wizard (Balanced tier)
5. Verify first broadcast generates within 15 minutes

### 13.2 Regression Tests

All existing `tests/` must continue to pass. Additionally:

- `tests/test_wizard.py` — Wizard state machine transitions
- `tests/test_model_download.py` — Resume interrupted downloads
- `tests/test_bundle_integrity.py` — Verify all bundled files present and signed
- `tests/test_backend_startup.py` — Backend starts within 15s on cold start
- `tests/test_crash_recovery.py` — Backend restart after SIGKILL

### 13.3 Platform Testing Matrix

Before each release, manual smoke test on:
- MacBook Air M2 (16 GB RAM) — minimum supported Apple Silicon config
- MacBook Pro M4 Pro (48 GB RAM) — primary dev machine
- Mac mini M1 (8 GB RAM) — minimum RAM config (minimal tier only)

---

## Part 14: Implementation Phases

### Phase 0: Foundation (Weeks 1-2)
- Set up build infrastructure (GitHub Actions workflow skeleton)
- Implement embedded Python runtime builder script
- Replace Qdrant with hnswlib in VectorStore
- Change data directory from `~/.objective03/` to `~/Library/Application Support/objective03/`
- Fix hardcoded port 8510 → dynamic port assignment
- Implement resumable model downloads in HuggingFace downloader

### Phase 1: Wizard (Weeks 3-4)
- Implement wizard React components (all 6 steps)
- Implement model tier catalog (bundled JSON)
- Implement voice preview playback
- Implement source configuration with live RSS validation
- Wire wizard to backend config write

### Phase 2: UX Polish (Weeks 5-6)
- Dashboard redesign (health bar, event feed, epistemic state panel)
- Broadcast page redesign (now playing, pipeline diagram)
- Sources page (full CRUD with live validation)
- Models page (installed/download/custom tabs)

### Phase 3: Distribution (Weeks 7-8)
- Code signing setup
- Notarization pipeline
- DMG visual design (background, icon)
- System tray integration
- macOS notification integration
- Auto-updater implementation

### Phase 4: Polish & QA (Week 9-10)
- Crash reporter
- Help documentation
- Accessibility pass
- Fresh install testing
- Performance profiling and optimization
- Beta release to limited users

### Phase 5: Release (Week 11)
- Signed, notarized, stapled DMG published to GitHub Releases
- Update server deployed
- User-facing changelog written

---

## Appendix A: electron-builder Configuration

`electron/electron-builder.yml`:

```yaml
appId: app.objective03
productName: objective03
copyright: "Copyright © 2026 objective03 Contributors"

directories:
  output: dist
  buildResources: build-resources

files:
  - dist/**/*
  - node_modules/**/*

extraResources:
  - from: ../python-runtime
    to: python
  - from: ../src
    to: backend/src
  - from: ../backend
    to: backend/backend
  - from: ../prompts
    to: backend/prompts
  - from: ../bin/ffmpeg
    to: bin/ffmpeg
  - from: ../assets/sounds
    to: assets/sounds

mac:
  category: public.app-category.news
  target:
    - target: dmg
      arch:
        - universal
  icon: build-resources/icon.icns
  entitlementsInherit: build-resources/entitlements.mac.plist
  entitlements: build-resources/entitlements.mac.plist
  hardenedRuntime: true
  gatekeeperAssess: false
  notarize:
    teamId: "XXXXXXXXXX"

dmg:
  background: build-resources/dmg-background.png
  icon: build-resources/icon.icns
  iconSize: 128
  window:
    width: 660
    height: 400
  contents:
    - x: 180
      y: 200
      type: file
    - x: 480
      y: 200
      type: link
      path: /Applications

afterSign: scripts/notarize.js
```

---

## Appendix B: Model Catalog Format

`resources/model-catalog.json` (bundled with app):

```json
{
  "version": 1,
  "tiers": [
    {
      "id": "minimal",
      "name": "Minimal",
      "description": "Single model for all tasks",
      "total_size_gb": 4.2,
      "min_ram_gb": 8,
      "models": [
        {
          "slot": ["extraction", "entity", "reasoning", "broadcast", "contradiction", "classification"],
          "name": "Qwen2.5-7B-Instruct Q4_K_M",
          "filename": "qwen2.5-7b-instruct-q4_k_m.gguf",
          "hf_repo": "Qwen/Qwen2.5-7B-Instruct-GGUF",
          "hf_file": "qwen2.5-7b-instruct-q4_k_m.gguf",
          "sha256": "...",
          "size_bytes": 4368342016,
          "context": 4096,
          "gpu_layers": 32
        }
      ]
    },
    {
      "id": "balanced",
      "name": "Balanced",
      "description": "Separate extraction and broadcast models",
      "total_size_gb": 11.8,
      "min_ram_gb": 16,
      "models": [...]
    }
  ]
}
```

---

## Appendix C: Setup State Machine

The wizard's state machine has the following states and transitions:

```
INITIAL
  → check setup-complete.json
  → if exists: MAIN_APP
  → if missing: WIZARD_WELCOME

WIZARD_WELCOME
  → [Begin Setup]: WIZARD_STORAGE

WIZARD_STORAGE
  → [Next]: WIZARD_MODELS
  → [Back]: WIZARD_WELCOME

WIZARD_MODELS
  → [Next]: WIZARD_VOICE
  → [Back]: WIZARD_STORAGE

WIZARD_VOICE
  → [Next]: WIZARD_SOURCES
  → [Back]: WIZARD_MODELS

WIZARD_SOURCES
  → [Next]: WIZARD_DOWNLOAD
  → [Back]: WIZARD_VOICE

WIZARD_DOWNLOAD
  → [all downloads complete]: WIZARD_COMPLETE
  → [user cancels download]: WIZARD_SOURCES (with partial state saved)

WIZARD_COMPLETE
  → [Launch]: write setup-complete.json → MAIN_APP
```

Any state can transition to `WIZARD_QUIT` (user closes window mid-wizard), which saves partial state to a `setup-in-progress.json` file and exits cleanly.

---

This spec defines every component required to transform objective03 from a developer-only project into a distributable, polished macOS desktop application. The implementation effort is substantial but sequenced so that Phase 0 and 1 deliver a testable product and Phase 3 delivers the actual DMG. The core system architecture is preserved entirely — only the packaging, onboarding, and UI layers change.