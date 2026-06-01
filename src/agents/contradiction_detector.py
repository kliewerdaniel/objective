"""Contradiction detection agent."""

import asyncio
import json
from src.agents.base import BaseAgent, AgentContext, AgentResult
from src.models.types import Contradiction, generate_uuid

CONTRADICTION_PROMPT = """Analyze if these two claims contradict each other.

Claim A: "{text_a}" (topic: {topic_a}, stance: {stance_a})
Claim B: "{text_b}" (topic: {topic_b}, stance: {stance_b})

Choose classification:
- DIRECT_CONTRADICTION: Opposite facts, cannot both be true
- NUMERICAL_DISCREPANCY: Different numbers/statistics
- FRAMING_DIFFERENCE: Different framing of same facts
- TEMPORAL_DISCREPANCY: Different timing claims
- COMPATIBLE: Both can be true simultaneously
- UNCERTAIN: Insufficient information

Output JSON: {{"type": "DIRECT_CONTRADICTION", "strength": 0.9, "reasoning": "..."}}
"""


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
            if not claim.embedding:
                continue
            similar = await context.vector.search(claim.embedding, top_k=20)
            for similar_id, similarity in similar:
                if similarity < 0.75:
                    continue
                other = context.graph.get_claim(similar_id)
                if not other:
                    continue
                stats["pairs_checked"] += 1
                contra = await self._classify(claim, other, model)
                if contra:
                    all_contradictions.append(contra)
                    stats["contradictions_found"] += 1

        return AgentResult(success=True, data=all_contradictions, metrics=stats)

    async def _classify(self, claim_a, claim_b, model) -> Contradiction:
        prompt = CONTRADICTION_PROMPT.format(
            text_a=claim_a.text, topic_a=claim_a.topic, stance_a=claim_a.stance,
            text_b=claim_b.text, topic_b=claim_b.topic, stance_b=claim_b.stance,
        )
        try:
            response = await asyncio.to_thread(model.generate, prompt, temperature=0.0, max_tokens=256, structured=True)
            result = json.loads(response.text)
            if result.get("type") in ("COMPATIBLE", "UNCERTAIN"):
                return None
            return Contradiction(
                claim_a=claim_a.id, claim_b=claim_b.id,
                contradiction_type=result["type"].lower(),
                strength=result["strength"],
                claim_a_text=claim_a.text, claim_b_text=claim_b.text,
            )
        except Exception:
            return None

    def validate(self, result: AgentResult) -> bool:
        return result.success
