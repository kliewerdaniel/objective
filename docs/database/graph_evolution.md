# Graph Evolution Strategies

## Overview

The graph is not a static snapshot. It evolves continuously through growth, merging, summarization, and pruning. This document describes the strategies for managing graph evolution.

## Growth

The graph grows through continuous ingestion. New nodes and edges are added without modifying existing data (append-only model):

```python
def insert_claim(graph: GraphStore, claim: Claim) -> str:
    """Insert a new claim. Never modifies existing data."""
    claim_id = graph.create_node("Claim", claim.to_dict())
    
    for entity_id in claim.entity_ids:
        # Increment frequency if edge exists, create if not
        edge = graph.get_edge("MENTIONS", claim_id, entity_id)
        if edge:
            graph.update_edge_property(edge.id, "frequency", edge.frequency + 1)
            graph.update_edge_property(edge.id, "last_seen", claim.timestamp.isoformat())
        else:
            graph.create_edge("MENTIONS", claim_id, entity_id, {
                "first_seen": claim.timestamp.isoformat(),
                "last_seen": claim.timestamp.isoformat(),
                "frequency": 1,
                "confidence": claim.confidence,
            })
    
    return claim_id
```

## Merging

Entities and events are merged when resolution determines they are identical:

### Entity Merging

```python
def merge_entities(graph: GraphStore, canonical_id: str, alias_ids: list[str]):
    """Merge alias entities into canonical entity."""
    canonical = graph.get_node("Entity", canonical_id)
    all_aliases = set(canonical.aliases or [])
    
    for alias_id in alias_ids:
        alias = graph.get_node("Entity", alias_id)
        all_aliases.add(alias.name)
        all_aliases.update(alias.aliases or [])
        
        # Move all edges from alias to canonical
        for edge in graph.get_all_edges(alias_id):
            if edge.label in ("MENTIONS", "APPEARS_IN", "RELATED_TO"):
                new_props = dict(edge.props)
                graph.create_edge(edge.label, edge.src, canonical_id, new_props)
        
        # Delete alias node
        graph.delete_node("Entity", alias_id)
    
    # Update canonical with merged aliases
    graph.update_node("Entity", canonical_id, {
        "aliases": list(all_aliases),
        "last_seen": max(canonical.last_seen, *[graph.get_node("Entity", a).last_seen for a in alias_ids if graph.node_exists("Entity", a)]),
    })
```

### Event Merging

```python
def merge_events(graph: GraphStore, target_id: str, source_id: str):
    """Merge source event into target event."""
    source = graph.get_node("Event", source_id)
    target = graph.get_node("Event", target_id)
    
    # Move all claims from source to target
    for edge in graph.get_incoming_edges(source_id, "ABOUT_EVENT"):
        graph.create_edge("ABOUT_EVENT", edge.src, target_id, edge.props)
    
    # Update target time range
    new_start = min(target.start_time, source.start_time)
    new_end = max(target.end_time, source.end_time) if target.end_time and source.end_time else (target.end_time or source.end_time)
    
    graph.update_node("Event", target_id, {
        "start_time": new_start.isoformat() if new_start else None,
        "end_time": new_end.isoformat() if new_end else None,
    })
    
    # Recompute importance
    new_importance = compute_event_importance(target_id, graph)
    graph.update_node("Event", target_id, {"importance": new_importance})
    
    # Delete source event
    graph.delete_node("Event", source_id)
```

## Summarization

Dense subgraphs that are no longer active are summarized into compact representations:

### Narrative Thread Summarization

```python
async def summarize_narrative_thread(graph: GraphStore, narrative_id: str, 
                                      model: LLMClient) -> str:
    """Generate a summary of a narrative thread for archival."""
    claims = graph.get_thread_claims(narrative_id)
    narrative = graph.get_node("Narrative", narrative_id)
    
    if len(claims) < 3:
        return narrative.description or narrative.label
    
    # Sample claims across the time range
    claims.sort(key=lambda c: c.timestamp)
    sample_size = min(10, len(claims))
    step = max(1, len(claims) // sample_size)
    sampled = [claims[i] for i in range(0, len(claims), step)]
    
    prompt = f"""Summarize this narrative thread that ran from {claims[0].timestamp} to {claims[-1].timestamp}:

Narrative: {narrative.label}

Key claims (sampled chronologically):
{chr(10).join(f"- [{c.timestamp.date()}] {c.text}" for c in sampled)}

Generate a concise summary covering: what the narrative was about, how it evolved, key turning points, and its current status. 2-3 paragraphs."""
    
    response = await model.generate(prompt, temperature=0.3, max_tokens=512)
    return response.text.strip()
```

### Event Subgraph Summarization

```python
async def summarize_event(event_id: str, graph: GraphStore, 
                           model: LLMClient) -> EventSummary:
    """Create a summary of an event and its associated claims."""
    event = graph.get_node("Event", event_id)
    claims = graph.get_event_claims(event_id)
    entities = graph.get_event_entities(event_id)
    contradictions = graph.get_event_contradictions(event_id)
    
    prompt = f"""Summarize this event from the knowledge graph:

Event: {event.title}
Status: {event.status}
Time range: {event.start_time} to {event.end_time or 'ongoing'}
Importance: {event.importance:.2f}

Entity count: {len(entities)}
Claim count: {len(claims)}
Contradiction count: {len(contradictions)}

Key entities: {', '.join(e.name for e in entities[:10])}

Generate a structured summary."""
    
    response = await model.generate(prompt, temperature=0.3, max_tokens=512)
    
    return EventSummary(
        event_id=event_id,
        title=event.title,
        summary=response.text.strip(),
        claim_count=len(claims),
        entity_count=len(entities),
        contradiction_count=len(contradictions),
        time_range=f"{event.start_time} - {event.end_time or 'ongoing'}",
    )
```

## Pruning

Low-value data is pruned to maintain graph health:

```python
def prune_graph(graph: GraphStore, metadata: SQLiteStore) -> PruningReport:
    """Prune low-value nodes from the graph."""
    stats = {
        "claims_pruned": 0,
        "entities_pruned": 0,
        "edges_removed": 0,
    }
    
    # Prune orphan claims (no event link, no contradictions, low confidence, old)
    orphans = graph.execute("""
        MATCH (c:Claim)
        WHERE NOT (c)-[:ABOUT_EVENT]->()
          AND NOT (c)-[:CONTRADICTS]-()
          AND c.confidence < 0.3
          AND c.timestamp < datetime() - duration('P7D')
        RETURN c.id
    """)
    
    for row in orphans:
        # Archive first
        metadata.log_audit("claim.pruned", "graph_updater", 
                          data={"claim_id": row["c.id"]})
        graph.delete_node("Claim", row["c.id"])
        stats["claims_pruned"] += 1
    
    # Prune unlinked entities (no mentions, never appeared in events)
    unlinked = graph.execute("""
        MATCH (e:Entity)
        WHERE NOT (e)<-[:MENTIONS]-()
          AND NOT (e)-[:APPEARS_IN]->()
          AND e.last_seen < datetime() - duration('P90D')
        RETURN e.id
    """)
    
    for row in unlinked:
        graph.delete_node("Entity", row["e.id"])
        stats["entities_pruned"] += 1
    
    return PruningReport(**stats)
```

## Evolution Metrics

The system tracks graph evolution metrics:

| Metric | Frequency | Purpose |
|--------|-----------|---------|
| Node count per type | Every consolidation | Growth tracking |
| Edge count per type | Every consolidation | Relationship density |
| Average degree | Every consolidation | Connectivity |
| Merge count | Per operation | Entity/event resolution |
| Prune count | Per operation | Cleanup effectiveness |
| Summary count | Per consolidation | Compression ratio |
| Graph size (MB) | Daily | Storage growth |

## Balancing Growth and Stability

```python
def optimize_graph_discipline(graph: GraphStore, metadata: SQLiteStore) -> dict:
    """Apply graph discipline strategies to maintain health."""
    results = {}
    
    # 1. Merge duplicates (entity resolution)
    duplicates = graph.find_duplicate_entities(threshold=0.9)
    merge_count = 0
    for canonical, aliases in duplicates:
        merge_entities(graph, canonical, aliases)
        merge_count += 1
    results["entities_merged"] = merge_count
    
    # 2. Remove self-loops and redundant edges
    removed = graph.execute("""
        MATCH (a)-[r]->(a)
        DELETE r
        RETURN count(r) AS removed
    """)
    results["self_loops_removed"] = removed[0]["removed"]
    
    # 3. Consolidate parallel edges
    parallel = graph.find_parallel_edges()
    for primary, duplicates in parallel:
        # Sum frequencies, keep primary
        for dup in duplicates:
            graph.delete_edge(dup.id)
    results["parallel_edges_consolidated"] = sum(len(d) for _, d in parallel)
    
    return results
```
