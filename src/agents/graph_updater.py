"""Graph updater — persists claims, entities, documents to KuzuDB."""

from src.agents.base import BaseAgent, AgentContext, AgentResult
from src.models.types import Claim, Entity, NormalizedDocument
from datetime import datetime


class GraphUpdater(BaseAgent):
    name = "graph_updater"
    timeout_seconds = 30.0

    async def run(self, context: AgentContext) -> AgentResult:
        documents = context.state.get("documents", [])
        claims = context.state.get("claims", [])
        entities = context.state.get("entities", [])

        stats = {"documents_inserted": 0, "claims_inserted": 0, "entities_inserted": 0}

        for doc in documents:
            if not context.graph.node_exists("Document", doc.id):
                context.graph.create_node("Document", doc.to_dict())
                stats["documents_inserted"] += 1

        for entity in entities:
            if not context.graph.node_exists("Entity", entity.id):
                context.graph.create_node("Entity", entity.to_dict())
                stats["entities_inserted"] += 1

        for claim in claims:
            props = claim.to_dict()
            props["timestamp"] = props["timestamp"]
            context.graph.create_node("Claim", props)
            context.graph.create_edge("EXTRACTED_FROM", claim.id, claim.source_document_id, {
                "extraction_confidence": claim.confidence,
                "extracted_at": datetime.utcnow().isoformat(),
            })
            for eid in claim.entity_ids:
                context.graph.create_edge("MENTIONS", claim.id, eid, {
                    "first_seen": datetime.utcnow().isoformat(),
                    "last_seen": datetime.utcnow().isoformat(),
                    "frequency": 1, "confidence": claim.confidence,
                })
            stats["claims_inserted"] += 1

        return AgentResult(success=True, data=stats, metrics=stats)

    def validate(self, result: AgentResult) -> bool:
        return result.success
