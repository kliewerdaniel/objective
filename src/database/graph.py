"""KuzuDB graph database interface."""

import json
import time
from datetime import datetime
from typing import Any, Optional, Callable
from pathlib import Path

import kuzu


class GraphStore:
    """Temporal property graph store backed by KuzuDB."""

    def __init__(self, db_path: str, buffer_pool_size: Optional[int] = None, max_threads: int = 4):
        self.db_path = db_path
        db_dir = Path(db_path)
        db_dir.parent.mkdir(parents=True, exist_ok=True)

        kwargs = {"max_num_threads": max_threads}
        if buffer_pool_size is not None:
            kwargs["buffer_pool_size"] = buffer_pool_size

        try:
            self.db = kuzu.Database(db_path, **kwargs)
        except Exception:
            # Corrupted DB — delete and recreate
            for f in db_dir.parent.glob(f"{db_dir.name}*"):
                try:
                    f.unlink()
                except Exception:
                    pass
            self.db = kuzu.Database(db_path, **kwargs)

        self.conn = kuzu.Connection(self.db)
        self._init_schema()

    def _init_schema(self):
        """Initialize KuzuDB schema."""
        queries = [
            "CREATE NODE TABLE IF NOT EXISTS Source (id STRING, name STRING, type STRING, base_url STRING, trust_score FLOAT, metadata STRING, created_at STRING, PRIMARY KEY (id))",
            "CREATE NODE TABLE IF NOT EXISTS Document (id STRING, title STRING, url STRING, published_at STRING, ingested_at STRING, language STRING, source_type STRING, PRIMARY KEY (id))",
            "CREATE NODE TABLE IF NOT EXISTS Claim (id STRING, text STRING, confidence FLOAT, stance STRING, timestamp STRING, topic STRING, evidence STRING, embedding_id STRING, PRIMARY KEY (id))",
            "CREATE NODE TABLE IF NOT EXISTS Entity (id STRING, name STRING, type STRING, aliases STRING[], metadata STRING, first_seen STRING, last_seen STRING, PRIMARY KEY (id))",
            "CREATE NODE TABLE IF NOT EXISTS Event (id STRING, title STRING, description STRING, start_time STRING, end_time STRING, status STRING, importance FLOAT, embedding_id STRING, PRIMARY KEY (id))",
            "CREATE NODE TABLE IF NOT EXISTS Narrative (id STRING, label STRING, description STRING, drift_score FLOAT, framing STRING, active BOOLEAN, first_seen STRING, last_updated STRING, embedding_id STRING, PRIMARY KEY (id))",
            "CREATE NODE TABLE IF NOT EXISTS Broadcast (id STRING, script STRING, duration_seconds FLOAT, aired_at STRING, topics STRING[], metrics STRING, PRIMARY KEY (id))",
            "CREATE NODE TABLE IF NOT EXISTS ContradictionSummary (id STRING, claim_a_text STRING, claim_b_text STRING, contradiction_type STRING, resolution STRING, resolved_at STRING, evidence_summary STRING, PRIMARY KEY (id))",
            "CREATE REL TABLE IF NOT EXISTS FROM_SOURCE (FROM Document TO Source)",
            "CREATE REL TABLE IF NOT EXISTS EXTRACTED_FROM (FROM Claim TO Document, extraction_confidence FLOAT, extractor_model STRING, prompt_hash STRING, raw_evidence STRING, extracted_at STRING)",
            "CREATE REL TABLE IF NOT EXISTS MENTIONS (FROM Claim TO Entity, first_seen STRING, last_seen STRING, frequency INT32, confidence FLOAT)",
            "CREATE REL TABLE IF NOT EXISTS ABOUT_EVENT (FROM Claim TO Event, confidence FLOAT, first_seen STRING)",
            "CREATE REL TABLE IF NOT EXISTS CONTRADICTS (FROM Claim TO Claim, contradiction_type STRING, strength FLOAT, confidence FLOAT, detected_at STRING, resolution_status STRING)",
            "CREATE REL TABLE IF NOT EXISTS SUPPORTS (FROM Claim TO Claim, strength FLOAT, confidence FLOAT)",
            "CREATE REL TABLE IF NOT EXISTS PART_OF_THREAD (FROM Claim TO Narrative, confidence FLOAT)",
            "CREATE REL TABLE IF NOT EXISTS APPEARS_IN (FROM Entity TO Event, role STRING, confidence FLOAT)",
            "CREATE REL TABLE IF NOT EXISTS REFERENCES (FROM Broadcast TO Event, snippet STRING)",
            "CREATE REL TABLE IF NOT EXISTS NEXT_EVENT (FROM Event TO Event, time_gap_hours FLOAT)",
            "CREATE REL TABLE IF NOT EXISTS SUBEVENT_OF (FROM Event TO Event)",
            "CREATE REL TABLE IF NOT EXISTS PRECEDES (FROM Narrative TO Narrative, drift_amount FLOAT)",
            "CREATE REL TABLE IF NOT EXISTS CALLS_BACK (FROM Broadcast TO Broadcast, snippet STRING, time_delta_hours FLOAT)",
        ]
        for q in queries:
            try:
                self.conn.execute(q)
            except Exception:
                pass

    def transaction(self):
        return GraphTransaction(self.conn)

    def execute(self, query: str, params: Optional[dict] = None) -> list[dict]:
        result = self.conn.execute(query, params or {})
        columns = result.get_column_names()
        rows = []
        while result.has_next():
            row = result.get_next()
            rows.append(dict(zip(columns, row)))
        return rows

    def create_node(self, table: str, properties: dict) -> str:
        cols = ", ".join(f"{k}: ${k}" for k in properties)
        q = f"CREATE (n:{table} {{ {cols} }}) RETURN n.id"
        result = self.conn.execute(q, properties)
        return result.get_next()[0]

    def node_exists(self, table: str, node_id: str) -> bool:
        q = f"MATCH (n:{table} {{id: $id}}) RETURN count(n) AS cnt"
        result = self.conn.execute(q, {"id": node_id})
        return result.get_next()[0] > 0

    def get_node(self, table: str, node_id: str) -> Optional[dict]:
        q = f"MATCH (n:{table} {{id: $id}}) RETURN n.*"
        result = self.conn.execute(q, {"id": node_id})
        if result.has_next():
            columns = result.get_column_names()
            return dict(zip(columns, result.get_next()))
        return None

    def update_node(self, table: str, node_id: str, properties: dict):
        set_clause = ", ".join(f"n.{k} = ${k}" for k in properties)
        q = f"MATCH (n:{table} {{id: $id}}) SET {set_clause}"
        self.conn.execute(q, {"id": node_id, **properties})

    def delete_node(self, table: str, node_id: str):
        q = f"MATCH (n:{table} {{id: $id}}) DETACH DELETE n"
        self.conn.execute(q, {"id": node_id})

    def create_edge(self, rel_name: str, from_id: str, to_id: str, properties: Optional[dict] = None):
        if properties:
            set_clause = ", ".join(f"{k}: ${k}" for k in properties)
            q = f"MATCH (a) WHERE a.id = $from_id MATCH (b) WHERE b.id = $to_id CREATE (a)-[r:{rel_name} {{ {set_clause} }}]->(b)"
            self.conn.execute(q, {"from_id": from_id, "to_id": to_id, **(properties or {})})
        else:
            q = "MATCH (a) WHERE a.id = $from_id MATCH (b) WHERE b.id = $to_id CREATE (a)-[:{}]->(b)".format(rel_name)
            self.conn.execute(q, {"from_id": from_id, "to_id": to_id})

    def get_edge(self, rel_name: str, from_id: str, to_id: str) -> Optional[dict]:
        q = f"MATCH (a {{id: $from_id}})-[r:{rel_name}]->(b {{id: $to_id}}) RETURN r.* LIMIT 1"
        result = self.conn.execute(q, {"from_id": from_id, "to_id": to_id})
        if result.has_next():
            columns = result.get_column_names()
            return dict(zip(columns, result.get_next()))
        return None

    def delete_edge(self, edge_id: int):
        self.conn.execute("MATCH ()-[r]->() WHERE id(r) = $id DELETE r", {"id": edge_id})

    def count_nodes(self, table: str) -> int:
        q = f"MATCH (n:{table}) RETURN count(n) AS cnt"
        result = self.conn.execute(q)
        return result.get_next()[0]

    def count_edges(self, rel_name: str) -> int:
        q = f"MATCH ()-[r:{rel_name}]->() RETURN count(r) AS cnt"
        result = self.conn.execute(q)
        return result.get_next()[0]

    def get_top_events(self, limit: int = 5, min_importance: float = 0.0) -> list[dict]:
        return self.execute(
            "MATCH (e:Event) WHERE e.importance >= $min RETURN e.* ORDER BY e.importance DESC LIMIT $limit",
            {"min": min_importance, "limit": limit},
        )

    def get_top_contradictions(self, limit: int = 3, status: str = "unresolved") -> list[dict]:
        return self.execute(
            """MATCH (c1:Claim)-[r:CONTRADICTS]->(c2:Claim)
            WHERE r.resolution_status = $status
            RETURN c1.text AS claim_a, c2.text AS claim_b, r.strength, r.contradiction_type, r.detected_at
            ORDER BY r.strength DESC LIMIT $limit""",
            {"status": status, "limit": limit},
        )

    def get_active_narratives(self, limit: int = 5) -> list[dict]:
        return self.execute(
            "MATCH (n:Narrative) WHERE n.active = true RETURN n.* ORDER BY n.drift_score DESC LIMIT $limit",
            {"limit": limit},
        )

    def get_latest_broadcast(self) -> Optional[dict]:
        results = self.execute(
            "MATCH (b:Broadcast) RETURN b.* ORDER BY b.aired_at DESC LIMIT 1"
        )
        return results[0] if results else None

    def get_claims_since(self, hours: float = 24) -> list[dict]:
        cutoff_dt = datetime.now().timestamp() - hours * 3600
        cutoff = datetime.fromtimestamp(cutoff_dt).strftime("%Y-%m-%dT%H:%M:%S")
        return self.execute(
            "MATCH (c:Claim) WHERE c.timestamp > $cutoff RETURN c.* ORDER BY c.timestamp DESC",
            {"cutoff": cutoff},
        )

    def get_all_claim_ids(self) -> list[str]:
        return [row["c.id"] for row in self.execute("MATCH (c:Claim) RETURN c.id")]

    def get_claim(self, claim_id: str) -> Optional[dict]:
        return self.get_node("Claim", claim_id)

    def find_entity(self, name: str) -> Optional[dict]:
        results = self.execute("MATCH (e:Entity) WHERE e.name = $name RETURN e.* LIMIT 1", {"name": name})
        return results[0] if results else None

    def find_entity_by_alias(self, alias: str) -> Optional[dict]:
        results = self.execute(
            "MATCH (e:Entity) WHERE array_contains(e.aliases, $alias) RETURN e.* LIMIT 1",
            {"alias": alias},
        )
        return results[0] if results else None

    def search_entities(self, name: str, threshold: float = 0.85) -> list[dict]:
        return self.execute(
            "MATCH (e:Entity) WHERE levenshtein(e.name, $name) < $dist RETURN e.* LIMIT 10",
            {"name": name, "dist": int((1 - threshold) * len(name))},
        )

    def get_claim_contradictions(self, claim_id: str) -> list[dict]:
        return self.execute(
            """MATCH (c:Claim {id: $id})-[r:CONTRADICTS]-(other:Claim)
            RETURN other.text, r.contradiction_type, r.strength, r.resolution_status""",
            {"id": claim_id},
        )

    def link_claim_to_event(self, claim_id: str, event_id: str, confidence: float = 0.5):
        self.create_edge("ABOUT_EVENT", claim_id, event_id, {
            "confidence": confidence,
            "first_seen": datetime.utcnow().isoformat(),
        })

    def find_orphan_claims(self, older_than_days: int = 7, max_confidence: float = 0.3,
                            max_contradictions: int = 0) -> list[dict]:
        cutoff_dt = time.time() - older_than_days * 86400
        cutoff = datetime.utcfromtimestamp(cutoff_dt).strftime("%Y-%m-%dT%H:%M:%S")
        return self.execute(
            """MATCH (c:Claim) WHERE c.confidence < $conf AND c.timestamp < $cutoff
            AND NOT (c)-[:ABOUT_EVENT]->() AND NOT (c)-[:CONTRADICTS]-()
            RETURN c.*""",
            {"conf": max_confidence, "cutoff": cutoff},
        )

    def get_unclustered_claims(self, hours: int = 24) -> list[dict]:
        cutoff_dt = time.time() - hours * 3600
        cutoff = datetime.utcfromtimestamp(cutoff_dt).strftime("%Y-%m-%dT%H:%M:%S")
        return self.execute(
            """MATCH (c:Claim) WHERE c.timestamp > $cutoff
            AND NOT (c)-[:ABOUT_EVENT]->() AND c.embedding_id IS NOT NULL
            RETURN c.*""",
            {"cutoff": cutoff},
        )

    def get_thread_claims(self, narrative_id: str) -> list[dict]:
        return self.execute(
            """MATCH (c:Claim)-[:PART_OF_THREAD]->(n:Narrative {id: $id})
            RETURN c.* ORDER BY c.timestamp""",
            {"id": narrative_id},
        )

    def get_event_claims(self, event_id: str) -> list[dict]:
        return self.execute(
            """MATCH (c:Claim)-[:ABOUT_EVENT]->(e:Event {id: $id})
            RETURN c.* ORDER BY c.timestamp""",
            {"id": event_id},
        )

    def get_event_entities(self, event_id: str) -> list[dict]:
        return self.execute(
            """MATCH (e:Entity)-[:APPEARS_IN]->(ev:Event {id: $id})
            RETURN e.*""",
            {"id": event_id},
        )

    def get_event_contradictions(self, event_id: str) -> list[dict]:
        return self.execute(
            """MATCH (c1:Claim)-[r:CONTRADICTS]->(c2:Claim)
            WHERE (c1)-[:ABOUT_EVENT]->(:Event {id: $id})
            OR (c2)-[:ABOUT_EVENT]->(:Event {id: $id})
            RETURN r.*""",
            {"id": event_id},
        )

    def get_drift_reports(self, hours: int = 24, min_score: float = 0.0) -> list[dict]:
        cutoff_dt = time.time() - hours * 3600
        cutoff = datetime.utcfromtimestamp(cutoff_dt).strftime("%Y-%m-%dT%H:%M:%S")
        return self.execute(
            """MATCH (n:Narrative) WHERE n.drift_score >= $min AND n.last_updated > $cutoff
            RETURN n.label, n.drift_score, n.framing, n.last_updated""",
            {"min": min_score, "cutoff": cutoff},
        )

    def get_all_sources(self) -> list[dict]:
        return self.execute("MATCH (s:Source) RETURN s.*")

    def get_random_claims(self, limit: int = 100) -> list[dict]:
        return self.execute(
            f"MATCH (c:Claim) RETURN c.* ORDER BY random() LIMIT {limit}"
        )

    def close(self):
        self.db.close()


class GraphTransaction:
    def __init__(self, conn: kuzu.Connection):
        self.conn = conn

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
