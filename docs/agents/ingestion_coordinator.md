# Ingestion Coordinator Agent

## Overview

The ingestion coordinator manages all source polling. It maintains polling state, respects rate limits, and produces normalized documents for downstream agents.

## Responsibilities

- Poll all configured sources on schedule
- Respect per-source rate limits
- Normalize documents to common format
- Track polling state (cursors, ETags, timestamps)
- Route documents to dedup and extraction pipeline

## Interface

```python
class IngestionCoordinator(BaseAgent):
    name = "ingestion_coordinator"
    timeout_seconds = 120.0
    
    async def run(self, context: AgentContext) -> AgentResult:
        """Poll all due sources and return new documents."""
        pollers = self._build_pollers(context.config["sources"])
        
        all_documents = []
        stats = {"sources_polled": 0, "documents_found": 0, "errors": 0}
        
        for poller in pollers:
            if not poller.is_due(context.state):
                continue
            try:
                docs = await poller.poll()
                normalized = [self._normalize(d) for d in docs]
                unique = self._deduplicate(normalized, context)
                all_documents.extend(unique)
                stats["sources_polled"] += 1
                stats["documents_found"] += len(unique)
            except Exception as e:
                stats["errors"] += 1
                context.logger.warning("source.poll.failed", 
                    source=poller.name, error=str(e))
        
        return AgentResult(
            success=True,
            data=all_documents,
            metrics=stats,
        )
    
    def validate(self, result: AgentResult) -> bool:
        return result.success and len(result.data) >= 0  # No documents is valid
```

## Poller Design

```python
class Poller(ABC):
    """Abstract base for source-specific pollers."""
    
    def __init__(self, config: SourceConfig, state: PollState):
        self.config = config
        self.state = state
        self.rate_limiter = RateLimiter(
            max_calls=config.get("rate_limit", 60),
            window_seconds=60,
        )
    
    @abstractmethod
    async def fetch(self) -> list[RawDocument]:
        """Fetch raw documents from the source."""
        ...
    
    async def poll(self) -> list[RawDocument]:
        """Poll source and return documents since last poll."""
        await self.rate_limiter.acquire()
        
        docs = await self.fetch()
        self.state.update_cursor(self.config.name, datetime.utcnow())
        
        return docs
    
    def is_due(self, state: Mapping) -> bool:
        last_poll = state.get_last_poll(self.config.name)
        if last_poll is None:
            return True
        elapsed = (datetime.utcnow() - last_poll).total_seconds()
        return elapsed >= self.config.interval
```

## RSS Poller

```python
class RSSPoller(Poller):
    async def fetch(self) -> list[RawDocument]:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                self.config.url,
                headers={"If-Modified-Since": self.state.get_etag(self.config.name)},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 304:  # Not Modified
                    return []
                
                text = await response.text()
                feed = feedparser.parse(text)
                
                documents = []
                for entry in feed.entries:
                    doc = RawDocument(
                        source_type="rss",
                        source_name=self.config.name,
                        url=entry.link,
                        title=entry.get("title", ""),
                        body=entry.get("description", "") or entry.get("summary", ""),
                        published_at=self._parse_date(entry.get("published_parsed")),
                        author=entry.get("author"),
                        metadata={"feed_title": feed.feed.get("title", "")},
                    )
                    documents.append(doc)
                
                # Store ETag for conditional requests
                etag = response.headers.get("ETag", "")
                if etag:
                    self.state.set_etag(self.config.name, etag)
                
                return documents
```

## Reddit Poller

```python
class RedditPoller(Poller):
    async def fetch(self) -> list[RawDocument]:
        import asyncpraw
        
        reddit = asyncpraw.Reddit(
            client_id=self.config.client_id,
            client_secret=self.config.client_secret,
            user_agent="objective03/1.0",
        )
        
        subreddit = await reddit.subreddit(self.config.name)
        posts = []
        
        async for post in subreddit.hot(limit=self.config.get("limit", 25)):
            posts.append(RawDocument(
                source_type="reddit",
                source_name=f"r/{self.config.name}",
                url=f"https://reddit.com{post.permalink}",
                title=post.title,
                body=post.selftext or post.title,
                published_at=datetime.fromtimestamp(post.created_utc),
                author=str(post.author),
                metadata={
                    "score": post.score,
                    "num_comments": post.num_comments,
                    "subreddit": self.config.name,
                },
            ))
        
        await reddit.close()
        return posts
```

## YouTube Poller

```python
class YouTubePoller(Poller):
    async def fetch(self) -> list[RawDocument]:
        import yt_dlp
        
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["en"],
            "skip_download": True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/@{self.config.name}/videos",
                download=False,
            )
            
            documents = []
            for entry in info.get("entries", [])[:self.config.get("limit", 10)]:
                # Get transcript if available
                transcript = await self._get_transcript(entry["id"])
                
                documents.append(RawDocument(
                    source_type="youtube",
                    source_name=self.config.name,
                    url=f"https://youtube.com/watch?v={entry['id']}",
                    title=entry.get("title", ""),
                    body=transcript or entry.get("description", ""),
                    published_at=datetime.fromtimestamp(entry.get("timestamp", 0)),
                    author=entry.get("channel", self.config.name),
                    metadata={
                        "video_id": entry["id"],
                        "duration": entry.get("duration", 0),
                        "channel": self.config.name,
                    },
                ))
            
            return documents
```

## Supported Sources

| Source Type | Connector | Config Notes |
|-------------|-----------|-------------|
| RSS | RSSPoller | Supports ETag/If-Modified-Since for bandwidth saving |
| Reddit | RedditPoller | Requires Reddit API credentials |
| YouTube | YouTubePoller | Requires yt-dlp, transcript extraction |
| Gov RSS | RSSPoller (subclass) | Same as RSS, separate config for trust scoring |
| News API | NewsAPIPoller | Requires API key (optional, NewsAPI.org) |
| Podcast | PodcastPoller | Supports RSS feeds with enclosures |

## Configuration Schema

```yaml
sources:
  rss:
    - name: "BBC World"
      url: "https://feeds.bbci.co.uk/news/world/rss.xml"
      interval: 600
      timeout: 30
      respect_etag: true
      max_entries: 50
  
  reddit:
    - name: "worldnews"
      sort: "hot"
      limit: 25
      interval: 900
      client_id: "${REDDIT_CLIENT_ID}"
      client_secret: "${REDDIT_CLIENT_SECRET}"
  
  youtube:
    - name: "BBCNews"
      channel_id: "UC16niRr50-MSBwiO3YDb3RA"
      interval: 3600
      limit: 10
```
