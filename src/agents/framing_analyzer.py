"""Framing analyzer — detects framing bias across sources."""

from src.agents.base import BaseAgent, AgentContext, AgentResult


FRAME_LABELS = ["positive", "negative", "neutral", "alarmist", "dismissive", "analytical"]


class FramingAnalyzer(BaseAgent):
    name = "framing_analyzer"
    timeout_seconds = 60.0

    async def run(self, context: AgentContext) -> AgentResult:
        claims = context.state.get("claims", [])
        if not claims:
            return AgentResult(success=True, data={"frames": {}}, metrics={"claims_analyzed": 0})

        model = await context.models.get("classification")
        frame_counts: dict[str, int] = {}
        source_frames: dict[str, dict[str, int]] = {}
        stats = {"claims_analyzed": 0, "frames_detected": 0}

        for claim in claims:
            frame = await self._detect_frame(model, claim)
            frame_counts[frame] = frame_counts.get(frame, 0) + 1
            src = getattr(claim, "source_id", "unknown")
            if src not in source_frames:
                source_frames[src] = {}
            source_frames[src][frame] = source_frames[src].get(frame, 0) + 1
            stats["claims_analyzed"] += 1

        stats["frames_detected"] = len(frame_counts)
        return AgentResult(success=True, data={
            "frames": frame_counts,
            "source_frames": source_frames,
        }, metrics=stats)

    async def _detect_frame(self, model, claim) -> str:
        prompt = (
            f"Classify the framing of this news claim into one: "
            f"{', '.join(FRAME_LABELS)}.\n"
            f"Claim: {claim.text}\nFraming:"
        )
        try:
            resp = model.generate(prompt, max_tokens=16, temperature=0.1)
            for label in FRAME_LABELS:
                if label in resp.text.lower():
                    return label
        except Exception:
            pass
        return "neutral"

    def validate(self, result: AgentResult) -> bool:
        return result.success
