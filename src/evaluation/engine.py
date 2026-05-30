"""Evaluation engine — quality metrics and system health."""

import json
import time
from src.agents.base import BaseAgent, AgentContext, AgentResult
from src.database.graph import GraphStore
from src.database.metadata import MetadataStore


class EvaluationEngine(BaseAgent):
    name = "evaluation_engine"
    timeout_seconds = 30.0

    async def run(self, context: AgentContext) -> AgentResult:
        metrics = {}
        tasks = [
            self._eval_claims(context),
            self._eval_contradictions(context),
            self._eval_narratives(context),
            self._eval_broadcasts(context),
        ]
        for result in await asyncio_gather(*tasks, return_exceptions=True):
            if isinstance(result, dict):
                metrics.update(result)

        context.metadata.store_evaluation(metrics)
        alerts = self._check_alerts(metrics)
        return AgentResult(success=True, data={"metrics": metrics, "alerts": alerts}, metrics=metrics)

    async def _eval_claims(self, context) -> dict:
        total = context.graph.count_nodes("Claim")
        if total == 0:
            return {"claims": {"total": 0}}
        sample = context.graph.get_random_claims(limit=100)
        avg_conf = sum(c.get("c.confidence", 0) for c in sample) / len(sample) if sample else 0
        stances = {}
        for c in sample:
            s = c.get("c.stance", "unknown")
            stances[s] = stances.get(s, 0) + 1
        return {"claims": {"total": total, "avg_confidence": round(avg_conf, 3), "stance_distribution": stances}}

    async def _eval_contradictions(self, context) -> dict:
        total = context.graph.count_edges("CONTRADICTS")
        if total == 0:
            return {"contradictions": {"total": 0}}
        return {"contradictions": {"total": total}}

    async def _eval_narratives(self, context) -> dict:
        total = context.graph.count_nodes("Narrative")
        return {"narratives": {"total": total, "active": total}}

    async def _eval_broadcasts(self, context) -> dict:
        total = context.graph.count_nodes("Broadcast")
        return {"broadcasts": {"total": total}}

    def _check_alerts(self, metrics: dict) -> list[dict]:
        alerts = []
        claims = metrics.get("claims", {})
        if claims.get("avg_confidence", 1) < 0.3:
            alerts.append({"level": "warning", "message": "Low average claim confidence"})
        return alerts

    def validate(self, result: AgentResult) -> bool:
        return result.success


async def asyncio_gather(*args, return_exceptions=False):
    import asyncio
    return await asyncio.gather(*args, return_exceptions=return_exceptions)
