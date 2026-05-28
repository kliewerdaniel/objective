# Data Schemas

## Event Schema

```python
@dataclass
class Event:
    id: str; title: str; description: str
    start_time: datetime; end_time: Optional[datetime]
    status: str  # emerging|active|ongoing|concluded|archived
    importance: float  # 0.0-1.0 computed
    embedding_id: Optional[str]
```

## Entity Schema

```python
@dataclass
class Entity:
    id: str; name: str (canonical)
    type: str  # person|organization|location|event|concept
    aliases: list[str]; metadata: dict
    first_seen: datetime; last_seen: datetime
```

## Source Schema

```python
@dataclass
class Source:
    id: str; name: str; type: str; base_url: str
    trust_score: float  # 0.0-1.0 dynamic
    metadata: dict; created_at: datetime
```

## Contradiction Schema

```python
@dataclass
class Contradiction:
    id: str; claim_a: str; claim_b: str
    contradiction_type: str  # direct|numerical|temporal|framing|contextual
    strength: float; confidence: float
    detected_at: datetime; resolved_at: Optional[datetime]
    resolution_status: str  # unresolved|resolved|false|superseded
```

## Narrative Schema

```python
@dataclass
class Narrative:
    id: str; label: str; description: str
    drift_score: float; framing: str; active: bool
    first_seen: datetime; last_updated: datetime
    claim_ids: list[str]; embedding: Optional[list[float]]
```

## Broadcast Schema

```python
@dataclass
class Broadcast:
    id: str; script: str
    segments: list[ScriptSegment]
    duration_seconds: float; aired_at: datetime
    topics: list[str]; metrics: dict
    audio_path: Optional[str]
```

## Timeline Schema

```python
@dataclass
class TimelineEntry:
    event_id: str; timestamp: datetime
    entry_type: str  # claim_added|contradiction_detected|broadcast
    description: str; confidence: float; source: str
```
