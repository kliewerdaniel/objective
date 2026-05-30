"""SQLite metadata store for pipeline state, audit logs, and evaluation metrics."""

import json
import sqlite3
import time
from pathlib import Path
from typing import Optional, Any


class MetadataStore:
    """SQLite-backed metadata and state store."""

    def __init__(self, path: str):
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA cache_size=-64000")
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS ingestion_state (
                source_name TEXT PRIMARY KEY,
                last_polled_at REAL NOT NULL,
                etag TEXT,
                last_modified TEXT,
                cursor TEXT,
                last_error TEXT,
                consecutive_failures INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS dedup_hashes (
                hash TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                ingested_at REAL NOT NULL,
                source_name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS scheduler_state (
                task_name TEXT PRIMARY KEY,
                last_run REAL NOT NULL,
                failures INTEGER DEFAULT 0,
                disabled INTEGER DEFAULT 0,
                last_duration REAL,
                last_error TEXT
            );

            CREATE TABLE IF NOT EXISTS evaluation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                metrics TEXT NOT NULL,
                alerts TEXT
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                event_type TEXT NOT NULL,
                component TEXT NOT NULL,
                trace_id TEXT,
                data TEXT,
                error TEXT
            );

            CREATE TABLE IF NOT EXISTS contradiction_index (
                id TEXT PRIMARY KEY,
                claim_a_id TEXT NOT NULL,
                claim_b_id TEXT NOT NULL,
                contradiction_type TEXT NOT NULL,
                strength REAL NOT NULL,
                confidence REAL NOT NULL,
                detected_at REAL NOT NULL,
                resolution_status TEXT NOT NULL DEFAULT 'unresolved',
                resolved_at REAL
            );
            CREATE INDEX IF NOT EXISTS idx_contra_unresolved
                ON contradiction_index(resolution_status);
            CREATE INDEX IF NOT EXISTS idx_contra_type
                ON contradiction_index(contradiction_type);

            CREATE TABLE IF NOT EXISTS provenance (
                claim_id TEXT NOT NULL,
                source_document_id TEXT NOT NULL,
                source_url TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_published_at REAL NOT NULL,
                ingested_at REAL NOT NULL,
                extraction_model TEXT NOT NULL,
                extraction_confidence REAL NOT NULL,
                extractor_version TEXT NOT NULL,
                prompt_hash TEXT NOT NULL,
                raw_evidence TEXT NOT NULL,
                transformations TEXT,
                previous_versions TEXT,
                PRIMARY KEY (claim_id, source_document_id)
            );

            CREATE TABLE IF NOT EXISTS model_cache (
                cache_key TEXT PRIMARY KEY,
                model_name TEXT NOT NULL,
                prompt_hash TEXT NOT NULL,
                output TEXT NOT NULL,
                created_at REAL NOT NULL,
                ttl_seconds INTEGER DEFAULT 86400,
                access_count INTEGER DEFAULT 1,
                last_accessed REAL NOT NULL
            );
        """)
        self.conn.commit()

    def get_ingestion_state(self, source_name: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM ingestion_state WHERE source_name = ?", (source_name,)
        ).fetchone()
        return dict(row) if row else None

    def update_ingestion_state(self, source_name: str, etag: str = None,
                                cursor: str = None, error: str = None):
        exists = self.get_ingestion_state(source_name)
        now = time.time()
        if exists:
            self.conn.execute("""
                UPDATE ingestion_state SET last_polled_at = ?,
                    etag = COALESCE(?, etag), cursor = COALESCE(?, cursor),
                    last_error = ?,
                    consecutive_failures = CASE WHEN ? IS NOT NULL THEN consecutive_failures + 1 ELSE 0 END
                WHERE source_name = ?
            """, (now, etag, cursor, error, error, source_name))
        else:
            self.conn.execute("""
                INSERT INTO ingestion_state (source_name, last_polled_at, etag, cursor, last_error)
                VALUES (?, ?, ?, ?, ?)
            """, (source_name, now, etag, cursor, error))
        self.conn.commit()

    def has_hash(self, hash_str: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM dedup_hashes WHERE hash = ?", (hash_str,)
        ).fetchone()
        return row is not None

    def store_hash(self, hash_str: str, document_id: str, source_name: str):
        self.conn.execute(
            "INSERT OR IGNORE INTO dedup_hashes (hash, document_id, ingested_at, source_name) VALUES (?, ?, ?, ?)",
            (hash_str, document_id, time.time(), source_name),
        )
        self.conn.commit()

    def update_scheduler_state(self, task_name: str, duration: float = None,
                                error: str = None):
        now = time.time()
        exists = self.conn.execute(
            "SELECT 1 FROM scheduler_state WHERE task_name = ?", (task_name,)
        ).fetchone()
        if exists:
            self.conn.execute("""
                UPDATE scheduler_state SET last_run = ?, last_duration = ?,
                    failures = CASE WHEN ? IS NOT NULL THEN failures + 1 ELSE 0 END,
                    last_error = ?
                WHERE task_name = ?
            """, (now, duration, error, error, task_name))
        else:
            self.conn.execute("""
                INSERT INTO scheduler_state (task_name, last_run, last_duration, last_error)
                VALUES (?, ?, ?, ?)
            """, (task_name, now, duration, error))
        self.conn.commit()

    def store_evaluation(self, metrics: dict):
        self.conn.execute(
            "INSERT INTO evaluation_history (timestamp, metrics, alerts) VALUES (?, ?, ?)",
            (time.time(), json.dumps(metrics), json.dumps(metrics.get("alerts", []))),
        )
        self.conn.commit()

    def get_evaluations(self, since_hours: float = 24) -> list[dict]:
        cutoff = time.time() - since_hours * 3600
        rows = self.conn.execute(
            "SELECT * FROM evaluation_history WHERE timestamp > ? ORDER BY timestamp DESC",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]

    def log_audit(self, event_type: str, component: str, trace_id: str = None,
                  data: dict = None, error: str = None):
        self.conn.execute(
            "INSERT INTO audit_log (timestamp, event_type, component, trace_id, data, error) VALUES (?, ?, ?, ?, ?, ?)",
            (time.time(), event_type, component, trace_id,
             json.dumps(data) if data else None, error),
        )
        self.conn.commit()

    def close(self):
        self.conn.close()
