# Contradiction Management System

## Overview

Contradiction preservation is the core philosophical and technical innovation of objective03. Unlike conventional systems that resolve contradictions into a single narrative, objective03 treats contradictions as first-class entities that persist, evolve, and inform the broadcast.

## Contradiction Types

| Type | Definition | Example | Detection Method |
|------|-----------|---------|-----------------|
| Direct | Two claims assert opposite facts | "Explosion caused by mechanical failure" vs "Explosion caused by sabotage" | LLM classification |
| Numerical | Claims differ on quantifiable values | "50 casualties" vs "200 casualties" | Entity comparison |
| Temporal | Claims disagree on timing | "Event occurred at 14:00" vs "Event occurred at 16:00" | Entity comparison |
| Source | Contradictory claims from same source | Source A says X on Monday, says not-X on Tuesday | Graph query |
| Framing | Different framing of same event | "Protest" vs "Riot" vs "Civil demonstration" | Framing classifier |
| Contextual | Claims contradict when combined | "Government denies involvement" + "Government officials observed at scene" | LLM reasoning |
| Epistemic | Disagreement on certainty | "Confirmed attack" vs "Alleged attack" | Stance comparison |

## Contradiction Schema

```python
@dataclass
class Contradiction:
    id: str                          # UUID
    claim_a: str                     # Claim ID
    claim_b: str                     # Claim ID
    contradiction_type: ContradictionType
    strength: float                  # 0.0 (weak) to 1.0 (strong contradiction)
    confidence: float                # Detection confidence
    detected_at: datetime
    last_evaluated: datetime
    resolution_status: ResolutionStatus
    resolution_evidence: Optional[str]  # If resolved, what evidence
    source_overlap: float            # How much source overlap exists (0-1)
    context_embedding: list[float]   # Embedding of the contradiction context
```

### Resolution Status

```python
class ResolutionStatus(Enum):
    UNRESOLVED = "unresolved"          # Both claims active, no resolution
    EVIDENCE_SHIFTED = "evidence_shifted"  # One claim gained more evidence
    CLAIM_RETRACTED = "claim_retracted"   # One claim retracted by source
    CLAIM_SUPERSEDED = "claim_superseded" # Better information available
    MERGED = "merged"                  # Claims actually compatible
    FALSE_CONTRADICTION = "false"      # Detected but not actually contradictory
```

## Contradiction Detection Pipeline

```
New Claim
    │
    ▼
1. Embedding Generation
    │
    ▼
2. Vector Similarity Search (top-20 nearest neighbors)
    │   │
    │   ▼
    ├── Threshold check: similarity > 0.75
    │
    ▼
3. Context Overlap Check
    │   └── Same entities? Same event? Same timeframe?
    │
    ▼
4. LLM Contradiction Classification
    │   └── Prompt: "Are these claims contradictory? Type? Strength?"
    │   │   └── Direct contradiction? → Edge
    │   │   └── Compatible? → No edge
    │   │   └── Ambiguous? → Weak edge with low confidence
    │
    ▼
5. Graph Update
    │   └── Insert contradiction edge between claims
    │
    ▼
6. Metrics Update
    │   └── Contradiction count, density, type distribution
```

## Detection Pseudocode

```python
class ContradictionDetector:
    def __init__(self, vector_store: VectorStore, graph_store: GraphStore, 
                 model_registry: ModelRegistry):
        self.vector = vector_store
        self.graph = graph_store
        self.model = model_registry
    
    async def find_contradictions(self, claim: Claim) -> list[Contradiction]:
        """Find all contradictions between a claim and existing claims."""
        contradictions = []
        
        # Step 1: Find semantically similar claims
        similar = await self.vector.search(claim.embedding, top_k=20)
        
        for other_id, similarity in similar:
            if similarity < 0.75:
                continue
            
            other = self.graph.get_claim(other_id)
            if not other:
                continue
            
            # Step 2: Check context overlap
            if not self._shared_context(claim, other):
                continue
            
            # Step 3: Check for exact contradiction or compatibility
            contradiction_type, strength = await self._classify_contradiction(
                claim.text, other.text,
                claim.entities, other.entities,
                claim.stance, other.stance,
            )
            
            if contradiction_type != ContradictionType.NONE:
                contradictions.append(Contradiction(
                    id=generate_uuid(),
                    claim_a=claim.id,
                    claim_b=other.id,
                    contradiction_type=contradiction_type,
                    strength=strength,
                    confidence=similarity,
                    detected_at=datetime.utcnow(),
                    last_evaluated=datetime.utcnow(),
                    resolution_status=ResolutionStatus.UNRESOLVED,
                    source_overlap=self._source_overlap(claim, other),
                    context_embedding=[],
                ))
        
        return contradictions
    
    def _shared_context(self, a: Claim, b: Claim) -> bool:
        """Check if two claims share enough context to be comparable."""
        # Must share at least one entity
        shared_entities = set(a.entity_ids) & set(b.entity_ids)
        if not shared_entities:
            return False
        
        # Must be within 7 days of each other (or same event cluster)
        time_diff = abs((a.timestamp - b.timestamp).total_seconds())
        same_event = a.event_id and a.event_id == b.event_id
        if time_diff > 7 * 86400 and not same_event:
            return False
        
        return True
    
    async def _classify_contradiction(self, text_a: str, text_b: str,
                                       entities_a: list[str], entities_b: list[str],
                                       stance_a: str, stance_b: str) -> tuple:
        """Use LLM to classify the contradiction type and strength."""
        prompt = f"""You are analyzing two claims about the same topic.
Determine if they are contradictory, and if so, what type.

Claim A: "{text_a}" (stance: {stance_a})
Claim B: "{text_b}" (stance: {stance_b})

Choose one:
- DIRECT_CONTRADICTION (they assert opposite facts)
- NUMERICAL_DISCREPANCY (they give different numbers)
- FRAMING_DIFFERENCE (they use different framings)
- COMPATIBLE (they can both be true)
- UNCERTAIN (can't determine)

Also provide a strength score (0.0 to 1.0).

Output JSON: {{"type": "...", "strength": 0.0}}"""

        response = await self.model.get("contradiction").generate(
            prompt=prompt, temperature=0.0, max_tokens=128, structured=True,
        )
        
        return self._parse_contradiction_response(response.text)
```

## Contradiction Indexing

Contradictions are indexed for efficient query:

```sql
-- SQLite contradiction index (for fast metadata queries)
CREATE TABLE contradiction_index (
    id TEXT PRIMARY KEY,
    claim_a_id TEXT NOT NULL,
    claim_b_id TEXT NOT NULL,
    contradiction_type TEXT NOT NULL,
    strength REAL NOT NULL,
    confidence REAL NOT NULL,
    detected_at REAL NOT NULL,
    resolution_status TEXT NOT NULL DEFAULT 'unresolved',
    resolved_at REAL,
    FOREIGN KEY (claim_a_id) REFERENCES claims(id),
    FOREIGN KEY (claim_b_id) REFERENCES claims(id)
);

CREATE INDEX idx_contra_unresolved ON contradiction_index(resolution_status);
CREATE INDEX idx_contra_claim_a ON contradiction_index(claim_a_id);
CREATE INDEX idx_contra_claim_b ON contradiction_index(claim_b_id);
CREATE INDEX idx_contra_type ON contradiction_index(contradiction_type);
CREATE INDEX idx_contra_strength ON contradiction_index(strength DESC);
```

In KuzuDB, contradictions are edges between claim nodes:

```cypher
CREATE REL TABLE CONTRADICTS(
    contradiction_type STRING,
    strength FLOAT,
    confidence FLOAT,
    detected_at TIMESTAMP,
    resolution_status STRING
)
```

## Contradiction Query Patterns

### Get all active contradictions for an event

```cypher
MATCH (e:Event {id: $event_id})
MATCH (e)<-[:ABOUT_EVENT]-(c1:Claim)
MATCH (c1)-[r:CONTRADICTS]-(c2:Claim)
WHERE r.resolution_status = 'unresolved'
RETURN c1, c2, r
ORDER BY r.strength DESC
```

### Get contradiction density over time

```cypher
MATCH (c:Claim)-[r:CONTRADICTS]->()
WHERE c.timestamp >= $start_time AND c.timestamp < $end_time
RETURN date_trunc('hour', c.timestamp) AS hour, 
       count(r) AS contradiction_count,
       count(DISTINCT r.contradiction_type) AS type_diversity
ORDER BY hour
```

### Find "lonely" claims (no contradictions, high confidence)

```cypher
MATCH (c:Claim)
WHERE c.confidence > 0.8
  AND NOT (c)-[:CONTRADICTS]-()
  AND NOT (c)-[:SUPPORTS]-()
RETURN c
ORDER BY c.confidence DESC
LIMIT 20
```

## Contradiction Metrics

| Metric | Definition | Purpose |
|--------|-----------|---------|
| Contradiction count | Total active contradictions | Overall system health |
| Contradiction density | Contradictions / total claim pairs | How contested the knowledge is |
| Resolution rate | Resolved contradictions / total | Epistemic progress |
| Type distribution | % per contradiction type | What kinds of uncertainty |
| Mean time to resolution | Average age at resolution | How quickly conflicts resolve |
| Source overlap | Avg sources per contradiction | Evidence depth |
| Strength distribution | Histogram of contradiction strengths | How sharp conflicts are |
| Lonely claim ratio | Claims with no connections | Coverage gaps |

These metrics are exposed to the terminal UI and influence broadcast content.

## Broadcast Integration

Contradictions directly shape broadcast content:

```python
def select_contradictions_for_broadcast(graph: GraphStore, max_items: int = 3) -> list:
    """Select contradictions that make good broadcast content."""
    candidates = graph.get_unresolved_contradictions()
    
    # Score by broadcast value
    scored = []
    for c in candidates:
        score = (
            c.strength * 0.4 +
            c.source_overlap * 0.3 +
            (1 - age_factor(c.detected_at)) * 0.2 +
            (0.5 if c.contradiction_type in (DIRECT, NUMERICAL) else 0.0) * 0.1
        )
        scored.append((score, c))
    
    scored.sort(reverse=True)
    return [c for _, c in scored[:max_items]]
```

## Anti-Patterns to Avoid

1. **Forcing resolution** — Do not automatically pick a "correct" side
2. **Ignoring weak contradictions** — Weak contradictions can become strong with evidence
3. **Contradiction fatigue** — Too many contradictions dilute the signal; use thresholds
4. **False contradiction propagation** — Validate before storing; false contradictions erode trust
5. **Source blending** — Don't create contradictions between unrelated sources (different regions, different domains)
