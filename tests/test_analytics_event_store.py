"""Analytics event store tests."""

import pytest
from pydantic import ValidationError

from assistant.analytics.event_store import AnalyticsEventStore
from assistant.analytics.events import AnalyticsEvent


def test_event_store_appends_events_as_jsonl(tmp_path):
    store = AnalyticsEventStore(tmp_path)
    first = store.record("source_uploaded", source_id="src-1", entity_type="source", entity_id="src-1")
    second = store.record("source_ingested", source_id="src-1", entity_type="source", entity_id="src-1")

    assert store.path.read_text(encoding="utf-8").count("\n") == 2
    assert [event.event_id for event in store.events()] == [first.event_id, second.event_id]
    assert [event.event_type for event in store.events()] == ["source_uploaded", "source_ingested"]


def test_event_store_accepts_prebuilt_event(tmp_path):
    store = AnalyticsEventStore(tmp_path)
    event = AnalyticsEvent(event_type="governance_issue_accepted", source_id="src-2", metadata={"check": "duplicate"})

    stored = store.append(event)

    assert stored.event_id == event.event_id
    assert store.events()[0].metadata["check"] == "duplicate"


def test_event_store_filters_by_type_and_source(tmp_path):
    store = AnalyticsEventStore(tmp_path)
    store.record("source_uploaded", source_id="src-1")
    store.record("source_uploaded", source_id="src-2")
    store.record("ask_answered", metadata={"citation_count": 2})

    assert [event.source_id for event in store.events(event_type="source_uploaded")] == ["src-1", "src-2"]
    assert [event.event_type for event in store.events(source_id="src-2")] == ["source_uploaded"]


def test_event_store_recent_returns_newest_first_with_guarded_limit(tmp_path):
    store = AnalyticsEventStore(tmp_path)
    first = store.record("source_uploaded", source_id="src-1")
    second = store.record("source_ingested", source_id="src-1")

    assert [event.event_id for event in store.recent(limit=1)] == [second.event_id]
    assert [event.event_id for event in store.recent(limit=0)] == [second.event_id]
    assert [event.event_id for event in store.recent(limit=5)] == [second.event_id, first.event_id]


def test_event_store_validates_before_append(tmp_path):
    store = AnalyticsEventStore(tmp_path)

    with pytest.raises(ValidationError):
        store.record("source_uploaded", metadata={"raw": ["not", "flat"]})

    assert not store.path.exists()
