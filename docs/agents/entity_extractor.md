# Entity Extractor Agent

## Overview

The entity extractor identifies and normalizes entities mentioned in documents. It uses a small, fast model for extraction and a resolution step to map surface forms to canonical entity IDs.

## Responsibility

- Extract named entities from documents (people, organizations, locations, events, concepts)
- Normalize entity names to canonical forms
- Detect aliases and coreferences
- Classify entity types

## Interface

```python
class EntityExtractor(BaseAgent):
    name = "entity_extractor"
    timeout_seconds = 30.0
    
    async def run(self, context: AgentContext) -> AgentResult:
        documents = context.state["documents"]
        model = await context.models.get("entity")
        
        all_entities = []
        stats = {"documents_processed": 0, "entities_found": 0}
        
        for doc in documents:
            entities = await self._extract_entities(doc, model)
            
            # Resolve to canonical entities
            resolved = await self._resolve_entities(entities, context)
            
            all_entities.extend(resolved)
            stats["documents_processed"] += 1
            stats["entities_found"] += len(resolved)
        
        return AgentResult(success=True, data=all_entities, metrics=stats)
    
    async def _extract_entities(self, doc: NormalizedDocument, 
                                  model: LLMClient) -> list[RawEntity]:
        prompt = f"""Extract named entities from this text.
For each entity, provide: name, type (person/organization/location/event/concept), and confidence.

Text: {doc.body[:2048]}

Output JSON array:
[{{"name": "...", "type": "...", "confidence": 0.95}}]"""
        
        response = await model.generate(prompt, temperature=0.0, max_tokens=1024, structured=True)
        return self._parse_entities(response.text)
    
    async def _resolve_entities(self, raw_entities: list[RawEntity], 
                                 context: AgentContext) -> list[Entity]:
        resolved = []
        for raw in raw_entities:
            canonical = context.graph.find_entity(raw.name)
            if canonical:
                resolved.append(canonical)
            else:
                entity = Entity(
                    id=generate_uuid(),
                    name=raw.name,
                    type=raw.type,
                    aliases=[raw.name],
                    first_seen=datetime.utcnow(),
                    last_seen=datetime.utcnow(),
                )
                resolved.append(entity)
        return resolved
    
    def validate(self, result: AgentResult) -> bool:
        return result.success  # Zero entities is valid
```

## Entity Types

| Type | Examples | Notes |
|------|----------|-------|
| person | "Joe Biden", "Vladimir Putin" | Includes titles, full names |
| organization | "UN", "NATO", "Apple Inc." | Acronyms expanded |
| location | "Ukraine", "Beijing", "Pacific" | Geographic entities |
| event_name | "World War II", "Covid-19" | Named historical events |
| concept | "inflation", "democracy" | Abstract entities |

## Entity Resolution

```python
class EntityResolver:
    def __init__(self, graph: GraphStore):
        self.graph = graph
    
    def find_entity(self, name: str) -> Optional[str]:
        """Find canonical entity ID by surface form."""
        # Exact match
        entity = self.graph.find_node("Entity", "name", name)
        if entity:
            return entity.id
        
        # Alias match
        entity = self.graph.find_node_by_alias("Entity", name)
        if entity:
            return entity.id
        
        # Fuzzy match for close variants
        candidates = self.graph.search_entities(name, threshold=0.85)
        if candidates:
            return candidates[0].id
        
        return None
    
    def merge_entities(self, canonical_id: str, alias_ids: list[str]):
        """Merge alias entities into canonical entity."""
        # Move all edges
        for alias_id in alias_ids:
            edges = self.graph.get_all_edges(alias_id)
            for edge in edges:
                if edge.label == "MENTIONS":
                    self.graph.create_edge("MENTIONS", edge.src, canonical_id, edge.props)
                elif edge.label == "APPEARS_IN":
                    self.graph.create_edge("APPEARS_IN", canonical_id, edge.dst, edge.props)
            self.graph.delete_node(alias_id)
        
        # Update aliases
        entity = self.graph.get_node(canonical_id)
        entity.aliases.extend(alias_ids)
        self.graph.update_node(canonical_id, entity)
```
