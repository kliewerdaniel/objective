# Temporal Graph Updater Agent

## Overview

The graph updater is the persistence layer for all extracted knowledge. It handles insertion of claims, entities, documents, and relationships into KuzuDB with proper temporal annotations.

## Responsibility

- Insert documents, claims, entities into KuzuDB
- Create and maintain temporal edges
- Update entity frequency and recency
- Maintain graph consistency
- Handle concurrent write contention

## Interface

```python
class TemporalGraphUpdater(BaseAgent):
    name = "graph_updater"
    timeout_seconds = 30.0
    
    async def run(self, context: AgentContext) -> AgentResult:
        documents = context.state.get("documents", [])
        claims = context.state.get("claims", [])
        entities = context.state.get("entities", [])
        
        stats = {
            "documents_inserted": 0,
            "claims_inserted": 0,
            "entities_inserted": 0,
            "edges_created": 0,
        }
        
        # Batch operations for efficiency
        with context.graph.transaction():
            # Insert documents
            for doc in documents:
                context.graph.create_node("Document", doc.to_dict())
                context.graph.create_edge("FROM_SOURCE", doc.id, doc.source_id)
                stats["documents_inserted"] += 1
            
            # Insert entities
            for entity in entities:
                if not context.graph.node_exists("Entity", entity.id):
                    context.graph.create_node("Entity", entity.to_dict())
                    stats["entities_inserted"] += 1
            
            # Insert claims with relationships
            for claim in claims:
                context.graph.create_node("Claim", claim.to_dict())
                context.graph.create_edge(
                    "EXTRACTED_FROM", claim.id, claim.source_document_id,
                    {"extraction_confidence": claim.confidence}
                )
                
                for entity_id in claim.entity_ids:
                    context.graph.create_edge(
                        "MENTIONS", claim.id, entity_id,
                        {"first_seen": claim.timestamp.isoformat(),
                         "last_seen": claim.timestamp.isoformat(),
                         "frequency": 1, "confidence": claim.confidence}
                    )
                
                if claim.event_id:
                    context.graph.create_edge(
                        "ABOUT_EVENT", claim.id, claim.event_id,
                        {"confidence": claim.confidence}
                    )
                
                stats["claims_inserted"] += 1
                stats["edges_created"] += 1 + len(claim.entity_ids) + (1 if claim.event_id else 0)
        
        return AgentResult(success=True, data=stats, metrics=stats)
    
    def validate(self, result: AgentResult) -> bool:
        return result.success and result.data.get("errors", 0) == 0
```

## Graph Operations

```python
class GraphStore:
    def __init__(self, db_path: str):
        self.db = kuzu.Database(db_path)
        self.conn = kuzu.Connection(self.db)
        self._init_schema()
    
    def _init_schema(self):
        """Initialize KuzuDB schema."""
        # Node tables
        self.conn.execute("CREATE NODE TABLE IF NOT EXISTS Source (
            id STRING, name STRING, type STRING, base_url STRING,
            trust_score FLOAT, metadata STRING, created_at TIMESTAMP,
            PRIMARY KEY (id))")
        
        self.conn.execute("CREATE NODE TABLE IF NOT EXISTS Document (
            id STRING, title STRING, url STRING, published_at TIMESTAMP,
            ingested_at TIMESTAMP, language STRING, source_type STRING,
            PRIMARY KEY (id))")
        
        self.conn.execute("CREATE NODE TABLE IF NOT EXISTS Claim (
            id STRING, text STRING, confidence FLOAT, stance STRING,
            timestamp TIMESTAMP, topic STRING, evidence STRING,
            embedding_id STRING, PRIMARY KEY (id))")
        
        self.conn.execute("CREATE NODE TABLE IF NOT EXISTS Entity (
            id STRING, name STRING, type STRING, aliases STRING[],
            metadata STRING, first_seen TIMESTAMP, last_seen TIMESTAMP,
            PRIMARY KEY (id))")
        
        self.conn.execute("CREATE NODE TABLE IF NOT EXISTS Event (
            id STRING, title STRING, description STRING,
            start_time TIMESTAMP, end_time TIMESTAMP, status STRING,
            importance FLOAT, embedding_id STRING, PRIMARY KEY (id))")
        
        self.conn.execute("CREATE NODE TABLE IF NOT EXISTS Narrative (
            id STRING, label STRING, description STRING, drift_score FLOAT,
            framing STRING, active BOOLEAN, first_seen TIMESTAMP,
            last_updated TIMESTAMP, embedding_id STRING, PRIMARY KEY (id))")
        
        self.conn.execute("CREATE NODE TABLE IF NOT EXISTS Broadcast (
            id STRING, script STRING, duration_seconds FLOAT,
            aired_at TIMESTAMP, topics STRING[], metrics STRING,
            PRIMARY KEY (id))")
        
        # Edge tables
        self.conn.execute("CREATE REL TABLE FROM_SOURCE (FROM Document TO Source)")
        self.conn.execute("CREATE REL TABLE EXTRACTED_FROM (
            FROM Claim TO Document, extraction_confidence FLOAT,
            extractor_model STRING, prompt_hash STRING,
            raw_evidence STRING, extracted_at TIMESTAMP)")
        
        self.conn.execute("CREATE REL TABLE MENTIONS (
            FROM Claim TO Entity, first_seen TIMESTAMP,
            last_seen TIMESTAMP, frequency INT32, confidence FLOAT)")
        
        self.conn.execute("CREATE REL TABLE ABOUT_EVENT (
            FROM Claim TO Event, confidence FLOAT, first_seen TIMESTAMP)")
        
        self.conn.execute("CREATE REL TABLE CONTRADICTS (
            FROM Claim TO Claim, contradiction_type STRING,
            strength FLOAT, confidence FLOAT, detected_at TIMESTAMP,
            resolution_status STRING)")
        
        self.conn.execute("CREATE REL TABLE SUPPORTS (
            FROM Claim TO Claim, strength FLOAT, confidence FLOAT)")
        
        self.conn.execute("CREATE REL TABLE PART_OF_THREAD (
            FROM Claim TO Narrative, confidence FLOAT)")
        
        self.conn.execute("CREATE REL TABLE APPEARS_IN (
            FROM Entity TO Event, role STRING, confidence FLOAT)")
        
        self.conn.execute("CREATE REL TABLE REFERENCES (
            FROM Broadcast TO Event, snippet STRING)")
        
        self.conn.execute("CREATE REL TABLE NEXT_EVENT (
            FROM Event TO Event, time_gap_hours FLOAT)")
    
    def create_node(self, table: str, properties: dict) -> str:
        """Create a node and return its ID."""
        cols = ", ".join(properties.keys())
        placeholders = ", ".join(f"${k}" for k in properties.keys())
        query = f"CREATE (n:{table} {{ {', '.join(f'{k}: ${k}' for k in properties.keys())} }}) RETURN n.id"
        result = self.conn.execute(query, properties)
        return result.get_next()[0]
    
    def create_edge(self, rel_name: str, from_id: str, to_id: str, 
                    properties: dict = None):
        """Create an edge between two nodes."""
        if properties:
            set_str = ", ".join(f"r.{k} = ${k}" for k in properties.keys())
            query = f"""
            MATCH (a) WHERE a.id = $from_id
            MATCH (b) WHERE b.id = $to_id
            CREATE (a)-[r:{rel_name} {{ {set_str} }}]->(b)
            """
            params = {"from_id": from_id, "to_id": to_id, **properties}
        else:
            query = """
            MATCH (a) WHERE a.id = $from_id
            MATCH (b) WHERE b.id = $to_id
            CREATE (a)-[:""" + rel_name + "]->(b)"
            params = {"from_id": from_id, "to_id": to_id}
        
        self.conn.execute(query, params)
```

## Transaction Management

```python
class GraphTransaction:
    def __init__(self, conn: kuzu.Connection):
        self.conn = conn
    
    def __enter__(self):
        self.conn.begin_transaction()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
```

## Performance Notes

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| Node creation | O(1) | Single insert |
| Edge creation | O(log N) | Node lookup + edge insert |
| Batch insert (1000 nodes) | O(N) | KuzuDB handles bulk well |
| Node lookup by ID | O(1) | Hash index on primary key |
| Edge traversal | O(degree) | KuzuDB columnar storage |
