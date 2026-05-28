# Temporal Querying

## Overview

Temporal querying is fundamental to objective03. Every edge carries temporal metadata, enabling time-travel queries, trend analysis, and narrative evolution tracking.

## Temporal Edge Properties

Every edge in the graph carries temporal metadata:

```cypher
// Example: MENTIONS edge with temporal properties
()-[r:MENTIONS]->()
WHERE r.first_seen <= $query_time
  AND r.last_seen >= $query_time
```

## Time-Travel Query Pattern

```python
def get_graph_snapshot(graph: GraphStore, timestamp: datetime) -> dict:
    """Get the state of the graph at a specific point in time."""
    
    # Claims that existed at that time
    claims = graph.execute("""
        MATCH (c:Claim)
        WHERE c.timestamp <= $timestamp
          AND (NOT EXISTS(c.superseded_at) OR c.superseded_at > $timestamp)
        RETURN c
    """, {"timestamp": timestamp.isoformat()})
    
    # Contradictions that were active at that time
    contradictions = graph.execute("""
        MATCH (c1:Claim)-[r:CONTRADICTS]->(c2:Claim)
        WHERE r.detected_at <= $timestamp
          AND (NOT EXISTS(r.resolved_at) OR r.resolved_at > $timestamp)
        RETURN c1, c2, r
    """, {"timestamp": timestamp.isoformat()})
    
    # Narratives that existed at that time
    narratives = graph.execute("""
        MATCH (n:Narrative)
        WHERE n.first_seen <= $timestamp
        RETURN n
    """, {"timestamp": timestamp.isoformat()})
    
    return {
        "timestamp": timestamp,
        "claims": claims,
        "contradictions": contradictions,
        "narratives": narratives,
    }
```

## Trend Analysis

### Confidence Over Time

```cypher
MATCH (c:Claim)-[:ABOUT_EVENT]->(e:Event {id: $event_id})
WHERE c.timestamp >= $start_time AND c.timestamp < $end_time
RETURN date_trunc('day', c.timestamp) AS day,
       avg(c.confidence) AS avg_confidence,
       percentile_cont(c.confidence, 0.5) AS median_confidence,
       stddev(c.confidence) AS confidence_stddev,
       count(c) AS claim_count
ORDER BY day
```

### Contradiction Evolution

```cypher
MATCH (c:Claim)-[r:CONTRADICTS]->()
WHERE r.detected_at >= $start_time
RETURN date_trunc('day', r.detected_at) AS day,
       count(r) AS new_contradictions,
       count(DISTINCT r.contradiction_type) AS type_diversity,
       avg(r.strength) AS avg_strength
ORDER BY day
```

### Narrative Drift Trajectory

```cypher
MATCH (n:Narrative {id: $narrative_id})
MATCH (n)-[:PRECEDES*]->(prev:Narrative)
RETURN prev.last_updated AS time,
       prev.drift_score,
       prev.framing,
       prev.label
ORDER BY time
```

## Temporal Windows

```python
from datetime import datetime, timedelta

class TemporalWindow:
    """Manage temporal query windows."""
    
    WINDOWS = {
        "last_hour": timedelta(hours=1),
        "last_6_hours": timedelta(hours=6),
        "last_24_hours": timedelta(hours=24),
        "last_7_days": timedelta(days=7),
        "last_30_days": timedelta(days=30),
    }
    
    @classmethod
    def get_range(cls, window: str) -> tuple[datetime, datetime]:
        end = datetime.utcnow()
        start = end - cls.WINDOWS.get(window, cls.WINDOWS["last_24_hours"])
        return start, end

def get_claims_in_window(graph: GraphStore, window: str) -> list:
    """Get claims within a temporal window."""
    start, end = TemporalWindow.get_range(window)
    return graph.execute("""
        MATCH (c:Claim)
        WHERE c.timestamp >= $start AND c.timestamp < $end
        RETURN c
        ORDER BY c.timestamp DESC
    """, {"start": start.isoformat(), "end": end.isoformat()})
```

## Temporal Aggregation

```python
def get_daily_metrics(graph: GraphStore, days: int = 30) -> list[dict]:
    """Get daily metrics for trend analysis."""
    results = graph.execute(f"""
        MATCH (c:Claim)
        WHERE c.timestamp >= datetime() - duration('P{days}D')
        WITH date_trunc('day', c.timestamp) AS day
        RETURN day,
               count(c) AS claims,
               avg(c.confidence) AS avg_confidence
        
        UNION ALL
        
        MATCH ()-[r:CONTRADICTS]->()
        WHERE r.detected_at >= datetime() - duration('P{days}D')
        WITH date_trunc('day', r.detected_at) AS day
        RETURN day,
               count(r) AS contradictions,
               avg(r.strength) AS avg_strength
    """)
    return results
```

## Snapshot Diff

```python
def diff_snapshots(before: dict, after: dict) -> dict:
    """Compare two graph snapshots to find changes."""
    return {
        "new_claims": [c for c in after["claims"] 
                      if c not in before["claims"]],
        "resolved_contradictions": [r for r in before["contradictions"]
                                   if r not in after["contradictions"]],
        "new_contradictions": [r for r in after["contradictions"]
                              if r not in before["contradictions"]],
        "new_narratives": [n for n in after["narratives"]
                          if n not in before["narratives"]],
        "claim_count_delta": len(after["claims"]) - len(before["claims"]),
        "contradiction_count_delta": len(after["contradictions"]) - len(before["contradictions"]),
    }
```
