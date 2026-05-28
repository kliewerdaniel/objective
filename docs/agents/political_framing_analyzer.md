# Political Framing Analyzer Agent

## Overview

The framing analyzer detects political and narrative framing in claims. It classifies the ideological slant, rhetorical framing, and linguistic patterns used by sources. This enables the system to track how different sources frame the same events differently.

## Responsibility

- Classify political framing (left, right, establishment, alternative, independent)
- Detect rhetorical framing (e.g., "crisis", "conflict", "incident")
- Measure framing convergence/divergence across sources
- Track linguistic markers of framing
- Update framing metrics in the graph

## Interface

```python
class FramingAnalyzer(BaseAgent):
    name = "framing_analyzer"
    timeout_seconds = 60.0
    
    async def run(self, context: AgentContext) -> AgentResult:
        model = await context.models.get("classification")
        
        # Get claims since last analysis
        claims = context.graph.get_claims_since(
            hours=context.config.get("analysis_window_hours", 24)
        )
        
        if not claims:
            return AgentResult(success=True, data=[], metrics={"claims_analyzed": 0})
        
        stats = {"claims_analyzed": 0, "frames_detected": 0}
        framing_results = []
        
        for claim in claims:
            frame = await self._analyze_frame(claim, model)
            if frame:
                context.graph.update_claim_framing(claim.id, frame)
                framing_results.append(frame)
                stats["claims_analyzed"] += 1
                stats["frames_detected"] += 1
        
        # Compute aggregate metrics
        aggregate = self._compute_aggregate_metrics(framing_results)
        context.graph.update_framing_metrics(aggregate)
        
        return AgentResult(
            success=True, 
            data={"individual": framing_results, "aggregate": aggregate},
            metrics=stats,
        )
    
    async def _analyze_frame(self, claim: Claim, 
                              model: LLMClient) -> Optional[FramingResult]:
        prompt = f"""Analyze the political and rhetorical framing of this claim:

Claim: "{claim.text}"
Source: {claim.source_name}
Topic: {claim.topic}

Classify:
1. Political frame: left, right, establishment, alternative, independent, neutral
2. Rhetorical frame: crisis, conflict, progress, decline, threat, opportunity, reform, stability, uncertainty
3. Emotional tone: analytical, alarmed, neutral, sympathetic, hostile, fearful
4. Linguistic intensity: 0.0-1.0 (how emotionally charged)
5. Narrative archetype: victimhood, heroism, conspiracy, reform, decline, progress

Output JSON:
{{
    "political_frame": "establishment",
    "rhetorical_frame": "conflict",
    "emotional_tone": "analytical",
    "linguistic_intensity": 0.4,
    "narrative_archetype": "decline",
    "confidence": 0.85
}}"""
        
        response = await model.generate(prompt, temperature=0.0, max_tokens=256, structured=True)
        return self._parse_framing(response.text)
    
    def _compute_aggregate_metrics(self, results: list[FramingResult]) -> dict:
        """Compute aggregate framing metrics."""
        if not results:
            return {}
        
        frames = [r.political_frame for r in results]
        tones = [r.emotional_tone for r in results]
        intensities = [r.linguistic_intensity for r in results]
        
        return {
            "political_framing_distribution": {
                frame: frames.count(frame) / len(frames)
                for frame in set(frames)
            },
            "dominant_frame": max(set(frames), key=frames.count),
            "average_intensity": sum(intensities) / len(intensities),
            "dominant_tone": max(set(tones), key=tones.count),
            "frame_diversity": len(set(frames)) / len(frames),
        }
```

## Framing Categories

```yaml
political_frames:
  left: ["progressive", "social justice", "equality", "anti-corporate"]
  right: ["nationalist", "traditional", "free market", "anti-regulation"]
  establishment: ["centrist", "institutional", "bipartisan"]
  alternative: ["anti-establishment", "populist", "outsider"]
  independent: ["non-aligned", "neutral"]
  neutral: ["factual reporting", "no framing detected"]

rhetorical_frames:
  crisis: ["emergency", "catastrophe", "disaster"]
  conflict: ["battle", "war", "fight", "clash"]
  progress: ["advancement", "growth", "improvement", "breakthrough"]
  decline: ["deterioration", "collapse", "decline", "fall"]
  threat: ["danger", "risk", "menace", "hazard"]
  opportunity: ["chance", "potential", "prospect", "possibility"]
  reform: ["change", "transformation", "overhaul", "revision"]
  stability: ["steady", "stable", "consistent", "balanced"]
  uncertainty: ["unclear", "unknown", "ambiguous", "unconfirmed"]

narrative_archetypes:
  - victimhood
  - heroism
  - conspiracy
  - reform
  - decline
  - progress
  - betrayal
  - redemption
```

## Framing Convergence Tracking

```python
class FramingConvergence:
    def __init__(self, graph: GraphStore):
        self.graph = graph
    
    def measure_convergence(self, event_id: str) -> float:
        """Measure how much sources converge on framing for an event.
        0.0 = all sources disagree, 1.0 = all sources agree."""
        frames = self.graph.get_event_framings(event_id)
        if not frames:
            return 0.0
        
        # Entropy-based convergence: lower entropy = more convergence
        frame_counts = {}
        for frame in frames:
            key = f"{frame.political_frame}/{frame.rhetorical_frame}"
            frame_counts[key] = frame_counts.get(key, 0) + 1
        
        total = sum(frame_counts.values())
        probabilities = [c / total for c in frame_counts.values()]
        entropy = -sum(p * math.log(p) for p in probabilities)
        max_entropy = math.log(len(frame_counts))
        
        if max_entropy == 0:
            return 1.0
        return 1.0 - (entropy / max_entropy)
    
    def track_linguistic_markers(self, event_id: str, time_horizon: str = "24h") -> dict:
        """Track which linguistic markers are being used by different sources."""
        claims = self.graph.get_event_claims(event_id, time_horizon)
        
        markers = {}
        for claim in claims:
            for frame_type, keywords in FRAMING_KEYWORDS.items():
                for keyword in keywords:
                    if keyword.lower() in claim.text.lower():
                        if keyword not in markers:
                            markers[keyword] = {"count": 0, "sources": set()}
                        markers[keyword]["count"] += 1
                        markers[keyword]["sources"].add(claim.source_name)
        
        return markers
```

## Source Framing Profile

Each source develops a framing profile over time:

```python
def get_source_profile(source_id: str, graph: GraphStore) -> dict:
    """Get the framing profile of a source."""
    claims = graph.get_source_claims(source_id, limit=500)
    if not claims:
        return {}
    
    frames = []
    for claim in claims:
        if claim.framing:
            frames.append(claim.framing)
    
    if not frames:
        return {}
    
    return {
        "dominant_political_frame": max(set(f.political_frame for f in frames), 
                                        key=[f.political_frame for f in frames].count),
        "average_intensity": sum(f.linguistic_intensity for f in frames) / len(frames),
        "frame_consistency": len(set(f.political_frame for f in frames)) / len(frames),
        "common_rhetorical_frames": list(set(f.rhetorical_frame for f in frames))[:3],
    }
```

## Broadcast Integration

```python
def build_framing_segment(event_id: str, graph: GraphStore) -> str:
    """Generate a framing analysis segment for broadcast."""
    frames = graph.get_event_framings(event_id)
    if not frames:
        return ""
    
    convergence = FramingConvergence(graph).measure_convergence(event_id)
    
    if convergence > 0.8:
        return f"Sources demonstrate high framing convergence on this event. Political frames align across {len(set(f.source_name for f in frames))} sources."
    elif convergence < 0.3:
        frames_by_source = {}
        for f in frames:
            frames_by_source.setdefault(f.source_name, set()).add(f.political_frame)
        divergent = [s for s, fs in frames_by_source.items() if len(fs) > 1]
        if divergent:
            return f"Significant framing divergence detected. {len(divergent)} sources employ multiple political framings, suggesting editorial inconsistency."
        return f"Low framing convergence. Sources employ distinct political framings: {', '.join(set(f.political_frame for f in frames))}."
    else:
        return "Moderate framing convergence. Sources generally align on narrative framing with some variation in emphasis."
```
