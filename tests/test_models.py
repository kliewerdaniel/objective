"""Tests for core functionality."""

import pytest
from src.models.types import Claim, Entity, Event, Narrative, Script, ScriptSegment, generate_uuid


def test_generate_uuid():
    ids = {generate_uuid() for _ in range(100)}
    assert len(ids) == 100


def test_claim_defaults():
    c = Claim(text="Test claim")
    assert c.text == "Test claim"
    assert c.confidence == 0.5
    assert c.stance == "neutral"
    assert c.topic == "other"
    assert c.id is not None


def test_entity_defaults():
    e = Entity(name="Test Entity", type="organization")
    assert e.name == "Test Entity"
    assert e.type == "organization"


def test_event_importance():
    e = Event(importance=0.8)
    assert e.importance == 0.8
    assert e.status == "emerging"


def test_narrative_active():
    n = Narrative(label="Test", active=True)
    assert n.active == True
    assert n.drift_score == 0.0


def test_script_segments():
    s = Script(segments=[
        ScriptSegment("intro", "Hello."),
        ScriptSegment("state", "System status."),
        ScriptSegment("outro", "Goodbye."),
    ])
    assert len(s.segments) == 3
    assert "Hello." in s.full_text
    assert s.estimated_duration() > 0


def test_claim_to_dict():
    c = Claim(text="Test", confidence=0.9)
    d = c.to_dict()
    assert d["text"] == "Test"
    assert d["confidence"] == 0.9


def test_event_to_dict():
    e = Event(title="Test Event", importance=0.7)
    d = e.to_dict()
    assert d["title"] == "Test Event"
    assert d["importance"] == 0.7
