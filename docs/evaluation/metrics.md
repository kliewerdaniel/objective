# Evaluation Metrics

## Core Metrics Tracked

| Category | Metric | Collection | Frequency |
|----------|--------|------------|-----------|
| Claim | avg_confidence, stance_distribution, dup_rate | Per extraction cycle | Continuous |
| Contradiction | count, fp_rate, resolution_rate, type_dist | Per analysis cycle | Continuous |
| Narrative | count, active, archived, avg_drift | Per analysis cycle | Per cycle |
| Broadcast | count, interval, duration, word_count | Per broadcast | Per broadcast |
| System | cpu, memory, disk, source_availability | Periodic sampling | Every 60s |

## Trend Analysis

Metrics are stored in SQLite `evaluation_history` and tracked over 1h, 24h, 7d, and 30d windows. Trend direction (improving/degrading/stable) is computed via linear regression slope.
