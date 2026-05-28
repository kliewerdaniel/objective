# Operations Subsystems

## Runbook

See [operations/runbook.md](runbook.md) for startup/shutdown/health check procedures.

## Observability

Structured logging via structlog. Every pipeline stage emits events with trace_id for correlation. The terminal UI consumes the same event stream for live display. Structured log format: `{"event": "pipeline.completed", "trace_id": "...", "duration_ms": 1240, ...}`

## Maintenance

Daily: check log tail, verify source availability, check disk usage. Weekly: review contradiction FP rate, verify broadcast quality. Monthly: rebuild contradiction index, archive old backups, prune old logs.

## Troubleshooting

Common issues: no audio (check Piper model path), empty graph (check model loading), high memory (reduce loaded models), source poll errors (check API keys, rate limits).
