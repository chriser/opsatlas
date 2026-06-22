"""Analytics event schema tests."""

import pytest
from pydantic import ValidationError

from assistant.analytics.events import EVENT_GROUPS, EVENT_TYPES, AnalyticsEvent


def test_event_taxonomy_groups_known_event_types():
    grouped = {event_type for group in EVENT_GROUPS.values() for event_type in group}
    assert set(EVENT_TYPES) == grouped
    assert "source_uploaded" in EVENT_GROUPS["source_lifecycle"]
    assert "ask_refused" in EVENT_GROUPS["assistant_usage"]
    assert "value_event_recorded" in EVENT_GROUPS["value"]


def test_analytics_event_defaults_and_safe_metadata():
    event = AnalyticsEvent(
        event_type="source_uploaded",
        actor_type="operator",
        entity_type="source",
        entity_id="src-1",
        source_id="src-1",
        metadata={"title": "Supplier setup", "sections": 4, "approved": False},
    )

    assert event.event_id
    assert event.timestamp
    assert event.metadata["sections"] == 4


def test_analytics_event_rejects_unknown_type_nested_metadata_and_negative_value():
    with pytest.raises(ValidationError):
        AnalyticsEvent(event_type="unknown")

    with pytest.raises(ValidationError):
        AnalyticsEvent(event_type="source_uploaded", metadata={"raw": {"nested": "not allowed"}})

    with pytest.raises(ValidationError):
        AnalyticsEvent(event_type="value_event_recorded", value_estimate=-1)
