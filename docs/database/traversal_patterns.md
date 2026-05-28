# Graph Traversal Patterns

## Common Cypher Queries

### Get Full Context for a Claim

```cypher
MATCH (c:Claim {id: $claim_id})
MATCH (c)-[:EXTRACTED_FROM]->(d:Document)
MATCH (d)-[:FROM_SOURCE]->(s:Source)
MATCH (c)-[:MENTIONS]->(e:Entity)
MATCH (c)-[:ABOUT_EVENT]->(ev:Event)
OPTIONAL MATCH (c)-[contra:CONTRADICTS]-(other:Claim)
RETURN c, d.title AS document_title, s.name AS source_name,
       s.trust_score AS source_trust,
       collect(DISTINCT e.name) AS entities,
       ev.title AS event_title,
       collect(DISTINCT {text: other.text, strength: contra.strength, 
                         type: contra.contradiction_type}) AS contradictions
```

### Get Event Summary with Metrics

```cypher
MATCH (e:Event {id: $event_id})
MATCH (c:Claim)-[:ABOUT_EVENT]->(e)
OPTIONAL MATCH (c)-[contra:CONTRADICTS]->()
WITH e, count(DISTINCT c) AS claim_count,
     avg(c.confidence) AS avg_confidence,
     count(DISTINCT contra) AS contradiction_count,
     collect(DISTINCT c.topic) AS topics
OPTIONAL MATCH (e)-[:NEXT_EVENT|CAUSED_BY|SUBEVENT_OF]->(related:Event)
RETURN e.title, e.status, e.importance,
       claim_count, avg_confidence, contradiction_count,
       topics, collect(DISTINCT related.title) AS related_events
```

### Find Narrative Thread Evolution

```cypher
MATCH (n:Narrative {id: $narrative_id})
MATCH (n)-[:PRECEDES*0..10]->(evolution:Narrative)
MATCH (c:Claim)-[:PART_OF_THREAD]->(evolution)
WITH evolution, c
ORDER BY c.timestamp
RETURN evolution.id, evolution.label, evolution.drift_score,
       evolution.framing, evolution.last_updated,
       collect(c.text) AS claims,
       count(c) AS claim_count
```

### Identify Highly Contested Events

```cypher
MATCH (e:Event)
MATCH (c:Claim)-[:ABOUT_EVENT]->(e)
MATCH (c)-[contra:CONTRADICTS]->()
WITH e, count(DISTINCT contra) AS contra_count,
     count(DISTINCT c) AS claim_count
WHERE contra_count > 2
RETURN e.title, contra_count, claim_count,
       round(1.0 * contra_count / claim_count, 2) AS contradiction_density
ORDER BY contradiction_density DESC
LIMIT 20
```

### Get Broadcast Narrative References

```cypher
MATCH (b:Broadcast {id: $broadcast_id})
MATCH (b)-[:REFERENCES]->(e:Event)
MATCH (c:Claim)-[:ABOUT_EVENT]->(e)
OPTIONAL MATCH (c)-[contra:CONTRADICTS]->()
WITH b, e, count(DISTINCT c) AS claims_referenced,
     count(DISTINCT contra) AS contradictions_referenced
OPTIONAL MATCH (b)-[:CALLS_BACK]->(previous:Broadcast)
RETURN b.aired_at, b.topics,
       claims_referenced, contradictions_referenced,
       previous.aired_at AS callback_to,
       previous.script AS callback_script
```

### Track Entity Across Events

```cypher
MATCH (ent:Entity {id: $entity_id})
MATCH (ent)<-[:MENTIONS]-(c:Claim)
MATCH (c)-[:ABOUT_EVENT]->(e:Event)
WITH ent, e, count(c) AS mentions
ORDER BY e.start_time
RETURN ent.name, e.title, e.start_time, e.importance, mentions
```

### Find Orphan Elements

```cypher
-- Claims with no events
MATCH (c:Claim)
WHERE NOT (c)-[:ABOUT_EVENT]->()
RETURN c.id, c.text, c.confidence, c.timestamp
LIMIT 20

-- Entities with no claims
MATCH (e:Entity)
WHERE NOT (e)<-[:MENTIONS]-()
RETURN e.name, e.type, e.first_seen
LIMIT 20

-- Events with only one claim (not yet emerging)
MATCH (e:Event)
OPTIONAL MATCH (c:Claim)-[:ABOUT_EVENT]->(e)
WITH e, count(c) AS claim_count
WHERE claim_count <= 1
RETURN e.title, e.status, e.start_time
```

### Contradiction Network Analysis

```cypher
-- Find claims with most contradictions
MATCH (c:Claim)-[r:CONTRADICTS]->()
RETURN c.id, c.text, count(r) AS contra_count,
       collect(DISTINCT r.contradiction_type) AS types
ORDER BY contra_count DESC
LIMIT 10

-- Find contradiction clusters (claims that contradict each other transitively)
MATCH (a:Claim)-[r:CONTRADICTS]-(b:Claim)
WHERE r.resolution_status = 'unresolved'
RETURN a.text AS claim_a, b.text AS claim_b, r.strength, r.contradiction_type
ORDER BY r.strength DESC
LIMIT 50
```

### Source Performance Analytics

```cypher
MATCH (s:Source)
MATCH (d:Document)-[:FROM_SOURCE]->(s)
MATCH (c:Claim)-[:EXTRACTED_FROM]->(d)
OPTIONAL MATCH (c)-[contra:CONTRADICTS]->()
RETURN s.name, s.type, s.trust_score,
       count(DISTINCT d) AS documents,
       count(DISTINCT c) AS claims,
       count(DISTINCT contra) AS contradictions,
       round(1.0 * count(DISTINCT contra) / NULLIF(count(DISTINCT c), 0), 3) AS contra_rate
ORDER BY contra_rate DESC
```

### Time-Travel: Graph State at Broadcast Time

```cypher
MATCH (b:Broadcast {id: $broadcast_id})
WITH b.aired_at AS snapshot_time

MATCH (c:Claim)
WHERE c.timestamp <= snapshot_time
  AND (NOT EXISTS(c.superseded_by) OR c.superseded_at > snapshot_time)

MATCH (c)-[:ABOUT_EVENT]->(e:Event)
WHERE e.start_time <= snapshot_time
  AND (e.end_time IS NULL OR e.end_time >= snapshot_time)

OPTIONAL MATCH (c)-[contra:CONTRADICTS]->(other:Claim)
WHERE contra.detected_at <= snapshot_time
  AND (contra.resolved_at IS NULL OR contra.resolved_at > snapshot_time)

RETURN e.title, count(DISTINCT c) AS claims_active,
       count(DISTINCT contra) AS contradictions_active
ORDER BY e.importance DESC
```
