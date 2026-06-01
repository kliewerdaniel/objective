"""RSS feed connector."""

import asyncio
import feedparser
from datetime import datetime
from src.ingestion.connector import SourceConnector
from src.models.types import RawDocument


class RSSConnector(SourceConnector):
    name = "rss"

    async def fetch(self) -> list[RawDocument]:
        import aiohttp
        async with aiohttp.ClientSession() as session:
            headers = {}
            etag = self.config.get("_etag", "")
            if etag:
                headers["If-None-Match"] = etag
            async with session.get(
                self.config["url"], headers=headers, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 304:
                    return []
                text = await resp.text()
                etag_new = resp.headers.get("ETag", "")
                if etag_new:
                    self.config["_etag"] = etag_new

                feed = await asyncio.to_thread(feedparser.parse, text)
                docs = []
                for entry in feed.entries[:self.config.get("limit", 50)]:
                    pub = entry.get("published_parsed")
                    docs.append(RawDocument(
                        source_type="rss",
                        source_name=self.config.get("name", feed.feed.get("title", "unknown")),
                        url=entry.get("link", ""),
                        title=entry.get("title", ""),
                        body=entry.get("description", "") or entry.get("summary", ""),
                        published_at=datetime(*pub[:6]) if pub else None,
                        author=entry.get("author"),
                        metadata={"feed_title": feed.feed.get("title", "")},
                    ))
                return docs
