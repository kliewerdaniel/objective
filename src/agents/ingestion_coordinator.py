"""Ingestion coordinator — manages all source polling."""

import asyncio
from datetime import datetime
from src.agents.base import BaseAgent, AgentContext, AgentResult
from src.ingestion.rss import RSSConnector
from src.ingestion.reddit import RedditConnector
from src.ingestion.youtube import YouTubeConnector
from src.ingestion.normalize import normalize, Deduplicator


class IngestionCoordinator(BaseAgent):
    name = "ingestion_coordinator"
    timeout_seconds = 120.0

    async def run(self, context: AgentContext) -> AgentResult:
        sources_cfg = context.config.get("sources", {})
        pollers = self._build_pollers(sources_cfg)
        dedup = Deduplicator(context.metadata)
        graph = context.graph

        all_docs = []
        stats = {"sources_polled": 0, "documents_found": 0, "errors": 0}
        seen_sources = set()

        async def _poll_one(poller):
            docs = await poller.poll()
            # Create Source node if not seen
            source_name = poller.config.get("name", poller.name)
            if source_name not in seen_sources:
                try:
                    graph.create_node("Source", {
                        "id": source_name,
                        "name": source_name,
                        "type": poller.config.get("type", poller.name),
                        "base_url": poller.config.get("url", ""),
                        "trust_score": 0.6 if poller.name == "rss" else 0.3,
                        "metadata": "{}",
                        "created_at": datetime.utcnow().isoformat(),
                    })
                except Exception:
                    pass
                seen_sources.add(source_name)

            new_docs = []
            for doc in docs:
                normalized = normalize(doc)
                if not dedup.is_duplicate(normalized):
                    context.metadata.store_hash(normalized.id, normalized.id, normalized.source_name)
                    try:
                        graph.create_node("Document", {
                            "id": normalized.id,
                            "title": normalized.title[:500],
                            "url": normalized.url[:500],
                            "published_at": str(normalized.published_at) if normalized.published_at else "",
                            "ingested_at": datetime.utcnow().isoformat(),
                            "language": normalized.language or "en",
                            "source_type": normalized.source_type or "rss",
                        })
                    except Exception:
                        pass
                    new_docs.append(normalized)
                    stats["documents_found"] += 1
            stats["sources_polled"] += 1
            return new_docs

        results = await asyncio.wait_for(
            asyncio.gather(
                *[_poll_one(p) for p in pollers],
                return_exceptions=True,
            ),
            timeout=self.timeout_seconds,
        )
        for r in results:
            if isinstance(r, Exception):
                stats["errors"] += 1
                if context.logger:
                    context.logger.error("source.poll.failed", error=str(r))
            else:
                all_docs.extend(r)

        existing = context.state.get("documents", [])
        context.state["documents"] = existing + all_docs

        return AgentResult(success=True, data=all_docs, metrics=stats)

    def _build_pollers(self, cfg: dict) -> list:
        pollers = []
        for item in cfg.get("rss", []):
            pollers.append(RSSConnector(dict(item)))
        for item in cfg.get("reddit", []):
            pollers.append(RedditConnector(dict(item)))
        for item in cfg.get("youtube", []):
            pollers.append(YouTubeConnector(dict(item)))
        return pollers

    def validate(self, result: AgentResult) -> bool:
        return result.success
