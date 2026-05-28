# Vector Database Schema

## Qdrant Collection Configuration

```python
from qdrant_client import QdrantClient
from qdrant_client.http import models

client = QdrantClient(host="localhost", port=6333)

client.recreate_collection(
    collection_name="objective03",
    vectors_config=models.VectorParams(
        size=384,                    # BGE-small embedding dimension
        distance=models.Distance.COSINE,
    ),
    hnsw_config=models.HnswConfigDiff(
        m=16,                        # Number of edges per node
        ef_construction=200,         # Build-time search width
        ef_search=100,               # Query-time search width
    ),
    optimizers_config=models.OptimizersConfigDiff(
        default_segment_number=2,    # Balance memory and performance
        memmap_threshold=20000,      # Use memmap for large segments
    ),
    wal_config=models.WalConfigDiff(
        wal_capacity_mb=512,         # Write-ahead log size
    ),
)
```

## Payload Schema

Each point in Qdrant stores:

```python
{
    "id": "claim_uuid_or_entity_uuid",
    "vector": [0.123, ...],  # 384-dim embedding
    "payload": {
        "type": "claim",            # or "entity", "narrative", "broadcast"
        "text": "Claim text here",
        "timestamp": 1716850000,    # Unix timestamp
        "source_type": "rss",
        "topic": "conflict",
        "confidence": 0.85,
        "stance": "neutral",
        "entity_ids": ["uuid1", "uuid2"],
        "event_id": "event_uuid",
        "narrative_id": "narrative_uuid",
        "contradiction_count": 3,
        "source_trust": 0.7,
        "language": "en",
    }
}
```

## Collection Indexes

```python
# Payload indexes for filtered search
client.create_payload_index(
    collection_name="objective03",
    field_name="type",
    field_schema=models.PayloadSchemaType.KEYWORD,
)

client.create_payload_index(
    collection_name="objective03",
    field_name="timestamp",
    field_schema=models.PayloadSchemaType.INTEGER,
)

client.create_payload_index(
    collection_name="objective03",
    field_name="topic",
    field_schema=models.PayloadSchemaType.KEYWORD,
)

client.create_payload_index(
    collection_name="objective03",
    field_name="event_id",
    field_schema=models.PayloadSchemaType.KEYWORD,
)
```

## Query Patterns

### Semantic Similarity Search

```python
def find_similar_claims(claim_text: str, embedding: list[float], 
                         client: QdrantClient, top_k: int = 20) -> list[dict]:
    """Find semantically similar claims."""
    results = client.search(
        collection_name="objective03",
        query_vector=embedding,
        query_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="type",
                    match=models.MatchValue(value="claim"),
                ),
            ],
        ),
        limit=top_k,
        with_payload=True,
    )
    return [r.payload for r in results]
```

### Topic-Specific Search

```python
def find_claims_by_topic(topic: str, embedding: list[float], 
                          client: QdrantClient, top_k: int = 20) -> list[dict]:
    """Find claims matching a topic with semantic similarity."""
    results = client.search(
        collection_name="objective03",
        query_vector=embedding,
        query_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="type",
                    match=models.MatchValue(value="claim"),
                ),
                models.FieldCondition(
                    key="topic",
                    match=models.MatchValue(value=topic),
                ),
            ],
        ),
        limit=top_k,
    )
    return [r.payload for r in results]
```

### Time-Restricted Search

```python
def find_claims_in_window(embedding: list[float], start_time: int, 
                           end_time: int, client: QdrantClient) -> list[dict]:
    """Find claims within a time window."""
    results = client.search(
        collection_name="objective03",
        query_vector=embedding,
        query_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="type",
                    match=models.MatchValue(value="claim"),
                ),
                models.FieldCondition(
                    key="timestamp",
                    range=models.Range(
                        gte=start_time,
                        lte=end_time,
                    ),
                ),
            ],
        ),
        limit=50,
    )
    return [r.payload for r in results]
```

### Contradiction Candidate Search

```python
def find_contradiction_candidates(claim_embedding: list[float], 
                                   claim_entities: list[str],
                                   claim_timestamp: int,
                                   client: QdrantClient) -> list[dict]:
    """Find potential contradiction partners."""
    time_window = 7 * 86400  # 7 days in seconds
    
    results = client.search(
        collection_name="objective03",
        query_vector=claim_embedding,
        query_filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="type",
                    match=models.MatchValue(value="claim"),
                ),
                models.FieldCondition(
                    key="timestamp",
                    range=models.Range(
                        gte=claim_timestamp - time_window,
                        lte=claim_timestamp + time_window,
                    ),
                ),
            ],
            must_not=[
                # Don't compare with same source type
                # (handled by application logic)
            ],
        ),
        limit=50,
        score_threshold=0.6,  # Minimum similarity
    )
    return [r.payload for r in results]
```

## Performance Considerations

| Query Type | Latency (p50) | Latency (p99) | Throughput |
|-----------|---------------|---------------|------------|
| Single vector search | 2ms | 10ms | 500/sec |
| Filtered search | 5ms | 25ms | 200/sec |
| Batch upsert (100) | 50ms | 200ms | 2000/sec |
| Point retrieval | 1ms | 5ms | 1000/sec |

## Memory Usage

| Collection Size | RAM (HNSW) | Disk |
|----------------|------------|------|
| 10K vectors | ~30MB | ~50MB |
| 100K vectors | ~300MB | ~500MB |
| 1M vectors | ~3GB | ~5GB |

## Maintenance

```python
def optimize_collection(client: QdrantClient):
    """Optimize vector collection for query performance."""
    client.update_collection(
        collection_name="objective03",
        optimizer_config=models.OptimizersConfigDiff(
            deleted_threshold=0.2,  # Vacuum when 20% deleted
            vacuum_min_vector_number=1000,
        ),
    )

def prune_deleted_points(client: QdrantClient, graph: GraphStore):
    """Remove vectors for deleted claims."""
    # Get all active claim IDs from graph
    active_ids = set(graph.get_all_claim_ids())
    
    # Get all vector IDs
    scroll_result = client.scroll(
        collection_name="objective03",
        limit=1000,
        with_payload=False,
    )
    
    for point in scroll_result[0]:
        if point.id not in active_ids:
            client.delete(
                collection_name="objective03",
                points_selector=models.PointIdsList(points=[point.id]),
            )
```
