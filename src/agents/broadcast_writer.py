"""Broadcast writer agent."""

from datetime import datetime
from src.agents.base import BaseAgent, AgentContext, AgentResult
from src.models.types import Script, ScriptSegment, BroadcastContext

BROADCAST_INSTRUCTIONS = """You are objective03, a synthetic news analysis broadcast. Write in a cold, analytical tone for TTS output.

You MUST split your response into two parts:
1. <think>your internal analysis and reasoning</think> — think through the news first.
2. Then output the broadcast content. This is the most important part.

IMPORTANT: The broadcast content comes AFTER </think>. Do NOT end after </think>. The think block is just your internal reasoning — you MUST still write the full 800–1200 word broadcast.

Rules for the broadcast content:
- Use natural spoken language. Spell out numbers under 20.
- Expand abbreviations on first use (e.g. "Department of Defense" not "DoD").
- Avoid symbols %, &, $ — write as "percent", "and", "dollars".
- Use paragraph breaks for natural pauses.
- NEVER include stage directions, sound effects, or bracketed text like "[music]" or "[pause]".
- NEVER output error messages, tracebacks, or internal diagnostics — only broadcast prose.
- Output ONLY the spoken broadcast text after </think>. No metadata.

Structure (800–1200 words):
1. Opening — establish the current news landscape and key themes.
2. Top stories — 3–5 sentences per event. Cite specific claims, sources, and evidence.
3. Contradictions & uncertainty — highlight conflicting information across sources.
4. Narrative analysis — how framing has shifted or consolidated.
5. Closing statement that ties back to the opening."""


class BroadcastWriter(BaseAgent):
    name = "broadcast_writer"
    timeout_seconds = 300.0

    async def run(self, context: AgentContext) -> AgentResult:
        model = await context.models.get("broadcast")
        state = self._gather(context)

        prev = ""
        if state.previous_broadcast:
            prev = state.previous_broadcast.get("b.script", "")[:300]

        event_details = self._fmt_events(state.top_events)
        contradiction_details = self._fmt_contradictions(state.contradictions)
        narrative_details = self._fmt_narratives(state.narratives)

        metrics = state.system_metrics
        headlines = "\n".join(f"- {h}" for h in state.uncertainty_zones[:8]) if state.uncertainty_zones else "None yet"

        user_prompt = f"""Current state:
Events: {metrics.get('events', 0)} | Claims: {metrics.get('claims', 0)} | Narratives: {metrics.get('narratives', 0)}
Contradictions: {metrics.get('contradictions', 0)} | Documents: {metrics.get('documents', 0)} | Sources: {metrics.get('sources', 0)} | Broadcasts: {metrics.get('broadcasts', 0)}

Recent headlines:
{headlines}

{event_details}

{contradiction_details}

{narrative_details}

Previous broadcast:
{prev if prev else 'None yet — this is the first broadcast.'}"""

        response = model.generate(user_prompt, temperature=0.5, max_tokens=4096, system=BROADCAST_INSTRUCTIONS)
        script = self._parse(response.text)

        if not self.validate(AgentResult(success=True, data=script)):
            script = self._fallback(state)

        context.graph.create_node("Broadcast", script.to_dict())
        context.state["script"] = script
        return AgentResult(success=True, data=script, metrics={
            "word_count": len(script.full_text.split()),
            "segment_count": len(script.segments),
        })

    def _gather(self, context) -> BroadcastContext:
        g = context.graph
        docs = []
        try:
            docs = g.execute("MATCH (d:Document) RETURN d.title, d.source_type, d.published_at ORDER BY d.published_at DESC LIMIT 10")
        except Exception:
            pass

        top_events = g.get_top_events(limit=5, min_importance=0.3) if g else []
        contradictions = g.get_top_contradictions(limit=5) if g else []
        narratives = g.get_active_narratives(limit=5) if g else []

        return BroadcastContext(
            top_events=top_events,
            contradictions=contradictions,
            narratives=narratives,
            drift_reports=g.get_drift_reports(hours=24, min_score=0.2) if g else [],
            previous_broadcast=g.get_latest_broadcast() if g else None,
            system_metrics={
                "events": g.count_nodes("Event") if g else 0,
                "claims": g.count_nodes("Claim") if g else 0,
                "narratives": g.count_nodes("Narrative") if g else 0,
                "contradictions": g.count_edges("CONTRADICTS") if g else 0,
                "sources": g.count_nodes("Source") if g else 0,
                "broadcasts": g.count_nodes("Broadcast") if g else 0,
                "documents": g.count_nodes("Document") if g else 0,
            },
            uncertainty_zones=[doc.get("d.title", "")[:60] for doc in docs[:8]],
        )

    def _fmt_events(self, events: list[dict]) -> str:
        if not events:
            return "No notable events."
        lines = []
        for ev in events[:5]:
            title = ev.get("e.title", ev.get("title", "Unknown"))
            desc = ev.get("e.description", ev.get("description", ""))
            importance = ev.get("e.importance", ev.get("importance", 0))
            status = ev.get("e.status", ev.get("status", "unknown"))
            lines.append(f"- {title} (importance: {importance:.2f}, status: {status})")
            if desc:
                lines.append(f"  {desc[:200]}")
        return "\n".join(lines)

    def _fmt_contradictions(self, contradictions: list[dict]) -> str:
        if not contradictions:
            return "No unresolved contradictions."
        lines = []
        for c in contradictions[:5]:
            claim_a = c.get("claim_a", c.get("c1.text", ""))
            claim_b = c.get("claim_b", c.get("c2.text", ""))
            ctype = c.get("contradiction_type", c.get("r.contradiction_type", "unknown"))
            strength = c.get("strength", c.get("r.strength", 0))
            lines.append(f"- Type: {ctype}, strength: {strength:.2f}")
            lines.append(f"  Claim A: {claim_a[:150]}")
            lines.append(f"  Claim B: {claim_b[:150]}")
        return "\n".join(lines)

    def _fmt_narratives(self, narratives: list[dict]) -> str:
        if not narratives:
            return "No active narratives."
        lines = []
        for n in narratives[:5]:
            label = n.get("n.label", n.get("label", "Unknown"))
            desc = n.get("n.description", n.get("description", ""))
            drift = n.get("n.drift_score", n.get("drift_score", 0))
            framing = n.get("n.framing", n.get("framing", "unknown"))
            lines.append(f"- {label} (drift: {drift:.2f}, framing: {framing})")
            if desc:
                lines.append(f"  {desc[:200]}")
        return "\n".join(lines)

    def _parse(self, text: str) -> Script:
        import re
        text = text.strip()
        # Strip model artifact tags (Gemma, ChatML, Llama3 formats)
        markers = [
            "<end_of_turn>", "<|im_end|>", "<|eot_id|>", "</s>",
            "<|channel>", "<channel|>",
        ]
        for marker in markers:
            text = text.replace(marker, "")
        for tag in ["thought", "commentary", "final"]:
            text = text.replace(f"<{tag}>", "").replace(f"</{tag}>", "")
        # Clean up any remaining angle-bracket noise
        text = re.sub(r'<\|?[^>]*>', '', text)
        # Remove bare artifact words at the start of text (Gemma outputs bare "thought")
        text = re.sub(r'^(?:thought|commentary|final)\s+', '', text, flags=re.IGNORECASE)
        # Strip stage directions in square brackets: [music], [pause], etc.
        text = re.sub(r'\[[^\]]*\]', '', text)
        # Strip error message patterns
        text = re.sub(r'(?i)\b(error|traceback|exception|failed|fault):.*?(?:\n|$)', '', text)
        # Remove lines that look like internal diagnostics (start with certain keywords)
        text = re.sub(r'(?im)^(?:debug|info|warn|error|trace):.*$', '', text)
        # Strip repeated/echoed prompt text (lines starting with common prompt prefixes)
        text = re.sub(r'(?im)^(?:user:|system:|assistant:|prompt:).*$', '', text)
        # Remove leading dashes/lists that might be remnants
        text = re.sub(r'^-\s+', '', text, flags=re.MULTILINE)
        # Collapse multiple blank lines into one
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()
        if not text or len(text) < 20:
            return self._fallback(None)
        return Script(segments=[ScriptSegment("broadcast", text)])

    def _fmt(self, items) -> str:
        if not items:
            return "None"
        return "\n".join(str(i) for i in items[:3])

    def _fallback(self, state) -> Script:
        metrics = state.system_metrics if state else {}
        return Script(segments=[
            ScriptSegment("intro", "objective03."),
            ScriptSegment("timestamp", f"System time: {datetime.utcnow().isoformat()}"),
            ScriptSegment("state", f"Tracking {metrics.get('events', 0)} events."),
            ScriptSegment("system", f"System operational. {metrics.get('claims', 0)} claims."),
            ScriptSegment("outro", "objective03 will continue monitoring."),
        ])

    def validate(self, result: AgentResult) -> bool:
        if not result.success or not result.data:
            return False
        script = result.data
        if not script.segments:
            return False
        wc = len(script.full_text.split())
        return 20 <= wc <= 5000
