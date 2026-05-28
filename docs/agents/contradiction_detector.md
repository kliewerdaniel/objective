# Contradiction Detector Agent

## Overview

The contradiction detector identifies conflicting claims within the same factual domain. It is the epistemic heart of the system — preserving uncertainty rather than resolving it.

## Responsibility

- Compare new claims against existing similar claims
- Classify contradiction type and strength
- Store contradiction edges in the graph
- Track contradiction resolution status
- Maintain contradiction metrics

## Interface

```python
class ContradictionDetector(BaseAgent):
    name = "contradiction_detector"
    timeout_seconds = 60.0
    
    async def run(self, context: AgentContext) -> AgentResult:
        new_claims = context.state.get("new_claims", [])
        if not new_claims:
            return AgentResult(success=True, data=[], metrics={"pairs_checked": 0})
        
        model = await context.models.get("contradiction")
        all_contradictions = []
        stats = {"pairs_checked": 0, "contradictions_found": 0}
        
        for claim in new_claims:
            similar = await context.vector.search(claim.embedding, top_k=20)
            
            for similar_id, similarity in similar:
                if similarity < 0.75:
                    continue
                
                other = context.graph.get_claim(similar_id)
                if not other:
                    continue
                
                if not self._shared_context(claim, other):
                    continue
                
                stats["pairs_checked"] += 1
                
                contradiction = await self._classify_contradiction(claim, other, model)
                if contradiction:
                    all_contradictions.append(contradiction)
                    stats["contradictions_found"] += 1
        
        return AgentResult(
            success=True,
            data=all_contradictions,
            metrics=stats,
        )
    
    async def _classify_contradiction(self, claim_a: Claim, claim_b: Claim,
                                       model: LLMClient) -> Optional[Contradiction]:
        prompt = self._build_contradiction_prompt(claim_a, claim_b)
        response = await model.generate(prompt, temperature=0.0, max_tokens=256, structured=True)
        result = json.loads(response.text)
        
        if result["type"] == "COMPATIBLE" or result["type"] == "UNCERTAIN":
            return None
        
        return Contradiction(
            id=generate_uuid(),
            claim_a=claim_a.id,
            claim_b=claim_b.id,
            contradiction_type=ContradictionType[result["type"]],
            strength=result["strength"],
            confidence=0.8,  # Base confidence for LLM detection
            detected_at=datetime.utcnow(),
        )
    
    def _build_contradiction_prompt(self, a: Claim, b: Claim) -> str:
        return f"""Analyze if these two claims contradict each other.

Claim A: "{a.text}"
  Topic: {a.topic}, Stance: {a.stance}
  Source: {a.source_name} ({a.source_type})
  Confidence: {a.confidence}

Claim B: "{b.text}"
  Topic: {b.topic}, Stance: {b.stance}
  Source: {b.source_name} ({b.source_type})
  Confidence: {b.confidence}

Choose classification:
- DIRECT_CONTRADICTION: Opposite facts, cannot both be true
- NUMERICAL_DISCREPANCY: Different numbers/statistics
- FRAMING_DIFFERENCE: Different framing of same underlying facts
- TEMPORAL_DISCREPANCY: Different timing claims
- COMPATIBLE: Both can be true simultaneously
- UNCERTAIN: Insufficient information

Provide strength score 0.0-1.0

Output JSON: {{"type": "DIRECT_CONTRADICTION", "strength": 0.9, "reasoning": "..."}}"""

    def _shared_context(self, a: Claim, b: Claim) -> bool:
        """Claims must share entities or be in the same event to compare."""
        shared = set(a.entity_ids) & set(b.entity_ids)
        if shared:
            return True
        
        same_event = a.event_id and a.event_id == b.event_id
        if same_event:
            return True
        
        # Check if topics overlap
        if a.topic == b.topic:
            time_diff = abs((a.timestamp - b.timestamp).total_seconds())
            if time_diff < 7 * 86400:  # Within 7 days
                return True
        
        return False
```

## Contradiction Validation

```python
def validate_contradiction(contradiction: Contradiction, 
                           graph: GraphStore) -> bool:
    """Validate a detected contradiction before storing."""
    # 1. Both claims must still exist
    claim_a = graph.get_claim(contradiction.claim_a)
    claim_b = graph.get_claim(contradiction.claim_b)
    if not claim_a or not claim_b:
        return False
    
    # 2. Must not be same claim
    if contradiction.claim_a == contradiction.claim_b:
        return False
    
    # 3. Must not already have a contradiction edge
    existing = graph.get_contradiction(contradiction.claim_a, contradiction.claim_b)
    if existing and existing.contradiction_type == contradiction.contradiction_type:
        return False  # Don't duplicate
    
    # 4. Strength must be above threshold
    if contradiction.strength < 0.3:
        return False
    
    return True
```

## Contradiction Resolution Status

Contradictions progress through statuses:

```python
class ContradictionStatus(Enum):
    UNRESOLVED = "unresolved"          # Freshly detected
    MONITORING = "monitoring"          # Actively tracking for resolution
    EVIDENCE_SHIFTED = "evidence_shifted"  # New evidence favors one side
    SUPERSEDED = "superseded"          # Better claim superseded both
    RETRACTED = "retracted"            # One side was retracted by source
    FALSE = "false_contradiction"      # Determined not actually contradictory
    RESOLVED = "resolved"              # Determined resolved
```

## Contradiction Metrics

| Metric | Computation | Purpose |
|--------|-------------|---------|
| Total contradictions | COUNT(contradictions) | Overall epistemic state |
| New contra. rate | New / day | Rate of new conflicts |
| Resolution rate | Resolved / total | How quickly conflicts resolve |
| Mean strength | AVG(strength) | How sharp conflicts are |
| Type distribution | COUNT() GROUP BY type | What kinds of uncertainty |
| Event density | Contradictions / event | How contested specific events are |
| Source overlap | Avg sources per contra | Evidence depth in conflicts |

## Failure Modes

| Failure | Detection | Handling |
|---------|-----------|----------|
| LLM classifies compatible claims as contradictory | Validation catches (strength check) | Store as low-confidence contradiction |
| Model timeout | Watchdog timer | Retry once, skip pair |
| Vector search returns irrelevant results | Threshold filter (>0.75) | No action needed |
| Contradiction flood (many new claims) | Rate monitoring | Process in batches, reduce top_k |
