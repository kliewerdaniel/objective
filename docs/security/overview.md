# Security Documentation

## Overview

objective03 faces security challenges from multiple vectors: malicious feed content, prompt injection, source poisoning, and system compromise. The security architecture assumes a local deployment on a personal machine, not a multi-tenant service, but still implements defense-in-depth.

## Feed Hardening

### Input Sanitization

All incoming content is sanitized before processing:

```python
def sanitize_feed_content(raw: RawDocument) -> RawDocument:
    """Remove malicious content from incoming feeds."""
    # Strip scripts and iframes
    raw.body = re.sub(r'<script[^>]*>.*?</script>', '', raw.body, flags=re.DOTALL)
    raw.body = re.sub(r'<iframe[^>]*>.*?</iframe>', '', raw.body, flags=re.DOTALL)
    
    # Remove zero-width characters
    raw.body = re.sub(r'[\u200b\u200c\u200d\u2060\u2061\u2062\u2063\u2064]', '', raw.body)
    
    # Normalize unicode
    raw.body = unicodedata.normalize('NFKC', raw.body)
    
    # Truncate excessively long content
    if len(raw.body) > 100000:
        raw.body = raw.body[:100000]
    
    return raw
```

### Rate Limiting

Prevents feed abuse:

```python
class FeedRateLimiter:
    def __init__(self, max_per_source: int = 1000, window_seconds: int = 3600):
        self.max_per_source = max_per_source
        self.window = window_seconds
        self.counts: dict[str, list[float]] = {}
    
    def is_rate_limited(self, source_name: str) -> bool:
        now = time.monotonic()
        self.counts.setdefault(source_name, [])
        self.counts[source_name] = [t for t in self.counts[source_name] if now - t < self.window]
        
        if len(self.counts[source_name]) >= self.max_per_source:
            return True
        
        self.counts[source_name].append(now)
        return False
```

## Provenance

See [architecture/claim_provenance_engine.md](../architecture/claim_provenance_engine.md).

## Audit Logging

Every significant operation is logged to the audit trail:

| Event Type | Logged Data | Retention |
|-----------|-------------|-----------|
| Ingestion | Source, document count, errors | 30 days |
| Extraction | Model, claims count, confidence | 30 days |
| Graph mutation | Node type, count, error | 7 days |
| Contradiction | Type, strength, claims | 30 days |
| Broadcast | Script ID, segments, duration | 90 days |
| System error | Component, traceback | 30 days |
| Config change | Key, old value, new value | 90 days |
| Model load/unload | Model name, memory | 7 days |
