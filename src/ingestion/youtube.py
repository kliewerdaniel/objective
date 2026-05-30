"""YouTube transcript connector."""

from datetime import datetime
from src.ingestion.connector import SourceConnector
from src.models.types import RawDocument


class YouTubeConnector(SourceConnector):
    name = "youtube"

    async def fetch(self) -> list[RawDocument]:
        import yt_dlp
        channel_url = f"https://www.youtube.com/@{self.config.get('name', '')}/videos"
        channel_id = self.config.get("channel_id", "")
        if channel_id:
            channel_url = f"https://www.youtube.com/channel/{channel_id}/videos"

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
        }

        docs = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
            entries = info.get("entries", [])[:self.config.get("limit", 10)]
            for entry in entries:
                docs.append(RawDocument(
                    source_type="youtube",
                    source_name=self.config.get("name", "unknown"),
                    url=f"https://youtube.com/watch?v={entry['id']}",
                    title=entry.get("title", ""),
                    body=entry.get("description", ""),
                    published_at=datetime.fromtimestamp(entry.get("timestamp", 0)) if entry.get("timestamp") else None,
                    author=entry.get("channel", self.config.get("name", "unknown")),
                    metadata={"video_id": entry["id"], "duration": entry.get("duration", 0)},
                ))
        return docs
