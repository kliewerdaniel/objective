# Memory Decay Strategies

## Overview

Information in the system decays over time. Confidence decreases, relevance wanes, and dormant data is archived. Decay is not deletion — it is a managed transition through memory layers.

## Decay Functions

### Claim Confidence Decay

```python
def claim_confidence_over_time(claim: Claim, graph: GraphStore, 
                                now: datetime = None) -> float:
    """Compute effective confidence considering age and verification."""
    now = now or datetime.utcnow()
    age_hours = (now - claim.timestamp).total_seconds() / 3600
    
    # Base decay: exponential with 24-hour half-life
    half_life = 24  # hours
    decay_factor = math.exp(-math.log(2) * age_hours / half_life)
    
    # Verification boost
    verifications = graph.get_claim_verification_count(claim.id)
    contradictions = graph.get_claim_contradiction_count(claim.id)
    
    verification_boost = math.log(1 + verifications) * 0.05
    contradiction_penalty = math.log(1 + contradictions) * 0.03
    
    effective_confidence = (
        claim.confidence * decay_factor +
        verification_boost -
        contradiction_penalty
    )
    
    return max(0.0, min(1.0, effective_confidence))
```

### Entity Relevance Decay

```python
def entity_relevance_score(entity_id: str, graph: GraphStore) -> float:
    """Compute entity relevance based on recency and frequency of mentions."""
    mentions = graph.get_entity_mention_times(entity_id)
    if not mentions:
        return 0.0
    
    now = datetime.utcnow()
    
    # Recency score with exponential decay (7-day half-life)
    recency = sum(
        math.exp(-(now - t).total_seconds() / (7 * 86400))
        for t in mentions
    )
    
    # Frequency score (logarithmic)
    frequency = math.log(1 + len(mentions)) / math.log(100)  # Normalize to ~1 at 100 mentions
    
    # Diversity score (how many different sources mention this entity)
    sources = len(set(m.source_id for m in mentions))
    diversity = min(sources / 10, 1.0)  # Max at 10 sources
    
    return recency * 0.5 + frequency * 0.3 + diversity * 0.2
```

### Event Relevancy Decay

```python
def event_relevance(event: Event, graph: GraphStore) -> float:
    """Compute event relevance, considering recency and activity."""
    now = datetime.utcnow()
    
    # Age factor
    age_days = (now - event.start_time).days
    age_factor = max(0, 1 - age_days / 30)  # Linear decay over 30 days
    
    # Activity factor (claims in last 24h)
    recent_claims = graph.get_event_claim_count_since(event.id, hours=24)
    activity_factor = min(recent_claims / 10, 1.0)
    
    # Importance factor (computed from source diversity, contradiction density)
    importance_factor = event.importance
    
    return age_factor * 0.3 + activity_factor * 0.4 + importance_factor * 0.3
```

## Memory Transition Thresholds

| Transition | Trigger | Action |
|-----------|---------|--------|
| Active → Warm | No updates for 24h | Reduced query priority |
| Warm → Cool | No updates for 7 days | Move to cool storage in graph |
| Cool → Cold | No updates for 30 days | Summarize, move to archive |
| Cold → Archived | No updates for 90 days | Full archive to Parquet |

```python
def classify_memory_temperature(node_type: str, last_update: datetime) -> str:
    """Classify the memory temperature of a data element."""
    age_days = (datetime.utcnow() - last_update).days
    
    temperatures = {
        "Claim": [(1, "hot"), (3, "warm"), (14, "cool"), (30, "cold")],
        "Event": [(1, "hot"), (7, "warm"), (30, "cool"), (90, "cold")],
        "Narrative": [(1, "hot"), (3, "warm"), (14, "cool"), (30, "cold")],
        "Entity": [(7, "hot"), (30, "warm"), (90, "cool"), (365, "cold")],
    }
    
    thresholds = temperatures.get(node_type, [(1, "hot"), (7, "warm"), (30, "cool")])
    
    for days, label in thresholds:
        if age_days < days:
            return label
    return "archived"
```

## Cache Eviction Policy

```python
class TemperatureAwareCache:
    """Cache that evicts coldest entries first."""
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
    
    def get(self, key: str) -> Optional[Any]:
        if key not in self.cache:
            return None
        entry = self.cache.pop(key)
        entry.access_count += 1
        entry.last_access = time.monotonic()
        self.cache[key] = entry
        return entry.value
    
    def set(self, key: str, value: Any, temperature: str = "hot"):
        self.cache[key] = CacheEntry(
            value=value,
            temperature=temperature,
            access_count=0,
            last_access=time.monotonic(),
            created_at=time.monotonic(),
        )
        if len(self.cache) > self.max_size:
            self._evict()
    
    def _evict(self):
        """Evict coldest entry."""
        temperature_order = {"hot": 0, "warm": 1, "cool": 2, "cold": 3, "archived": 4}
        
        coldest = min(
            self.cache.items(),
            key=lambda x: (
                temperature_order.get(x[1].temperature, 5),
                -x[1].access_count,
                x[1].last_access,
            ),
        )
        del self.cache[coldest[0]]
```

## Automated Archival

```python
def should_archive(node_type: str, node: dict, graph: GraphStore) -> bool:
    """Determine if a node should be archived."""
    now = datetime.utcnow()
    
    if node_type == "Claim":
        # Archive if: old + low confidence + no contradictions + no event link
        age_days = (now - node["timestamp"]).days
        if age_days > 30 and node["confidence"] < 0.5:
            contradictions = graph.get_claim_contradiction_count(node["id"])
            if contradictions == 0 and not node.get("event_id"):
                return True
    
    elif node_type == "Event":
        # Archive if: concluded + no activity for 30 days
        if node.get("status") == "concluded":
            activity = graph.get_event_claim_count_since(node["id"], days=30)
            if activity == 0:
                return True
    
    elif node_type == "Narrative":
        # Archive if: inactive for 7 days
        age_days = (now - node["last_updated"]).days
        if age_days > 7 and not node.get("active"):
            return True
    
    return False
```

## Relevancy Scoring for Queries

```python
def score_search_result(payload: dict, age_days: float) -> float:
    """Score a search result combining semantic similarity and freshness."""
    similarity = payload.get("score", 0.5)
    
    # Freshness bonus (decay over 7 days)
    freshness = math.exp(-age_days / 7)
    
    # Source trust bonus
    source_trust = payload.get("source_trust", 0.5)
    
    # Combined score
    return similarity * 0.6 + freshness * 0.25 + source_trust * 0.15
```
