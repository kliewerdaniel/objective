# Metadata Database Schema

## SQLite Schema

The metadata store uses SQLite for its ACID guarantees, zero configuration, and lightweight operation. All tables use INTEGER PRIMARY KEY for internal IDs and TEXT for external UUID references.

```sql
-- Pipeline state
CREATE TABLE ingestion_state (
    source_name TEXT PRIMARY KEY,
    last_polled_at REAL NOT NULL,     -- unix timestamp
    etag TEXT,
    last_modified TEXT,
    cursor TEXT,                      -- opaque cursor for paginated APIs
    last_error TEXT,
    consecutive_failures INTEGER DEFAULT 0
);

CREATE TABLE dedup_hashes (
    hash TEXT PRIMARY KEY,            -- SHA-256 of normalized content
    document_id TEXT NOT NULL,
    ingested_at REAL NOT NULL,
    source_name TEXT NOT NULL
);

CREATE INDEX idx_dedup_time ON dedup_hashes(ingested_at DESC);

-- Scheduler state
CREATE TABLE scheduler_state (
    task_name TEXT PRIMARY KEY,
    last_run REAL NOT NULL,
    failures INTEGER DEFAULT 0,
    disabled INTEGER DEFAULT 0,
    last_duration REAL,
    last_error TEXT
);

-- Evaluation and metrics
CREATE TABLE evaluation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    metrics TEXT NOT NULL,             -- JSON blob
    alerts TEXT                        -- JSON array
);

CREATE INDEX idx_eval_time ON evaluation_history(timestamp DESC);

-- Audit log
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    event_type TEXT NOT NULL,
    component TEXT NOT NULL,
    trace_id TEXT,
    data TEXT,                         -- JSON payload
    error TEXT
);

CREATE INDEX idx_audit_type ON audit_log(event_type);
CREATE INDEX idx_audit_time ON audit_log(timestamp DESC);
CREATE INDEX idx_audit_trace ON audit_log(trace_id);

-- Provenance
CREATE TABLE provenance (
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
    transformations TEXT,              -- JSON array
    previous_versions TEXT,            -- JSON array of claim IDs
    PRIMARY KEY (claim_id, source_document_id)
);

CREATE INDEX idx_provenance_claim ON provenance(claim_id);
CREATE INDEX idx_provenance_source ON provenance(source_document_id);
CREATE INDEX idx_provenance_model ON provenance(extraction_model);

-- Archival storage
CREATE TABLE archived_documents (
    id TEXT PRIMARY KEY,               -- Original document ID
    data TEXT NOT NULL,                -- JSON serialized document
    archived_at REAL NOT NULL
);

-- Model cache
CREATE TABLE model_cache (
    cache_key TEXT PRIMARY KEY,        -- SHA-256 of input
    model_name TEXT NOT NULL,
    prompt_hash TEXT NOT NULL,
    output TEXT NOT NULL,              -- JSON serialized output
    created_at REAL NOT NULL,
    ttl_seconds INTEGER DEFAULT 86400,
    access_count INTEGER DEFAULT 1,
    last_accessed REAL NOT NULL
);

CREATE INDEX idx_cache_model ON model_cache(model_name);
CREATE INDEX idx_cache_access ON model_cache(last_accessed DESC);

-- Configuration overrides
CREATE TABLE config_overrides (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);
```

## Usage Examples

```python
class MetadataStore:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA cache_size=-64000")  # 64MB
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
            -- ... other tables
        """)
        self.conn.commit()
    
    def update_ingestion_state(self, source_name: str, cursor: str = None,
                                etag: str = None, error: str = None):
        self.conn.execute("""
            INSERT INTO ingestion_state 
            (source_name, last_polled_at, etag, cursor, last_error, consecutive_failures)
            VALUES (?, ?, ?, ?, ?, 
                CASE WHEN ? IS NOT NULL THEN consecutive_failures + 1 ELSE 0 END)
            ON CONFLICT(source_name) DO UPDATE SET
                last_polled_at = ?,
                etag = COALESCE(?, etag),
                cursor = COALESCE(?, cursor),
                last_error = ?,
                consecutive_failures = 
                    CASE WHEN ? IS NOT NULL THEN consecutive_failures + 1 ELSE 0 END
        """, (source_name, time.time(), etag, cursor, error, 
              time.time(), etag, cursor, error, error))
        self.conn.commit()
    
    def log_audit(self, event_type: str, component: str, 
                  trace_id: str = None, data: dict = None, error: str = None):
        self.conn.execute("""
            INSERT INTO audit_log (timestamp, event_type, component, trace_id, data, error)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (time.time(), event_type, component, trace_id,
              json.dumps(data) if data else None, error))
        self.conn.commit()
    
    def get_evaluation_history(self, since_hours: int = 24) -> list[dict]:
        cutoff = time.time() - since_hours * 3600
        rows = self.conn.execute("""
            SELECT * FROM evaluation_history 
            WHERE timestamp > ? 
            ORDER BY timestamp DESC
        """, (cutoff,)).fetchall()
        return [dict(r) for r in rows]
```

## Backup and Maintenance

```sql
-- WAL checkpoint
PRAGMA wal_checkpoint(TRUNCATE);

-- Vacuum (after deletes)
VACUUM;

-- Integrity check
PRAGMA integrity_check;
```
