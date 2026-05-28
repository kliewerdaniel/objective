# Broadcast Synthesis Pipeline

## Overview

The broadcast synthesis pipeline transforms graph state into audio scripts. It is the public-facing output of the system. The pipeline prioritizes uncertainty, contradiction, and narrative evolution over simplistic news summary.

## Script Structure

Every broadcast segment follows a consistent structure:

```
[ATMOSPHERIC INTRO] — 3-10 seconds ambient audio

SEGMENT 1: STATE OF KNOWLEDGE
  "As of {timestamp}, the system is tracking {N} active events
   across {M} narratives with {C} unresolved contradictions."

SEGMENT 2: TOP EVENTS
  "Leading indicators..." — top 3 events by importance score
  Each event: title, key claims, confidence trend, contradiction count

SEGMENT 3: CONTRADICTION SPOTLIGHT
  "Notable contradictions persist..." — top 1-2 contradictions
  Display: both claims, source information, evolution

SEGMENT 4: NARRATIVE DRIFT
  "Narrative drift detected..." — narratives with highest drift
  Analysis: what changed, framing shift, linguistic trajectory

SEGMENT 5: RECURRING THREAD (if applicable)
  "As previously reported..." — callback to earlier broadcast
  Context: how the situation has evolved

SEGMENT 6: UNCERTAINTY SUMMARY
  "Areas of low confidence..." — topics with highest uncertainty
  Note: what we don't know, what evidence is needed

SEGMENT 7: SYSTEM METRICS
  "System status..." — sources ingested, claims extracted,
   contradictions tracked, broadcast continuity

CLOSING
  "objective03 will continue monitoring."
  "This has been objective03."

[ATMOSPHERIC OUTRO] — 3-10 seconds ambient audio
```

## Script Generation

```python
class BroadcastWriter:
    def __init__(self, model_registry: ModelRegistry, graph: GraphStore,
                 broadcast_memory: BroadcastMemory):
        self.model = model_registry
        self.graph = graph
        self.memory = broadcast_memory
    
    async def generate_script(self) -> Script:
        """Generate a complete broadcast script from current graph state."""
        
        # Gather all context
        state = await self._gather_broadcast_context()
        
        # Build the prompt
        prompt = self._build_prompt(state)
        
        # Generate
        response = await self.model.get("broadcast").generate(
            prompt=prompt,
            temperature=0.5,        # Some variety for natural feel
            max_tokens=4096,        # ~3-4 minutes of spoken content
        )
        
        # Parse structured script
        script = self._parse_script(response.text)
        
        # Validate
        if not self._validate_script(script):
            script = self._fallback_script(state)
        
        return script
    
    async def _gather_broadcast_context(self) -> BroadcastContext:
        """Gather current state for broadcast generation."""
        return BroadcastContext(
            timestamp=datetime.utcnow(),
            top_events=self.graph.get_top_events(
                limit=5, 
                min_importance=0.3,
            ),
            contradictions=self.graph.get_top_contradictions(
                limit=3,
                status="unresolved",
            ),
            narratives=self.graph.get_active_narratives(
                limit=3,
                min_drift=0.1,
            ),
            recent_drift=self.graph.get_drift_reports(
                hours=24,
                min_score=0.2,
            ),
            entity_focus=await self._get_entity_focus(),
            previous_broadcast=self.graph.get_latest_broadcast(),
            callbacks=self.memory.get_callbacks_for_recurring_events(),
            system_metrics=self._get_system_metrics(),
            uncertainty_zones=self._find_uncertainty_zones(),
        )
    
    def _build_prompt(self, state: BroadcastContext) -> str:
        previous = state.previous_broadcast
        
        return f"""You are objective03, a synthetic news broadcast system.
Your voice is cold, detached, analytical, and precise.
You do NOT use warm, friendly, or conversational language.
You do NOT editorialize or express opinions.
You report on the state of information, not the state of events.

Generate a broadcast script using this EXACT structure:

[ATMOSPHERIC_INTRO]
[TIMESTAMP_ANNOUNCEMENT]

[SEGMENT: STATE_OF_KNOWLEDGE]
Brief overview of what the system is tracking.

[SEGMENT: TOP_EVENTS]
Top events with key claims, confidence trends, and contradiction counts.
For each event, note if confidence is rising or falling.

[SEGMENT: CONTRADICTIONS]
Notable unresolved contradictions. Present both sides without resolution.
Include source information and confidence levels.

[SEGMENT: NARRATIVE_DRIFT]
Narratives with significant drift. Describe what changed.

[SEGMENT: RECURRING_THREADS]
Callbacks to previous broadcasts. Use phrases like "As previously reported..."

[SEGMENT: UNCERTAINTY]
Areas where confidence is low. What is unknown or contested.

[SEGMENT: SYSTEM_METRICS]
Current system status: sources, claims, contradictions, broadcasts.

[OUTRO]

Current system state:
- Top events: {self._format_events(state.top_events)}
- Key contradictions: {self._format_contradictions(state.contradictions)}
- Active narratives: {self._format_narratives(state.narratives)}
- Drift reports: {self._format_drift(state.recent_drift)}
- Previous broadcast (summary): {previous.script[:500] if previous else "None"}
- Previous broadcast topics: {previous.topics if previous else "None"}
- Callbacks available: {self._format_callbacks(state.callbacks)}
- System metrics: {state.system_metrics}
- Uncertainty zones: {state.uncertainty_zones}

IMPORTANT RULES:
1. Never resolve contradictions. Report both sides.
2. Always note confidence levels and source reliability.
3. Reference previous broadcasts when relevant.
4. Use precise language about uncertainty.
5. Keep segments focused on information quality, not just events.
6. Total script should be 1500-3000 words.
7. Use the cold, detached, analytical voice."""

    def _fallback_script(self, state: BroadcastContext) -> Script:
        """Minimum viable script when generation fails."""
        return Script(
            id=generate_uuid(),
            segments=[
                ScriptSegment(type="intro", 
                    text="objective03. System status: degraded. Broadcast synthesis unavailable."),
                ScriptSegment(type="state",
                    text=f"As of {datetime.utcnow().isoformat()}, "
                         f"the system is operating in degraded mode."),
                ScriptSegment(type="system",
                    text=f"Last successful broadcast: {state.previous_broadcast.aired_at.isoformat() if state.previous_broadcast else 'N/A'}"),
                ScriptSegment(type="outro",
                    text="objective03 will resume normal broadcast when synthesis is restored."),
            ]
        )
```

## Voice Configuration

The broadcast voice is configurable:

```yaml
broadcast:
  voice:
    style: "cold_detached"  # Options: cold_detached, analytical, archival
    uncertainty_phrases:
      - "Confidence remains low"
      - "Evidence is inconclusive"
      - "Contradictory claims persist"
      - "Independent verification is lacking"
      - "Multiple sources report conflicting information"
    confidence_phrases:
      high: "Multiple independent sources confirm"
      moderate: "Several sources suggest"
      low: "Some sources indicate, though confidence remains limited"
    callback_style: "temporal"  # How to reference past broadcasts
    max_contradictions_per_broadcast: 3
    min_contradiction_strength: 0.5
    include_system_metrics: true
```

## Segment Scheduling

Broadcast segments are scheduled and prioritized:

| Segment Type | Frequency | Priority | Notes |
|-------------|-----------|----------|-------|
| State of Knowledge | Every broadcast | Always | Brief system overview |
| Top Events | Every broadcast | Always | Top 3 by importance |
| Contradiction Spotlight | Every 2nd broadcast | High | Rotate through contradictions |
| Narrative Drift | Every 3rd broadcast | Medium | When drift > threshold |
| Recurring Thread | Variable | Medium | When callbacks available |
| Uncertainty Summary | Every broadcast | Always | Key unknowns |
| System Metrics | Every broadcast | Always | Brief metrics |
| Deep Dive | Every 4th broadcast | Low | Long-form analysis of single topic |

## Fallback and Degradation

| Failure Mode | Effect | Fallback |
|-------------|--------|----------|
| Model OOM | Script generation fails | Use fallback script template |
| Graph unavailable | No context data | Use metrics-only broadcast |
| All models down | No generation | Loop ambient audio + last broadcast |
| Contradiction data stale | No contradiction segment | Skip segment |
| No new data | Repetitive content | Note: "No significant changes since last cycle" |

## Broadcast Quality Checklist

Before a broadcast is queued:

- [ ] Every claim referenced has a provenance chain
- [ ] Contradictions are presented as unresolved (unless resolved)
- [ ] At least one uncertainty mention exists
- [ ] Previous broadcast is referenced if relevant callbacks exist
- [ ] System metrics are accurate
- [ ] Script fits within configured duration limits
- [ ] No editorializing or opinion language
- [ ] Confidence levels are included with claims
