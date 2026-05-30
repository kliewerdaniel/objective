"""End-to-end integration test for the pipeline."""

import pytest
from pathlib import Path
from src.config import Config
from src.database.graph import GraphStore
from src.database.vector import VectorStore
from src.database.metadata import MetadataStore
from src.models.types import Claim, NormalizedDocument, generate_uuid
from datetime import datetime


@pytest.fixture
def config():
    return Config()


@pytest.fixture
def components(tmp_path):
    db_path = str(tmp_path / "test_graph.db")
    md_path = str(tmp_path / "test_metadata.db")

    graph = GraphStore(db_path)
    metadata = MetadataStore(md_path)
    yield {"graph": graph, "metadata": metadata}
    graph.close()
    metadata.conn.close()


@pytest.mark.asyncio
async def test_document_to_claim_pipeline(components):
    graph = components["graph"]
    metadata = components["metadata"]

    # Simulate ingestion
    doc_id = generate_uuid()
    graph.create_node("Source", {
        "id": "test_source", "name": "Test Source", "type": "rss",
        "base_url": "https://example.com", "trust_score": 0.5,
        "metadata": "{}", "created_at": datetime.utcnow().isoformat(),
    })
    graph.create_node("Document", {
        "id": doc_id, "title": "Test Article", "url": "https://example.com/test",
        "published_at": datetime.utcnow().isoformat(),
        "ingested_at": datetime.utcnow().isoformat(),
        "language": "en", "source_type": "rss",
    })
    graph.create_edge("FROM_SOURCE", doc_id, "test_source")

    # Simulate claim extraction
    claim_id = generate_uuid()
    graph.create_node("Claim", {
        "id": claim_id, "text": "Test claim from article", "confidence": 0.85,
        "stance": "neutral", "timestamp": datetime.utcnow().isoformat(),
        "topic": "politics", "evidence": "from test article", "embedding_id": "",
    })
    graph.create_edge("EXTRACTED_FROM", claim_id, doc_id,
                      {"extraction_confidence": 0.85, "extracted_at": datetime.utcnow().isoformat()})

    # Simulate event clustering
    event_id = generate_uuid()
    graph.create_node("Event", {
        "id": event_id, "title": "Test Event", "description": "",
        "start_time": datetime.utcnow().isoformat(), "end_time": "",
        "status": "active", "importance": 0.7, "embedding_id": "",
    })
    graph.create_edge("ABOUT_EVENT", claim_id, event_id,
                      {"confidence": 0.8,
                       "first_seen": datetime.utcnow().isoformat()})

    # Simulate contradiction detection
    claim2_id = generate_uuid()
    graph.create_node("Claim", {
        "id": claim2_id, "text": "Contradictory claim", "confidence": 0.7,
        "stance": "opposing", "timestamp": datetime.utcnow().isoformat(),
        "topic": "politics", "evidence": "from another source", "embedding_id": "",
    })
    graph.create_edge("CONTRADICTS", claim_id, claim2_id, {
        "contradiction_type": "direct", "strength": 0.9, "confidence": 0.8,
        "detected_at": datetime.utcnow().isoformat(), "resolution_status": "unresolved",
    })

    # Simulate narrative creation
    narrative_id = generate_uuid()
    graph.create_node("Narrative", {
        "id": narrative_id, "label": "Test Narrative", "description": "",
        "drift_score": 0.1, "framing": "neutral", "active": True,
        "first_seen": datetime.utcnow().isoformat(),
        "last_updated": datetime.utcnow().isoformat(),
        "embedding_id": "",
    })
    graph.create_edge("PART_OF_THREAD", claim_id, narrative_id,
                      {"confidence": 0.8})

    # Verify the graph state
    assert graph.count_nodes("Document") == 1
    assert graph.count_nodes("Claim") == 2
    assert graph.count_nodes("Event") == 1
    assert graph.count_nodes("Narrative") == 1
    assert graph.count_edges("CONTRADICTS") == 1
    assert graph.count_edges("PART_OF_THREAD") == 1
    assert graph.count_edges("EXTRACTED_FROM") == 1
    assert graph.count_edges("ABOUT_EVENT") == 1

    # Query back
    events = graph.get_top_events(limit=5)
    assert len(events) >= 1
    contras = graph.get_claim_contradictions(claim_id)
    assert len(contras) == 1
    narratives = graph.get_active_narratives(limit=5)
    assert len(narratives) >= 1


@pytest.mark.asyncio
async def test_orphan_claim_cleanup(components):
    graph = components["graph"]
    graph.create_node("Claim", {
        "id": "orphan_claim", "text": "Old orphan", "confidence": 0.15,
        "stance": "neutral", "timestamp": "2024-01-01T00:00:00",
        "topic": "other", "evidence": "", "embedding_id": "",
    })
    graph.create_node("Claim", {
        "id": "keep_claim", "text": "Recent good claim", "confidence": 0.8,
        "stance": "neutral", "timestamp": datetime.utcnow().isoformat(),
        "topic": "politics", "evidence": "source data", "embedding_id": "",
    })
    orphans = graph.find_orphan_claims(older_than_days=365, max_confidence=0.2)
    assert len(orphans) >= 1
    assert orphans[0].get("c.id") == "orphan_claim"


@pytest.mark.asyncio
async def test_source_lifecycle(components):
    graph = components["graph"]
    graph.create_node("Source", {
        "id": "src_lifecycle", "name": "Lifecycle Source", "type": "rss",
        "base_url": "https://lifecycle.example.com", "trust_score": 0.6,
        "metadata": '{"language": "en"}', "created_at": datetime.utcnow().isoformat(),
    })
    sources = graph.get_all_sources()
    assert any(s.get("s.id") == "src_lifecycle" for s in sources)
    graph.update_node("Source", "src_lifecycle", {"trust_score": 0.75})
    updated = graph.get_node("Source", "src_lifecycle")
    assert updated.get("n.trust_score") == 0.75
