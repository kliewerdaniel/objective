"""FastAPI backend server for objective03 Electron frontend."""

import os
import sys
import re
import json
import yaml
import asyncio
import subprocess
import time
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.events import event_manager, Event

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

PROMPTS_DIR = PROJECT_ROOT / "prompts"
CUSTOM_VOICES_DIR = PROJECT_ROOT / "custom_voices"
MODELS_DIR = PROJECT_ROOT / "models"

# Data directory: use env var, else platform-appropriate default
import sys as _sys
if _sys.platform == "darwin":
    _DEFAULT_DATA_DIR = Path.home() / "Library" / "Application Support" / "objective03"
else:
    _DEFAULT_DATA_DIR = Path.home() / ".objective03"
DATA_DIR = Path(os.environ.get("OBJECTIVE03_DATA_DIR", str(_DEFAULT_DATA_DIR)))
AUDIO_DIR = DATA_DIR / "audio"
CONFIG_PATH = Path(os.environ.get("OBJECTIVE03_CONFIG", str(DATA_DIR / "config.yaml")))
if not CONFIG_PATH.exists():
    CONFIG_PATH = PROJECT_ROOT / "config.yaml"


# ---------------------------------------------------------------------------
# Pipeline progress tracker
# ---------------------------------------------------------------------------
PIPELINE_STAGES = [
    {"id": "ingestion", "label": "Ingesting sources"},
    {"id": "claims", "label": "Extracting claims"},
    {"id": "entities", "label": "Extracting entities"},
    {"id": "clustering", "label": "Clustering events"},
    {"id": "contradictions", "label": "Detecting contradictions"},
    {"id": "narratives", "label": "Analyzing narratives"},
    {"id": "broadcast", "label": "Writing broadcast script"},
    {"id": "tts", "label": "Synthesizing speech"},
    {"id": "stitching", "label": "Stitching audio"},
    {"id": "ready", "label": "Ready to play"},
]

_pipeline_state = {
    "stages": PIPELINE_STAGES,
    "current_stage": None,
    "completed_stages": [],
    "failed_stage": None,
    "broadcast_id": None,
    "script_preview": None,
    "segments_total": 0,
    "segments_done": 0,
    "current_segment_text": None,
    "is_playing": False,
    "now_playing": None,
    "playback_position": 0.0,
    "playback_duration": 0.0,
    "generating": False,
    "generation_error": None,
}

_playback_proc: Optional[subprocess.Popen] = None
_playback_start: float = 0.0
_broadcast_task: Optional[asyncio.Task] = None


async def emit_pipeline_state():
    try:
        await event_manager.emit("pipeline_progress", {
            "stages": _pipeline_state["stages"],
            "current_stage": _pipeline_state["current_stage"],
            "completed_stages": _pipeline_state["completed_stages"],
            "failed_stage": _pipeline_state["failed_stage"],
            "broadcast_id": _pipeline_state["broadcast_id"],
            "script_preview": _pipeline_state["script_preview"],
            "segments_total": _pipeline_state["segments_total"],
            "segments_done": _pipeline_state["segments_done"],
            "current_segment_text": _pipeline_state["current_segment_text"],
            "is_playing": _pipeline_state["is_playing"],
            "now_playing": _pipeline_state["now_playing"],
            "playback_position": _pipeline_state["playback_position"],
            "playback_duration": _pipeline_state["playback_duration"],
            "generating": _pipeline_state["generating"],
            "generation_error": _pipeline_state["generation_error"],
        })
    except Exception:
        pass


def _set_stage(stage_id: str, **kwargs):
    _pipeline_state["current_stage"] = stage_id
    if stage_id not in _pipeline_state["completed_stages"]:
        _pipeline_state["completed_stages"].append(stage_id)
    for k, v in kwargs.items():
        _pipeline_state[k] = v


# ---------------------------------------------------------------------------
# Broadcast generation (runs in-process)
# ---------------------------------------------------------------------------
async def _run_broadcast_pipeline():
    """Run the broadcast generation pipeline in a background task."""
    try:
        from src.config import Config
        from src.agents.broadcast_writer import BroadcastWriter
        from src.agents.audio_producer import AudioProducer
        from src.agents.base import AgentContext
        from src.database.graph import GraphStore
        from src.database.vector import VectorStore
        from src.database.metadata import MetadataStore
        from src.models.client import ModelRegistry
        from src.audio.piper import QwenTTS, AudioCache
        from src.audio.player import AudioQueue, AudioStitcher, StreamingAudioQueue, StreamingPlayer, AudioChunk, BroadcastEnd

        config = Config.load(str(CONFIG_PATH))

        # Initialize minimal components
        _set_stage("ingestion", generating=True, generation_error=None)
        await emit_pipeline_state()

        print("[backend] Initializing components...", flush=True)

        graph = None
        vector = None
        metadata = None
        models = None

        try:
            graph = GraphStore(config.databases.path, max_threads=config.databases.max_threads)
            print("[backend] Graph store ready", flush=True)
        except Exception as e:
            print(f"[backend] Graph unavailable: {e}", flush=True)

        await asyncio.sleep(0)  # yield to event loop

        try:
            vector = VectorStore(
                vector_size=config.vector.vector_size,
                persist_path=str(config.vector_persist_path),
            )
            print("[backend] Vector store ready", flush=True)
        except Exception as e:
            print(f"[backend] Vector unavailable: {e}", flush=True)

        try:
            metadata = MetadataStore(config.metadata.path)
            print("[backend] Metadata store ready", flush=True)
        except Exception as e:
            print(f"[backend] Metadata unavailable: {e}", flush=True)

        try:
            models = ModelRegistry(config)
            print("[backend] Model registry ready", flush=True)
        except Exception as e:
            print(f"[backend] Models unavailable: {e}", flush=True)

        await asyncio.sleep(0)

        # Init audio components
        tts = None
        audio_cache = None
        audio_queue = None
        audio_stitcher = None
        streaming_queue = None
        streaming_player_task = None

        if config.audio.enabled:
            try:
                print("[backend] Initializing TTS engine...", flush=True)
                tts = QwenTTS(config.audio)
                cache_dir = config.audio_dir / "cache"
                cache_dir.mkdir(parents=True, exist_ok=True)
                audio_cache = AudioCache(cache_dir)
                audio_queue = AudioQueue()
                audio_stitcher = AudioStitcher()
                streaming_queue = StreamingAudioQueue()
                streaming_player = StreamingPlayer(streaming_queue, config.audio.sample_rate)
                streaming_player_task = asyncio.create_task(streaming_player.run())
                print("[backend] TTS engine ready", flush=True)
            except Exception as e:
                print(f"[backend] Audio init failed: {e}", flush=True)

        await asyncio.sleep(0)

        shared_state = {}
        if tts:
            shared_state["tts"] = tts
        if audio_cache:
            shared_state["audio_cache"] = audio_cache
        if audio_queue:
            shared_state["audio_queue"] = audio_queue
        if audio_stitcher:
            shared_state["audio_stitcher"] = audio_stitcher
        if streaming_queue:
            shared_state["streaming_queue"] = streaming_queue
        shared_state["audio_dir"] = config.audio_dir

        ctx = AgentContext(
            trace_id=f"web-{int(time.time())}",
            config=config.model_dump(),
            state=shared_state,
            models=models,
            graph=graph,
            vector=vector,
            metadata=metadata,
        )

        # --- Step 1: Run full analysis pipeline ---
        _set_stage("ingestion", generating=True)
        _pipeline_state["script_preview"] = "Fetching news and analyzing..."
        await emit_pipeline_state()
        t_start = time.time()
        print("[backend] Analysis pipeline started", flush=True)

        # Import all analysis agents
        from src.agents.ingestion_coordinator import IngestionCoordinator
        from src.agents.claim_extractor import ClaimExtractor
        from src.agents.entity_extractor import EntityExtractor
        from src.agents.event_clustering import EventClusteringEngine
        from src.agents.contradiction_detector import ContradictionDetector
        from src.agents.narrative_analyzer import NarrativeAnalyzer
        from src.agents.framing_analyzer import FramingAnalyzer
        from src.agents.source_reliability import SourceReliabilityEvaluator
        from src.agents.graph_updater import GraphUpdater

        # Step 1a: Ingest from sources
        print("[backend] Running ingestion...", flush=True)
        ingestion = IngestionCoordinator()
        result = await ingestion.run(ctx)
        print(f"[backend] Ingestion: {result.metrics.get('documents_found', 0)} new documents", flush=True)
        _set_stage("claims", generating=True)
        await emit_pipeline_state()

        # Step 1b: Extract claims
        print("[backend] Extracting claims...", flush=True)
        extractor = ClaimExtractor()
        result = await extractor.run(ctx)
        print(f"[backend] Claims: {result.metrics.get('claims_extracted', 0)} extracted", flush=True)
        _set_stage("entities", generating=True)
        await emit_pipeline_state()

        # Step 1c: Extract entities
        print("[backend] Extracting entities...", flush=True)
        entity_ext = EntityExtractor()
        result = await entity_ext.run(ctx)
        print(f"[backend] Entities extracted", flush=True)
        _set_stage("clustering", generating=True)
        await emit_pipeline_state()

        # Step 1d: Cluster into events
        print("[backend] Clustering events...", flush=True)
        clustering = EventClusteringEngine()
        result = await clustering.run(ctx)
        print(f"[backend] Events clustered", flush=True)
        _set_stage("contradictions", generating=True)
        await emit_pipeline_state()

        # Step 1e: Detect contradictions
        print("[backend] Detecting contradictions...", flush=True)
        contradiction = ContradictionDetector()
        result = await contradiction.run(ctx)
        print(f"[backend] Contradictions detected", flush=True)
        _set_stage("narratives", generating=True)
        await emit_pipeline_state()

        # Step 1f: Analyze narratives
        print("[backend] Analyzing narratives...", flush=True)
        narrative = NarrativeAnalyzer()
        result = await narrative.run(ctx)
        print(f"[backend] Narratives analyzed", flush=True)

        # Step 1g: Update graph
        print("[backend] Updating graph...", flush=True)
        graph_updater = GraphUpdater()
        result = await graph_updater.run(ctx)
        print(f"[backend] Graph updated", flush=True)

        # --- Step 2: Run broadcast writer (continued) ---
        broadcast_agent = BroadcastWriter()
        t0 = time.time()
        print("[backend] Running broadcast writer (loading model + generating script)...", flush=True)
        result = await broadcast_agent.run(ctx)
        elapsed = time.time() - t0
        print(f"[backend] Broadcast writer finished in {elapsed:.1f}s (success={result.success})", flush=True)

        if not result.success:
            _pipeline_state["failed_stage"] = "broadcast"
            _pipeline_state["generation_error"] = f"Script generation failed: {result.error}"
            _pipeline_state["generating"] = False
            await emit_pipeline_state()
            return

        script = shared_state.get("script")
        if not script:
            _pipeline_state["failed_stage"] = "broadcast"
            _pipeline_state["generation_error"] = "No script produced"
            _pipeline_state["generating"] = False
            await emit_pipeline_state()
            return

        _pipeline_state["script_preview"] = script.full_text[:500]
        _pipeline_state["broadcast_id"] = script.id
        await emit_pipeline_state()

        # --- Step 3: Run TTS with streaming chunks ---
        _set_stage("tts", generating=True, segments_total=0, segments_done=0)
        await emit_pipeline_state()

        from src.audio.preprocessor import TTSProcessor
        from src.models.types import generate_uuid

        processor = TTSProcessor()

        # Split script into small chunks at sentence boundaries for cleaner TTS
        all_chunks = []
        for seg in script.segments:
            text = seg.text.strip()
            if not text:
                continue
            # Split into sentences
            sentences = re.split(r'(?<=[.!?])\s+', text)
            current = ""
            for sent in sentences:
                words = current.split()
                sent_words = sent.split()
                if len(words) + len(sent_words) > 50 and current:
                    all_chunks.append(current.strip())
                    current = sent
                else:
                    current = (current + " " + sent).strip() if current else sent
            if current.strip():
                all_chunks.append(current.strip())

        _pipeline_state["segments_total"] = len(all_chunks)
        _pipeline_state["segments_done"] = 0
        await emit_pipeline_state()
        print(f"[backend] TTS: {len(all_chunks)} chunks to synthesize (streaming)", flush=True)

        broadcast_id = generate_uuid()
        streaming_queue.register_broadcast(broadcast_id)
        segment_paths = []

        # Sequential TTS — each chunk is enqueued immediately as it completes
        for i, chunk in enumerate(all_chunks):
            _pipeline_state["current_segment_text"] = chunk[:80] + "..." if len(chunk) > 80 else chunk
            _pipeline_state["segments_done"] = i
            await emit_pipeline_state()

            processed = processor.preprocess(chunk)
            cached = audio_cache.get(processed) if audio_cache else None
            if cached:
                segment_paths.append(cached)
                await streaming_queue.enqueue_chunk(AudioChunk(
                    audio_path=cached, broadcast_id=broadcast_id, chunk_index=i,
                ))
                print(f"[backend] TTS chunk {i+1}/{len(all_chunks)}: cached", flush=True)
                continue

            out = str(config.audio_dir / "queue" / f"seg_{generate_uuid()[:8]}.wav")
            t0 = time.time()
            print(f"[backend] TTS chunk {i+1}/{len(all_chunks)}: synthesizing ({len(chunk.split())} words)...", flush=True)
            try:
                ok = await tts.synthesize(processed, out)
                elapsed = time.time() - t0
                if ok:
                    if audio_cache:
                        audio_cache.set(processed, out)
                    segment_paths.append(out)
                    # Enqueue chunk immediately for streaming playback
                    await streaming_queue.enqueue_chunk(AudioChunk(
                        audio_path=out, broadcast_id=broadcast_id, chunk_index=i,
                    ))
                    print(f"[backend] TTS chunk {i+1}/{len(all_chunks)}: done in {elapsed:.1f}s (streaming)", flush=True)
                else:
                    print(f"[backend] TTS chunk {i+1}/{len(all_chunks)}: False in {elapsed:.1f}s", flush=True)
            except Exception as e:
                elapsed = time.time() - t0
                print(f"[backend] TTS chunk {i+1}/{len(all_chunks)}: FAILED in {elapsed:.1f}s: {e}", flush=True)
            # Yield to event loop
            await asyncio.sleep(0)

        # Signal end of broadcast
        await streaming_queue.enqueue_end(BroadcastEnd(broadcast_id=broadcast_id))

        _pipeline_state["segments_done"] = len(all_chunks)
        _pipeline_state["current_segment_text"] = None
        await emit_pipeline_state()
        print(f"[backend] TTS streaming complete: {len(all_chunks)} chunks enqueued", flush=True)

        if not all_chunks:
            _pipeline_state["failed_stage"] = "tts"
            _pipeline_state["generation_error"] = "No audio segments produced"
            _pipeline_state["generating"] = False
            await emit_pipeline_state()
            return

        # --- Step 4: Save stitched broadcast for sidebar + replay ---
        _set_stage("stitching", generating=True)
        await emit_pipeline_state()

        if not segment_paths:
            _pipeline_state["failed_stage"] = "tts"
            _pipeline_state["generation_error"] = "TTS produced no audio — check voice/model configuration"
            _pipeline_state["generating"] = False
            await emit_pipeline_state()
            return

        output_path = str(config.audio_dir / "queue" / f"bcast_{generate_uuid()[:8]}.wav")
        try:
            if len(segment_paths) == 1:
                import shutil
                shutil.copy2(segment_paths[0], output_path)
            else:
                audio_stitcher.stitch(segment_paths, output_path)
        except Exception as e:
            print(f"[backend] Stitch failed (non-fatal): {e}", flush=True)
            output_path = None

        # Get duration
        duration = script.estimated_duration()
        if output_path:
            try:
                import soundfile as sf
                data, sr = sf.read(output_path)
                duration = len(data) / sr
            except Exception:
                pass

        _set_stage("ready", generating=False, generation_error=None)
        if output_path:
            _pipeline_state["now_playing"] = {
                "broadcast_id": broadcast_id,
                "chunks": len(all_chunks),
                "streaming": True,
                "path": output_path,
                "filename": Path(output_path).name,
                "duration": duration,
            }
            _pipeline_state["playback_duration"] = duration
        else:
            _pipeline_state["generation_error"] = "Broadcast generated but audio could not be stitched"
            await emit_pipeline_state()

        total_elapsed = time.time() - t_start
        print(f"[backend] Broadcast pipeline complete in {total_elapsed:.1f}s ({len(all_chunks)} chunks, saved)", flush=True)
        await emit_pipeline_state()

        # Cleanup
        if streaming_player_task:
            streaming_player_task.cancel()
        if graph:
            try:
                graph.close()
            except Exception:
                pass

    except Exception as e:
        import traceback
        print(f"[backend] Broadcast pipeline FAILED: {e}", flush=True)
        traceback.print_exc()
        _pipeline_state["generation_error"] = str(e)
        _pipeline_state["generating"] = False
        _pipeline_state["failed_stage"] = _pipeline_state.get("current_stage")
        await emit_pipeline_state()
        print(f"[backend] Broadcast pipeline error: {e}")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------
class VoiceSelectRequest(BaseModel):
    voice: str


class ModelAssignRequest(BaseModel):
    task: str
    path: str
    context: Optional[int] = None
    gpu_layers: Optional[int] = None
    name: Optional[str] = None
    chat_format: Optional[str] = None


class PromptUpdateRequest(BaseModel):
    content: str


class ConfigUpdateRequest(BaseModel):
    content: str


class BroadcastPlayRequest(BaseModel):
    broadcast_id: Optional[str] = None
    audio_path: Optional[str] = None


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    global _playback_proc, _broadcast_task
    if _playback_proc:
        try:
            _playback_proc.kill()
        except Exception:
            pass
    if _broadcast_task:
        _broadcast_task.cancel()


app = FastAPI(title="objective03 backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _load_config() -> dict:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


def _save_config(data: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def _scan_broadcasts() -> list[dict]:
    broadcasts = []
    for subdir in ["queue", "archive"]:
        d = AUDIO_DIR / subdir
        if not d.exists():
            continue
        for f in sorted(d.glob("bcast_*.wav"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                import soundfile as sf
                info = sf.info(str(f))
                broadcasts.append({
                    "id": f.stem,
                    "filename": f.name,
                    "path": str(f),
                    "duration": info.duration,
                    "sample_rate": info.samplerate,
                    "subdir": subdir,
                    "size_bytes": f.stat().st_size,
                    "created_at": f.stat().st_mtime,
                })
            except Exception:
                broadcasts.append({
                    "id": f.stem,
                    "filename": f.name,
                    "path": str(f),
                    "duration": 0,
                    "sample_rate": 0,
                    "subdir": subdir,
                    "size_bytes": f.stat().st_size,
                    "created_at": f.stat().st_mtime,
                })
    return broadcasts


# ---------------------------------------------------------------------------
# SSE stream
# ---------------------------------------------------------------------------
@app.get("/api/events")
async def sse_events():
    async def event_generator():
        async for event in event_manager.subscribe():
            yield event.to_sse()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
@app.get("/api/status")
async def get_status():
    config = _load_config()
    return {
        "system_name": config.get("system", {}).get("name", "objective03"),
        "config_path": str(CONFIG_PATH),
        "prompts_dir": str(PROMPTS_DIR),
        "voices_dir": str(CUSTOM_VOICES_DIR),
        "models_dir": str(MODELS_DIR),
        "audio_dir": str(AUDIO_DIR),
    }


@app.get("/api/daemon")
async def get_daemon_status():
    """Report daemon status — if this endpoint responds, the backend IS running."""
    import os
    config = _load_config()
    pid = str(os.getpid())
    uptime = None
    try:
        # Get process uptime via ps
        import subprocess as _sp
        result = _sp.run(["ps", "-o", "etime=", "-p", pid], capture_output=True, text=True)
        if result.returncode == 0:
            uptime = result.stdout.strip()
    except Exception:
        pass
    # Also check launchd status on macOS
    launchd_running = False
    try:
        import subprocess as _sp
        result = _sp.run(["launchctl", "list", "com.danielkliewer.objective03"], capture_output=True, text=True)
        launchd_running = "PID" in result.stdout and "0" not in result.stdout.split("PID")[1].split("\n")[0].strip()
    except Exception:
        pass
    return {
        "daemon_running": True,
        "pid": pid,
        "uptime": uptime,
        "launchd_managed": launchd_running,
        "scheduler_intervals": {
            "ingestion": config.get("scheduler", {}).get("ingestion_interval", 60),
            "analysis": config.get("scheduler", {}).get("analysis_interval", 120),
            "broadcast": config.get("scheduler", {}).get("broadcast_interval", 90),
        },
    }


# ---------------------------------------------------------------------------
# Pipeline progress
# ---------------------------------------------------------------------------
@app.get("/api/pipeline")
async def get_pipeline():
    return _pipeline_state


@app.post("/api/pipeline/reset")
async def post_pipeline_reset():
    global _broadcast_task
    if _broadcast_task and not _broadcast_task.done():
        _broadcast_task.cancel()
    _pipeline_state["current_stage"] = None
    _pipeline_state["completed_stages"] = []
    _pipeline_state["failed_stage"] = None
    _pipeline_state["broadcast_id"] = None
    _pipeline_state["script_preview"] = None
    _pipeline_state["segments_total"] = 0
    _pipeline_state["segments_done"] = 0
    _pipeline_state["current_segment_text"] = None
    _pipeline_state["generating"] = False
    _pipeline_state["generation_error"] = None
    await emit_pipeline_state()
    return {"ok": True}


@app.post("/api/broadcast/new")
async def start_new_broadcast():
    """Start generating a new broadcast in the background."""
    global _broadcast_task
    if _pipeline_state["generating"]:
        raise HTTPException(status_code=409, detail="Broadcast already being generated")

    # Reset state
    _pipeline_state["current_stage"] = None
    _pipeline_state["completed_stages"] = []
    _pipeline_state["failed_stage"] = None
    _pipeline_state["script_preview"] = None
    _pipeline_state["generating"] = True
    _pipeline_state["generation_error"] = None

    _broadcast_task = asyncio.create_task(_run_broadcast_pipeline())
    return {"ok": True, "message": "Broadcast generation started"}


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
@app.get("/api/config")
async def get_config():
    return _load_config()


@app.put("/api/config")
async def update_config(req: ConfigUpdateRequest):
    try:
        data = yaml.safe_load(req.content)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {e}")
    _save_config(data)
    await event_manager.emit("config_updated", {})
    return {"ok": True}


# ---------------------------------------------------------------------------
# Voices
# ---------------------------------------------------------------------------
@app.get("/api/voices")
async def list_voices():
    voices = []
    search_dirs = [CUSTOM_VOICES_DIR, DATA_DIR / "custom_voices"]
    for d in search_dirs:
        if d.exists():
            for f in sorted(d.iterdir()):
                if f.suffix.lower() in (".wav", ".mp3", ".flac", ".ogg"):
                    voices.append({
                        "name": f.stem,
                        "path": str(f),
                        "format": f.suffix.lstrip(".").lower(),
                        "directory": str(d),
                    })
    seen = set()
    unique = []
    for v in voices:
        if v["name"] not in seen:
            seen.add(v["name"])
            unique.append(v)
    return {"voices": unique, "active": _load_config().get("audio", {}).get("tts", {}).get("voice", "chris")}


@app.put("/api/voice")
async def select_voice(req: VoiceSelectRequest):
    config = _load_config()
    if "audio" not in config:
        config["audio"] = {}
    if "tts" not in config["audio"]:
        config["audio"]["tts"] = {}
    config["audio"]["tts"]["voice"] = req.voice
    _save_config(config)
    await event_manager.emit("voice_changed", {"voice": req.voice})
    return {"ok": True, "voice": req.voice}


@app.post("/api/voices/upload")
async def upload_voice(file: bytes = File(...), filename: str = Form(...)):
    import re as _re
    safe = _re.sub(r'[^\w.\-]', '_', filename)
    if not safe or safe.startswith('.'):
        safe = f"voice_{int(time.time())}.wav"
    CUSTOM_VOICES_DIR.mkdir(parents=True, exist_ok=True)
    dest = CUSTOM_VOICES_DIR / safe
    dest.write_bytes(file)
    await event_manager.emit("voice_uploaded", {"name": safe})
    return {"ok": True, "name": safe, "path": str(dest)}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
def _scan_models(folder: Path) -> list[dict]:
    models = []
    if not folder.exists():
        return models
    for f in sorted(folder.rglob("*.gguf")):
        stat = f.stat()
        models.append({
            "name": f.stem,
            "path": str(f),
            "size_bytes": stat.st_size,
            "size_gb": round(stat.st_size / (1024**3), 2),
        })
    return models


@app.get("/api/models")
async def list_models():
    return {"models": _scan_models(MODELS_DIR), "folder": str(MODELS_DIR)}


@app.get("/api/models/scan")
async def scan_models(folder: str):
    target = Path(folder).expanduser()
    if not target.exists():
        raise HTTPException(status_code=400, detail=f"Folder not found: {folder}")
    return {"models": _scan_models(target), "folder": str(target)}


@app.get("/api/models/assigned")
async def get_assigned_models():
    config = _load_config()
    return {"assigned": config.get("models", {})}


@app.put("/api/models/assign")
async def assign_model(req: ModelAssignRequest):
    config = _load_config()
    if "models" not in config:
        config["models"] = {}
    task = req.task
    if task not in config["models"]:
        config["models"][task] = {}
    entry = config["models"][task]
    entry["path"] = req.path
    if req.context is not None:
        entry["context"] = req.context
    if req.gpu_layers is not None:
        entry["gpu_layers"] = req.gpu_layers
    if req.name is not None:
        entry["name"] = req.name
    if req.chat_format is not None:
        entry["chat_format"] = req.chat_format
    _save_config(config)
    await event_manager.emit("model_assigned", {"task": task, "path": req.path})
    return {"ok": True, "task": task}


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------
@app.get("/api/prompts")
async def list_prompts():
    prompts = []
    if PROMPTS_DIR.exists():
        for f in sorted(PROMPTS_DIR.glob("*.md")):
            prompts.append({"name": f.stem, "path": str(f), "size_bytes": f.stat().st_size})
    return {"prompts": prompts, "directory": str(PROMPTS_DIR)}


@app.get("/api/prompts/{name}")
async def get_prompt(name: str):
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Prompt '{name}' not found")
    return {"name": name, "content": path.read_text(encoding="utf-8"), "path": str(path)}


@app.put("/api/prompts/{name}")
async def update_prompt(name: str, req: PromptUpdateRequest):
    PROMPTS_DIR.mkdir(parents=True, exist_ok=True)
    path = PROMPTS_DIR / f"{name}.md"
    path.write_text(req.content, encoding="utf-8")
    await event_manager.emit("prompt_updated", {"name": name})
    return {"ok": True, "name": name, "path": str(path)}


# ---------------------------------------------------------------------------
# Broadcasts
# ---------------------------------------------------------------------------
@app.get("/api/broadcasts")
async def list_broadcasts():
    return {"broadcasts": _scan_broadcasts()}


@app.get("/api/broadcasts/now-playing")
async def get_now_playing():
    global _playback_proc
    is_playing = _playback_proc is not None and _playback_proc.poll() is None
    return {
        "is_playing": is_playing,
        "now_playing": _pipeline_state.get("now_playing"),
        "playback_position": _pipeline_state.get("playback_position", 0),
        "playback_duration": _pipeline_state.get("playback_duration", 0),
    }


@app.post("/api/broadcasts/play")
async def play_broadcast(req: BroadcastPlayRequest):
    global _playback_proc, _playback_start

    # Stop any current playback
    if _playback_proc and _playback_proc.poll() is None:
        try:
            _playback_proc.kill()
        except Exception:
            pass
    _playback_proc = None

    audio_path = req.audio_path
    if not audio_path and req.broadcast_id:
        broadcasts = _scan_broadcasts()
        for b in broadcasts:
            if b["id"] == req.broadcast_id:
                audio_path = b["path"]
                break

    if not audio_path or not Path(audio_path).exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    try:
        import soundfile as sf
        info = sf.info(audio_path)
        duration = info.duration
    except Exception:
        duration = 0

    _pipeline_state["is_playing"] = True
    _pipeline_state["now_playing"] = {
        "path": audio_path,
        "filename": Path(audio_path).name,
        "duration": duration,
    }
    _pipeline_state["playback_duration"] = duration
    _pipeline_state["playback_position"] = 0

    await emit_pipeline_state()

    try:
        _playback_proc = subprocess.Popen(
            ["afplay", audio_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        _playback_start = time.time()
    except Exception as e:
        _pipeline_state["is_playing"] = False
        await emit_pipeline_state()
        raise HTTPException(status_code=500, detail=f"Playback failed: {e}")

    # Watch for playback end (simple polling in background)
    async def _watch():
        global _playback_proc
        proc = _playback_proc
        while proc and proc.poll() is None:
            elapsed = time.time() - _playback_start
            _pipeline_state["playback_position"] = min(elapsed, duration)
            await emit_pipeline_state()
            await asyncio.sleep(1)
        _pipeline_state["is_playing"] = False
        _pipeline_state["playback_position"] = 0
        if _playback_proc is proc:
            _pipeline_state["now_playing"] = None
        await emit_pipeline_state()

    try:
        asyncio.create_task(_watch())
    except Exception:
        pass

    return {"ok": True, "playing": audio_path, "duration": duration}


@app.post("/api/broadcasts/stop")
async def stop_broadcast():
    global _playback_proc
    if _playback_proc and _playback_proc.poll() is None:
        try:
            _playback_proc.kill()
        except Exception:
            pass
    _playback_proc = None
    _pipeline_state["is_playing"] = False
    _pipeline_state["now_playing"] = None
    _pipeline_state["playback_position"] = 0
    await emit_pipeline_state()
    return {"ok": True}


@app.post("/api/broadcasts/{broadcast_id}/rename")
async def rename_broadcast(broadcast_id: str, body: dict):
    new_name = body.get("name", "").strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="Name required")
    broadcasts = _scan_broadcasts()
    for b in broadcasts:
        if b["id"] == broadcast_id:
            old_path = Path(b["path"])
            new_stem = f"bcast_{broadcast_id}_{new_name}"
            new_path = old_path.parent / f"{new_stem}.wav"
            old_path.rename(new_path)
            return {"ok": True, "path": str(new_path), "filename": new_path.name}
    raise HTTPException(status_code=404, detail="Broadcast not found")


@app.get("/api/broadcasts/{broadcast_id}/download")
async def download_broadcast(broadcast_id: str):
    from fastapi.responses import FileResponse
    broadcasts = _scan_broadcasts()
    for b in broadcasts:
        if b["id"] == broadcast_id:
            p = Path(b["path"])
            if p.exists():
                parts = p.stem.split("_", 2)
                display_name = parts[2] if len(parts) > 2 else p.stem
                return FileResponse(
                    path=str(p),
                    media_type="audio/wav",
                    filename=f"{display_name}.wav",
                )
    raise HTTPException(status_code=404, detail="Broadcast not found")


@app.delete("/api/broadcasts/{broadcast_id}")
async def delete_broadcast(broadcast_id: str):
    global _playback_proc
    broadcasts = _scan_broadcasts()
    for b in broadcasts:
        if b["id"] == broadcast_id:
            # Stop playback if this is the one playing
            if _playback_proc and _playback_proc.poll() is None:
                now = _pipeline_state.get("now_playing")
                if now and now.get("path") == b["path"]:
                    try:
                        _playback_proc.kill()
                    except Exception:
                        pass
                    _playback_proc = None
                    _pipeline_state["is_playing"] = False
                    _pipeline_state["now_playing"] = None
                    _pipeline_state["playback_position"] = 0
                    await emit_pipeline_state()
            # Delete the file
            Path(b["path"]).unlink(missing_ok=True)
            return {"ok": True, "deleted": b["filename"]}
    raise HTTPException(status_code=404, detail="Broadcast not found")


@app.delete("/api/broadcasts")
async def clear_broadcasts():
    global _playback_proc
    # Stop any playback
    if _playback_proc and _playback_proc.poll() is None:
        try:
            _playback_proc.kill()
        except Exception:
            pass
    _playback_proc = None
    _pipeline_state["is_playing"] = False
    _pipeline_state["now_playing"] = None
    _pipeline_state["playback_position"] = 0
    await emit_pipeline_state()

    # Delete all broadcast files
    deleted = 0
    for subdir in ["queue", "archive"]:
        d = AUDIO_DIR / subdir
        if not d.exists():
            continue
        for f in d.glob("bcast_*.wav"):
            f.unlink(missing_ok=True)
            deleted += 1
    return {"ok": True, "deleted": deleted}


# ---------------------------------------------------------------------------
# Wizard
# ---------------------------------------------------------------------------
class WizardCompleteRequest(BaseModel):
    storage_path: str
    models_path: str
    tier: str
    voice: str
    sources: list[str]
    custom_rss_urls: list[str] = []
    use_existing_models: bool = False


@app.get("/api/wizard/status")
async def wizard_status():
    """Check if setup has been completed."""
    setup_file = DATA_DIR / "setup-complete.json"
    return {"setup_complete": setup_file.exists()}


@app.post("/api/wizard/complete")
async def wizard_complete(req: WizardCompleteRequest):
    """Write config and mark setup as complete."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Build config from wizard choices
    config = {
        "system": {
            "name": "objective03",
            "data_dir": req.storage_path,
            "models_dir": req.models_path,
            "log_level": "INFO",
        },
        "databases": {
            "path": str(DATA_DIR / "graph.db"),
            "max_threads": 4,
        },
        "vector": {
            "vector_size": 384,
        },
        "metadata": {
            "path": str(DATA_DIR / "metadata.db"),
        },
        "audio": {
            "tts": {
                "engine": "qwen",
                "voice": req.voice,
                "speed": 1.0,
                "length_scale": 1.0,
                "sentence_silence": 0.5,
            },
            "sample_rate": 24000,
            "channels": 1,
            "device": "default",
            "enabled": True,
        },
        "scheduler": {
            "ingestion_interval": 300,
            "analysis_interval": 1800,
            "broadcast_interval": 900,
            "consolidation_interval": 86400,
            "health_check_interval": 60,
        },
        "sources": {
            "rss": [],
            "reddit": [],
        },
    }

    # Map sources to config format
    for url in req.sources:
        config["sources"]["rss"].append({
            "url": url,
            "name": url.split("//")[-1].split("/")[0],
            "interval": 600,
            "timeout": 30,
        })

    # Auto-detect models when using existing directory
    if req.use_existing_models:
        models_dir = Path(req.models_path)
        if models_dir.is_dir():
            gguf_files = sorted(models_dir.rglob("*.gguf"))
            if gguf_files:
                # Task definitions with keywords and defaults
                task_defs = [
                    ("extraction", ["7b", "7b", "qwen"], 4096, 32, "qwen2.5-7b"),
                    ("entity", ["3b", "3b", "qwen", "entity"], 2048, 32, "qwen2.5-3b"),
                    ("reasoning", ["8b", "8b", "llama", "reason"], 8192, 32, "llama-3.1-8b"),
                    ("broadcast", ["14b", "14b", "qwen", "broadcast"], 8192, 32, "qwen2.5-14b"),
                    ("contradiction", ["3b", "3b", "llama", "contra"], 4096, 32, "llama-3.2-3b"),
                    ("classification", ["3b", "3b", "qwen", "class"], 2048, 32, "qwen2.5-3b-cls"),
                    ("embedding", ["bge", "embed", "small"], 512, 0, "bge-small"),
                ]
                models_cfg = {}
                used = set()
                for task_key, keywords, context, gpu_layers, name in task_defs:
                    best = None
                    best_score = -1
                    for f in gguf_files:
                        if f in used:
                            continue
                        fname_lower = f.stem.lower()
                        score = sum(2 for kw in keywords if kw in fname_lower)
                        if score > best_score:
                            best_score = score
                            best = f
                    if best is None:
                        # Pick any unused file
                        for f in gguf_files:
                            if f not in used:
                                best = f
                                break
                    if best:
                        used.add(best)
                        models_cfg[task_key] = {
                            "path": str(best),
                            "context": context,
                            "gpu_layers": gpu_layers,
                            "name": name,
                        }
                if models_cfg:
                    config["models"] = models_cfg

    # Save config
    config_path = DATA_DIR / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    # Mark setup complete
    setup_data = {
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "tier": req.tier,
        "voice": req.voice,
        "source_count": len(req.sources),
        "models_path": req.models_path,
        "use_existing_models": req.use_existing_models,
    }
    setup_file = DATA_DIR / "setup-complete.json"
    with open(setup_file, "w") as f:
        json.dump(setup_data, f, indent=2)

    await event_manager.emit("setup_complete", setup_data)
    return {"ok": True, "config_path": str(config_path)}


# ---------------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------------
@app.get("/api/dashboard/stats")
async def dashboard_stats():
    """Aggregate stats for the dashboard health bar."""
    config = _load_config()
    stats = {
        "events": 0,
        "claims": 0,
        "contradictions": 0,
        "narratives": 0,
        "documents": 0,
        "sources": 0,
        "source_reliability": {},
    }
    try:
        from src.database.graph import GraphStore
        graph = GraphStore(
            config.get("databases", {}).get("path", str(DATA_DIR / "graph.db")),
            max_threads=config.get("databases", {}).get("max_threads", 4),
        )
        stats["events"] = graph.count_nodes("Event")
        stats["claims"] = graph.count_nodes("Claim")
        stats["contradictions"] = graph.count_edges("CONTRADICTS")
        stats["narratives"] = graph.count_nodes("Narrative")
        stats["documents"] = graph.count_nodes("Document")
        stats["sources"] = graph.count_nodes("Source")

        # Source reliability scores
        sources = graph.get_all_sources()
        for s in sources:
            name = s.get("s.name", "unknown")
            score = s.get("s.trust_score", 0.5)
            stats["source_reliability"][name] = round(score, 2)

        graph.close()
    except Exception:
        pass
    return stats


@app.get("/api/dashboard/events")
async def dashboard_events(limit: int = 20):
    """Recent significant events for the dashboard feed."""
    config = _load_config()
    events = []
    try:
        from src.database.graph import GraphStore
        graph = GraphStore(
            config.get("databases", {}).get("path", str(DATA_DIR / "graph.db")),
            max_threads=config.get("databases", {}).get("max_threads", 4),
        )
        raw = graph.get_top_events(limit=limit)
        for e in raw:
            event_id = e.get("e.id", "")
            claims = graph.get_event_claims(event_id) if hasattr(graph, "get_event_claims") else []
            contradictions = []
            try:
                contradictions = graph.get_event_contradictions(event_id) if hasattr(graph, "get_event_contradictions") else []
            except Exception:
                pass
            events.append({
                "id": event_id,
                "title": e.get("e.title", ""),
                "description": e.get("e.description", ""),
                "importance": e.get("e.importance", 0),
                "status": e.get("e.status", "active"),
                "start_time": e.get("e.start_time", ""),
                "claim_count": len(claims) if isinstance(claims, list) else 0,
                "contradiction_count": len(contradictions) if isinstance(contradictions, list) else 0,
            })
        graph.close()
    except Exception:
        pass
    return {"events": events}


# ---------------------------------------------------------------------------
# Sources CRUD
# ---------------------------------------------------------------------------
@app.get("/api/sources")
async def list_sources():
    config = _load_config()
    sources = config.get("sources", {})
    return {
        "rss": sources.get("rss", []),
        "reddit": sources.get("reddit", []),
        "youtube": sources.get("youtube", []),
    }


class SourceAddRequest(BaseModel):
    type: str  # rss, reddit, youtube
    name: str
    url: str = ""
    subreddit: str = ""
    channel_id: str = ""
    interval: int = 600
    timeout: int = 30


@app.post("/api/sources")
async def add_source(req: SourceAddRequest):
    config = _load_config()
    if "sources" not in config:
        config["sources"] = {}
    source_type = req.type
    if source_type not in config["sources"]:
        config["sources"][source_type] = []
    entry = {"name": req.name, "url": req.url, "interval": req.interval, "timeout": req.timeout}
    if req.subreddit:
        entry["subreddit"] = req.subreddit
    if req.channel_id:
        entry["channel_id"] = req.channel_id
    config["sources"][source_type].append(entry)
    _save_config(config)
    await event_manager.emit("source_added", {"type": source_type, "name": req.name})
    return {"ok": True}


@app.delete("/api/sources")
async def delete_source(body: dict):
    source_type = body.get("type", "rss")
    name = body.get("name", "")
    config = _load_config()
    sources = config.get("sources", {}).get(source_type, [])
    config["sources"][source_type] = [s for s in sources if s.get("name") != name]
    _save_config(config)
    await event_manager.emit("source_removed", {"type": source_type, "name": name})
    return {"ok": True}


@app.put("/api/sources/{source_type}/{name}/toggle")
async def toggle_source(source_type: str, name: str):
    config = _load_config()
    sources = config.get("sources", {}).get(source_type, [])
    for s in sources:
        if s.get("name") == name:
            s["enabled"] = not s.get("enabled", True)
            break
    _save_config(config)
    return {"ok": True}


@app.get("/api/sources/validate")
async def validate_source(url: str):
    """Validate an RSS feed URL by fetching and parsing it."""
    try:
        import feedparser
        feed = feedparser.parse(url)
        if feed.bozo and not feed.entries:
            return {"valid": False, "error": str(feed.bozo_exception)}
        title = feed.feed.get("title", "Unknown")
        entries = [{"title": e.get("title", ""), "published": e.get("published", "")} for e in feed.entries[:3]]
        return {"valid": True, "title": title, "entries": entries}
    except Exception as e:
        return {"valid": False, "error": str(e)}
