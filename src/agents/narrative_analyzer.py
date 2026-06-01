"""Narrative analysis agent."""

import asyncio
import json
import numpy as np
from src.agents.base import BaseAgent, AgentContext, AgentResult
from src.models.types import Narrative, generate_uuid


class NarrativeAnalyzer(BaseAgent):
    name = "narrative_analyzer"
    timeout_seconds = 120.0

    async def run(self, context: AgentContext) -> AgentResult:
        model = await context.models.get("reasoning")
        unclustered = context.graph.get_unclustered_claims(hours=24)
        existing = context.graph.get_active_narratives()
        stats = {"narratives_created": 0, "claims_clustered": 0, "narratives_updated": 0}

        if unclustered:
            claims = [context.graph.get_claim(c["c.id"]) for c in unclustered if c.get("c.id")]
            claims = [c for c in claims if c]
            if claims:
                narratives = await self._cluster(claims, model, context)
                for n in narratives:
                    context.graph.create_node("Narrative", n.to_dict())
                    for cid in n.claim_ids:
                        context.graph.create_edge("PART_OF_THREAD", cid, n.id, {"confidence": 0.5})
                    stats["narratives_created"] += 1
                    stats["claims_clustered"] += len(n.claim_ids)

        for n in existing:
            drift = self._measure_drift(n, context)
            context.graph.update_node("Narrative", n["n.id"], {"drift_score": drift})
            stats["narratives_updated"] += 1

        return AgentResult(success=True, data=stats, metrics=stats)

    async def _cluster(self, claims, model, context) -> list[Narrative]:
        model_emb = await context.models.get("embedding")
        texts = [c["text"] for c in claims]
        embeddings = await asyncio.to_thread(model_emb.create_embedding, texts)

        clusters = []
        assigned = set()
        for i, claim_a in enumerate(claims):
            if i in assigned:
                continue
            cluster = [i]
            assigned.add(i)
            for j, claim_b in enumerate(claims):
                if j in assigned:
                    continue
                sim = float(np.dot(embeddings[i], embeddings[j]) /
                            (np.linalg.norm(embeddings[i]) * np.linalg.norm(embeddings[j])))
                if sim > 0.75:
                    cluster.append(j)
                    assigned.add(j)
            if len(cluster) >= 2:
                clusters.append(cluster)

        narratives = []
        for cluster in clusters:
            cids = [claims[i]["c.id"] for i in cluster]
            texts_sample = [claims[i]["c.text"] for i in cluster[:5]]
            label = await self._generate_label(texts_sample, model)
            narratives.append(Narrative(
                label=label, drift_score=0.0, claim_ids=cids,
            ))
        return narratives

    async def _generate_label(self, texts, model) -> str:
        prompt = "Generate a concise label for this narrative thread (5 words max):\n" + \
                 "\n".join(f"- {t}" for t in texts) + "\nLabel:"
        try:
            response = await asyncio.to_thread(model.generate, prompt, temperature=0.3, max_tokens=50)
            return response.text.strip().strip('"')
        except Exception:
            return "Unnamed narrative"

    def _measure_drift(self, narrative, context) -> float:
        return 0.0

    def validate(self, result: AgentResult) -> bool:
        return result.success
