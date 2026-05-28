# Graph Update Pipeline

## Pipeline Flow

```
Claims + Documents + Entities
    │
    ▼
Entity Resolution (merge with existing)
    │
    ▼
Event Clustering (assign to events)
    │
    ▼
Graph Insertion (nodes)
    │
    ▼
Edge Creation (relationships)
    │
    ▼
Embedding Generation
    │
    ▼
Qdrant Insertion
    │
    ▼
SQLite Provenance Log
```

## Batch Insert Strategy

KuzuDB supports efficient batch operations. The pipeline collects nodes and edges and inserts them in transactions:

```python
async def batch_graph_update(context: AgentContext):
    """Batch update graph with multiple claims."""
    claims = context.state["claims"]
    documents = context.state["documents"]
    entities = context.state["entities"]
    
    with context.graph.transaction():
        # Batch insert documents
        for doc in documents:
            context.graph.create_node("Document", doc.to_dict())
        
        # Batch insert entities
        for entity in entities:
            if not context.graph.node_exists("Entity", entity.id):
                context.graph.create_node("Entity", entity.to_dict())
        
        # Batch insert claims with edges
        for claim in claims:
            context.graph.create_node("Claim", claim.to_dict())
            context.graph.create_edge("EXTRACTED_FROM", claim.id, 
                                     claim.source_document_id, {...})
            for entity_id in claim.entity_ids:
                context.graph.create_edge("MENTIONS", claim.id, entity_id, {...})
            if claim.event_id:
                context.graph.create_edge("ABOUT_EVENT", claim.id, claim.event_id, {...})
```

## Embedding Generation

Claims and entities are embedded for vector search:

```python
async def generate_embeddings(items: list, model: LLMClient, 
                              batch_size: int = 32) -> dict[str, list[float]]:
    """Generate embeddings for items in batches."""
    embeddings = {}
    
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        texts = [item.text for item in batch]
        
        response = model.create_embedding(texts)
        
        for j, embedding in enumerate(response["data"]):
            embeddings[batch[j].id] = embedding["embedding"]
    
    return embeddings
```

## Transaction Size Guidelines

| Batch Size | Memory | Duration | Risk |
|-----------|--------|----------|------|
| 10 claims | Low | <1s | Very low |
| 100 claims | Medium | 3-5s | Low |
| 1000 claims | High | 15-30s | Moderate |
| 10000 claims | Very high | 60-120s | High |
