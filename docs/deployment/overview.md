# Deployment Documentation

## Target Hardware

| Component | Specification |
|-----------|--------------|
| CPU | Apple M4 Pro (12-14 cores) |
| RAM | 48GB unified memory |
| GPU | Integrated 16-core GPU (Metal) |
| Storage | 1TB+ SSD (512GB minimum) |
| OS | macOS 15+ (Sequoia) |

## Resource Budget

| Component | RAM | Disk | Notes |
|-----------|-----|------|-------|
| macOS + system | 4GB | 50GB | OS overhead |
| KuzuDB | 2GB | 10-100GB | Growing with graph |
| Qdrant | 2GB | 5-50GB | Growing with vectors |
| SQLite | 128MB | 1-5GB | Metadata + audit |
| Models (peak) | 22GB | 15GB | GGUF files |
| Audio cache | 2GB | 5GB | WAV files |
| System overhead | 4GB | 10GB | Logs, temp files |
| **Total** | **~36GB** | **~100GB** | Operating budget |

## Installation

```bash
# Prerequisites
brew install python@3.11 ffmpeg piper

# Python environment
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Qdrant (local)
brew install qdrant
brew services start qdrant

# Download models
python -m objective03.models download
```

## Daemonization

See [architecture/continuous_daemon.md](../architecture/continuous_daemon.md) for launchd configuration.

## Containerization

Docker is an option but not recommended for daily use (GPU passthrough adds complexity):

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y ffmpeg

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . /app
WORKDIR /app

CMD ["python", "-m", "objective03.daemon"]
```

## Scaling Paths

| Scenario | Solution |
|----------|----------|
| Larger graph | Increase KuzuDB buffer pool, add SSD |
| More sources | Parallel polling, increase connection pool |
| Faster inference | Lighter models, more GPU layers |
| More storage | External SSD, S3 archival of old data |
| Multi-machine | Add message bus, remote Qdrant, shared KuzuDB |
