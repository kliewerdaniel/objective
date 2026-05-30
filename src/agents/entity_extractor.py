"""Entity extraction agent."""

import json
from src.agents.base import BaseAgent, AgentContext, AgentResult
from src.models.types import Entity, generate_uuid

MAX_DOCUMENTS_PER_CYCLE = 25

ENTITY_EXTRACTION_PROMPT = """Extract named entities from this text. For each entity, provide: name, type (person/organization/location/event/concept), and confidence.

Text: {text}

Output JSON array:
[{{"name": "...", "type": "...", "confidence": 0.95}}]
"""


class EntityExtractor(BaseAgent):
    name = "entity_extractor"
    timeout_seconds = 60.0

    async def run(self, context: AgentContext) -> AgentResult:
        documents = context.state.get("documents", [])[:MAX_DOCUMENTS_PER_CYCLE]
        model = await context.models.get("entity")

        all_entities = []
        stats = {"documents_processed": 0, "entities_found": 0}

        for doc in documents:
            raw = await self._extract(doc, model)
            for r in raw:
                entity = await self._resolve(r, context)
                if entity:
                    all_entities.append(entity)
            stats["documents_processed"] += 1
            stats["entities_found"] += len(raw)

        context.state["entities"] = all_entities
        return AgentResult(success=True, data=all_entities, metrics=stats)

    async def _extract(self, doc, model) -> list[dict]:
        prompt = ENTITY_EXTRACTION_PROMPT.format(text=doc.body[:2048])
        response = model.generate(prompt, temperature=0.0, max_tokens=1024, structured=True)
        try:
            return json.loads(response.text)
        except json.JSONDecodeError:
            return []

    async def _resolve(self, raw: dict, context: AgentContext) -> Entity:
        name = raw.get("name", "")
        if not name:
            return None
        existing = context.graph.find_entity(name)
        if existing:
            eid = existing["e.id"]
            context.graph.update_node("Entity", eid, {"last_seen": "datetime()"})
            return Entity(id=eid, name=name, type=raw.get("type", "concept"))
        entity = Entity(
            name=name,
            type=raw.get("type", "concept"),
            aliases=[name],
        )
        return entity

    def validate(self, result: AgentResult) -> bool:
        return result.success
