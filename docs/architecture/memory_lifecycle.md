# Memory Lifecycle Architecture

## Overview

Memory in objective03 is not a single store. It is a layered system where data moves through stages based on age, relevance, confidence, and access patterns. The system exhibits behavior analogous to human memory: short-term, working, and long-term.

## Memory Layers

```
                    ┌──────────────────────────────────────────────────┐
                    │                 MEMORY LAYERS                    │
                    │                                                  │
                    │  ┌────────────────────────────────────────────┐  │
                    │  │         WORKING MEMORY (in-memory cache)    │  │
                    │  │  Hot claims, recent events, active threads  │  │
                    │  │  Invalidation: time-based + access-based    │  │
                    │  └────────────────────────────────────────────┘  │
                    │                    │                              │
                    │                    ▼                              │
                    │  ┌────────────────────────────────────────────┐  │
                    │  │     SHORT-TERM MEMORY (KuzuDB + Qdrant)    │  │
                    │  │  All claims < 7 days, active narratives    │  │
                    │  │  Full graph traversability                 │  │
                    │  └────────────────────────────────────────────┘  │
                    │                    │                              │
                    │                    ▼                              │
                    │  ┌────────────────────────────────────────────┐  │
                    │  │    LONG-TERM MEMORY (KuzuDB + Summaries)    │  │
                    │  │  Claims > 7 days, consolidated narratives   │  │
                    │  │  Reduced graph density, summary nodes       │  │
                    │  └────────────────────────────────────────────┘  │
                    │                    │                              │
                    │                    ▼                              │
                    │  ┌────────────────────────────────────────────┐  │
                    │  │        ARCHIVAL MEMORY (SQLite/Parquet)     │  │
                    │  │  Raw data, audit logs, full graph snapshots │  │
                    │  │  Not directly queryable, for replay/audit   │  │
                    │  └────────────────────────────────────────────┘  │
                    └──────────────────────────────────────────────────┘
```

## Memory Consolidation Process

The consolidation agent runs daily. It promotes, demotes, and archives data across layers.

```python
class MemoryConsolidator:
    def __init__(self, graph: GraphStore, vector: VectorStore, metadata: SQLiteStore):
        self.graph = graph
        self.vector = vector
        self.metadata = metadata
    
    async def consolidate(self):
        """Run memory consolidation cycle."""
        now = datetime.utcnow()
        
        # 1. Archive old raw documents
        await self._archive_documents(older_than=days=7)
        
        # 2. Consolidate resolved contradictions
        await self._consolidate_contradictions()
        
        # 3. Summarize old narrative threads
        await self._summarize_threads(older_than=days=3)
        
        # 4. Prune low-confidence orphan claims
        await self._prune_low_confidence(threshold=0.3, older_than=days=1)
        
        # 5. Update entity resolution caches
        await self._refresh_entity_cache()
        
        # 6. Archive resolved contradictions
        await self._archive_resolved_contradictions()
        
        logger.info("memory.consolidated",
            archived_docs=self.stats.archived_docs,
            consolidated_threads=self.stats.consolidated_threads,
            pruned_claims=self.stats.pruned_claims,
        )
    
    async def _consolidate_contradictions(self):
        """For contradictions older than threshold, create meta-note."""
        resolved = self.graph.get_resolved_contradictions(older_than=days=7)
        for contra in resolved:
            # Create a summary node linking both sides
            self.graph.create_contradiction_summary(contra)
            # Remove individual contradiction edges
            self.graph.remove_edge(contra.edge_id)
```

## Access Temperature

Memory is tagged with access temperature, which determines cache priority:

| Temperature | Definition | Examples |
|------------|-----------|---------|
| Hot | Accessed in last hour | Current broadcast data, latest claims, active threads |
| Warm | Accessed in last 24h | Recent events, unresolved contradictions |
| Cool | Accessed in last 7 days | Last week's narratives, reference entities |
| Cold | Accessed > 7 days ago | Historical events, archived broadcasts |

The cache eviction policy is LRU-aware:

```python
class WorkingMemory:
    def __init__(self, max_entries: int = 1000):
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.max_entries = max_entries
    
    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            entry = self.cache.pop(key)
            entry.last_access = time.monotonic()
            entry.access_count += 1
            self.cache[key] = entry
            return entry.value
        return None
    
    def set(self, key: str, value: Any, ttl: float = 3600):
        if len(self.cache) >= self.max_entries:
            self._evict()
        self.cache[key] = CacheEntry(
            value=value,
            created=time.monotonic(),
            last_access=time.monotonic(),
            access_count=1,
            ttl=ttl,
        )
    
    def _evict(self):
        """Evict coldest entries. Cold = fewest accesses + oldest last_access."""
        coldest = min(
            self.cache.items(),
            key=lambda x: (x[1].access_count, -x[1].last_access),
        )
        del self.cache[coldest[0]]
```

## Temporal Decay Functions

Confidence and relevance decay over time. Different decay functions apply to different data types:

### Claim Confidence Decay

```python
def confidence_decay(initial_confidence: float, age_hours: float, 
                     verification_count: int) -> float:
    """Confidence decays exponentially but is reinforced by verification."""
    decay_rate = 0.01  # 1% per hour base decay
    verification_bonus = math.log(1 + verification_count) * 0.05
    effective_decay = decay_rate / (1 + verification_bonus)
    return initial_confidence * math.exp(-effective_decay * age_hours)
```

### Entity Relevance Decay

```python
def entity_relevance(entity_id: str, graph: GraphStore) -> float:
    """Entity relevance based on recency and frequency of mentions."""
    mentions = graph.get_entity_mention_times(entity_id)
    if not mentions:
        return 0.0
    
    now = datetime.utcnow()
    recency_score = sum(
        math.exp(-(now - t).total_seconds() / 86400)  # 1-day half-life
        for t in mentions
    )
    frequency_score = math.log(1 + len(mentions)) / 10
    
    return min(1.0, recency_score * 0.7 + frequency_score * 0.3)
```

### Narrative Thread Decay

```python
def narrative_decay(thread_id: str, last_update: datetime) -> float:
    """Narrative decays to archival state if no updates for threshold."""
    age_days = (datetime.utcnow() - last_update).days
    
    if age_days < 1:
        return 1.0  # Active
    elif age_days < 3:
        return 0.8  # Warm
    elif age_days < 7:
        return 0.5  # Cooling
    elif age_days < 30:
        return 0.2  # Cold
    else:
        return 0.0  # Archival (consolidate)
```

## Broadcast Memory (Explicit Recall)

The broadcast system must appear to "remember" previous broadcasts. This is achieved through the broadcast callback system:

```python
class BroadcastMemory:
    def __init__(self, graph: GraphStore):
        self.graph = graph
    
    def get_callbacks(self, event_ids: list[str]) -> list[Callback]:
        """Find previous broadcasts that referenced these events."""
        callbacks = []
        for event_id in event_ids:
            previous_broadcasts = self.graph.get_broadcasts_for_event(event_id, limit=5)
            for bcast in previous_broadcasts:
                callbacks.append(Callback(
                    event_id=event_id,
                    broadcast_id=bcast.id,
                    timestamp=bcast.broadcast_at,
                    snippet=bcast.reference_snippet,
                    days_ago=(datetime.utcnow() - bcast.broadcast_at).days,
                ))
        return callbacks
    
    def format_callback(self, callback: Callback) -> str:
        """Format a callback for inclusion in current broadcast."""
        if callback.days_ago == 0:
            return f"As reported earlier today, {callback.snippet}"
        elif callback.days_ago == 1:
            return f"Yesterday, we reported that {callback.snippet}"
        else:
            return f"{callback.days_ago} days ago, we noted that {callback.snippet}"
```

## Archival Policy

| Data Type | Short-Term | Long-Term | Archive | Delete |
|-----------|-----------|-----------|---------|--------|
| Raw documents | 7 days | N/A | Parquet | 30 days |
| Claims | Active | 30 days | Summary | 90 days |
| Entities | Active | Permanent | N/A | Never |
| Contradictions | Active | 30 days | Summary | 90 days |
| Narratives | Active | 30 days | Summary nodes | 90 days |
| Broadcast scripts | 7 days | 30 days | WAV files | Never |
| Audio files | 1 day | 7 days | Compressed | 30 days |
| Audit logs | N/A | 30 days | Parquet | 1 year |
| Vector embeddings | Active | N/A | N/A | Pruned with claim |
| Graph snapshots | N/A | 30 days | Parquet | 1 year |

## Graph Evolution Over Time

The graph is not static. It evolves through:

1. **Growth** — New claims, entities, edges added continuously
2. **Merging** — Entity resolution merges duplicate nodes
3. **Linking** — Contradiction edges added between claims
4. **Summarization** — Dense subgraphs replaced with summary nodes
5. **Pruning** — Low-confidence, unlinked claims removed after threshold
6. **Archival** — Cold subgraphs moved to summary-only representation

```python
async def evolve_graph(self):
    """One cycle of graph evolution."""
    # Merge duplicate entities
    duplicates = self.graph.find_duplicate_entities(threshold=0.9)
    for canon, alias in duplicates:
        self.graph.merge_entities(canon, alias)
    
    # Summarize dense subgraphs
    dense_subgraphs = self.graph.find_dense_subgraphs(min_nodes=20, max_age_days=30)
    for subgraph in dense_subgraphs:
        summary = await self._summarize_subgraph(subgraph)
        self.graph.replace_with_summary(summary)
    
    # Prune unlinked claims
    orphans = self.graph.find_orphan_claims(older_than_days=7, max_confidence=0.3)
    for claim_id in orphans:
        self.graph.archive_claim(claim_id)
```
