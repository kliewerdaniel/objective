# Claim Provenance Engine

## Overview

Every claim in objective03 carries a complete provenance chain — from the original source document through every transformation, analysis, and reference. Provenance is the foundation of trust, auditability, and contradiction analysis.

## Provenance Chain

```
Source Document (raw) 
    │
    ▼
Normalized Document (clean) 
    │
    ▼
Extracted Claim (atomic factoid) 
    │
    ▼            
Resolved Entities (canonical IDs) 
    │
    ▼
Graph Node (stored with metadata)
    │
    ├──▶ Contradiction Detection
    │       └── Contradiction edge with provenance
    │
    ├──▶ Narrative Classification
    │       └── Claim-thread membership with confidence
    │
    ├──▶ Framing Analysis
    │       └── Framing label with confidence
    │
    └──▶ Broadcast Reference
            └── Broadcast segment with citation
```

## Provenance Data Model

```python
@dataclass
class ProvenanceEntry:
    claim_id: str
    source_document_id: str
    source_url: str
    source_name: str
    source_type: str
    source_published_at: datetime
    ingested_at: datetime
    extraction_model: str
    extraction_confidence: float
    extractor_version: str
    prompt_hash: str           # Hash of the prompt used
    raw_evidence: str          # Direct quote from source
    transformations: list[Transformation]
    previous_versions: list[str]  # If claim was updated/superseded

@dataclass
class Transformation:
    type: str                  # "extraction", "entity_resolution", "translation", etc.
    applied_by: str            # Component or model name
    input_hash: str
    output_hash: str
    timestamp: datetime
    confidence: float
```

## Provenance Storage

Provenance is stored in two places:

### 1. KuzuDB (graph edges)

Each `EXTRACTED_FROM` edge carries provenance metadata:

```cypher
CREATE REL TABLE EXTRACTED_FROM(
    extraction_confidence FLOAT,
    extractor_model STRING,
    extractor_version STRING,
    prompt_hash STRING,
    raw_evidence STRING,
    extracted_at TIMESTAMP
)
```

### 2. SQLite (audit trail)

Full provenance records are stored in the audit log:

```sql
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
    transformations TEXT,  -- JSON array of Transformation
    previous_versions TEXT, -- JSON array of claim IDs
    
    PRIMARY KEY (claim_id, source_document_id)
);

CREATE INDEX idx_provenance_claim ON provenance(claim_id);
CREATE INDEX idx_provenance_source ON provenance(source_document_id);
CREATE INDEX idx_provenance_model ON provenance(extraction_model);
```

## Source Trust Scoring

Each source has a trust score that evolves based on:

```python
class SourceTrustEvaluator:
    def __init__(self, graph: GraphStore, metadata: SQLiteStore):
        self.graph = graph
        self.metadata = metadata
    
    def compute_trust_score(self, source_id: str) -> float:
        """Compute dynamic trust score for a source."""
        factors = {}
        
        # 1. Historical accuracy
        retractions = self.graph.get_source_retraction_count(source_id)
        claims = self.graph.get_source_claim_count(source_id)
        factors["accuracy"] = 1.0 - (retractions / max(claims, 1))
        
        # 2. Contradiction ratio (high contradiction = lower trust)
        contradictions = self.graph.get_source_contradiction_count(source_id)
        factors["consistency"] = 1.0 - min(contradictions / max(claims, 1) * 2, 1.0)
        
        # 3. Source type base trust
        source_type = self.graph.get_source_type(source_id)
        type_trust = {
            "gov_rss": 0.5,      # Government sources: moderate (spin risk)
            "news_api": 0.7,     # News APIs: moderate-high
            "rss": 0.6,          # RSS feeds: moderate
            "reddit": 0.3,       # Reddit: low (noise risk)
            "youtube": 0.4,      # YouTube: moderate-low
        }
        factors["type_trust"] = type_trust.get(source_type, 0.5)
        
        # 4. Longevity (older sources have more track record)
        age_days = self.graph.get_source_age_days(source_id)
        factors["longevity"] = min(age_days / 365, 1.0)  # Max at 1 year
        
        # 5. Citation rate (how often other sources corroborate)
        corroboration = self.graph.get_source_corroboration_rate(source_id)
        factors["corroboration"] = corroboration
        
        # Weighted combination
        weights = {
            "accuracy": 0.35,
            "consistency": 0.20,
            "type_trust": 0.20,
            "longevity": 0.10,
            "corroboration": 0.15,
        }
        
        score = sum(factors[k] * weights[k] for k in weights)
        return max(0.0, min(1.0, score))
```

## Claim Verification

Claims can be verified against the provenance chain:

```python
def verify_claim(claim_id: str, graph: GraphStore) -> VerificationResult:
    """Verify a claim by checking its provenance chain."""
    claim = graph.get_claim(claim_id)
    provenance = graph.get_claim_provenance(claim_id)
    
    issues = []
    
    # Check 1: Source still exists
    source = graph.get_source(provenance.source_id)
    if not source:
        issues.append(Issue("source_deleted", severity="warning"))
    
    # Check 2: Source trust score
    trust = SourceTrustEvaluator(graph).compute_trust_score(provenance.source_id)
    if trust < 0.3:
        issues.append(Issue(f"low_source_trust: {trust:.2f}", severity="warning"))
    
    # Check 3: Model confidence
    if provenance.extraction_confidence < 0.5:
        issues.append(Issue(f"low_extraction_confidence: {provenance.extraction_confidence:.2f}", 
                          severity="info"))
    
    # Check 4: Contradiction count
    contradictions = graph.get_claim_contradictions(claim_id)
    if len(contradictions) > 5:
        issues.append(Issue(f"highly_contested: {len(contradictions)} contradictions", 
                          severity="info"))
    
    # Check 5: Age (confidence decays)
    age_hours = (datetime.utcnow() - claim.timestamp).total_seconds() / 3600
    if age_hours > 72 and not graph.is_claim_verified(claim_id):
        issues.append(Issue(f"unverified_old_claim: {age_hours:.0f} hours old", 
                          severity="info"))
    
    return VerificationResult(
        claim_id=claim_id,
        verified=len([i for i in issues if i.severity == "error"]) == 0,
        issues=issues,
        source_trust=trust,
        age_hours=age_hours,
        contradiction_count=len(contradictions),
    )
```

## Broadcast Provenance

When claims are referenced in broadcasts, the provenance is included as metadata:

```python
@dataclass
class BroadcastProvenance:
    broadcast_id: str
    claim_references: list[ClaimReference]
    
@dataclass
class ClaimReference:
    claim_id: str
    text: str
    source_url: str
    source_name: str
    extraction_confidence: float
    source_trust: float
    contradiction_count: int
    
    def to_citation(self) -> str:
        """Generate a citation for the broadcast script."""
        trust_label = "high" if self.source_trust > 0.7 else "moderate" if self.source_trust > 0.4 else "low"
        return (f"[Source: {self.source_name}, "
                f"confidence: {self.extraction_confidence:.0%}, "
                f"source trust: {trust_label}]")
```

## Deterministic Replay

The provenance chain enables deterministic replay of any broadcast:

```python
def reconstruct_broadcast(broadcast_id: str, graph: GraphStore, 
                          metadata: SQLiteStore) -> BroadcastReconstruction:
    """Reconstruct the state of the graph at broadcast time."""
    broadcast = graph.get_broadcast(broadcast_id)
    
    # Get all claims referenced in this broadcast
    claim_refs = graph.get_broadcast_claim_refs(broadcast_id)
    
    # For each claim, get the provenance at broadcast time
    claim_provenances = {}
    for ref in claim_refs:
        provenance = graph.get_claim_provenance_at_time(
            ref.claim_id, broadcast.aired_at
        )
        claim_provenances[ref.claim_id] = provenance
    
    # Get graph state at broadcast time
    graph_snapshot = graph.get_snapshot_at_time(broadcast.aired_at)
    
    return BroadcastReconstruction(
        broadcast=broadcast,
        claim_provenances=claim_provenances,
        graph_snapshot=graph_snapshot,
        contradictions_active=graph.get_contradictions_at_time(broadcast.aired_at),
    )
```

## Provenance Verification Dashboard

The terminal UI exposes provenance metrics:

```
┌────────────────────────────────────────────┐
│ PROVENANCE METRICS                         │
├────────────────────────────────────────────┤
│ Total claims:          12,847              │
│ With provenance:       12,847 (100%)       │
│ ───────────────────────────────────────── │
│ Source trust distribution:                 │
│   High (0.7+):        3,421 (27%)         │
│   Moderate (0.4-0.7): 6,933 (54%)         │
│   Low (<0.4):         2,493 (19%)         │
│ ───────────────────────────────────────── │
│ Claims with issues:    1,247 (10%)         │
│   Low confidence:        892               │
│   Highly contested:      355               │
│   Unverified old:        412               │
│ ───────────────────────────────────────── │
│ Verification rate:     90%                 │
└────────────────────────────────────────────┘
```
