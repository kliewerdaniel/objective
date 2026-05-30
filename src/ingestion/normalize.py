"""Document normalization and deduplication."""

import re
import html
import unicodedata
import hashlib
from datetime import datetime
from src.models.types import RawDocument, NormalizedDocument


def normalize(raw: RawDocument) -> NormalizedDocument:
    text = raw.body or ""

    text = re.sub(r'<[^>]+>', ' ', text)
    text = html.unescape(text)
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'\s+', ' ', text).strip()

    if len(text) > 100000:
        text = text[:100000]

    content_hash = hashlib.sha256(text.encode()).hexdigest()

    return NormalizedDocument(
        id=content_hash,
        source_type=raw.source_type,
        source_name=raw.source_name,
        title=(raw.title or "").strip(),
        body=text,
        url=raw.url,
        published_at=raw.published_at or datetime.utcnow(),
        ingested_at=datetime.utcnow(),
        author=raw.author,
        language="en",
        raw_metadata=raw.metadata,
    )


class Deduplicator:
    def __init__(self, metadata_store):
        self.metadata = metadata_store

    def is_duplicate(self, doc: NormalizedDocument) -> bool:
        return self.metadata.has_hash(doc.id)
