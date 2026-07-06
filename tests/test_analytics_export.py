"""Raw analytics export endpoint tests."""

from __future__ import annotations

import csv
from io import StringIO

from fastapi.testclient import TestClient

from assistant.analytics.log import UsageEntry
from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.sources.register import SourceRegister

PASSWORD = "export-test-pass"


def test_analytics_export_index_and_datasets_are_auth_protected_and_round_trip(tmp_path) -> None:
    register = SourceRegister(tmp_path)
    client = TestClient(create_app(register, AuthService(PASSWORD)))

    assert client.get("/api/analytics/export").status_code == 401
    assert client.get("/api/analytics/export/dictionary").status_code == 401
    assert client.get("/api/analytics/export/usage_log").status_code == 401

    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    _seed_export_data(client)

    index = client.get("/api/analytics/export", headers=headers)
    assert index.status_code == 200
    datasets = {item["dataset"]: item for item in index.json()["datasets"]}
    assert set(datasets) == {
        "usage_log",
        "events",
        "knowledge_gap_clusters",
        "value_events",
        "value_scenarios",
        "process_complexity",
        "ontology_stats",
        "governance_history",
    }
    assert datasets["usage_log"]["row_count"] == 2
    assert datasets["events"]["row_count"] >= 2

    dictionary_response = client.get("/api/analytics/export/dictionary", headers=headers)
    assert dictionary_response.status_code == 200
    dictionary = dictionary_response.json()
    dictionary_by_dataset = {
        dataset["dataset"]: {field["field"] for field in dataset["fields"]}
        for dataset in dictionary["datasets"]
    }
    assert set(dictionary_by_dataset) == set(datasets)

    for dataset in datasets:
        json_response = client.get(f"/api/analytics/export/{dataset}?format=json", headers=headers)
        csv_response = client.get(f"/api/analytics/export/{dataset}?format=csv", headers=headers)
        assert json_response.status_code == 200
        assert csv_response.status_code == 200
        assert csv_response.headers["content-type"].startswith("text/csv")
        assert f"opsatlas-{dataset}.csv" in csv_response.headers["content-disposition"]
        body = json_response.json()
        parsed_csv = list(csv.DictReader(StringIO(csv_response.text)))
        assert body["row_count"] == len(body["rows"])
        assert body["columns"] == list(parsed_csv[0].keys()) if parsed_csv else body["columns"] == []
        assert set(body["columns"]) <= dictionary_by_dataset[dataset]
        assert len(parsed_csv) == body["row_count"]

    usage_json = client.get("/api/analytics/export/usage_log", headers=headers).json()
    usage_csv = list(csv.DictReader(StringIO(client.get("/api/analytics/export/usage_log?format=csv", headers=headers).text)))
    assert usage_json["rows"][0]["question"] == usage_csv[0]["question"]
    assert usage_json["rows"][0]["mode"] == usage_csv[0]["mode"]
    events_json = client.get("/api/analytics/export/events", headers=headers).json()
    assert "metadata" in events_json["columns"]
    assert "metadata.check" not in events_json["columns"]

    dictionary_markdown = client.get("/api/analytics/export/dictionary?format=md", headers=headers)
    assert dictionary_markdown.status_code == 200
    assert dictionary_markdown.headers["content-type"].startswith("text/markdown")
    assert "opsatlas-analytics-data-dictionary.md" in dictionary_markdown.headers["content-disposition"]
    assert "# OpsAtlas Analytics Data Dictionary" in dictionary_markdown.text
    assert "usage_log" in dictionary_markdown.text

    for dataset in dictionary["datasets"]:
        assert dataset["undocumented_active_columns"] == []


def test_analytics_export_rejects_unknown_dataset(tmp_path) -> None:
    register = SourceRegister(tmp_path)
    client = TestClient(create_app(register, AuthService(PASSWORD)))
    token = client.post("/api/auth/login", json={"password": PASSWORD}).json()["token"]

    response = client.get("/api/analytics/export/not-a-dataset", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 404


def _seed_export_data(client: TestClient) -> None:
    client.app.state.answer.usage_log.append(
        UsageEntry(
            timestamp="2026-07-06T08:00:00+00:00",
            question="Who owns supplier ordering?",
            mode="ask",
            answer_path="oag",
            refused=False,
            confidence="grounded",
            citation_count=2,
        )
    )
    client.app.state.answer.usage_log.append(
        UsageEntry(
            timestamp="2026-07-06T08:05:00+00:00",
            question="What is missing for VAT evidence?",
            mode="ask",
            answer_path="rag",
            refused=True,
            confidence="none",
            citation_count=0,
        )
    )
    client.app.state.analytics_events.record(
        "governance_issue_detected",
        timestamp="2026-07-06T09:00:00+00:00",
        actor_type="system",
        entity_type="governance_issue",
        entity_id="issue-1",
        source_id="source-1",
        outcome="detected",
        metadata={"check": "undefined_acronym", "severity": "medium", "source_title": "Pack 1"},
    )
    client.app.state.analytics_events.record(
        "value_event_recorded",
        timestamp="2026-07-06T10:00:00+00:00",
        actor_type="operator",
        entity_type="value_event",
        entity_id="value-1",
        process_area="supplier setup",
        outcome="recorded",
        value_driver="time_saved",
        value_estimate=250.0,
        metadata={"label": "Manual review avoided", "scenario_id": "base", "unit": "GBP", "confidence": "review"},
    )
