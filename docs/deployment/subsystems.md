# Deployment Subsystems

## Local Setup

```bash
# System dependencies
brew install python@3.11 ffmpeg piper qdrant

# Clone and configure
git clone <repo>
cd objective03
cp config.yaml.example config.yaml
# Edit config.yaml with your source selections

# Python environment
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Start vector DB
brew services start qdrant

# Launch
python -m objective03.daemon
```

## Daemonization

macOS launchd plist at `~/Library/LaunchAgents/com.objective03.plist`. Auto-restarts on crash with 10s throttle interval.

## Resource Management

Memory budget: 48GB total. The system reserves ~4GB for macOS, ~2GB each for KuzuDB/Qdrant/SQLite, and allocates the remainder to models (max 3 loaded simultaneously to stay under 32GB).

## Monitoring

Prometheus metrics endpoint (optional) on port 9090. Key metrics: daemon_uptime, pipeline_latency, model_memory, graph_size, source_success_rate.

## Crash Recovery

- KuzuDB: `RESTORE FROM backup_path`
- SQLite: WAL mode provides crash safety
- Qdrant: WAL replay on restart

## Scaling

| Dimension | Limit | Scaling Strategy |
|-----------|-------|-----------------|
| Graph nodes | ~10M | KuzuDB columnar handles millions |
| Vectors | ~1M | Qdrant on-disk mode |
| Sources | ~100 | Thread pool per source type |
| Models | 3 loaded | Unload LRU when not in use |
