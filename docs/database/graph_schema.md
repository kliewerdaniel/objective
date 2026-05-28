# Graph Database Schema

## Node Types

### Source Node

```cypher
CREATE NODE TABLE Source (
    id STRING PRIMARY KEY,
    name STRING,
    type STRING,           -- "rss", "reddit", "youtube", "gov_rss", "news_api"
    base_url STRING,
    trust_score FLOAT,     -- 0.0-1.0, dynamic
    metadata STRING,       -- JSON blob
    created_at TIMESTAMP
)
```

### Document Node

```cypher
CREATE NODE TABLE Document (
    id STRING PRIMARY KEY,         -- SHA-256 of normalized content
    title STRING,
    url STRING,
    published_at TIMESTAMP,
    ingested_at TIMESTAMP,
    language STRING,
    source_type STRING
)
```

### Claim Node

```cypher
CREATE NODE TABLE Claim (
    id STRING PRIMARY KEY,         -- UUID
    text STRING,
    confidence FLOAT,              -- 0.0-1.0
    stance STRING,                 -- "support", "neutral", "oppose", "uncertain"
    timestamp TIMESTAMP,
    topic STRING,                  -- classification
    evidence STRING,               -- direct quote from source
    embedding_id STRING            -- reference to Qdrant vector
)
```

### Entity Node

```cypher
CREATE NODE TABLE Entity (
    id STRING PRIMARY KEY,         -- UUID
    name STRING,                   -- canonical name
    type STRING,                   -- "person", "organization", "location", "event", "concept"
    aliases STRING[],              -- alternative names
    metadata STRING,               -- JSON blob
    first_seen TIMESTAMP,
    last_seen TIMESTAMP
)
```

### Event Node

```cypher
CREATE NODE TABLE Event (
    id STRING PRIMARY KEY,
    title STRING,
    description STRING,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    status STRING,                 -- "emerging", "active", "ongoing", "concluded", "archived"
    importance FLOAT,              -- 0.0-1.0, computed
    embedding_id STRING
)
```

### Narrative Node

```cypher
CREATE NODE TABLE Narrative (
    id STRING PRIMARY KEY,
    label STRING,                  -- generated title
    description STRING,
    drift_score FLOAT,             -- 0.0-1.0, how much this narrative has changed
    framing STRING,                -- dominant political framing
    active BOOLEAN,
    first_seen TIMESTAMP,
    last_updated TIMESTAMP,
    embedding_id STRING
)
```

### Broadcast Node

```cypher
CREATE NODE TABLE Broadcast (
    id STRING PRIMARY KEY,
    script STRING,                 -- full broadcast text
    duration_seconds FLOAT,
    aired_at TIMESTAMP,
    topics STRING[],               -- topics covered
    metrics STRING                 -- JSON: system state at broadcast time
)
```

### ContradictionSummary Node

```cypher
CREATE NODE TABLE ContradictionSummary (
    id STRING PRIMARY KEY,
    claim_a_text STRING,
    claim_b_text STRING,
    contradiction_type STRING,
    resolution STRING,             -- how it was resolved
    resolved_at TIMESTAMP,
    evidence_summary STRING
)
```

## Edge Types

### Ingestion Edges

```cypher
CREATE REL TABLE FROM_SOURCE (FROM Document TO Source)
CREATE REL TABLE EXTRACTED_FROM (
    FROM Claim TO Document,
    extraction_confidence FLOAT,
    extractor_model STRING,
    prompt_hash STRING,
    raw_evidence STRING,
    extracted_at TIMESTAMP
)
```

### Entity Edges

```cypher
CREATE REL TABLE MENTIONS (
    FROM Claim TO Entity,
    first_seen TIMESTAMP,
    last_seen TIMESTAMP,
    frequency INT32,
    confidence FLOAT
)

CREATE REL TABLE APPEARS_IN (
    FROM Entity TO Event,
    role STRING,          -- "subject", "location", "perpetrator", "victim", "observer"
    confidence FLOAT
)

CREATE REL TABLE RELATED_TO (
    FROM Entity TO Entity,
    relationship STRING,  -- "affiliated_with", "opposes", "part_of", "located_in"
    confidence FLOAT
)
```

### Event Edges

```cypher
CREATE REL TABLE ABOUT_EVENT (
    FROM Claim TO Event,
    confidence FLOAT,
    first_seen TIMESTAMP
)

CREATE REL TABLE NEXT_EVENT (
    FROM Event TO Event,
    time_gap_hours FLOAT
)

CREATE REL TABLE SUBEVENT_OF (
    FROM Event TO Event
)

CREATE REL TABLE CAUSED_BY (
    FROM Event TO Event,
    probability FLOAT
)

CREATE REL TABLE EVOLVED_INTO (
    FROM Event TO Event,
    transition_type STRING,  -- "escalation", "de-escalation", "transformation"
    confidence FLOAT
)
```

### Epistemic Edges

```cypher
CREATE REL TABLE CONTRADICTS (
    FROM Claim TO Claim,
    contradiction_type STRING,  -- "direct", "numerical", "temporal", "framing", "contextual"
    strength FLOAT,             -- 0.0-1.0
    confidence FLOAT,           -- detection confidence
    detected_at TIMESTAMP,
    resolution_status STRING    -- "unresolved", "resolved", "false", "superseded"
)

CREATE REL TABLE SUPPORTS (
    FROM Claim TO Claim,
    strength FLOAT,
    confidence FLOAT
)

CREATE REL TABLE OBSOLETES (
    FROM Claim TO Claim
)
```

### Narrative Edges

```cypher
CREATE REL TABLE PART_OF_THREAD (
    FROM Claim TO Narrative,
    confidence FLOAT
)

CREATE REL TABLE PRECEDES (
    FROM Narrative TO Narrative,
    drift_amount FLOAT
)
```

### Broadcast Edges

```cypher
CREATE REL TABLE REFERENCES (
    FROM Broadcast TO Event,
    snippet STRING
)

CREATE REL TABLE CALLS_BACK (
    FROM Broadcast TO Broadcast,
    snippet STRING,
    time_delta_hours FLOAT
)
```

## Schema Constraints

```cypher
-- Primary key constraints (implicit in node table definitions)

-- Edge constraints (type safety)
-- Each edge must connect the correct node types

-- Indexes for common lookups
CREATE INDEX claim_topic_idx ON Claim(topic)
CREATE INDEX claim_timestamp_idx ON Claim(timestamp)
CREATE INDEX event_status_idx ON Event(status)
CREATE INDEX narrative_active_idx ON Narrative(active)
CREATE INDEX entity_name_idx ON Entity(name)
CREATE INDEX broadcast_aired_idx ON Broadcast(aired_at)
```

## Schema Migration Strategy

```python
class SchemaMigration:
    """Manage KuzuDB schema evolution."""
    
    MIGRATIONS = [
        {
            "version": 1,
            "description": "Initial schema",
            "up": [
                "CREATE NODE TABLE IF NOT EXISTS Source (...) ...",
            ],
        },
        {
            "version": 2,
            "description": "Add ContradictionSummary",
            "up": [
                "CREATE NODE TABLE IF NOT EXISTS ContradictionSummary (...) ...",
            ],
        },
    ]
    
    @classmethod
    def migrate(cls, conn: kuzu.Connection, target_version: int = None):
        current = cls._get_current_version(conn)
        target = target_version or len(cls.MIGRATIONS)
        
        for migration in cls.MIGRATIONS[current:target]:
            logger.info("schema.migrating", version=migration["version"],
                       description=migration["description"])
            for statement in migration["up"]:
                conn.execute(statement)
            cls._set_current_version(conn, migration["version"])
```
