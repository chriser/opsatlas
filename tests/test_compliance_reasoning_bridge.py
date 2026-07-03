"""Main application bridge tests for the compliance reasoning service."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from assistant.analytics.event_store import AnalyticsEventStore
from assistant.api.routes_compliance import build_compliance_reasoning_router
from assistant.api.routes_governance import build_governance_router
from assistant.compliance.payload import build_compliance_review_payload, build_internal_source_review_payload
from assistant.external.models import FetchedPublicContent
from assistant.external.registry import PublicContentRegistry
from assistant.governance.intelligence import KnowledgeIntelligence
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
        return {"service": "compliance-reasoning", "modes": ["queued-pairwise-review"]}

    def create_review(self, payload: dict) -> dict:
        self.payload = payload
        return {
            "status": {
                "job_id": "cr-test",
                "status": "queued",
                "created_at": "2026-06-27T10:00:00Z",
                "completed_at": "",
                "failure_reason": "",
                "review_mode": "external_vs_internal",
                "review_depth": self.payload.get("options", {}).get("review_depth", "balanced") if self.payload else "balanced",
                "throttle_deep": self.payload.get("options", {}).get("throttle_deep", False) if self.payload else False,
                "obligation_count": 0,
                "internal_claim_count": 0,
                "finding_count": 0,
                "pair_total": 1,
                "pair_completed": 0,
                "progress_percent": 0,
                "current_pair": None,
                "pairs": [],
                "audit": {
                    "engine": "queued-pairwise-review",
                    "engine_version": "0.1.0",
                    "model_profile": "llm-ready-deterministic-fallback",
                    "prompt_version": "",
                    "review_mode": "external_vs_internal",
                    "review_depth": self.payload.get("options", {}).get("review_depth", "balanced") if self.payload else "balanced",
                    "throttle_deep": self.payload.get("options", {}).get("throttle_deep", False) if self.payload else False,
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

    def review_status(self, job_id: str) -> dict:
        return {
            "job_id": job_id,
            "status": "completed",
            "created_at": "2026-06-27T10:00:00Z",
            "completed_at": "2026-06-27T10:00:01Z",
            "failure_reason": "",
            "review_mode": "external_vs_internal",
            "review_depth": self.payload.get("options", {}).get("review_depth", "balanced") if self.payload else "balanced",
            "throttle_deep": self.payload.get("options", {}).get("throttle_deep", False) if self.payload else False,
            "obligation_count": 1,
            "internal_claim_count": 1,
            "finding_count": 1,
            "pair_total": 1,
            "pair_completed": 1,
            "progress_percent": 100,
            "current_pair": None,
            "pairs": [],
            "audit": {
                "engine": "queued-pairwise-review",
                "engine_version": "0.1.0",
                "model_profile": "llm-ready-deterministic-fallback",
                "prompt_version": "",
                "review_mode": "external_vs_internal",
                "review_depth": self.payload.get("options", {}).get("review_depth", "balanced") if self.payload else "balanced",
                "throttle_deep": self.payload.get("options", {}).get("throttle_deep", False) if self.payload else False,
                "external_document_count": 1,
                "internal_document_count": 1,
                "source_hashes": {},
                "assumptions": [],
            },
        }

    def review_findings(self, job_id: str) -> dict:
        return {"job_id": job_id, "status": "completed", "findings": []}


class DisabledComplianceClient(FakeComplianceClient):
    enabled = False


class FakeInternalComplianceClient(FakeComplianceClient):
    def create_review(self, payload: dict) -> dict:
        self.payload = payload
        return {
            "status": {
                "job_id": "cr-internal",
                "status": "queued",
                "created_at": "2026-06-27T10:00:00Z",
                "started_at": "",
                "completed_at": "",
                "failure_reason": "",
                "review_mode": "internal_vs_internal",
                "review_depth": self.payload.get("options", {}).get("review_depth", "fast") if self.payload else "fast",
                "throttle_deep": self.payload.get("options", {}).get("throttle_deep", False) if self.payload else False,
                "cancel_requested": False,
                "obligation_count": 0,
                "internal_claim_count": 0,
                "finding_count": 0,
                "pair_total": 1,
                "pair_completed": 0,
                "progress_percent": 0,
                "elapsed_seconds": 0,
                "estimated_remaining_seconds": 0,
                "estimated_remaining_label": "Learning from first reviewed pair",
                "eta_confidence": "unknown",
                "current_pair_elapsed_seconds": 0,
                "cache_hit_count": 0,
                "cache_miss_count": 0,
                "cache_bypass_count": 0,
                "current_pair": None,
                "pairs": [
                    {
                        "pair_id": "pair-1",
                        "external_document_id": "source-a",
                        "external_title": "Approved controls",
                        "internal_document_id": "source-b",
                        "internal_title": "Approved VAT controls",
                        "status": "queued",
                        "classification": "",
                        "relevance_score": 0,
                        "finding_count": 0,
                        "rationale": "",
                        "cache_status": "pending",
                        "started_at": "",
                        "completed_at": "",
                        "duration_seconds": 0,
                        "input_weight": 1,
                    }
                ],
                "audit": {
                    "engine": "governance-review-agent",
                    "engine_version": "0.1.0",
                    "model_profile": "local-llm-adjudicator:deepseek-r1:32b",
                    "prompt_version": "governance-review-agent-v6",
                    "review_mode": "internal_vs_internal",
                    "review_depth": self.payload.get("options", {}).get("review_depth", "fast") if self.payload else "fast",
                    "throttle_deep": self.payload.get("options", {}).get("throttle_deep", False) if self.payload else False,
                    "external_document_count": 0,
                    "internal_document_count": 2,
                    "source_hashes": {},
                    "assumptions": [],
                },
            },
            "obligations": [],
            "internal_claims": [],
            "findings": [],
        }

    def review_status(self, job_id: str) -> dict:
        status = self.create_review(self.payload or {})["status"]
        status.update({
            "job_id": job_id,
            "status": "completed",
            "completed_at": "2026-06-27T10:00:01Z",
            "finding_count": 1,
            "pair_completed": 1,
            "progress_percent": 100,
        })
        status["pairs"][0].update({"status": "completed", "finding_count": 1})
        return status

    def review_findings(self, job_id: str) -> dict:
        return {
            "job_id": job_id,
            "status": "completed",
            "findings": [
                {
                    "id": "internal-finding-1",
                    "classification": "contradiction",
                    "severity": "high",
                    "confidence": 0.9,
                    "alignment_score": 0.72,
                    "rationale": "Internal sources disagree on VAT record retention.",
                    "obligation_id": "claim-a",
                    "internal_claim_id": "claim-b",
                    "external_evidence": {
                        "source_id": "source-a",
                        "source_title": "Approved controls",
                        "section_id": "source-a-1",
                        "heading": "Controls",
                        "citation": "Approved controls - Controls",
                        "text": "Finance teams must keep VAT invoice records.",
                        "url": "",
                        "version": "",
                        "content_sha256": "",
                    },
                    "internal_evidence": {
                        "source_id": "source-b",
                        "source_title": "Approved VAT controls",
                        "section_id": "source-b-1",
                        "heading": "Controls",
                        "citation": "Approved VAT controls - Controls",
                        "text": "Finance teams may delete VAT invoice records.",
                        "url": "",
                        "version": "",
                        "content_sha256": "",
                    },
                    "signals": ["agent_internal_pair=true"],
                    "advisor_summary": "The two internal sources conflict.",
                    "why_it_matters": "The assistant may answer inconsistently.",
                    "recommended_action": "Align Source B.",
                    "proposed_internal_text": "Finance teams must keep VAT invoice records.",
                    "confidence_interpretation": "High-confidence internal contradiction.",
                    "evidence_highlights": [],
                }
            ],
        }

    def cancel_review(self, job_id: str) -> dict:
        status = self.create_review(self.payload or {})["status"]
        status.update({
            "job_id": job_id,
            "status": "cancelled",
            "failure_reason": "Cancelled by operator.",
            "completed_at": "2026-06-27T10:00:01Z",
            "cancel_requested": True,
            "pair_completed": 1,
            "progress_percent": 100,
        })
        status["pairs"][0].update({"status": "cancelled"})
        return status


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


def test_internal_source_review_payload_uses_internal_pair_mode(tmp_path) -> None:
    register, sections, _public = _stores(tmp_path)
    second = register_upload(
        register,
        "approved-vat.md",
        b"# Controls\n\nFinance teams may delete VAT invoice records.",
        title="Approved VAT controls",
    )
    ingest_source(register, sections, second.id)
    register.update(second.id, approval_status="approved")

    payload = build_internal_source_review_payload(register, sections, options={"force_rerun": True})

    assert payload["review_mode"] == "internal_vs_internal"
    assert payload["external_documents"] == []
    assert len(payload["internal_documents"]) == 2
    assert {document["title"] for document in payload["internal_documents"]} == {"Approved controls", "Approved VAT controls"}
    assert payload["options"]["force_rerun"] is True


def test_governance_internal_review_uses_compliance_reasoning_service_when_configured(tmp_path) -> None:
    register, sections, _public = _stores(tmp_path)
    second = register_upload(
        register,
        "approved-vat.md",
        b"# Controls\n\nFinance teams may delete VAT invoice records.",
        title="Approved VAT controls",
    )
    ingest_source(register, sections, second.id)
    register.update(second.id, approval_status="approved")
    fake = FakeInternalComplianceClient()
    events = AnalyticsEventStore(register.base_dir)
    app = FastAPI()
    app.include_router(
        build_governance_router(
            register,
            KnowledgeIntelligence(register, sections),
            section_store=sections,
            compliance_reasoning=fake,
            event_store=events,
        )
    )
    client = TestClient(app)

    started = client.post(
        "/api/governance/internal-review/reviews",
        json={"force_rerun": True, "review_depth": "deep", "throttle_deep": True},
    ).json()

    assert started["status"]["job_id"] == "cr-internal"
    assert started["status"]["review_mode"] == "internal_vs_internal"
    assert started["status"]["item_total"] == 1
    assert fake.payload is not None
    assert fake.payload["review_mode"] == "internal_vs_internal"
    assert fake.payload["options"]["include_supported_findings"] is False
    assert fake.payload["options"]["force_rerun"] is True
    assert fake.payload["options"]["review_depth"] == "deep"
    assert fake.payload["options"]["throttle_deep"] is True
    assert fake.payload["options"]["max_agent_calls_per_pair"] == 0
    assert len(fake.payload["internal_documents"]) == 2

    completed = client.get("/api/governance/internal-review/reviews/cr-internal").json()

    assert completed["status"]["status"] == "completed"
    assert completed["status"]["review_depth"] == "deep"
    assert completed["status"]["throttle_deep"] is True
    assert completed["status"]["model_profile"] == "local-llm-adjudicator:deepseek-r1:32b"
    assert completed["status"]["item_completed"] == 1
    assert completed["findings"][0]["classification"] == "contradiction"
    assert completed["findings"][0]["signals"] == ["agent_internal_pair=true"]
    assert client.get("/api/governance/internal-review/latest").json()["status"]["job_id"] == "cr-internal"
    recorded = events.events(event_type="compliance_reasoning_review_requested")
    assert recorded[0].metadata["review_mode"] == "internal_vs_internal"


def test_governance_internal_review_cancel_calls_reasoning_service(tmp_path) -> None:
    register, sections, _public = _stores(tmp_path)
    second = register_upload(
        register,
        "approved-vat.md",
        b"# Controls\n\nFinance teams may delete VAT invoice records.",
        title="Approved VAT controls",
    )
    ingest_source(register, sections, second.id)
    register.update(second.id, approval_status="approved")
    fake = FakeInternalComplianceClient()
    app = FastAPI()
    app.include_router(
        build_governance_router(
            register,
            KnowledgeIntelligence(register, sections),
            section_store=sections,
            compliance_reasoning=fake,
        )
    )
    client = TestClient(app)
    client.post("/api/governance/internal-review/reviews", json={"review_depth": "deep"})

    cancelled = client.post("/api/governance/internal-review/reviews/cr-internal/cancel").json()

    assert cancelled["status"]["status"] == "cancelled"
    assert cancelled["status"]["cancel_requested"] is True
    assert cancelled["status"]["review_depth"] == "deep"


def test_compliance_reasoning_bridge_calls_configured_service(tmp_path) -> None:
    register, sections, public = _stores(tmp_path)
    fake = FakeComplianceClient()
    events = AnalyticsEventStore(register.base_dir)
    app = FastAPI()
    app.include_router(build_compliance_reasoning_router(register, sections, public, fake, event_store=events))
    client = TestClient(app)

    assert client.get("/api/compliance-reasoning/status").json()["status"] == "available"
    response = client.post(
        "/api/compliance-reasoning/reviews",
        json={"include_supported_findings": False, "review_depth": "deep", "throttle_deep": True},
    )

    assert response.status_code == 200
    assert response.json()["status"]["job_id"] == "cr-test"
    assert fake.payload is not None
    assert fake.payload["options"]["include_supported_findings"] is False
    assert fake.payload["options"]["include_missing_obligations"] is False
    assert fake.payload["options"]["review_depth"] == "deep"
    assert fake.payload["options"]["throttle_deep"] is True
    assert len(fake.payload["external_documents"]) == 1
    assert len(fake.payload["internal_documents"]) == 1
    recorded = events.events(event_type="compliance_reasoning_review_requested")
    assert recorded[0].entity_id == "cr-test"
    assert recorded[0].metadata["finding_count"] == 0

    assert client.get("/api/compliance-reasoning/reviews/cr-test").json()["progress_percent"] == 100
    assert client.get("/api/compliance-reasoning/reviews/cr-test/findings").json()["status"] == "completed"
    latest = client.get("/api/compliance-reasoning/reviews/latest").json()
    assert latest["status"]["job_id"] == "cr-test"
    assert latest["status"]["audit"]["model_profile"] == "llm-ready-deterministic-fallback"

    reloaded = FastAPI()
    reloaded.include_router(build_compliance_reasoning_router(register, sections, public, FakeComplianceClient()))
    reloaded_client = TestClient(reloaded)
    reloaded_latest = reloaded_client.get("/api/compliance-reasoning/reviews/latest").json()
    assert reloaded_latest["status"]["job_id"] == "cr-test"
    assert reloaded_latest["status"]["completed_at"] == "2026-06-27T10:00:01Z"

    resolution = client.post(
        "/api/compliance-reasoning/resolutions",
        json={
            "finding_id": "finding-1",
            "action": "fixed",
            "source_id": fake.payload["internal_documents"][0]["id"],
            "source_title": "Approved controls",
            "classification": "contradiction",
            "severity": "high",
            "external_source_title": "Example regulation",
            "internal_evidence_text": "Finance teams may delete VAT invoice records.",
            "proposed_internal_text": "Finance teams must keep VAT invoice records.",
        },
    )

    assert resolution.status_code == 200
    report = client.get("/api/compliance-reasoning/resolutions").json()
    assert report["by_finding"]["finding-1"]["action"] == "fixed"
    assert report["source_summary"][fake.payload["internal_documents"][0]["id"]]["fixed"] == 1


def test_compliance_finding_reconcile_marks_stale_related_findings_superseded(tmp_path) -> None:
    register, sections, public = _stores(tmp_path)
    fake = FakeComplianceClient()
    app = FastAPI()
    app.include_router(build_compliance_reasoning_router(register, sections, public, fake))
    client = TestClient(app)
    source_id = register.list()[0].id
    findings = [
        {
            "finding_id": "finding-1",
            "source_id": source_id,
            "source_title": "Approved controls",
            "classification": "contradiction",
            "severity": "high",
            "external_source_title": "Example regulation",
            "internal_evidence_text": "Finance teams must keep VAT invoice records.",
            "proposed_internal_text": "Finance teams must retain VAT invoice records.",
        },
        {
            "finding_id": "finding-2",
            "source_id": source_id,
            "source_title": "Approved controls",
            "classification": "missing_detail",
            "severity": "medium",
            "external_source_title": "Example regulation",
            "internal_evidence_text": "Finance teams must keep VAT invoice records.",
            "proposed_internal_text": "Finance teams must retain VAT invoice records for audit.",
        },
    ]

    before = client.post("/api/compliance-reasoning/findings/reconcile", json={"findings": findings}).json()

    assert before["by_finding"]["finding-1"]["source_status"] == "still_present"
    assert before["by_finding"]["finding-1"]["related_count"] == 2
    assert len(before["groups"]) == 1

    register.write_content(source_id, b"# Controls\n\nFinance teams retain VAT invoice records for audit.")
    after = client.post(
        "/api/compliance-reasoning/findings/reconcile",
        json={"findings": findings, "persist_superseded": True},
    ).json()

    assert after["by_finding"]["finding-1"]["source_status"] == "already_changed"
    assert {record["finding_id"] for record in after["superseded_records"]} == {"finding-1", "finding-2"}
    resolutions = client.get("/api/compliance-reasoning/resolutions").json()
    assert resolutions["by_finding"]["finding-2"]["action"] == "superseded_by_source_edit"
    assert resolutions["source_summary"][source_id]["superseded_by_source_edit"] == 2


def test_compliance_reasoning_bridge_is_feature_flagged(tmp_path) -> None:
    register, sections, public = _stores(tmp_path)
    app = FastAPI()
    app.include_router(build_compliance_reasoning_router(register, sections, public, DisabledComplianceClient()))
    client = TestClient(app)

    assert client.get("/api/compliance-reasoning/status").json()["status"] == "not_configured"
    assert client.post("/api/compliance-reasoning/reviews").status_code == 503
