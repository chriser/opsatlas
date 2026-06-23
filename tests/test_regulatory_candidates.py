"""Regulatory candidate discovery tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from assistant.api.app import create_app
from assistant.api.auth import AuthService
from assistant.external.models import FetchedPublicContent
from assistant.external.registry import PublicContentRegistry
from assistant.ingestion.service import ingest_source
from assistant.ingestion.store import SectionStore
from assistant.regulatory.discovery import discover_regulatory_candidates
from assistant.regulatory.impact import simulate_regulatory_impact
from assistant.regulatory.review import RegulatoryReviewStore
from assistant.retrieval.service import RetrievalService
from assistant.sources.register import SourceRegister
from assistant.sources.service import register_upload

REGULATORY_PACK = """# Site Operating Procedure

## Customer data and invoices

The process stores customer data for retention checks. VAT invoices must be created before the weekly fiscal reconciliation.

## Safety checks

The site team completes a risk assessment and records any health and safety incident before reopening the premises.
"""


def _approved_source(tmp_path):
    register = SourceRegister(tmp_path)
    sections = SectionStore(register.base_dir)
    source = register_upload(register, "site-ops.md", REGULATORY_PACK.encode(), title="Site ops pack")
    ingest_source(register, sections, source.id)
    register.update(source.id, approval_status="approved")
    return register, sections, source


def test_regulatory_discovery_scans_only_approved_sections(tmp_path):
    register, sections, source = _approved_source(tmp_path)
    pending = register_upload(register, "pending.md", b"# Pending\n\nVAT and tax text.", title="Pending pack")
    ingest_source(register, sections, pending.id)
    reviews = RegulatoryReviewStore(register.base_dir)

    report = discover_regulatory_candidates(register, sections, reviews)
    themes = {candidate["theme"] for candidate in report["candidates"]}

    assert report["candidate_count"] >= 3
    assert {"data_privacy", "financial_tax", "health_safety"}.issubset(themes)
    assert {candidate["source_id"] for candidate in report["candidates"]} == {source.id}
    first = report["candidates"][0]
    assert first["reason"].startswith("Candidate only:")
    assert first["passages"][0]["source_title"] == "Site ops pack"
    assert first["confidence"] in {"medium", "high"}


def test_regulatory_review_state_is_applied_to_candidates(tmp_path):
    register, sections, _ = _approved_source(tmp_path)
    reviews = RegulatoryReviewStore(register.base_dir)
    report = discover_regulatory_candidates(register, sections, reviews)
    candidate_id = report["candidates"][0]["id"]

    reviews.set(candidate_id, "needs_research", note="Check current guidance.")
    updated = discover_regulatory_candidates(register, sections, reviews)
    reviewed = next(candidate for candidate in updated["candidates"] if candidate["id"] == candidate_id)

    assert reviewed["review_status"] == "needs_research"
    assert reviewed["review_note"] == "Check current guidance."
    assert updated["review_counts"]["needs_research"] == 1


def test_regulatory_candidates_include_external_context_matches(tmp_path):
    register, sections, _ = _approved_source(tmp_path)
    reviews = RegulatoryReviewStore(register.base_dir)
    public = PublicContentRegistry(register.base_dir)
    public_source = public.upsert_source(provider="govuk", url="https://www.gov.uk/vat-businesses", topics=["tax"])
    public.add_snapshot(
        public_source.id,
        FetchedPublicContent(
            url="https://www.gov.uk/vat-businesses",
            title="VAT guidance for businesses",
            public_body="HM Revenue & Customs",
            document_type="guidance",
            update_date="2026-06-19T00:00:00Z",
            retrieved_at="2026-06-22T10:00:00Z",
            text="VAT records and invoices for tax compliance.",
            metadata={"schema_name": "guide"},
        ),
    )

    report = discover_regulatory_candidates(register, sections, reviews, public)
    financial = next(candidate for candidate in report["candidates"] if candidate["theme"] == "financial_tax")

    assert financial["external_matches"][0]["title"] == "VAT guidance for businesses"
    assert "vat" in financial["external_matches"][0]["matched_terms"]


def test_regulatory_impact_simulation_scores_affected_sources(tmp_path):
    register, sections, source = _approved_source(tmp_path)
    reviews = RegulatoryReviewStore(register.base_dir)
    public = PublicContentRegistry(register.base_dir)
    public_source = public.upsert_source(provider="govuk", url="https://www.gov.uk/vat-businesses", topics=["tax"])
    public.add_snapshot(
        public_source.id,
        FetchedPublicContent(
            url="https://www.gov.uk/vat-businesses",
            title="VAT guidance for businesses",
            public_body="HM Revenue & Customs",
            document_type="guidance",
            update_date="2026-06-19T00:00:00Z",
            retrieved_at="2026-06-22T10:00:00Z",
            text="VAT records and invoices for tax compliance.",
            metadata={"schema_name": "guide"},
        ),
    )
    report = discover_regulatory_candidates(register, sections, reviews, public)
    financial = next(candidate for candidate in report["candidates"] if candidate["theme"] == "financial_tax")

    simulation = simulate_regulatory_impact(register, sections, reviews, public, financial["id"])

    assert simulation.candidate_id == financial["id"]
    assert simulation.affected_source_count == 1
    assert simulation.affected_sources[0].source_id == source.id
    assert simulation.impact_score < 100
    assert simulation.affected_sources[0].impact_score < 100
    assert simulation.affected_sources[0].impact_band in {"medium", "high"}
    assert simulation.external_context_count == 1
    assert "Tax and finance controls" in simulation.affected_process_areas
    assert simulation.recommended_actions


def test_regulatory_impact_preserves_markdown_table_evidence(tmp_path):
    register = SourceRegister(tmp_path)
    sections = SectionStore(register.base_dir)
    source = register_upload(
        register,
        "tax-table.md",
        b"""# Article Controls

## Tax validation matrix

| Step | VAT control | Owner |
| --- | --- | --- |
| Article setup | VAT invoices are checked before launch | Finance |
| Exception review | Tax exception goes to the article owner | Commercial |
""",
        title="Tax table pack",
    )
    ingest_source(register, sections, source.id)
    register.update(source.id, approval_status="approved")
    reviews = RegulatoryReviewStore(register.base_dir)
    report = discover_regulatory_candidates(register, sections, reviews)
    financial = next(candidate for candidate in report["candidates"] if candidate["theme"] == "financial_tax")

    simulation = simulate_regulatory_impact(register, sections, reviews, None, financial["id"])
    excerpt = simulation.affected_sources[0].passages[0].excerpt

    assert "| Step | VAT control | Owner |" in excerpt
    assert "| --- | --- | --- |" in excerpt
    assert "VAT invoices are checked before launch" in excerpt


def test_regulatory_candidates_api_and_review_flow(tmp_path):
    register = SourceRegister(tmp_path)
    sections = SectionStore(register.base_dir)
    client = TestClient(create_app(register, AuthService("pw"), retrieval=RetrievalService(register, sections)))

    assert client.get("/api/regulatory/candidates").status_code == 401
    token = client.post("/api/auth/login", json={"password": "pw"}).json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    source = client.post(
        "/api/sources/upload",
        files={"file": ("site-ops.md", REGULATORY_PACK.encode(), "text/markdown")},
        data={"title": "Site ops pack"},
    ).json()
    client.post(f"/api/sources/{source['id']}/ingest")
    client.post(f"/api/governance/sources/{source['id']}/approve")

    report = client.get("/api/regulatory/candidates").json()
    candidate_id = report["candidates"][0]["id"]
    response = client.post(f"/api/regulatory/candidates/{candidate_id}/review", json={"status": "relevant"})

    assert response.status_code == 200
    updated = client.get("/api/regulatory/candidates").json()
    assert any(candidate["review_status"] == "relevant" for candidate in updated["candidates"])
    assert client.post(f"/api/regulatory/candidates/{candidate_id}/review", json={"status": "unreviewed"}).status_code == 400

    impact_response = client.post(f"/api/regulatory/candidates/{candidate_id}/impact-simulation")
    assert impact_response.status_code == 200
    impact = impact_response.json()
    assert impact["candidate_id"] == candidate_id
    assert impact["affected_source_count"] >= 1
    assert impact["impact_band"] in {"low", "medium", "high"}
    events = client.app.state.analytics_events.events(event_type="regulatory_impact_simulated")
    assert events[0].entity_id == candidate_id
    assert events[0].metadata["affected_source_count"] >= 1
