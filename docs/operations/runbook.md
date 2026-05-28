# Operations Documentation

## Runbook

### Startup

```bash
# Start Qdrant
brew services start qdrant

# Start objective03
cd ~/Projects/objective03
source .venv/bin/activate
python -m objective03.daemon
```

### Shutdown

```bash
# Graceful: SIGINT or SIGTERM
kill -INT $(pgrep -f objective03)

# Force: SIGKILL (last resort)
kill -KILL $(pgrep -f objective03)
```

### Health Check

```bash
# Check daemon status
curl http://localhost:9090/health  # If metrics endpoint enabled

# Check Qdrant
curl http://localhost:6333/health

# Check graph size
ls -lh ~/.objective03/graph.db

# Check log tail
tail -100 ~/.objective03/logs/objective03.log
```

### Recovery

```bash
# Restore from backup
cd ~/Projects/objective03
python -m objective03.database restore --backup ~/.objective03/backups/backup_20260528_120000

# Rebuild contradiction index
python -m objective03.database rebuild-contradiction-index

# Reset ingestion cursor for a source
python -m objective03.ingestion reset-cursor --source "BBC World"
```

## Monitoring

### Key Metrics to Monitor

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| daemon_uptime_hours | < 1 (after crash) | < 0 | Restart daemon |
| pipeline_latency_ms | > 30000 | > 60000 | Reduce batch size |
| model_memory_gb | > 20 | > 25 | Unload idle models |
| graph_size_gb | > 10 | > 50 | Archive, consolidate |
| source_success_rate | < 0.8 | < 0.5 | Check source configs |
| contradiction_fp_rate | > 0.1 | > 0.2 | Tune detection |
| broadcast_gap_minutes | > 30 | > 60 | Check broadcast agent |

### Logs

```
~/.objective03/logs/
├── objective03.log        # Main structured log
├── audit.log              # Audit trail
├── stdout.log             # launchd stdout
└── stderr.log             # launchd stderr
```

## Maintenance

### Daily

- Check log tail for errors
- Verify sources are returning data
- Check disk usage

### Weekly

- Review contradiction false positive rate
- Verify broadcast quality
- Check for model updates

### Monthly

- Rebuild contradiction index
- Archive old backups
- Review graph growth metrics

## Troubleshooting

| Problem | Likely Cause | Solution |
|---------|-------------|----------|
| No audio | TTS model missing, audio device | Check Piper model path, audio device |
| Empty graph | Ingestion failing, extraction model | Check logs, verify model loading |
| High memory | Too many models loaded | Reduce simultaneous models |
| Slow extraction | GPU contention, context overflow | Reduce context, increase GPU layers |
| Contradiction flood | Threshold too low | Increase contradiction threshold |
| Source poll errors | Rate limiting, source changes | Check source config, reduce poll rate |
