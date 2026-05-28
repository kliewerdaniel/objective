# Source Reliability Evaluator Agent

## Overview

The source reliability evaluator computes and tracks trust scores for information sources. It uses a combination of behavioral signals and network effects rather than relying on predefined trust lists.

## Responsibility

- Compute dynamic trust scores for each source
- Track retractions and corrections
- Measure corroboration rate with other sources
- Detect coordinated framing (potential propaganda)
- Update trust scores over time

## Interface

```python
class SourceReliabilityEvaluator(BaseAgent):
    name = "source_reliability"
    timeout_seconds = 30.0
    
    async def run(self, context: AgentContext) -> AgentResult:
        """Evaluate and update source reliability."""
        sources = context.graph.get_all_sources()
        
        stats = {"sources_evaluated": 0, "scores_updated": 0}
        results = []
        
        for source in sources:
            score = self._compute_trust_score(source.id, context)
            if score:
                context.graph.update_source_trust(source.id, score)
                results.append({"source_id": source.id, "score": score})
                stats["sources_evaluated"] += 1
                
                if abs(score - (source.trust_score or 0.5)) > 0.1:
                    stats["scores_updated"] += 1
        
        return AgentResult(success=True, data=results, metrics=stats)
    
    def _compute_trust_score(self, source_id: str, 
                              context: AgentContext) -> float:
        """Compute dynamic trust score for a source."""
        source = context.graph.get_source(source_id)
        claims = context.graph.get_source_claims(source_id, limit=200)
        
        if not claims:
            return 0.5  # Neutral starting score
        
        factors = {}
        
        # 1. Retraction rate
        retractions = context.graph.get_source_retractions(source_id, 
                                                           hours=720)  # 30 days
        factors["accuracy"] = 1.0 - (len(retractions) / max(len(claims), 1) * 3)
        factors["accuracy"] = max(0.0, factors["accuracy"])
        
        # 2. Contradiction ratio
        contradictions = context.graph.get_source_contradiction_count(source_id)
        factors["consistency"] = 1.0 - min(
            contradictions / max(len(claims), 1), 1.0
        )
        
        # 3. Corroboration rate
        corroborated = self._compute_corroboration_rate(source_id, claims, context)
        factors["corroboration"] = corroborated
        
        # 4. Source type base
        type_scores = {
            "rss": 0.6,
            "news_api": 0.7,
            "reddit": 0.3,
            "youtube": 0.4,
            "gov_rss": 0.5,
        }
        factors["type_base"] = type_scores.get(source.type, 0.5)
        
        # 5. Longevity bonus
        age_days = context.graph.get_source_age_days(source_id)
        factors["longevity"] = min(age_days / 365, 1.0) * 0.1
        
        # 6. Framing consistency penalty
        if self._detects_coordinated_framing(source_id, claims, context):
            factors["framing_penalty"] = -0.2
        else:
            factors["framing_penalty"] = 0.0
        
        weights = {
            "accuracy": 0.35,
            "consistency": 0.20,
            "corroboration": 0.25,
            "type_base": 0.10,
            "longevity": 0.10,
            "framing_penalty": 1.0,  # Applied directly
        }
        
        score = sum(factors.get(k, 0) * w for k, w in weights.items())
        return max(0.0, min(1.0, score))
    
    def _compute_corroboration_rate(self, source_id: str, claims: list[Claim],
                                     context: AgentContext) -> float:
        """What fraction of this source's claims are corroborated by other sources?"""
        if not claims:
            return 0.0
        
        corroborated = 0
        for claim in claims[:50]:  # Sample first 50
            similar = context.vector.search(claim.embedding, top_k=10)
            other_sources = set()
            for similar_id, _ in similar:
                other_claim = context.graph.get_claim(similar_id)
                if other_claim and other_claim.source_id != source_id:
                    other_sources.add(other_claim.source_id)
            
            if len(other_sources) >= 2:  # At least 2 other sources
                corroborated += 1
        
        return corroborated / min(len(claims), 50)
    
    def _detects_coordinated_framing(self, source_id: str, claims: list[Claim],
                                      context: AgentContext) -> bool:
        """Detect if a source shows signs of coordinated framing."""
        if len(claims) < 10:
            return False
        
        # Check for unusually consistent framing across diverse topics
        frames = [c.framing.political_frame for c in claims if c.framing]
        if not frames:
            return False
        
        frame_consistency = frames.count(frames[0]) / len(frames)
        
        # High consistency + low linguistic variety = possible coordination
        if frame_consistency > 0.9:
            intensities = [c.framing.linguistic_intensity for c in claims if c.framing]
            if intensities:
                intensity_std = np.std(intensities)
                if intensity_std < 0.1:  # Very consistent intensity
                    return True
        
        return False
```

## Trust Score Distribution

| Score Range | Label | Characteristics |
|-------------|-------|-----------------|
| 0.0-0.2 | Very Low | High retraction rate, no corroboration, coordinated framing |
| 0.2-0.4 | Low | Frequent contradictions, low corroboration |
| 0.4-0.6 | Moderate | Typical source, mixed record |
| 0.6-0.8 | High | Low retractions, good corroboration |
| 0.8-1.0 | Very High | Excellent track record, widely corroborated |

## Trust Score Display

Trust scores are displayed as running metrics in the terminal UI and influence how broadcasts reference sources:

```python
def format_source_citation(source_name: str, trust_score: float) -> str:
    """Format a source citation for broadcast."""
    trust_label = "HIGH" if trust_score > 0.7 else "MODERATE" if trust_score > 0.4 else "LOW"
    return f"{source_name} (trust: {trust_label})"
```
