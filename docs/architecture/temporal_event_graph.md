# Temporal Event Graph Architecture

## Overview

The temporal event graph is the central data structure of objective03. It is a directed property graph with temporal annotations on all relationships. This enables time-travel queries, narrative evolution tracking, and contradiction persistence.

## Why a Temporal Graph

Conventional knowledge graphs store the current state. objective03 stores the evolving state — every edge has a time range, enabling queries like:

- "What did we know about event X on day Y?"
- "How did the framing of this event change over time?"
- "Which contradictions existed before the new evidence arrived?"
- "Show me the state of the graph at the time of broadcast #42"

## Graph Schema

### Node Types

```
┌─────────────────────────────────────────────────────────────────────┐
│                          NODE TYPES                                  │
│                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │  Source   │  │ Document │  │  Claim   │  │  Entity  │             │
│  │          │  │          │  │          │  │          │             │
│  │ id       │  │ id       │  │ id       │  │ id       │             │
│  │ name     │  │ title    │  │ text     │  │ name     │             │
│  │ type     │  │ url      │  │ confidenc│  │ type     │             │
│  │ base_url │  │ published│  │ stance   │  │ aliases  │             │
│  │ trust    │  │ ingested │  │ timestamp│  │ metadata │             │
│  │ metadata │  │ language │  │ evidence │  │          │             │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘             │
│                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │  Event   │  │Narrative │  │Broadcast │  │Contradic.│             │
│  │          │  │  Thread  │  │  Segment │  │  Summary │             │
│  │ id       │  │          │  │          │  │          │             │
│  │ title    │  │ id       │  │ id       │  │ id       │             │
│  │ summary  │  │ label    │  │ script   │  │ summaries│             │
│  │ start_t  │  │ drift    │  │ duration │  │ resolved │             │
│  │ end_t    │  │ framing  │  │ aired_at │  │ evidence │             │
│  │ status   │  │ active   │  │ topics   │  │          │             │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘             │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Edge Types

```cypher
// Ingestion edges
()-[FROM_SOURCE]->()          // Document → Source
()-[EXTRACTED_FROM]->()       // Claim → Document

// Entity edges
()-[MENTIONS]->()             // Claim → Entity
()-[APPEARS_IN]->()           // Entity → Event
()-[RELATED_TO]->()           // Entity → Entity

// Event edges
()-[ABOUT_EVENT]->()          // Claim → Event
()-[NEXT_EVENT]->()           // Event → Event (chronological)
()-[CAUSED_BY]->()            // Event → Event
()-[SUBEVENT_OF]->()          // Event → Event (hierarchy)

// Narrative edges
()-[PART_OF_THREAD]->()       // Claim → Narrative
()-[PRECEDES]->()             // Narrative → Narrative (evolution)
()-[REFERENCES]->()           // Broadcast → Event
()-[CALLS_BACK]->()           // Broadcast → Broadcast

// Epistemic edges
()-[CONTRADICTS]->()          // Claim → Claim
()-[SUPPORTS]->()             // Claim → Claim
()-[CONTEXTUALIZES]->()       // Claim → Event

// Temporal edges
()-[EVOLVED_INTO]->()         // Node → Node (state change)
()-[OBSOLETES]->()            // Claim → Claim
```

### Temporal Edge Properties

Every edge carries temporal metadata:

```cypher
CREATE REL TABLE MENTIONS(
    first_seen TIMESTAMP,
    last_seen TIMESTAMP,
    frequency INT,
    confidence FLOAT,
    source_evidence STRING[]
)
```

## KuzuDB Schema Implementation

```python
class GraphSchema:
    """KuzuDB schema definition for objective03."""
    
    NODE_TABLES = {
        "Source": {
            "id": "STRING",
            "name": "STRING",
            "type": "STRING",        # "rss", "reddit", "youtube", etc.
            "base_url": "STRING",
            "trust_score": "FLOAT",  # 0-1
            "metadata": "STRING",    # JSON blob
            "created_at": "TIMESTAMP",
        },
        "Document": {
            "id": "STRING",          # SHA-256 of content
            "title": "STRING",
            "url": "STRING",
            "published_at": "TIMESTAMP",
            "ingested_at": "TIMESTAMP",
            "language": "STRING",
            "source_type": "STRING",
        },
        "Claim": {
            "id": "STRING",          # UUID
            "text": "STRING",
            "confidence": "FLOAT",
            "stance": "STRING",      # "support", "neutral", "oppose", "uncertain"
            "timestamp": "TIMESTAMP",
            "topic": "STRING",
            "evidence": "STRING",    # Direct quote from source
            "embedding_id": "STRING", # Reference to Qdrant vector
        },
        "Entity": {
            "id": "STRING",          # UUID
            "name": "STRING",        # Canonical name
            "type": "STRING",        # "person", "organization", "location", "event_name", "concept"
            "aliases": "STRING[]",
            "metadata": "STRING",    # JSON blob
            "first_seen": "TIMESTAMP",
            "last_seen": "TIMESTAMP",
        },
        "Event": {
            "id": "STRING",          # UUID
            "title": "STRING",
            "description": "STRING",
            "start_time": "TIMESTAMP",
            "end_time": "TIMESTAMP",
            "status": "STRING",      # "ongoing", "concluded", "unknown"
            "importance": "FLOAT",   # 0-1, computed from claim volume + source diversity
            "embedding_id": "STRING",
        },
        "Narrative": {
            "id": "STRING",
            "label": "STRING",
            "description": "STRING",
            "drift_score": "FLOAT",   # How much this narrative has changed
            "framing": "STRING",      # Dominant framing
            "active": "BOOLEAN",
            "first_seen": "TIMESTAMP",
            "last_updated": "TIMESTAMP",
            "embedding_id": "STRING",
        },
        "Broadcast": {
            "id": "STRING",
            "script": "STRING",      # Full broadcast script
            "duration_seconds": "FLOAT",
            "aired_at": "TIMESTAMP",
            "topics": "STRING[]",
            "metrics": "STRING",     # JSON: contradiction_count, narrative_count, etc.
        },
        "ContradictionSummary": {
            "id": "STRING",
            "claim_a_text": "STRING",
            "claim_b_text": "STRING",
            "contradiction_type": "STRING",
            "resolution": "STRING",
            "resolved_at": "TIMESTAMP",
            "evidence_summary": "STRING",
        },
    }
    
    EDGE_TABLES = {
        "FROM_SOURCE": {
            "from": "Document", "to": "Source",
            "properties": {},
        },
        "EXTRACTED_FROM": {
            "from": "Claim", "to": "Document",
            "properties": {},
        },
        "MENTIONS": {
            "from": "Claim", "to": "Entity",
            "properties": {
                "first_seen": "TIMESTAMP",
                "last_seen": "TIMESTAMP",
                "frequency": "INT32",
                "confidence": "FLOAT",
            },
        },
        "APPEARS_IN": {
            "from": "Entity", "to": "Event",
            "properties": {
                "role": "STRING",       # "subject", "location", "perpetrator", "victim"
                "confidence": "FLOAT",
            },
        },
        "RELATED_TO": {
            "from": "Entity", "to": "Entity",
            "properties": {
                "relationship": "STRING",  # "affiliated_with", "opposes", "part_of", etc.
                "confidence": "FLOAT",
            },
        },
        "ABOUT_EVENT": {
            "from": "Claim", "to": "Event",
            "properties": {
                "confidence": "FLOAT",
                "first_seen": "TIMESTAMP",
            },
        },
        "PART_OF_THREAD": {
            "from": "Claim", "to": "Narrative",
            "properties": {
                "confidence": "FLOAT",
            },
        },
        "CONTRADICTS": {
            "from": "Claim", "to": "Claim",
            "properties": {
                "contradiction_type": "STRING",
                "strength": "FLOAT",
                "confidence": "FLOAT",
                "detected_at": "TIMESTAMP",
                "resolution_status": "STRING",
            },
        },
        "SUPPORTS": {
            "from": "Claim", "to": "Claim",
            "properties": {
                "strength": "FLOAT",
                "confidence": "FLOAT",
            },
        },
        "REFERENCES": {
            "from": "Broadcast", "to": "Event",
            "properties": {
                "snippet": "STRING",
            },
        },
        "CALLS_BACK": {
            "from": "Broadcast", "to": "Broadcast",
            "properties": {
                "snippet": "STRING",
            },
        },
        "PRECEDES": {
            "from": "Narrative", "to": "Narrative",
            "properties": {
                "drift_amount": "FLOAT",
            },
        },
        "EVOLVED_INTO": {
            "from": "Event", "to": "Event",
            "properties": {
                "transition_type": "STRING",  # "escalation", "de-escalation", "transformation"
                "confidence": "FLOAT",
            },
        },
        "NEXT_EVENT": {
            "from": "Event", "to": "Event",
            "properties": {
                "time_gap_hours": "FLOAT",
            },
        },
        "SUBEVENT_OF": {
            "from": "Event", "to": "Event",
            "properties": {},
        },
    }
```

## Temporal Query Patterns

### Time-Travel: Graph State at Broadcast Time

```cypher
MATCH (b:Broadcast {id: $broadcast_id})
MATCH (c:Claim)
WHERE c.timestamp <= b.aired_at
  AND (NOT EXISTS(c.superceded_by) OR c.superceded_at > b.aired_at)
MATCH (c)-[:ABOUT_EVENT]->(e:Event)
RETURN e, collect(c) AS claims_at_broadcast_time
```

### Narrative Evolution Over Time

```cypher
MATCH (n:Narrative {id: $narrative_id})
MATCH (n)-[:PRECEDES*]->(prev:Narrative)
MATCH (c:Claim)-[:PART_OF_THREAD]->(n)
RETURN n.label, n.drift_score, n.framing, n.last_updated, 
       count(c) AS claim_count
ORDER BY n.last_updated
```

### Entity Impact Over Time

```cypher
MATCH (ent:Entity {name: $entity_name})
MATCH (ent)<-[:MENTIONS]-(c:Claim)
MATCH (c)-[:ABOUT_EVENT]->(e:Event)
RETURN e.title, e.start_time, e.importance,
       collect(c.text) AS claims,
       count(DISTINCT c) AS claim_count
ORDER BY e.start_time
```

### Unresolved Contradictions for Active Narratives

```cypher
MATCH (n:Narrative {active: true})
MATCH (c:Claim)-[:PART_OF_THREAD]->(n)
MATCH (c)-[r:CONTRADICTS]->(other:Claim)
WHERE r.resolution_status = 'unresolved'
RETURN n.label, r.contradiction_type, r.strength, c.text, other.text
ORDER BY r.strength DESC
```

## Graph Evolution Strategy

The graph grows directionally — new data is always added, never modifying existing nodes (except for entity merges and metadata). This creates a append-only temporal structure:

```python
def insert_claim(graph: GraphStore, claim: Claim) -> str:
    """Insert claim without modifying existing data."""
    claim_id = graph.create_node("Claim", claim.to_dict())
    
    # Create edges to existing entities (don't modify entity nodes)
    for entity_id in claim.entity_ids:
        graph.create_edge("MENTIONS", claim_id, entity_id, {
            "first_seen": claim.timestamp,
            "last_seen": claim.timestamp,
            "frequency": 1,
            "confidence": claim.confidence,
        })
    
    # Cluster into event (or create new event)
    event_id = find_or_create_event(graph, claim)
    graph.create_edge("ABOUT_EVENT", claim_id, event_id, {
        "confidence": claim.confidence,
        "first_seen": claim.timestamp,
    })
    
    return claim_id
```

## Graph Maintenance

### Entity Resolution (Merging)

```python
def merge_entities(graph: GraphStore, canonical_id: str, alias_ids: list[str]):
    """Merge alias entities into canonical entity."""
    # Move all edges from aliases to canonical
    for alias_id in alias_ids:
        edges = graph.get_outgoing_edges(alias_id)
        for edge in edges:
            if edge.label in ("MENTIONS", "APPEARS_IN"):
                graph.create_edge(edge.label, edge.src, canonical_id, edge.props)
        graph.delete_node(alias_id)
    
    # Update canonical entity
    graph.update_node(canonical_id, {
        "aliases": graph.get_node_property(canonical_id, "aliases") + alias_ids,
    })
```

### Subgraph Summarization

For dense subgraphs that are no longer active:

```python
async def summarize_subgraph(graph: GraphStore, event_id: str, model: ModelRegistry):
    """Replace dense event subgraph with summary nodes."""
    claims = graph.get_claims_for_event(event_id)
    
    # Generate summary via LLM
    prompt = f"Summarize these claims about an event:\n" + "\n".join(c.text for c in claims)
    summary = await model.get("reasoning").generate(prompt, temperature=0.3, max_tokens=512)
    
    # Create summary node and link
    summary_id = graph.create_node("ContradictionSummary", {
        "summary": summary,
        "claim_count": len(claims),
        "time_range": f"{claims[0].timestamp} - {claims[-1].timestamp}",
    })
    
    # Optionally prune individual claim nodes after archiving
    graph.archive_event(event_id, summary_id)
```
