# Ingestion Pipeline

## Pipeline Flow

```
Source Poller
    │
    ▼
Raw Document
    │
    ▼
Normalization Layer
    │
    ├── HTML stripping
    ├── Encoding fixing
    ├── Whitespace normalization
    ├── Boilerplate removal
    └── Language detection
    │
    ▼
Normalized Document
    │
    ▼
Deduplication Layer
    │
    ├── Exact match (SHA-256)
    └── Fuzzy match (MinHash)
    │
    ▼
Unique Document
    │
    ▼
Claim Extraction
    │
    ▼
Graph Update
```

## Connector Framework

```python
class BaseConnector(ABC):
    """Abstract base for source connectors."""
    
    def __init__(self, config: dict):
        self.config = config
        self.rate_limiter = RateLimiter(
            config.get("rate_limit", 60),
            60,  # window seconds
        )
    
    @abstractmethod
    async def fetch(self) -> list[RawDocument]:
        """Fetch new documents from source."""
        ...
    
    @property
    @abstractmethod
    def name(self) -> str:
        ...
    
    async def poll(self, state: PollState) -> list[RawDocument]:
        await self.rate_limiter.acquire()
        docs = await self.fetch()
        state.update(self.name)
        return docs

class RSSConnector(BaseConnector):
    name = "rss"
    
    async def fetch(self) -> list[RawDocument]:
        # RSS parsing with feedparser
        async with aiohttp.ClientSession() as session:
            async with session.get(self.config["url"]) as resp:
                text = await resp.text()
                feed = feedparser.parse(text)
                return [self._to_raw(e) for e in feed.entries]

class RedditConnector(BaseConnector):
    name = "reddit"
    
    async def fetch(self) -> list[RawDocument]:
        # PRAW integration
        import asyncpraw
        reddit = asyncpraw.Reddit(...)
        subreddit = await reddit.subreddit(self.config["name"])
        posts = []
        async for post in subreddit.hot(limit=25):
            posts.append(self._to_raw(post))
        return posts

class YouTubeConnector(BaseConnector):
    name = "youtube"
    
    async def fetch(self) -> list[RawDocument]:
        # yt-dlp for transcripts
        import yt_dlp
        # ...
```

## Deduplication

```python
class Deduplicator:
    def __init__(self, metadata: SQLiteStore):
        self.metadata = metadata
    
    def is_duplicate(self, doc: NormalizedDocument) -> bool:
        """Check both exact and near-duplicate."""
        if self._exact_match(doc):
            return True
        if self._near_duplicate(doc):
            return True
        return False
    
    def _exact_match(self, doc: NormalizedDocument) -> bool:
        return self.metadata.has_hash(doc.id)
    
    def _near_duplicate(self, doc: NormalizedDocument, 
                        threshold: float = 0.85) -> bool:
        """MinHash-based near-duplicate detection."""
        hash = self._minhash(doc.body)
        return any(
            self._jaccard_similarity(hash, existing) > threshold
            for existing in self.metadata.get_recent_hashes(limit=1000)
        )
```

## Polling Strategy

| Source Type | Poll Interval | Rate Limit | Max Items | ETag Support |
|-------------|--------------|------------|-----------|--------------|
| RSS | 5-15 min | 60/min | 50 | Yes |
| Reddit | 10-15 min | 60/min | 25 | No |
| YouTube | 1-6 hours | 10/min | 10 | No |
| Gov RSS | 5-10 min | 60/min | 100 | Yes |
| News API | 10-15 min | Varies | 100 | No |

## Normalization Pipeline

```python
def normalize(raw: RawDocument) -> NormalizedDocument:
    text = raw.body
    
    # Strip HTML
    text = re.sub(r'<[^>]+>', ' ', text)
    
    # Decode HTML entities
    text = html.unescape(text)
    
    # Normalize unicode
    text = unicodedata.normalize('NFKC', text)
    
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Remove boilerplate
    text = remove_boilerplate(text)
    
    # Detect language
    lang = detect_language(text)
    
    return NormalizedDocument(
        id=sha256(text.encode()),
        source_type=raw.source_type,
        source_name=raw.source_name,
        title=normalize_title(raw.title),
        body=text,
        url=raw.url,
        published_at=raw.published_at or datetime.utcnow(),
        ingested_at=datetime.utcnow(),
        author=raw.author,
        language=lang,
        raw_metadata=raw.metadata,
    )
```

## State Management (SQLite)

```sql
CREATE TABLE ingestion_state (
    source_name TEXT PRIMARY KEY,
    last_polled_at REAL NOT NULL,
    etag TEXT,
    cursor TEXT,
    last_error TEXT,
    consecutive_failures INTEGER DEFAULT 0
);
```

Source polling resets cursor position after successful poll, enabling crash recovery.
