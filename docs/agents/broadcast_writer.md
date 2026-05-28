# Broadcast Writer Agent

## Overview

The broadcast writer synthesizes the current state of the graph into cold, analytical broadcast scripts. It is the primary creative agent, using a larger reasoning model to produce coherent narrative output from structured graph data.

## Responsibility

- Synthesize graph state into broadcast scripts
- Maintain the cold, detached, analytical voice
- Reference previous broadcasts for continuity
- Surface contradictions and uncertainty
- Structure scripts for TTS consumption

## Interface

```python
class BroadcastWriter(BaseAgent):
    name = "broadcast_writer"
    timeout_seconds = 180.0
    
    async def run(self, context: AgentContext) -> AgentResult:
        model = await context.models.get("broadcast")
        broadcast_memory = BroadcastMemory(context.graph)
        
        # Gather current state
        state = await self._gather_context(context, broadcast_memory)
        
        # Generate script
        prompt = self._build_prompt(state)
        response = await model.generate(
            prompt=prompt,
            temperature=0.5,
            max_tokens=4096,
        )
        
        script = self._parse_script(response.text, state)
        
        if not script or not self.validate(AgentResult(success=True, data=script)):
            script = self._fallback_script(state)
        
        # Store in graph
        context.graph.create_node("Broadcast", script.to_dict())
        
        return AgentResult(
            success=True,
            data=script,
            metrics={
                "word_count": len(script.full_text.split()),
                "segment_count": len(script.segments),
                "estimated_duration_s": script.estimated_duration(),
            },
        )
    
    async def _gather_context(self, context, broadcast_memory) -> BroadcastContext:
        return BroadcastContext(
            timestamp=datetime.utcnow(),
            top_events=context.graph.get_top_events(limit=5, min_importance=0.3),
            contradictions=context.graph.get_top_contradictions(limit=3),
            narratives=context.graph.get_active_narratives(limit=3),
            drift_reports=context.graph.get_drift_reports(hours=24, min_score=0.2),
            previous_broadcast=context.graph.get_latest_broadcast(),
            callbacks=broadcast_memory.get_callbacks_for_recurring_events(),
            system_metrics=self._get_system_metrics(context),
            uncertainty_zones=self._find_uncertainty_zones(context),
            source_trusts=self._get_source_trusts(context),
        )
    
    def _build_prompt(self, state: BroadcastContext) -> str:
        return f"""You are objective03, a synthetic news broadcast system. Your voice is cold, detached, analytical, and precise. You do NOT use warm, friendly, or conversational language. You do NOT editorialize or express opinions. You report on the state of information.

Generate a broadcast script using this EXACT format:

[ATMOSPHERIC_INTRO]
[TIMESTAMP: {state.timestamp.isoformat()}]

[STATE_OF_KNOWLEDGE]
Overview of tracked events, contradictions, and narratives.

[TOP_EVENTS]
For each event: title, key claims, confidence trends, contradictions.
{self._format_events(state.top_events)}

[CONTRADICTIONS]
Notable unresolved contradictions. Present both sides.
{self._format_contradictions(state.contradictions)}

[NARRATIVE_DRIFT]
Narratives with significant linguistic or framing drift.
{self._format_narratives(state.narratives)}

{[RECURRING_THREADS] if state.callbacks else ""}
{self._format_callbacks(state.callbacks)}

[UNCERTAINTY]
Areas where confidence is low or evidence is contested.
{self._format_uncertainty(state.uncertainty_zones)}

[SYSTEM_METRICS]
{self._format_metrics(state.system_metrics)}

[OUTRO]
objective03 will continue monitoring.

Rules:
1. Never resolve contradictions. Present both sides with confidence levels.
2. Always note source reliability when citing claims.
3. Reference previous broadcasts when relevant: "As previously reported..."
4. Use precise language about uncertainty, not vague hedging.
5. The broadcast is about the STATE OF INFORMATION, not about events themselves.
6. Total: 1500-3000 words, 8-15 segments.
"""
    
    def validate(self, result: AgentResult) -> bool:
        if not result.success or not result.data:
            return False
        script = result.data
        if not script.segments:
            return False
        if len(script.full_text.split()) < 200:
            return False
        if len(script.full_text.split()) > 5000:
            return False
        return True
    
    def _fallback_script(self, state: BroadcastContext) -> Script:
        """Generate a minimum viable script."""
        return Script(
            id=generate_uuid(),
            timestamp=datetime.utcnow(),
            segments=[
                ScriptSegment("intro", "objective03."),
                ScriptSegment("timestamp", f"System time: {datetime.utcnow().isoformat()}"),
                ScriptSegment("state", f"Tracking {state.system_metrics.get('events', 0)} events across {state.system_metrics.get('narratives', 0)} narratives."),
                ScriptSegment("system", f"System operational. {state.system_metrics.get('claims', 0)} claims in graph. {state.system_metrics.get('contradictions', 0)} contradictions being tracked."),
                ScriptSegment("outro", "objective03 will continue monitoring."),
            ]
        )
```

## Script Data Model

```python
@dataclass
class Script:
    id: str
    timestamp: datetime
    segments: list[ScriptSegment]
    
    @property
    def full_text(self) -> str:
        return "\n\n".join(s.text for s in self.segments)
    
    def estimated_duration(self) -> float:
        """Estimate spoken duration in seconds (~150 wpm)."""
        word_count = len(self.full_text.split())
        return word_count / 150 * 60  # 150 words per minute
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "script": self.full_text,
            "duration_seconds": self.estimated_duration(),
            "aired_at": self.timestamp.isoformat(),
            "topics": [s.segment_type for s in self.segments],
        }

@dataclass
class ScriptSegment:
    segment_type: str  # intro, state, events, contradictions, drift, threads, uncertainty, system, outro
    text: str
```

## Voice Configuration

```yaml
broadcast:
  voice:
    style: "cold_detached"
    uncertainty_phrases:
      - "Confidence remains low"
      - "Evidence is inconclusive"
      - "Independent verification is lacking"
    confidence_phrases:
      high: "Multiple independent sources confirm"
      moderate: "Several sources suggest"
      low: "Some sources indicate, though verification is limited"
    callback_style: "temporal"
    max_contradictions: 3
    min_contradiction_strength: 0.5
    include_system_metrics: true
```

## Broadcast Example

```
[ATMOSPHERIC_INTRO]

objective03. Broadcast timestamp: 2026-05-28T14:30:00Z.

[STATE_OF_KNOWLEDGE]

The system is currently tracking 127 active events across 43 narrative threads, with 892 unresolved contradictions. Information confidence has declined 4.2% over the last 24 hours across monitored sources.

[TOP_EVENTS]

Event: Eastern Mediterranean Maritime Dispute
Importance: 0.87
Claims: 47 claims from 12 sources
Confidence trend: Declining
Contradictions: 8 active

Key claims: "Naval vessels exchanged warning shots near the exclusion zone" (confidence 0.72, corroborated by 4 sources). "No direct engagement occurred" (confidence 0.65, originating from state-aligned sources). Casualty estimates range from 0 to 12, with no independent verification available.

[CONTRADICTIONS]

Contradiction type: DIRECT, strength 0.91
Claim A: "The vessel was operating in international waters" (source trust: MODERATE)
Claim B: "The vessel had entered territorial waters without authorization" (source trust: MODERATE)
These claims have been in direct contradiction for 72 hours with no resolution.

[NARRATIVE_DRIFT]

Significant linguistic drift detected in the "Eastern Mediterranean Security" narrative. Term "naval incident" has shifted to "maritime confrontation" over the past 48 hours across 60% of monitored sources. Framing analysis shows increased militaristic language from state-aligned media.

[UNCERTAINTY]

Areas requiring additional evidence: casualty figures (highly contested, range spans two orders of magnitude), territorial status of incident location (no independent navigational data available), and official government statements (delayed, contradictory).

[SYSTEM_METRICS]

Current system state: 127 events, 14,892 claims, 43 narratives, 892 contradictions, 3,421 sources. Last broadcast: 15 minutes ago. All systems nominal.

[OUTRO]

objective03 will continue monitoring.
```

## Failure Modes

| Failure | Detection | Fallback |
|---------|-----------|----------|
| Model OOM | Memory check | Fallback script template |
| Model timeout | Watchdog timer | Use cached last script with update |
| Empty graph | Zero events/claims | "Initializing knowledge base" script |
| All contradictions resolved | No active contradictions | Skip contradiction segment |
| No new data since last broadcast | Duplicate content | "No significant changes" with system metrics only |
