"""Main application bridge tests for the compliance reasoning service."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from assistant.api.routes_compliance import build_compliance_reasoning_router
from assistant.compliance.payload import build_compliance_review_payload
from assistant.external.models import FetchedPublicContent
from assistant.external.registry import PublicContentRegistry
from assistant.ingestion.service import ingest_source
from assistant.ingestion.store import SectionStore
from assistant.sources.register import SourceRegister
from assistant.sources.service import register_upload


class FakeComplianceClient:
    enabled = True
    base_url = "http://compliance.test"

    def __init__(self) -> None:
        self.payload = None

    def health(self) -> dict:
        return {"status": "ok", "service": "compliance-reasoning"}

    def capabilities(self) -> dict:
        return {"service": "compliance-reasoning", "modes": ["deterministic-baseline"]}

    def create_review(self, payload: dict) -> dict:
        self.payload = payload
        return {
            "status": {
                "job_id": "cr-test",
                "status": "completed",
                "created_at": "2026-06-27T10:00:00Z",
                "completed_at": "2026-06-27T10:00:01Z",
                "obligation_count": 1,
                "internal_claim_count": 1,
                "finding_count": 1,
                "audit": {
                    "engine": "deterministic-baseline",
                    "engine_version": "0.1.0",
                    "model_profile": "no-ml",
                    "external_document_count": 1,
                    "internal_document_count": 1,
                    "source_hashes": {},
                    "assumptions": [],
                },
            },
            "obligations": [],
            "internal_claims": [],
            "findings": [],
        }


class DisabledComplianceClient(FakeComplianceClient):
    enabled = False


def _stores(tmp_path):
    register = SourceRegister(tmp_path)
    sections = SectionStore(register.base_dir)
    public = PublicContentRegistry(register.base_dir)

    approved = register_upload(
        register,
        "approved.md",
        b"# Controls\n\nFinance teams must keep VAT invoice records.",
        title="Approved controls",
    )
    ingest_source(register, sections, approved.id)
    register.update(approved.id, approval_status="approved")

    pending = register_upload(
        register,
        "pending.md",
        b"# Draft\n\nDraft teams must do something.",
        title="Pending controls",
    )
    ingest_source(register, sections, pending.id)

    public_source = public.upsert_source(provider="legislation", url="https://www.legislation.gov.uk/example")
    public.add_snapshot(
        public_source.id,
        FetchedPublicContent(
            provider="legislation",
            url="https://www.legislation.gov.uk/example/data.xml",
            title="Example regulation",
            public_body="The National Archives",
            document_type="legislation",
            retrieved_at="2026-06-27T10:00:00Z",
            text="# VAT controls\n\nFinance teams must keep VAT invoice records.",
            metadata={"source_format": "xml"},
        ),
    )
    return register, sections, public


def test_payload_builder_uses_approved_internal_sources_and_external_snapshots(tmp_path) -> None:
    register, sections, public = _stores(tmp_path)

    payload = build_compliance_review_payload(register, sections, public)

    assert len(payload["external_documents"]) == 1
    assert len(payload["internal_documents"]) == 1
    assert payload["internal_documents"][0]["title"] == "Approved controls"
    assert payload["external_documents"][0]["source_type"] == "external"
    assert payload["external_documents"][0]["sections"][0]["citation"].startswith("Example regulation")
    assert payload["metadata"]["source"] == "knowledge-platform"


def test_compliance_reasoning_bridge_calls_configured_service(tmp_path) -> None:
    register, sections, public = _stores(tmp_path)
    fake = FakeComplianceClient()
    app = FastAPI()
    app.include_router(build_compliance_reasoning_router(register, sections, public, fake))
    client = TestClient(app)

    assert client.get("/api/compliance-reasoning/status").json()["status"] == "available"
    response = client.post("/api/compliance-reasoning/reviews", json={"include_supported_findings": False})

    assert response.status_code == 200
    assert response.json()["status"]["job_id"] == "cr-test"
    assert fake.payload is not None
    assert fake.payload["options"]["include_supported_findings"] is False
    assert len(fake.payload["external_documents"]) == 1
    assert len(fake.payload["internal_documents"]) == 1


def test_compliance_reasoning_bridge_is_feature_flagged(tmp_path) -> None:
    register, sections, public = _stores(tmp_path)
    app = FastAPI()
    app.include_router(build_compliance_reasoning_router(register, sections, public, DisabledComplianceClient()))
    client = TestClient(app)

    assert client.get("/api/compliance-reasoning/status").json()["status"] == "not_configured"
    assert client.post("/api/compliance-reasoning/reviews").status_code == 503
