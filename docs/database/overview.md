# Database Overview

## Three-Layer Storage Architecture

objective03 uses three distinct database systems, each serving a specific purpose. This layered approach avoids the "one database to rule them all" anti-pattern.

| Database | Role | Data | Access Pattern |
|----------|------|------|----------------|
| KuzuDB | Primary graph storage | Temporal property graph with events, claims, entities, narratives, broadcasts | Graph traversals, temporal queries, relationship analysis |
| Qdrant | Vector similarity search | Embeddings for claims, entities, narratives, broadcast segments | Semantic search, similarity matching, drift detection |
| SQLite | Metadata and state | Pipeline state, evaluation metrics, provenance, audit logs, configuration overrides | Key-value lookups, time-series queries |

## Why Three Databases?

### KuzuDB
- **Why graph?** The data model is inherently graph-shaped (claims reference entities, contradiction connects claims, narratives contain claims, broadcasts reference events). A graph database makes these relationships first-class and queryable.
- **Why KuzuDB specifically?** Embedded (no server process), columnar (fast analytic queries), native temporal support, lightweight for a single-machine deployment, Python-native API.
- **Why not Neo4j?** Requires a running server, higher resource overhead, overkill for single-machine deployment.
- **Why not just SQL?** Relational databases require join tables for every relationship, making temporal graph traversal queries complex and slow. A graph database stores relationships as first-class objects.

### Qdrant
- **Why vector?** Semantic similarity is essential for contradiction detection, narrative clustering, and drift measurement. Vector embeddings enable O(1) semantic comparison where string matching fails completely.
- **Why Qdrant specifically?** Local deployment, efficient HNSW indexing, filtering support, good Python bindings, reasonable memory usage.
- **Why not just KuzuDB embeddings?** KuzuDB doesn't natively support vector similarity search. Storing embeddings and doing the search in application code would be slow and memory-intensive.

### SQLite
- **Why relational?** Pipeline state, scheduler state, evaluation metrics, and audit logs are naturally tabular. SQLite provides ACID guarantees, zero configuration, and lightweight operation.
- **Why not KuzuDB?** Graph databases are optimized for connected data, not simple key-value or time-series storage. Using KuzuDB for metadata would be wasteful.
- **Why not Qdrant?** Qdrant is a vector store, not a general-purpose database.

## Data Flow Between Databases

```
Ingestion Pipeline
    │
    ▼
┌──────────────────┐
│    SQLite         │  ← Pipeline state, cursors, dedup hashes
│  (Metadata)       │
└──────────────────┘
    │
    ▼
┌──────────────────┐     ┌──────────────────┐
│    KuzuDB         │◀───│    Qdrant         │
│  (Graph)          │     │  (Vectors)        │
│                   │     │                  │
│ Nodes + edges     │     │ Claim embeddings │
│ Temporal relations│     │ Entity embeddings│
│ Contradictions    │     │ Narrative emb.   │
│ Broadcasts        │     │                  │
└──────────────────┘     └──────────────────┘
    │                           │
    └───────────────────────────┘
                │
                ▼
┌──────────────────┐
│    SQLite         │  ← Evaluation metrics, audit logs
│  (Metadata)       │
└──────────────────┘
```

## Why Not a Single Database?

The obvious question: why not use one database for everything?

- **Graph + Vector**: No single database excels at both graph traversal and vector similarity. KuzuDB is optimized for graph queries; Qdrant for vector search.
- **Graph + Metadata**: Graph databases have higher overhead per query than SQLite for simple key-value lookups. Using SQLite for metadata reduces graph query load.
- **Vector + Metadata**: Qdrant can store payloads, but it's not designed for relational queries or ACID transactions.

The operational cost of managing three databases (one embedded, one local HTTP service, one file) is justified by the performance and architectural clarity.

## Configuration

```yaml
databases:
  graph:
    path: "~/.objective03/graph.db"   # KuzuDB embedded file
    buffer_pool_size: 1024            # MB
    max_threads: 4
  
  vector:
    host: "localhost"
    port: 6333
    collection: "objective03"
    vector_size: 384                  # BGE-small dimension
    distance: "Cosine"
    hnsw_config:
      m: 16
      ef_construction: 200
      ef_search: 100
  
  metadata:
    path: "~/.objective03/metadata.db"
    wal_mode: "WAL"                  # Write-ahead logging for concurrency
    cache_size: -64000               # 64MB page cache
```
