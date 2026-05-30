"""Memory consolidator — archives, prunes, and maintains graph health."""

from src.agents.base import BaseAgent, AgentContext, AgentResult


class MemoryConsolidator(BaseAgent):
    name = "memory_consolidator"
    timeout_seconds = 300.0

    async def run(self, context: AgentContext) -> AgentResult:
        stats = {"claims_pruned": 0}
        orphans = context.graph.find_orphan_claims(
            older_than_days=7, max_confidence=0.3, max_contradictions=0
        )
        for claim in orphans:
            context.graph.delete_node("Claim", claim["c.id"])
            stats["claims_pruned"] += 1
        return AgentResult(success=True, data=stats, metrics=stats)

    def validate(self, result: AgentResult) -> bool:
        return result.success
