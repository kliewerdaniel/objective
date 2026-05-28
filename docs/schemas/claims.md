# Data Schemas

## Claim Schema

```python
@dataclass
class Claim:
    id: str                          # UUID
    text: str                        # Atomic claim (20-500 chars)
    confidence: float                # 0.0-1.0 extraction confidence
    stance: str                      # "support", "neutral", "oppose", "uncertain"
    topic: str                       # Classification
    evidence: str                    # Direct quote from source
    source_document_id: str          # Reference to document
    source_name: str                 # Human-readable source name
    source_type: str                 # "rss", "reddit", etc.
    published_at: datetime           # Source publication time
    ingested_at: datetime            # System ingestion time
    entity_ids: list[str]            # References to entities
    entity_names: list[str]          # Surface forms
    event_id: Optional[str]          # Assigned event
    narrative_ids: list[str]         # Assigned narratives
    embedding_id: Optional[str]      # Qdrant point ID
    verified: bool = False           # Manual verification flag
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "confidence": self.confidence,
            "stance": self.stance,
            "topic": self.topic,
            "evidence": self.evidence,
            "timestamp": self.published_at.isoformat(),
            "embedding_id": self.embedding_id,
        }
```

## Event Schema

```python
@dataclass
class Event:
    id: str                          # UUID
    title: str                       # Generated title
    description: str                 # Summary
    start_time: datetime
    end_time: Optional[datetime]
    status: str                      # "emerging", "active", "ongoing", "concluded", "archived"
    importance: float                # 0.0-1.0 computed
    embedding_id: Optional[str]
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "status": self.status,
            "importance": self.importance,
            "embedding_id": self.embedding_id,
        }
```

## Entity Schema

```python
@dataclass
class Entity:
    id: str                          # UUID
    name: str                        # Canonical name
    type: str                        # "person", "organization", "location", "event", "concept"
    aliases: list[str]               # Alternative names
    metadata: dict                   # Additional data
    first_seen: datetime
    last_seen: datetime
```

## Source Schema

```python
@dataclass
class Source:
    id: str                          # UUID
    name: str                        # Human-readable
    type: str                        # Connector type
    base_url: str
    trust_score: float               # 0.0-1.0 dynamic
    metadata: dict
    created_at: datetime
```

## Contradiction Schema

```python
@dataclass
class Contradiction:
    id: str                          # UUID
    claim_a: str                     # Claim ID
    claim_b: str                     # Claim ID
    contradiction_type: str          # "direct", "numerical", "temporal", "framing", "contextual"
    strength: float                  # 0.0-1.0
    confidence: float                # Detection confidence
    detected_at: datetime
    resolved_at: Optional[datetime]
    resolution_status: str           # "unresolved", "resolved", "false", "superseded"
    resolution: Optional[str]        # How resolved
```

## Narrative Schema

```python
@dataclass
class Narrative:
    id: str                          # UUID
    label: str                       # Generated label
    description: str                 # Summary
    drift_score: float               # 0.0-1.0
    framing: str                     # Dominant frame
    active: bool
    first_seen: datetime
    last_updated: datetime
    claim_ids: list[str]
    embedding: Optional[list[float]]
```

## Broadcast Schema

```python
@dataclass
class Broadcast:
    id: str                          # UUID
    script: str                      # Full text
    segments: list[ScriptSegment]
    duration_seconds: float
    aired_at: datetime
    topics: list[str]
    metrics: dict                    # System state snapshot
    audio_path: Optional[str]        # Rendered audio file
```

## Timeline Schema

```python
@dataclass
class TimelineEntry:
    event_id: str
    timestamp: datetime
    entry_type: str                  # "claim_added", "contradiction_detected", "broadcast"
    description: str
    confidence: float
    source: str
```
