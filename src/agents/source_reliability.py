"""Source reliability evaluator."""

from src.agents.base import BaseAgent, AgentContext, AgentResult


class SourceReliabilityEvaluator(BaseAgent):
    name = "source_reliability"
    timeout_seconds = 30.0

    async def run(self, context: AgentContext) -> AgentResult:
        sources = context.graph.get_all_sources()
        stats = {"sources_evaluated": 0}

        for source in sources:
            sid = source.get("s.id")
            if not sid:
                continue
            score = self._compute(sid, context)
            context.graph.update_node("Source", sid, {"trust_score": score})
            stats["sources_evaluated"] += 1

        return AgentResult(success=True, data=stats, metrics=stats)

    def _compute(self, source_id: str, context) -> float:
        source = context.graph.get_node("Source", source_id)
        if not source:
            return 0.5
        base = {"rss": 0.6, "news_api": 0.7, "reddit": 0.3, "youtube": 0.4, "gov_rss": 0.5}
        return base.get(source.get("s.type", ""), 0.5)

    def validate(self, result: AgentResult) -> bool:
        return result.success
