import os
from pathlib import Path
from typing import Any, Optional
import yaml
from pydantic import BaseModel, Field


DATA_DIR = Path.home() / ".objective03"


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
    host: str = "localhost"
    port: int = 6333
    collection: str = "objective03"
    vector_size: int = 384


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
            path="models/qwen2.5-7b-instruct-q4.gguf",
            context=4096, gpu_layers=32, name="qwen2.5-7b"
        ),
        "entity": ModelConfig(
            path="models/qwen2.5-3b-instruct-q4.gguf",
            context=2048, gpu_layers=32, name="qwen2.5-3b"
        ),
        "reasoning": ModelConfig(
            path="models/llama-3.1-8b-instruct-q4.gguf",
            context=8192, gpu_layers=32, name="llama-3.1-8b"
        ),
        "broadcast": ModelConfig(
            path="models/qwen2.5-14b-instruct-q4.gguf",
            context=8192, gpu_layers=32, name="qwen2.5-14b"
        ),
        "contradiction": ModelConfig(
            path="models/llama-3.2-3b-instruct-q4.gguf",
            context=4096, gpu_layers=32, name="llama-3.2-3b"
        ),
        "classification": ModelConfig(
            path="models/qwen2.5-3b-instruct-q4.gguf",
            context=2048, gpu_layers=32, name="qwen2.5-3b-cls"
        ),
        "embedding": ModelConfig(
            path="models/bge-small-en-v1.5-q4.gguf",
            context=512, gpu_layers=0, name="bge-small"
        ),
    }

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Config":
        path = path or os.environ.get("OBJECTIVE03_CONFIG", str(DATA_DIR / "config.yaml"))
        p = Path(path)
        if p.exists():
            with open(p) as f:
                data = yaml.safe_load(f)
            return cls(**data)
        return cls()

    def ensure_dirs(self):
        dirs = [
            Path(self.system.data_dir),
            Path(self.system.data_dir) / "audio" / "cache",
            Path(self.system.data_dir) / "audio" / "queue",
            Path(self.system.data_dir) / "audio" / "archive",
            Path(self.system.data_dir) / "logs",
            Path(self.system.data_dir) / "state",
            Path(self.system.data_dir) / "backups",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    @property
    def audio_dir(self) -> Path:
        return Path(self.system.data_dir) / "audio"
