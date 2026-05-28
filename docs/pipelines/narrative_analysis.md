# Narrative Analysis Pipeline

## Pipeline Flow

```
New Claims + Existing Graph State
    │
    ▼
Claim Clustering (embedding + temporal)
    │
    ├── Assign to existing narratives
    └── Create new narratives
    │
    ▼
Narrative Update
    │
    ├── Drift measurement
    ├── Framing analysis
    ├── Source diversity tracking
    └── Confidence tracking
    │
    ▼
Contradiction Cross-Reference
    │
    ▼
Narrative State Store (graph)
    │
    ▼
Drift Report Generation
```

## Clustering Algorithm

```python
def cluster_claims_to_narratives(claims: list[Claim], 
                                  existing_narratives: list[Narrative],
                                  embeddings: dict[str, np.ndarray]) -> dict:
    """Assign claims to narratives via similarity clustering."""
    clusters = {n.id: n for n in existing_narratives}
    unassigned = []
    
    for claim in claims:
        best_match = None
        best_score = 0.0
        
        for narrative in existing_narratives:
            score = cosine_similarity(
                embeddings[claim.id],
                narrative.embedding_centroid
            )
            
            # Temporal bonus
            time_diff = (claim.timestamp - narrative.last_updated).total_seconds()
            if time_diff < 86400:  # Within 24 hours
                score += 0.1 * (1 - time_diff / 86400)
            
            if score > best_score:
                best_score = score
                best_match = narrative
        
        if best_score > 0.7:
            clusters[best_match.id].claim_ids.append(claim.id)
        else:
            unassigned.append(claim)
    
    return {
        "assigned": {k: v for k, v in clusters.items() if v.claim_ids},
        "unassigned": unassigned,
    }
```

## Drift Measurement

See [architecture/narrative_drift_engine.md](../architecture/narrative_drift_engine.md) for detailed drift measurement algorithms.

## Framing Analysis

See [agents/political_framing_analyzer.md](../agents/political_framing_analyzer.md) for framing classification.

## Source Diversity Tracking

```python
def track_source_diversity(narrative_id: str, graph: GraphStore) -> dict:
    """Track source diversity for a narrative."""
    claims = graph.get_thread_claims(narrative_id)
    
    sources = {}
    for claim in claims:
        source = claim.source_name
        if source not in sources:
            sources[source] = {"count": 0, "first": claim.timestamp, "last": claim.timestamp}
        sources[source]["count"] += 1
        sources[source]["last"] = max(sources[source]["last"], claim.timestamp)
    
    return {
        "total_sources": len(sources),
        "herfindahl_index": sum((v["count"]/len(claims))**2 for v in sources.values()),
        "dominant_source": max(sources, key=lambda s: sources[s]["count"]),
        "source_shifts": count_source_changes(sources),
    }
```

## Analysis Frequency

| Component | Frequency | Duration | Model |
|-----------|-----------|----------|-------|
| Clustering | Every claim batch | 5-30s | Embedding |
| Drift measurement | Every 30min | 30-120s | Embedding + LLM |
| Framing analysis | Every 30min | 10-30s | Classification |
| Source diversity | Every 60min | 5-10s | Heuristic |
| Report generation | Every 60min | 10-30s | Template |
