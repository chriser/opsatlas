"""Public external-source connector and snapshot tests."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.api.routes_external import build_external_sources_router
from assistant.external.govuk import GOVUKContentClient, GOVUKContentError, GOVUKRateLimitError, govuk_content_path
from assistant.external.models import FetchedPublicContent
from assistant.external.registry import PublicContentRegistry
from assistant.sources.register import SourceRegister

GOVUK_FIXTURE = {
    "content_id": "abc-123",
    "base_path": "/guidance/example-regulatory-topic",
    "title": "Example regulatory topic",
    "description": "Fallback description.",
    "document_type": "guidance",
    "locale": "en",
    "public_updated_at": "2026-06-18T09:30:00Z",
    "schema_name": "detailed_guide",
    "publishing_app": "publisher",
    "links": {"organisations": [{"title": "Department for Example"}]},
    "details": {
        "body": "<h2>Overview</h2><p>Businesses must keep records.</p><ul><li>Check eligibility.</li></ul>",
        "parts": [{"title": "Exceptions", "body": "<p>Manual review may be required.</p>"}],
    },
}


def fetched_content() -> FetchedPublicContent:
    return FetchedPublicContent(
        url="https://www.gov.uk/guidance/example-regulatory-topic",
        title="Example regulatory topic",
        public_body="Department for Example",
        content_id="abc-123",
        document_type="guidance",
        locale="en",
        update_date="2026-06-18T09:30:00Z",
        retrieved_at="2026-06-22T10:00:00Z",
        text="Businesses must keep records.",
        metadata={"schema_name": "detailed_guide"},
    )


def test_govuk_path_validation_accepts_public_content_paths_only():
    assert govuk_content_path("https://www.gov.uk/guidance/example-regulatory-topic") == "/guidance/example-regulatory-topic"
    assert govuk_content_path("https://www.gov.uk/api/content/guidance/example-regulatory-topic") == "/guidance/example-regulatory-topic"
    assert govuk_content_path("/guidance/example-regulatory-topic") == "/guidance/example-regulatory-topic"

    try:
        govuk_content_path("https://example.com/not-govuk")
    except GOVUKContentError as exc:
        assert "GOV.UK" in str(exc)
    else:
        raise AssertionError("non-GOV.UK URL should be rejected")


def test_govuk_client_parses_fixture_without_live_network():
    requested_urls: list[str] = []

    def fetch_json(api_url: str) -> dict:
        requested_urls.append(api_url)
        return GOVUK_FIXTURE

    content = GOVUKContentClient(fetch_json=fetch_json).fetch("https://www.gov.uk/guidance/example-regulatory-topic")

    assert requested_urls == ["https://www.gov.uk/api/content/guidance/example-regulatory-topic"]
    assert content.title == "Example regulatory topic"
    assert content.public_body == "Department for Example"
    assert content.update_date == "2026-06-18T09:30:00Z"
    assert "Businesses must keep records." in content.text
    assert "Manual review may be required." in content.text
    assert content.metadata["schema_name"] == "detailed_guide"


def test_public_content_registry_versions_snapshots_and_updates_source(tmp_path):
    registry = PublicContentRegistry(tmp_path)
    source = registry.upsert_source(
        provider="govuk",
        url="https://www.gov.uk/guidance/example-regulatory-topic",
        topics=["compliance", "records"],
    )

    first = registry.add_snapshot(source.id, fetched_content())
    second = registry.add_snapshot(source.id, fetched_content())
    updated = registry.get_source(source.id)

    assert first.version == 1
    assert second.version == 2
    assert updated is not None
    assert updated.snapshot_count == 2
    assert updated.latest_snapshot_id == second.id
    assert updated.licence == "Open Government Licence v3.0"
    assert updated.topics == ["compliance", "records"]
    assert registry.list_snapshots(include_text=False)[0]["id"] == second.id
    assert "text" not in registry.list_snapshots(include_text=False)[0]


def test_external_source_api_snapshots_with_injected_client(tmp_path):
    class FakeClient:
        def fetch(self, url: str) -> FetchedPublicContent:
            assert url == "https://www.gov.uk/guidance/example-regulatory-topic"
            return fetched_content()

    app = FastAPI()
    registry = PublicContentRegistry(tmp_path)
    app.include_router(build_external_sources_router(registry, govuk_client=FakeClient()))
    client = TestClient(app)

    response = client.post(
        "/api/external-sources/govuk/snapshot",
        json={"url": "https://www.gov.uk/guidance/example-regulatory-topic", "topics": ["records"]},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source"]["snapshot_count"] == 1
    assert body["source"]["topics"] == ["records"]
    assert body["snapshot"]["version"] == 1
    assert client.get("/api/external-sources").json()[0]["title"] == "Example regulatory topic"
    assert "text" not in client.get("/api/external-sources/snapshots").json()[0]


def test_external_source_api_handles_rate_limit_without_snapshot(tmp_path):
    class RateLimitedClient:
        def fetch(self, url: str) -> FetchedPublicContent:
            raise GOVUKRateLimitError("GOV.UK rate limit reached; try again later.")

    app = FastAPI()
    registry = PublicContentRegistry(tmp_path)
    app.include_router(build_external_sources_router(registry, govuk_client=RateLimitedClient()))
    client = TestClient(app)

    response = client.post("/api/external-sources/govuk/snapshot", json={"url": "https://www.gov.uk/guidance/example"})

    assert response.status_code == 503
    assert registry.list_snapshots() == []
    assert registry.list_sources()[0].last_error == "GOV.UK rate limit reached; try again later."


def test_external_source_api_rejects_non_govuk_without_registering_source(tmp_path):
    app = FastAPI()
    registry = PublicContentRegistry(tmp_path)
    app.include_router(build_external_sources_router(registry, govuk_client=GOVUKContentClient(fetch_json=lambda _: GOVUK_FIXTURE)))
    client = TestClient(app)

    response = client.post("/api/external-sources/govuk/snapshot", json={"url": "https://example.com/not-govuk"})

    assert response.status_code == 400
    assert registry.list_sources() == []


def test_external_sources_are_protected_in_main_app(tmp_path):
    client = TestClient(create_app(SourceRegister(tmp_path), AuthService("pw")))
    assert client.get("/api/external-sources").status_code == 401

    token = client.post("/api/auth/login", json={"password": "pw"}).json()["token"]
    assert client.get("/api/external-sources", headers={"Authorization": f"Bearer {token}"}).status_code == 200
