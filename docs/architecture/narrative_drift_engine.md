# Narrative Drift Engine

## Overview

Narrative drift is the measurement of how language, framing, and claims about a topic change over time. objective03 treats drift as a first-class signal — drift is not noise to be filtered, but information to be measured and broadcast.

## Drift Dimensions

| Dimension | What It Measures | How | Example |
|-----------|-----------------|-----|---------|
| Linguistic drift | Changes in word choice and terminology | Embedding trajectory over time | "Conflict" → "War" → "Genocide" |
| Framing drift | Changes in political/narrative framing | Classifier scores over time | "Protest" → "Riot" → "Insurrection" |
| Confidence drift | Changes in certainty levels | Confidence score trends | "Alleged" → "Confirmed" (rising certainty) |
| Source drift | Changes in which sources dominate | Source diversity metrics | Independent → State media dominance |
| Entity drift | Changes in mentioned entities | Entity co-occurrence shifts | "Rebels" → "Foreign fighters" |
| Contradiction drift | Changes in contradiction patterns | Contradiction type evolution | Numerical → Direct contradictions |
| Stance drift | Changes in stance distribution | Stance classifier trends | Neutral → Polarized |
| Temporal drift | Changes in event timelines | Temporal reference shifts | "Last week" → "Months ago" |

## Drift Detection Pipeline

```python
class NarrativeDriftEngine:
    def __init__(self, vector_store: VectorStore, graph_store: GraphStore, 
                 model_registry: ModelRegistry):
        self.vector = vector_store
        self.graph = graph_store
        self.model = model_registry
    
    async def measure_drift(self, narrative_id: str, 
                            window_size: str = "24h") -> DriftReport:
        """Measure drift for a narrative thread over a time window."""
        narrative = self.graph.get_narrative(narrative_id)
        claims = self.graph.get_thread_claims(narrative_id)
        
        # Partition claims by time window
        windows = self._partition_by_time(claims, window_size)
        
        if len(windows) < 2:
            return DriftReport(narrative_id=narrative_id, drift_score=0.0, windows=1)
        
        # Measure drift between consecutive windows
        drift_scores = []
        for i in range(1, len(windows)):
            score = await self._window_drift(windows[i-1], windows[i])
            drift_scores.append(score)
        
        # Aggregate
        total_drift = sum(ds.total for ds in drift_scores) / len(drift_scores)
        max_drift = max(ds.total for ds in drift_scores)
        drift_acceleration = self._compute_acceleration(drift_scores)
        
        return DriftReport(
            narrative_id=narrative_id,
            drift_score=total_drift,
            max_drift=max_drift,
            acceleration=drift_acceleration,
            window_count=len(windows),
            dimension_scores={
                "linguistic": sum(d.linguistic for d in drift_scores) / len(drift_scores),
                "framing": sum(d.framing for d in drift_scores) / len(drift_scores),
                "confidence": sum(d.confidence for d in drift_scores) / len(drift_scores),
                "source": sum(d.source for d in drift_scores) / len(drift_scores),
            },
        )
    
    async def _window_drift(self, window_a: list[Claim], window_b: list[Claim]) -> WindowDrift:
        """Measure drift between two time windows."""
        # Compute embeddings for each window
        emb_a = await self._embed_claims(window_a)
        emb_b = await self._embed_claims(window_b)
        
        # Linguistic drift: cosine distance between window centroids
        linguistic = 1 - cosine_similarity(emb_a, emb_b)
        
        # Framing drift: change in framing classifier output
        framing_a = await self._classify_framing(window_a)
        framing_b = await self._classify_framing(window_b)
        framing = self._framing_distance(framing_a, framing_b)
        
        # Confidence drift: change in confidence distribution
        conf_a = [c.confidence for c in window_a]
        conf_b = [c.confidence for c in window_b]
        confidence = abs(np.mean(conf_a) - np.mean(conf_b))
        
        # Source drift: change in source diversity
        sources_a = set(c.source for c in window_a)
        sources_b = set(c.source for c in window_b)
        source = 1 - len(sources_a & sources_b) / max(len(sources_a | sources_b), 1)
        
        total = (linguistic * 0.35 + framing * 0.25 + confidence * 0.2 + source * 0.2)
        
        return WindowDrift(linguistic=linguistic, framing=framing, 
                          confidence=confidence, source=source, total=total)
    
    def _compute_acceleration(self, scores: list[WindowDrift]) -> float:
        """Is drift accelerating or decelerating? Positive = accelerating."""
        if len(scores) < 3:
            return 0.0
        # Linear regression slope of drift scores
        x = np.arange(len(scores))
        y = np.array([s.total for s in scores])
        slope = np.polyfit(x, y, 1)[0]
        return float(slope)
```

## Drift Reporting

Drift reports are stored in the graph and exposed to the broadcast writer:

```python
@dataclass
class DriftReport:
    narrative_id: str
    drift_score: float           # 0-1 aggregate
    max_drift: float
    acceleration: float          # Negative = decelerating, positive = accelerating
    window_count: int
    dimension_scores: dict[str, float]
    
    def to_broadcast_segment(self) -> str:
        threshold = 0.3
        segments = []
        
        if self.drift_score > threshold:
            segments.append(
                f"Significant narrative drift detected: "
                f"{self.drift_score:.0%} over the analysis period."
            )
        
        if self.acceleration > 0.1:
            segments.append("Drift is accelerating.")
        elif self.acceleration < -0.1:
            segments.append("Drift is decelerating, suggesting narrative stabilization.")
        
        for dim, score in self.dimension_scores.items():
            if score > threshold:
                segments.append(f"{dim.title()} drift: {score:.0%}")
        
        return " ".join(segments)
```

## Embedding Trajectory

For each narrative thread, the system tracks an embedding trajectory — a time-ordered sequence of embedding centroids:

```python
class EmbeddingTrajectory:
    def __init__(self, narrative_id: str):
        self.narrative_id = narrative_id
        self.waypoints: list[EmbeddingWaypoint] = []
    
    def add_waypoint(self, timestamp: datetime, embedding: np.ndarray, 
                     claim_ids: list[str]):
        self.waypoints.append(EmbeddingWaypoint(
            timestamp=timestamp,
            embedding=embedding,
            claim_ids=claim_ids,
        ))
    
    def smooth(self, window: int = 3):
        """Apply temporal smoothing to trajectory."""
        if len(self.waypoints) < window:
            return
        smoothed = []
        for i in range(len(self.waypoints)):
            start = max(0, i - window // 2)
            end = min(len(self.waypoints), i + window // 2 + 1)
            avg_emb = np.mean([w.embedding for w in self.waypoints[start:end]], axis=0)
            smoothed.append(EmbeddingWaypoint(
                timestamp=self.waypoints[i].timestamp,
                embedding=avg_emb,
                claim_ids=self.waypoints[i].claim_ids,
            ))
        self.waypoints = smoothed
    
    def inflection_points(self) -> list[int]:
        """Find points where trajectory changes direction sharply."""
        if len(self.waypoints) < 3:
            return []
        
        # Compute angles between consecutive segments
        angles = []
        for i in range(1, len(self.waypoints) - 1):
            v1 = self.waypoints[i].embedding - self.waypoints[i-1].embedding
            v2 = self.waypoints[i+1].embedding - self.waypoints[i].embedding
            cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
            angles.append(np.arccos(np.clip(cos_angle, -1, 1)))
        
        # Points where angle exceeds threshold
        threshold = np.pi / 4  # 45 degrees
        return [i+1 for i, a in enumerate(angles) if a > threshold]
```

## Drift Classification

Drift above threshold triggers classification to understand the nature of the change:

```python
async def classify_drift_event(self, narrative: Narrative, 
                                old_claims: list[Claim], 
                                new_claims: list[Claim]) -> DriftEvent:
    
    prompt = f"""Analyze the narrative drift between two time windows:

Narrative: {narrative.label}

Previous period claims:
{chr(10).join(f"- {c.text}" for c in old_claims[:5])}

Current period claims:
{chr(10).join(f"- {c.text}" for c in new_claims[:5])}

What type of drift occurred?
Options:
- ESCALATION (language became more severe)
- DE_ESCALATION (language became less severe)
- FRAMING_SHIFT (the framing changed entirely)
- NARROWING (focus became more specific)
- WIDENING (scope expanded)
- SOURCE_CHANGE (different sources now dominate)
- CONFIDENCE_SHIFT (certainty changed significantly)

Output JSON: {{"drift_type": "...", "description": "...", "severity": 0.0-1.0}}"""

    response = await self.model.get("reasoning").generate(
        prompt=prompt, temperature=0.3, max_tokens=256, structured=True,
    )
    
    return parse_drift_response(response.text)
```

## Broadcast Integration

The drift engine feeds into broadcast content generation:

```python
def build_drift_segment(drift_report: DriftReport, 
                         drift_events: list[DriftEvent]) -> str:
    """Build a broadcast segment from drift analysis."""
    if drift_report.drift_score < 0.2:
        return ""  # Not interesting enough to broadcast
    
    lines = []
    
    # Opening
    if drift_report.acceleration > 0.1:
        lines.append(f"Narrative drift is accelerating across the monitored information space.")
    else:
        lines.append(f"Narrative drift has been detected across multiple dimensions.")
    
    # Specific drifts
    for de in drift_events[:2]:
        lines.append(de.description)
    
    # Key metrics
    lines.append(f"Aggregate drift score: {drift_report.drift_score:.0%}.")
    if drift_report.dimension_scores.get("linguistic", 0) > 0.3:
        lines.append(f"Linguistic drift is the dominant component.")
    if drift_report.dimension_scores.get("framing", 0) > 0.3:
        lines.append(f"Framing has shifted significantly.")
    
    return " ".join(lines)
```

## Performance Considerations

| Operation | Complexity | Frequency | Caching |
|-----------|-----------|-----------|---------|
| Embedding window claims | O(N * D) | Per analysis cycle | Embedding cache |
| Trajectory computation | O(W * D) | Per analysis cycle | In-memory trajectory store |
| Drift classification | O(1) LLM call | When drift > threshold | N/A (unique each call) |
| Broadcast segment | O(1) | Per broadcast | N/A |

Where N = claims per window, D = embedding dimension, W = number of windows.

## Drift Alerting

When drift exceeds configurable thresholds, alerts are generated:

```yaml
drift_alerting:
  thresholds:
    linguistic: 0.5
    framing: 0.4
    acceleration: 0.2
  cooldown: 3600  # Don't alert on same narrative more than once per hour
  actions:
    - log
    - ui_highlight
    - broadcast_segment
```
