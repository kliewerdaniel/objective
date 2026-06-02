import os
import sys
import shutil
from pathlib import Path
from typing import Any, Optional
import yaml
from pydantic import BaseModel, Field


def _default_data_dir() -> Path:
    """Return the platform-appropriate data directory."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "objective03"
    return Path.home() / ".objective03"


def _legacy_data_dir() -> Path:
    return Path.home() / ".objective03"


DATA_DIR = _default_data_dir()


def migrate_legacy_data():
    """Copy config + databases from ~/.objective03/ to the new location if needed."""
    legacy = _legacy_data_dir()
    current = DATA_DIR
    if legacy == current:
        return
    if not legacy.exists() or current.exists():
        return
    current.mkdir(parents=True, exist_ok=True)
    for name in ("config.yaml", "graph.db", "metadata.db"):
        src = legacy / name
        if src.exists():
            shutil.copy2(src, current / name)
    for dirname in ("models", "voices", "custom_voices", "audio"):
        src = legacy / dirname
        if src.is_dir():
            dst = current / dirname
            if not dst.exists():
                shutil.copytree(src, dst)
    migrate_marker = current / ".migrated_from_legacy"
    migrate_marker.write_text(str(legacy))


class ModelConfig(BaseModel):
    path: str
    context: int = 4096
    gpu_layers: int = 32
    threads: Optional[int] = None
    name: str = ""
    chat_format: Optional[str] = None


class DatabaseConfig(BaseModel):
    path: str = str(DATA_DIR / "graph.db")
    buffer_pool_size: Optional[int] = None
    max_threads: int = 4


class VectorConfig(BaseModel):
    vector_size: int = 384
    persist_path: str = ""  # defaults to {data_dir}/vector at runtime


class MetadataConfig(BaseModel):
    path: str = str(DATA_DIR / "metadata.db")


class TTSConfig(BaseModel):
    engine: str = "qwen"
    model: str = ""
    voice: str = "chris"
    speed: float = 1.0
    length_scale: float = 1.0
    sentence_silence: float = 0.5


class AudioConfig(BaseModel):
    tts: TTSConfig = TTSConfig()
    sample_rate: int = 22050
    channels: int = 1
    device: str = "default"
    enabled: bool = True


class SchedulerConfig(BaseModel):
    ingestion_interval: float = 300.0
    analysis_interval: float = 1800.0
    broadcast_interval: float = 900.0
    consolidation_interval: float = 86400.0
    health_check_interval: float = 60.0


class SourceItem(BaseModel):
    url: str = ""
    name: str = ""
    interval: int = 600
    timeout: int = 30
    client_id: str = ""
    client_secret: str = ""
    user_agent: str = ""
    subreddit: str = ""
    channel_id: str = ""
    respect_etag: bool = True
    limit: int = 25


class SourcesConfig(BaseModel):
    rss: list[SourceItem] = []
    reddit: list[SourceItem] = []
    youtube: list[SourceItem] = []


class DaemonConfig(BaseModel):
    health_check_interval: float = 60.0
    restart_delay: float = 5.0
    max_restarts: int = 3
    thread_pool_size: int = 4


class SystemConfig(BaseModel):
    name: str = "objective03"
    data_dir: str = str(DATA_DIR)
    log_level: str = "INFO"
    prompts_dir: str = "prompts"
    models_dir: str = str(DATA_DIR / "models")


class Config(BaseModel):
    system: SystemConfig = SystemConfig()
    daemon: DaemonConfig = DaemonConfig()
    scheduler: SchedulerConfig = SchedulerConfig()
    databases: DatabaseConfig = DatabaseConfig()
    vector: VectorConfig = VectorConfig()
    metadata: MetadataConfig = MetadataConfig()
    audio: AudioConfig = AudioConfig()
    sources: SourcesConfig = SourcesConfig()

    models: dict[str, ModelConfig] = {
        "extraction": ModelConfig(
            path="qwen2.5-7b-instruct-q4.gguf",
            context=4096, gpu_layers=32, name="qwen2.5-7b"
        ),
        "entity": ModelConfig(
            path="qwen2.5-3b-instruct-q4.gguf",
            context=2048, gpu_layers=32, name="qwen2.5-3b"
        ),
        "reasoning": ModelConfig(
            path="llama-3.1-8b-instruct-q4.gguf",
            context=8192, gpu_layers=32, name="llama-3.1-8b"
        ),
        "broadcast": ModelConfig(
            path="qwen2.5-14b-instruct-q4.gguf",
            context=8192, gpu_layers=32, name="qwen2.5-14b"
        ),
        "contradiction": ModelConfig(
            path="llama-3.2-3b-instruct-q4.gguf",
            context=4096, gpu_layers=32, name="llama-3.2-3b"
        ),
        "classification": ModelConfig(
            path="qwen2.5-3b-instruct-q4.gguf",
            context=2048, gpu_layers=32, name="qwen2.5-3b-cls"
        ),
        "embedding": ModelConfig(
            path="bge-small-en-v1.5-q4.gguf",
            context=512, gpu_layers=0, name="bge-small"
        ),
    }

    def model_path(self, task: str) -> str:
        """Resolve model path relative to models_dir if relative."""
        cfg = self.models.get(task)
        if not cfg:
            return ""
        p = cfg.path
        if not p.startswith("/"):
            return str(Path(self.system.models_dir) / p)
        return p

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Config":
        migrate_legacy_data()
        path = path or os.environ.get("OBJECTIVE03_CONFIG", str(DATA_DIR / "config.yaml"))
        p = Path(path)
        if p.exists():
            with open(p) as f:
                data = yaml.safe_load(f)
            return cls(**data)
        return cls()

    def ensure_dirs(self):
        dirs = [
            Path(self.system.data_dir).expanduser(),
            Path(self.system.models_dir).expanduser(),
            Path(self.system.data_dir).expanduser() / "audio" / "cache",
            Path(self.system.data_dir).expanduser() / "audio" / "queue",
            Path(self.system.data_dir).expanduser() / "audio" / "archive",
            Path(self.system.data_dir).expanduser() / "logs",
            Path(self.system.data_dir).expanduser() / "state",
            Path(self.system.data_dir).expanduser() / "backups",
            self.vector_persist_path,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    @property
    def audio_dir(self) -> Path:
        return Path(self.system.data_dir).expanduser() / "audio"

    @property
    def vector_persist_path(self) -> Path:
        if self.vector.persist_path:
            return Path(self.vector.persist_path).expanduser()
        return Path(self.system.data_dir).expanduser() / "vector"
