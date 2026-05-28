# Evaluation Engine Agent

## Overview

The evaluation engine monitors the quality and health of the entire system. It runs quality checks, computes metrics, and generates evaluation reports. Unlike other agents, it is purely observational — it does not modify graph state.

## Responsibility

- Compute quality metrics for claims, contradictions, narratives, and broadcasts
- Detect quality degradation
- Generate evaluation reports for the UI
- Track metrics over time for trend analysis
- Flag anomalies for human review

## Interface

```python
class EvaluationEngine(BaseAgent):
    name = "evaluation_engine"
    timeout_seconds = 30.0
    
    async def run(self, context: AgentContext) -> AgentResult:
        """Run all evaluation checks."""
        metrics = {}
        
        # Run evaluations in parallel
        tasks = [
            self._evaluate_claims(context),
            self._evaluate_contradictions(context),
            self._evaluate_narratives(context),
            self._evaluate_broadcasts(context),
            self._evaluate_system_health(context),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, dict):
                metrics.update(result)
        
        # Store evaluation in SQLite
        context.metadata.store_evaluation({
            "timestamp": datetime.utcnow().isoformat(),
            **metrics,
        })
        
        # Check for degradation alerts
        alerts = self._check_alerts(metrics, context)
        
        return AgentResult(
            success=True,
            data={"metrics": metrics, "alerts": alerts},
            metrics=metrics,
        )
    
    async def _evaluate_claims(self, context: AgentContext) -> dict:
        """Evaluate claim quality metrics."""
        total = context.graph.count_nodes("Claim")
        if total == 0:
            return {"claims": {"total": 0}}
        
        # Sample claims for quality check
        sample = context.graph.get_random_claims(limit=100)
        
        avg_confidence = sum(c.confidence for c in sample) / len(sample)
        stance_distribution = {}
        for c in sample:
            stance_distribution[c.stance] = stance_distribution.get(c.stance, 0) + 1
        
        # Duplicate detection rate
        duplicates = context.graph.count_duplicate_claims()
        
        return {
            "claims": {
                "total": total,
                "avg_confidence": round(avg_confidence, 3),
                "stance_distribution": stance_distribution,
                "duplicates": duplicates,
                "duplicate_rate": round(duplicates / total, 3) if total > 0 else 0,
            }
        }
    
    async def _evaluate_contradictions(self, context: AgentContext) -> dict:
        """Evaluate contradiction quality metrics."""
        total = context.graph.count_edges("CONTRADICTS")
        if total == 0:
            return {"contradictions": {"total": 0}}
        
        unresolved = context.graph.count_unresolved_contradictions()
        resolved = context.graph.count_resolved_contradictions()
        false_positives = context.graph.count_false_contradictions()
        
        # Type distribution
        type_dist = context.graph.get_contradiction_type_distribution()
        
        return {
            "contradictions": {
                "total": total,
                "unresolved": unresolved,
                "resolved": resolved,
                "false_positives": false_positives,
                "resolution_rate": round(resolved / total, 3) if total > 0 else 0,
                "false_positive_rate": round(false_positives / total, 3) if total > 0 else 0,
                "type_distribution": type_dist,
            }
        }
    
    async def _evaluate_narratives(self, context: AgentContext) -> dict:
        """Evaluate narrative quality metrics."""
        total = context.graph.count_nodes("Narrative")
        if total == 0:
            return {"narratives": {"total": 0}}
        
        active = context.graph.count_active_narratives()
        avg_drift = context.graph.get_average_drift_score()
        
        return {
            "narratives": {
                "total": total,
                "active": active,
                "archived": total - active,
                "avg_drift": round(avg_drift, 3),
            }
        }
    
    async def _evaluate_broadcasts(self, context: AgentContext) -> dict:
        """Evaluate broadcast quality metrics."""
        total = context.graph.count_nodes("Broadcast")
        if total == 0:
            return {"broadcasts": {"total": 0}}
        
        latest = context.graph.get_latest_broadcast()
        hours_since_last = (datetime.utcnow() - latest.aired_at).total_seconds() / 3600 if latest else None
        
        # Broadcast interval consistency
        intervals = context.graph.get_broadcast_intervals(limit=20)
        avg_interval = sum(intervals) / len(intervals) if intervals else 0
        
        return {
            "broadcasts": {
                "total": total,
                "hours_since_last": round(hours_since_last, 2) if hours_since_last else None,
                "avg_interval_min": round(avg_interval / 60, 1),
            }
        }
    
    async def _evaluate_system_health(self, context: AgentContext) -> dict:
        """Evaluate overall system health."""
        import psutil
        
        process = psutil.Process()
        memory = process.memory_info()
        
        return {
            "system": {
                "cpu_percent": process.cpu_percent(),
                "memory_rss_gb": round(memory.rss / 1024**3, 2),
                "memory_percent": process.memory_percent(),
                "disk_usage_percent": psutil.disk_usage("/").percent,
                "uptime_hours": round((time.monotonic() - context.state.get("start_time", time.monotonic())) / 3600, 2),
            }
        }
    
    def _check_alerts(self, metrics: dict, context: AgentContext) -> list[dict]:
        """Check for conditions that require alerts."""
        alerts = []
        
        # Memory warning
        if metrics.get("system", {}).get("memory_percent", 0) > 80:
            alerts.append({"level": "warning", "message": "Memory usage above 80%"})
        
        # Contradiction false positive rate too high
        contra = metrics.get("contradictions", {})
        if contra.get("false_positive_rate", 0) > 0.15:
            alerts.append({"level": "warning", 
                          "message": f"False positive contradiction rate: {contra['false_positive_rate']:.1%}"})
        
        # No broadcasts for too long
        if metrics.get("broadcasts", {}).get("hours_since_last", 0) > 2:
            alerts.append({"level": "warning", 
                          "message": f"No broadcast for {metrics['broadcasts']['hours_since_last']:.0f} hours"})
        
        return alerts
```

## Evaluation Storage

```sql
CREATE TABLE evaluation_history (
    timestamp REAL PRIMARY KEY,
    metrics TEXT NOT NULL,  -- JSON blob of all metrics
    alerts TEXT            -- JSON array of alerts
);

CREATE INDEX idx_eval_timestamp ON evaluation_history(timestamp DESC);
```

## Quality Thresholds

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| Memory usage | >80% | >90% | Unload models, consolidate |
| CPU usage | >90% for 5min | >95% | Reduce pipeline frequency |
| Claim dup rate | >5% | >10% | Reduce dedup threshold |
| Contradiction FP rate | >10% | >15% | Increase detection threshold |
| Broadcast gap | >2 hours | >6 hours | Alert, force regenerate |
| Source availability | <50% online | <25% | Alert, check sources |
| Graph integrity | Warnings | Errors | Restore from backup |

## Trend Tracking

Metrics are tracked over time for trend analysis:

```python
def get_metric_trend(metric_name: str, hours: int, 
                     metadata: SQLiteStore) -> dict:
    """Get trend data for a metric."""
    records = metadata.get_evaluations(since_hours=hours)
    
    values = []
    for record in records:
        metrics = json.loads(record.metrics)
        value = nested_get(metrics, metric_name.split("."))
        if value is not None:
            values.append({"timestamp": record.timestamp, "value": value})
    
    if len(values) < 2:
        return {"current": None, "trend": "insufficient_data"}
    
    # Simple linear regression for trend
    x = np.array([v["timestamp"] for v in values])
    y = np.array([v["value"] for v in values])
    slope = np.polyfit(x, y, 1)[0] if len(values) > 2 else 0
    
    return {
        "current": values[-1]["value"],
        "previous": values[0]["value"],
        "change": values[-1]["value"] - values[0]["value"],
        "slope": slope,
        "trend": "improving" if slope < 0 else "degrading" if slope > 0 else "stable",
        "data_points": len(values),
    }
```
