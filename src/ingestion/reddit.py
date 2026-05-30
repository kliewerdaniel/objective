"""Reddit connector using OAuth2 authentication."""

import aiohttp
from datetime import datetime
from src.ingestion.connector import SourceConnector
from src.models.types import RawDocument


class RedditConnector(SourceConnector):
    name = "reddit"

    async def fetch(self) -> list[RawDocument]:
        subreddit = self.config.get("subreddit", self.config.get("name", "worldnews"))
        sort = self.config.get("sort", "hot")
        limit = self.config.get("limit", 25)
        client_id = self.config.get("client_id", "")
        client_secret = self.config.get("client_secret", "")
        user_agent = self.config.get("user_agent") or "objective03/1.0"

        token = await self._get_token(client_id, client_secret, user_agent)
        headers = {"Authorization": f"Bearer {token}", "User-Agent": user_agent}

        async with aiohttp.ClientSession(headers=headers) as session:
            url = f"https://oauth.reddit.com/r/{subreddit}/{sort}?limit={limit}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    raise Exception(f"Reddit API returned {resp.status} for r/{subreddit}")
                data = await resp.json()

        posts = []
        for child in data.get("data", {}).get("children", []):
            post = child.get("data", {})
            created = post.get("created_utc")
            posts.append(RawDocument(
                source_type="reddit",
                source_name=f"r/{subreddit}",
                url=f"https://reddit.com{post.get('permalink', '')}",
                title=post.get("title", ""),
                body=post.get("selftext", "") or post.get("title", ""),
                published_at=datetime.fromtimestamp(created) if created else None,
                author=str(post.get("author", "unknown")),
                metadata={"score": post.get("score", 0), "num_comments": post.get("num_comments", 0)},
            ))
        return posts

    async def _get_token(self, client_id: str, client_secret: str, user_agent: str) -> str:
        auth = aiohttp.BasicAuth(client_id, client_secret)
        data = {"grant_type": "client_credentials", "scope": "read"}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://www.reddit.com/api/v1/access_token",
                auth=auth, data=data,
                headers={"User-Agent": user_agent},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    raise Exception(f"Reddit auth returned {resp.status}")
                body = await resp.json()
                return body["access_token"]
