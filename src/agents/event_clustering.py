"""Event clustering agent — groups claims into events."""

import numpy as np
from src.agents.base import BaseAgent, AgentContext, AgentResult
from src.models.types import Event, generate_uuid
from datetime import datetime


class EventClusteringEngine(BaseAgent):
    name = "event_clustering"
    timeout_seconds = 60.0

    async def run(self, context: AgentContext) -> AgentResult:
        claims = context.state.get("claims", [])
        if not claims:
            return AgentResult(success=True, data=[], metrics={"claims_clustered": 0})

        stats = {"claims_clustered": 0, "events_created": 0}

        for claim in claims:
            event_id = await self._assign(claim, context)
            if event_id:
                claim.event_id = event_id
                stats["claims_clustered"] += 1

        return AgentResult(success=True, data=stats, metrics=stats)

    async def _assign(self, claim, context) -> str:
        existing = context.graph.execute(
            "MATCH (e:Event) WHERE e.status = 'active' OR e.status = 'emerging' RETURN e.* ORDER BY e.importance DESC LIMIT 20"
        )
        for ev in existing:
            eid = ev.get("e.id")
            if not eid:
                continue
            e_entities = context.graph.execute(
                "MATCH (e:Entity)-[:APPEARS_IN]->(:Event {id: $id}) RETURN e.id",
                {"id": eid},
            )
            e_ids = {r["e.id"] for r in e_entities}
            shared = set(claim.entity_ids) & e_ids
            if shared:
                context.graph.link_claim_to_event(claim.id, eid)
                return eid

        event = Event(
            start_time=claim.published_at or datetime.utcnow(),
            importance=0.3 + claim.confidence * 0.3,
        )
        context.graph.create_node("Event", event.to_dict())
        context.graph.link_claim_to_event(claim.id, event.id)
        return event.id

    def validate(self, result: AgentResult) -> bool:
        return result.success
