# Broadcast Generation Pipeline

## Pipeline Flow

```
Graph State Snapshot
    │
    ├── Top events (importance > 0.3)
    ├── Top contradictions (strength > 0.5)
    ├── Active narratives (drift > 0.1)
    ├── Drift reports (last 24h)
    ├── Source trust scores
    ├── System metrics
    └── Previous broadcast reference
    │
    ▼
Context Assembly
    │
    ├── Format events
    ├── Format contradictions
    ├── Format narratives
    ├── Format callbacks
    └── Format metrics
    │
    ▼
Prompt Construction
    │
    ▼
LLM Inference (Qwen 14B Q4)
    │
    ▼
Script Parsing (structured segments)
    │
    ▼
Validation
    │
    ├── Contains all required segments
    ├── Word count in range
    ├── References valid entities
    └── No editorializing detected
    │
    ▼
Graph Store
    │
    ▼
Audio Production
```

## Context Gathering

```python
async def gather_broadcast_context(graph: GraphStore, 
                                    broadcast_memory: BroadcastMemory) -> BroadcastContext:
    """Gather all context needed for broadcast generation."""
    return BroadcastContext(
        timestamp=datetime.utcnow(),
        top_events=graph.get_top_events(limit=5, min_importance=0.3),
        contradictions=graph.get_top_contradictions(limit=3),
        narratives=graph.get_active_narratives(limit=3),
        drift_reports=graph.get_drift_reports(hours=24, min_score=0.2),
        source_trusts=graph.get_all_source_trusts(),
        previous_broadcast=graph.get_latest_broadcast(),
        callbacks=broadcast_memory.get_callbacks_for_recurring_events(),
        system_metrics={
            "events": graph.count_nodes("Event"),
            "claims": graph.count_nodes("Claim"),
            "narratives": graph.count_nodes("Narrative"),
            "contradictions": graph.count_edges("CONTRADICTS"),
            "sources": graph.count_nodes("Source"),
            "broadcasts": graph.count_nodes("Broadcast"),
        },
        uncertainty_zones=find_uncertainty_zones(graph),
    )
```

## Script Structure Validation

```python
VALID_SEGMENTS = {"intro", "timestamp", "state", "events", "contradictions",
                   "drift", "threads", "uncertainty", "system", "outro"}

REQUIRED_SEGMENTS = {"intro", "state", "outro"}

def validate_script(script: Script) -> tuple[bool, list[str]]:
    """Validate broadcast script structure."""
    issues = []
    segment_types = {s.segment_type for s in script.segments}
    
    # Check required segments
    missing = REQUIRED_SEGMENTS - segment_types
    if missing:
        issues.append(f"Missing required segments: {missing}")
    
    # Check valid segment types
    invalid = segment_types - VALID_SEGMENTS
    if invalid:
        issues.append(f"Invalid segment types: {invalid}")
    
    # Check word count
    word_count = len(script.full_text.split())
    if word_count < 200:
        issues.append(f"Script too short: {word_count} words (min 200)")
    if word_count > 5000:
        issues.append(f"Script too long: {word_count} words (max 5000)")
    
    return len(issues) == 0, issues
```

## Fallback Content

When the system has insufficient data for a segment:

| Segment | Fallback |
|---------|----------|
| events | "No events above reporting threshold." |
| contradictions | "No active contradictions above reporting threshold." |
| drift | "No significant narrative drift detected." |
| threads | "No recurring threads with updates." |
| uncertainty | "Confidence is stable across monitored topics." |
