"""Tests for KuzuDB graph store."""

import pytest
import tempfile
from pathlib import Path
from src.database.graph import GraphStore


@pytest.fixture
def graph():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    g = GraphStore(db_path)
    yield g
    g.close()
    Path(db_path).unlink(missing_ok=True)


def test_create_source(graph):
    graph.create_node("Source", {
        "id": "src1", "name": "Test Source", "type": "rss",
        "base_url": "https://example.com", "trust_score": 0.5,
        "metadata": "{}", "created_at": "2026-05-28T00:00:00",
    })
    assert graph.node_exists("Source", "src1")


def test_create_claim(graph):
    graph.create_node("Source", {
        "id": "src1", "name": "Test", "type": "rss",
        "base_url": "", "trust_score": 0.5,
        "metadata": "{}", "created_at": "2026-05-28T00:00:00",
    })
    graph.create_node("Document", {
        "id": "doc1", "title": "Test Doc", "url": "https://example.com",
        "published_at": "2026-05-28T00:00:00",
        "ingested_at": "2026-05-28T00:00:00",
        "language": "en", "source_type": "rss",
    })
    graph.create_node("Claim", {
        "id": "claim1", "text": "Test claim", "confidence": 0.8,
        "stance": "neutral", "timestamp": "2026-05-28T00:00:00",
        "topic": "politics", "evidence": "source says X", "embedding_id": "",
    })
    graph.create_edge("EXTRACTED_FROM", "claim1", "doc1",
                      {"extraction_confidence": 0.8, "extracted_at": "2026-05-28T00:00:00"})
    assert graph.node_exists("Claim", "claim1")


def test_event_clustering(graph):
    graph.create_node("Event", {
        "id": "ev1", "title": "Test Event", "description": "",
        "start_time": "2026-05-28T00:00:00",
        "end_time": "2026-05-28T00:00:00",
        "status": "active", "importance": 0.8, "embedding_id": "",
    })
    events = graph.get_top_events(limit=5)
    assert len(events) == 1


def test_count_nodes(graph):
    assert graph.count_nodes("Source") == 0
    assert graph.count_nodes("Claim") == 0
    assert graph.count_nodes("Event") == 0


def test_claim_contradictions(graph):
    graph.create_node("Claim", {
        "id": "c1", "text": "Claim A", "confidence": 0.8,
        "stance": "neutral", "timestamp": "2026-05-28T00:00:00",
        "topic": "politics", "evidence": "X", "embedding_id": "",
    })
    graph.create_node("Claim", {
        "id": "c2", "text": "Claim B", "confidence": 0.8,
        "stance": "neutral", "timestamp": "2026-05-28T00:00:00",
        "topic": "politics", "evidence": "Y", "embedding_id": "",
    })
    graph.create_edge("CONTRADICTS", "c1", "c2", {
        "contradiction_type": "direct", "strength": 0.9, "confidence": 0.8,
        "detected_at": "2026-05-28T00:00:00", "resolution_status": "unresolved",
    })
    contras = graph.get_claim_contradictions("c1")
    assert len(contras) == 1
    assert graph.count_edges("CONTRADICTS") == 1


def test_orphan_claims(graph):
    graph.create_node("Claim", {
        "id": "orphan1", "text": "Old orphan claim", "confidence": 0.2,
        "stance": "neutral", "timestamp": "2026-05-01T00:00:00",
        "topic": "other", "evidence": "", "embedding_id": "",
    })
    orphans = graph.find_orphan_claims(older_than_days=1, max_confidence=0.3)
    assert len(orphans) >= 1


def test_narrative_operations(graph):
    graph.create_node("Narrative", {
        "id": "n1", "label": "Test Narrative", "description": "",
        "drift_score": 0.0, "framing": "neutral", "active": True,
        "first_seen": "2026-05-28T00:00:00",
        "last_updated": "2026-05-28T00:00:00",
        "embedding_id": "",
    })
    assert graph.node_exists("Narrative", "n1")
    narratives = graph.get_active_narratives(limit=5)
    assert len(narratives) >= 1
