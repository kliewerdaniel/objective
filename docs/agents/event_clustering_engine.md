# Event Clustering Engine

## Overview

The event clustering engine groups claims into events based on entity overlap, temporal proximity, and semantic similarity. Events are the primary organizational unit in the graph.

## Responsibility

- Assign new claims to existing events or create new events
- Merge events when claims reveal them to be the same
- Track event lifecycle (emerging, ongoing, concluding, archived)
- Compute event importance scores
- Maintain event-entity-claim relationships

## Interface

```python
class EventClusteringEngine(BaseAgent):
    name = "event_clustering"
    timeout_seconds = 60.0
    
    async def run(self, context: AgentContext) -> AgentResult:
        new_claims = context.state.get("new_claims", [])
        if not new_claims:
            return AgentResult(success=True, data=[], metrics={"claims_clustered": 0})
        
        stats = {
            "claims_clustered": 0,
            "events_created": 0,
            "events_updated": 0,
        }
        
        for claim in new_claims:
            event_id = await self._assign_to_event(claim, context)
            if event_id:
                stats["claims_clustered"] += 1
        
        # Check for events that should be merged
        merges = await self._find_merge_candidates(context)
        for target_id, source_id in merges:
            context.graph.merge_events(target_id, source_id)
            stats["events_updated"] += 1
        
        return AgentResult(success=True, data={
            "claims_clustered": stats["claims_clustered"],
            "events_created": stats["events_created"],
            "events_merged": len(merges),
        }, metrics=stats)
    
    async def _assign_to_event(self, claim: Claim, 
                                context: AgentContext) -> Optional[str]:
        """Assign a claim to an existing event or create a new one."""
        # Find candidate events by shared entities
        candidates = context.graph.find_events_by_entities(
            claim.entity_ids,
            time_window_hours=72,
        )
        
        if not candidates:
            # Need entities to cluster - wait for entity extraction
            if not claim.entity_ids:
                return None
            
            # Create new event
            event = Event(
                id=generate_uuid(),
                title="",  # Will be generated later
                description="",
                start_time=claim.timestamp,
                end_time=claim.timestamp,
                status="emerging",
                importance=self._compute_initial_importance(claim),
            )
            context.graph.create_event(event)
            context.graph.link_claim_to_event(claim.id, event.id)
            return event.id
        
        # Score candidates
        scored = []
        for event_id in candidates:
            score = self._score_event_match(claim, event_id, context)
            scored.append((score, event_id))
        
        scored.sort(reverse=True)
        best_score, best_event = scored[0]
        
        if best_score > 0.5:
            # Assign to existing event
            context.graph.link_claim_to_event(claim.id, best_event)
            context.graph.update_event_time(best_event, claim.timestamp)
            context.graph.update_event_importance(best_event)
            return best_event
        else:
            # Create new event
            event = Event(
                id=generate_uuid(),
                title="",
                description="",
                start_time=claim.timestamp,
                end_time=claim.timestamp,
                status="emerging",
                importance=self._compute_initial_importance(claim),
            )
            context.graph.create_event(event)
            context.graph.link_claim_to_event(claim.id, event.id)
            return event.id
    
    def _score_event_match(self, claim: Claim, event_id: str, 
                           context: AgentContext) -> float:
        """Score how well a claim matches an existing event."""
        event = context.graph.get_event(event_id)
        if not event:
            return 0.0
        
        score = 0.0
        
        # Entity overlap
        event_entities = set(context.graph.get_event_entity_ids(event_id))
        claim_entities = set(claim.entity_ids)
        if event_entities and claim_entities:
            overlap = len(event_entities & claim_entities)
            union = len(event_entities | claim_entities)
            score += (overlap / union) * 0.5
        
        # Temporal proximity
        time_diff = abs((claim.timestamp - event.start_time).total_seconds())
        if time_diff < 86400:  # Within 1 day
            score += 0.3 * (1 - time_diff / 86400)
        elif time_diff < 604800:  # Within 1 week
            score += 0.15 * (1 - time_diff / 604800)
        
        # Topic match
        event_topics = context.graph.get_event_topics(event_id)
        if claim.topic in event_topics:
            score += 0.2
        
        return score
    
    def _compute_initial_importance(self, claim: Claim) -> float:
        """Compute initial event importance from first claim."""
        importance = claim.confidence * 0.3
        if claim.topic in ("conflict", "disaster", "politics"):
            importance += 0.2
        return min(importance, 1.0)
```

## Event Importance Scoring

```python
def compute_event_importance(event_id: str, graph: GraphStore) -> float:
    """Compute event importance from multiple factors."""
    event = graph.get_event(event_id)
    claims = graph.get_event_claims(event_id)
    
    if not claims:
        return 0.0
    
    factors = {}
    
    # Claim volume
    factors["volume"] = min(len(claims) / 50, 1.0)  # Max at 50 claims
    
    # Source diversity
    sources = set(c.source_name for c in claims)
    factors["source_diversity"] = min(len(sources) / 10, 1.0)  # Max at 10 sources
    
    # Temporal span
    if len(claims) > 1:
        span_hours = (max(c.timestamp for c in claims) - 
                      min(c.timestamp for c in claims)).total_seconds() / 3600
        factors["longevity"] = min(span_hours / 168, 1.0)  # Max at 1 week
    
    # Contradiction density
    contradictions = graph.get_event_contradictions(event_id)
    if len(claims) > 0:
        factors["contested"] = min(len(contradictions) / len(claims), 1.0)
    
    # Entity prominence
    entities = graph.get_event_entities(event_id)
    prominent = [e for e in entities if graph.get_entity_mention_count(e.id) > 10]
    factors["entity_prominence"] = min(len(prominent) / 5, 1.0)
    
    # Weighted combination
    weights = {
        "volume": 0.30,
        "source_diversity": 0.25,
        "longevity": 0.20,
        "contested": 0.15,
        "entity_prominence": 0.10,
    }
    
    importance = sum(factors.get(k, 0) * w for k, w in weights.items())
    return max(0.0, min(1.0, importance))
```

## Event Title Generation

```python
async def generate_event_title(event_id: str, model: LLMClient, 
                                graph: GraphStore) -> str:
    """Generate or update an event title from its claims."""
    claims = graph.get_event_claims(event_id, limit=10)
    texts = [c.text for c in claims[:5]]
    
    prompt = f"""Generate a concise title (10 words max) for this event:
{chr(10).join(f"- {t}" for t in texts)}
Title:"""
    
    response = await model.generate(prompt, temperature=0.3, max_tokens=50)
    return response.text.strip().strip('"')
```

## Event Lifecycle

```python
def classify_event_stage(event: Event, graph: GraphStore) -> str:
    """Classify the lifecycle stage of an event."""
    claims_last_24h = graph.get_event_claim_count_since(event.id, hours=24)
    age_days = (datetime.utcnow() - event.start_time).days
    
    if not claims_last_24h and age_days > 7:
        return "archived"
    elif not claims_last_24h and age_days > 2:
        return "dormant"
    elif claims_last_24h < 3 and age_days < 2:
        return "emerging"
    elif claims_last_24h >= 3:
        return "active"
    elif event.status == "concluded":
        return "concluded"
    else:
        return "ongoing"
```

## Merge Detection

```python
async def _find_merge_candidates(self, context: AgentContext) -> list[tuple[str, str]]:
    """Find events that should be merged."""
    active_events = context.graph.get_active_events(hours=72)
    
    merges = []
    for i, a in enumerate(active_events):
        for b in active_events[i+1:]:
            # Check entity overlap
            entities_a = set(context.graph.get_event_entity_ids(a.id))
            entities_b = set(context.graph.get_event_entity_ids(b.id))
            
            if not entities_a or not entities_b:
                continue
            
            overlap = len(entities_a & entities_b)
            min_len = min(len(entities_a), len(entities_b))
            
            if overlap / min_len >= 0.5:  # 50% entity overlap
                merges.append((a.id, b.id))  # Merge b into a
    
    return merges
```
