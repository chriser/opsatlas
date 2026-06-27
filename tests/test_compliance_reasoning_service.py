"""Standalone compliance reasoning service tests."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from services.compliance_reasoning.agent import AgenticComplianceEngine
from services.compliance_reasoning.app import create_app
from services.compliance_reasoning.engine import (
    DeterministicComplianceEngine,
    extract_internal_claims,
    extract_obligations,
    review_document_pair,
)
from services.compliance_reasoning.models import ComplianceReviewRequest, EvidenceDocument, EvidenceSection


class FakeGenerator:
    def __init__(self, response: str) -> None:
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def external_document(doc_id: str, title: str, text: str) -> EvidenceDocument:
    return EvidenceDocument(
        id=doc_id,
        title=title,
        source_type="external",
        url=f"https://example.test/{doc_id}",
        version="v1",
        content_sha256=f"hash-{doc_id}",
        sections=[
            EvidenceSection(
                id=f"{doc_id}-s1",
                heading=title,
                citation=f"{title}, section 1",
                ordinal=1,
                text=text,
            )
        ],
    )


def internal_document(doc_id: str, title: str, text: str) -> EvidenceDocument:
    return EvidenceDocument(
        id=doc_id,
        title=title,
        source_type="internal",
        content_sha256=f"hash-{doc_id}",
        sections=[
            EvidenceSection(
                id=f"{doc_id}-s1",
                heading=title,
                citation=f"{title}, learning pack",
                ordinal=1,
                text=text,
            )
        ],
    )


def sample_review_request() -> dict:
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "bribery-act",
                "Bribery Act section 7",
                "A commercial organisation must have adequate procedures to prevent bribery by associated persons.",
            ),
            external_document(
                "vat-guidance",
                "VAT record guidance",
                "Finance teams must keep VAT invoice records for audit and tax compliance.",
            ),
            external_document(
                "site-safety",
                "Site safety guidance",
                "Site operators must record a risk assessment before reopening premises.",
            ),
        ],
        internal_documents=[
            internal_document(
                "anti-bribery-pack",
                "Supplier onboarding anti-bribery pack",
                "Adequate procedures to prevent bribery are optional during supplier onboarding.",
            ),
            internal_document(
                "finance-pack",
                "Finance controls pack",
                "Finance teams must keep VAT invoice records for audit and tax compliance.",
            ),
        ],
    )
    return request.model_dump()


def wait_for_completion(client: TestClient, job_id: str) -> dict:
    for _ in range(40):
        status = client.get(f"/v1/reviews/{job_id}").json()
        if status["status"] in {"completed", "failed"}:
            return status
        time.sleep(0.05)
    raise AssertionError(f"Review job {job_id} did not complete.")


def test_extractors_return_structured_obligations_and_internal_claims() -> None:
    request = ComplianceReviewRequest(**sample_review_request())

    obligations = extract_obligations(request.external_documents)
    claims = extract_internal_claims(request.internal_documents)

    assert len(obligations) == 3
    assert len(claims) == 2
    assert obligations[0].evidence.citation
    assert any("bribery" in obligation.key_terms for obligation in obligations)
    assert any(claim.modality == "permission" for claim in claims)


def test_review_lifecycle_returns_evidence_backed_findings() -> None:
    client = TestClient(create_app(engine=DeterministicComplianceEngine()))

    capabilities = client.get("/v1/capabilities").json()
    assert capabilities["service"] == "compliance-reasoning"
    assert "contradiction" in capabilities["supported_findings"]

    response = client.post("/v1/reviews", json=sample_review_request())
    assert response.status_code == 202
    result = response.json()
    job_id = result["status"]["job_id"]

    assert result["status"]["status"] in {"queued", "running", "completed"}
    assert result["status"]["pair_total"] == 6

    status = wait_for_completion(client, job_id)
    assert status["status"] == "completed"
    assert status["progress_percent"] == 100
    assert status["audit"]["engine"] == "queued-pairwise-review"
    assert status["audit"]["source_hashes"]["bribery-act"] == "hash-bribery-act"
    assert any(pair["status"] == "not_related" for pair in status["pairs"])
    findings_response = client.get(f"/v1/reviews/{job_id}/findings")
    findings = findings_response.json()["findings"]
    classifications = {finding["classification"] for finding in findings}
    assert {"contradiction", "supported"}.issubset(classifications)
    assert "missing_obligation" not in classifications
    contradiction = next(finding for finding in findings if finding["classification"] == "contradiction")
    assert contradiction["severity"] == "high"
    assert "optional" in contradiction["internal_evidence"]["text"].lower()
    assert "adequate procedures" in contradiction["external_evidence"]["text"].lower()

    status_response = client.get(f"/v1/reviews/{job_id}")
    assert status_response.status_code == 200
    assert status_response.json()["finding_count"] == len(findings)

    assert findings_response.status_code == 200
    assert findings_response.json()["job_id"] == job_id
    assert len(findings_response.json()["findings"]) == len(findings)


def test_unrelated_vat_and_supplier_contract_pair_is_suppressed() -> None:
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "vat-notice-700",
                "VAT guide (VAT Notice 700)",
                "If you're approved to use the Cash Accounting Scheme referred to in paragraph 19.2.1 you must also "
                "have paid for the supply.",
            )
        ],
        internal_documents=[
            internal_document(
                "pack-2",
                "Pack 2: Supplier Master Data and Contract Design",
                "Where a supplier has materially different fulfilment or operational rules, multiple commercial or "
                "service contracts may be needed.",
            )
        ],
    )

    pair = review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert pair["status"] == "not_related"
    assert pair["findings"] == []


def test_single_generic_shared_word_does_not_create_contradiction() -> None:
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "vat-notice-700",
                "VAT guide (VAT Notice 700)",
                "10.6 Evidence needed for claims of input tax You must keep certain records to be able to reclaim "
                "input tax.",
            )
        ],
        internal_documents=[
            internal_document(
                "pack-2",
                "Pack 2: Supplier Master Data and Contract Design",
                "Where a supplier has materially different fulfilment or operational rules, multiple commercial or "
                "service contracts may be needed.",
            )
        ],
    )
    request.options.min_pair_relevance_score = 0.0

    pair = review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert all(finding.classification != "contradiction" for finding in pair["findings"])


def test_generic_discourse_words_do_not_create_vat_contradiction() -> None:
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "vat-notice-700",
                "VAT guide (VAT Notice 700)",
                "But, the full VAT invoicing procedure must still be followed.",
            )
        ],
        internal_documents=[
            internal_document(
                "pack-1",
                "End-to-End Supplier Setup Process",
                "A supplier record can exist but still be incomplete until contracts, mapping and readiness controls "
                "are finished.",
            )
        ],
    )
    request.options.min_pair_relevance_score = 0.0

    pair = review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert pair["findings"] == []


def test_agentic_review_returns_contradiction_after_same_obligation_decision() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "contradiction",
          "severity": "high",
          "confidence": 0.91,
          "rationale": "Internal wording permits deleting records that the external source requires keeping.",
          "recommended_action": "Update internal VAT record retention wording."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator)
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "vat-notice-700",
                "VAT guide (VAT Notice 700)",
                "Finance teams must keep VAT invoice records for audit.",
            )
        ],
        internal_documents=[
            internal_document(
                "finance-pack",
                "Finance controls pack",
                "Finance teams may delete VAT invoice records after supplier setup.",
            )
        ],
    )

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert generator.prompts
    assert len(pair["findings"]) == 1
    finding = pair["findings"][0]
    assert finding.classification == "contradiction"
    assert finding.severity == "high"
    assert finding.confidence == 0.91
    assert "agent_same_obligation=true" in finding.signals


def test_agentic_review_suppresses_not_related_decision() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": false,
          "classification": "not_related",
          "severity": "low",
          "confidence": 0.9,
          "rationale": "The passages use similar words but discuss different obligations.",
          "recommended_action": "No compliance action required."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator)
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "vat-notice-700",
                "VAT guide (VAT Notice 700)",
                "Finance teams must keep VAT invoice records for audit.",
            )
        ],
        internal_documents=[
            internal_document(
                "finance-pack",
                "Finance controls pack",
                "Finance teams may delete VAT invoice records after supplier setup.",
            )
        ],
    )

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert generator.prompts
    assert pair["findings"] == []


def test_agentic_review_lifecycle_reports_agent_capability_and_audit() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "supported",
          "severity": "low",
          "confidence": 0.83,
          "rationale": "Internal wording supports the external VAT record obligation.",
          "recommended_action": "No change required."
        }
        """
    )
    client = TestClient(create_app(engine=AgenticComplianceEngine(generator=generator)))
    payload = {
        "external_documents": [
            external_document(
                "vat-notice-700",
                "VAT guide (VAT Notice 700)",
                "Finance teams must keep VAT invoice records for audit.",
            ).model_dump()
        ],
        "internal_documents": [
            internal_document(
                "finance-pack",
                "Finance controls pack",
                "Finance teams must keep VAT invoice records for audit.",
            ).model_dump()
        ],
    }

    capabilities = client.get("/v1/capabilities").json()
    assert "governance-review-agent" in capabilities["modes"]
    response = client.post("/v1/reviews", json=payload)
    assert response.status_code == 202
    status = wait_for_completion(client, response.json()["status"]["job_id"])

    assert status["audit"]["engine"] == "governance-review-agent"
    assert status["audit"]["model_profile"] == "local-llm-adjudicator"
    assert status["audit"]["prompt_version"] == "governance-review-agent-v1"


def test_missing_obligation_findings_are_opt_in() -> None:
    client = TestClient(create_app(engine=DeterministicComplianceEngine()))
    payload = sample_review_request()
    payload["options"]["include_missing_obligations"] = True
    payload["options"]["min_pair_relevance_score"] = 0.0

    response = client.post("/v1/reviews", json=payload)
    assert response.status_code == 202
    job_id = response.json()["status"]["job_id"]

    wait_for_completion(client, job_id)
    findings = client.get(f"/v1/reviews/{job_id}/findings").json()["findings"]

    assert any(finding["classification"] == "missing_obligation" for finding in findings)


def test_queued_review_applies_global_finding_cap() -> None:
    client = TestClient(create_app(engine=DeterministicComplianceEngine()))
    payload = sample_review_request()
    payload["options"]["max_findings"] = 2

    response = client.post("/v1/reviews", json=payload)
    assert response.status_code == 202
    job_id = response.json()["status"]["job_id"]

    status = wait_for_completion(client, job_id)
    findings = client.get(f"/v1/reviews/{job_id}/findings").json()["findings"]

    assert status["finding_count"] == 2
    assert len(findings) == 2
    assert any(finding["classification"] == "contradiction" for finding in findings)


def test_unknown_review_returns_404() -> None:
    client = TestClient(create_app(engine=DeterministicComplianceEngine()))

    assert client.get("/v1/reviews/cr-missing").status_code == 404
    assert client.get("/v1/reviews/cr-missing/findings").status_code == 404
