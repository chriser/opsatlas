"""Standalone compliance reasoning service tests."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from services.compliance_reasoning.agent import AgenticComplianceEngine, OllamaComplianceGenerator, _record_prompt_observation
from services.compliance_reasoning.app import _ollama_generator_from_env, create_app
from services.compliance_reasoning.cache import PairResultCache
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


class SequencedFakeGenerator:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if not self.responses:
            raise AssertionError("No fake generator response left.")
        return self.responses.pop(0)


class FakeEmbedder:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.texts.append(text)
        return [1.0, 0.0]


class LowSimilarityEmbedder:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.texts.append(text)
        if len(self.texts) % 2:
            return [1.0, 0.0]
        return [0.0, 1.0]


class MediumSimilarityEmbedder:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.texts.append(text)
        if len(self.texts) % 2:
            return [1.0, 0.0]
        return [0.5, 0.8660254]


class SlowDeterministicEngine(DeterministicComplianceEngine):
    def review_document_pair(self, external: EvidenceDocument, internal: EvidenceDocument, request: ComplianceReviewRequest) -> dict:
        time.sleep(0.25)
        return super().review_document_pair(external, internal, request)


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
        if status["status"] in {"completed", "failed", "cancelled"}:
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


def test_internal_claim_extractor_captures_imperative_guidance() -> None:
    claims = extract_internal_claims(
        [
            internal_document(
                "vat-pack",
                "VAT controls",
                "Keep enough VAT paperwork for audit purposes.",
            )
        ]
    )

    assert len(claims) == 1
    assert claims[0].modality == "recommendation"
    assert claims[0].action == "Keep enough VAT paperwork for audit purposes"


def test_internal_claim_extractor_captures_no_requirement_negation() -> None:
    claims = extract_internal_claims(
        [
            internal_document(
                "anti-bribery-pack",
                "Anti-bribery controls",
                "No training evidence is required for third parties after contract approval.",
            )
        ]
    )

    assert len(claims) == 1
    assert claims[0].modality == "permission"
    assert claims[0].action == "No training evidence is required for third parties after contract approval"


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


def test_internal_review_mode_checks_unique_internal_source_pairs() -> None:
    client = TestClient(create_app(engine=DeterministicComplianceEngine()))
    payload = {
        "review_mode": "internal_vs_internal",
        "internal_documents": [
            internal_document(
                "finance-a",
                "Finance pack A",
                "Finance teams must keep VAT invoice records for audit review.",
            ).model_dump(),
            internal_document(
                "finance-b",
                "Finance pack B",
                "Finance teams may delete VAT invoice records after supplier setup.",
            ).model_dump(),
            internal_document(
                "supplier-pack",
                "Supplier setup pack",
                "Supplier owners must complete contract readiness checks before go live.",
            ).model_dump(),
        ],
        "options": {"include_supported_findings": False, "min_pair_relevance_score": 0.0},
    }

    response = client.post("/v1/reviews", json=payload)
    assert response.status_code == 202
    result = response.json()
    job_id = result["status"]["job_id"]

    assert result["status"]["review_mode"] == "internal_vs_internal"
    assert result["status"]["pair_total"] == 3
    assert all(pair["external_document_id"] != pair["internal_document_id"] for pair in result["status"]["pairs"])

    status = wait_for_completion(client, job_id)
    assert status["status"] == "completed"
    assert status["audit"]["review_mode"] == "internal_vs_internal"
    assert status["pair_total"] == 3


def test_review_job_can_be_cancelled() -> None:
    client = TestClient(create_app(engine=SlowDeterministicEngine()))
    response = client.post("/v1/reviews", json=sample_review_request())
    assert response.status_code == 202
    job_id = response.json()["status"]["job_id"]

    cancelled = client.post(f"/v1/reviews/{job_id}/cancel")

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["cancel_requested"] is True
    assert wait_for_completion(client, job_id)["status"] == "cancelled"
    assert client.get(f"/v1/reviews/{job_id}/findings").json()["status"] == "cancelled"


def test_queued_review_reuses_pair_cache_and_force_rerun_bypasses(tmp_path) -> None:
    client = TestClient(create_app(engine=DeterministicComplianceEngine(), cache=PairResultCache(tmp_path / "pair-cache.json")))

    first = client.post("/v1/reviews", json=sample_review_request()).json()
    first_status = wait_for_completion(client, first["status"]["job_id"])

    second = client.post("/v1/reviews", json=sample_review_request()).json()
    second_status = wait_for_completion(client, second["status"]["job_id"])

    forced_payload = sample_review_request()
    forced_payload["options"]["force_rerun"] = True
    forced = client.post("/v1/reviews", json=forced_payload).json()
    forced_status = wait_for_completion(client, forced["status"]["job_id"])

    assert first_status["cache_miss_count"] == first_status["pair_total"]
    assert second_status["cache_hit_count"] == second_status["pair_total"]
    assert forced_status["cache_bypass_count"] == forced_status["pair_total"]
    assert second_status["elapsed_seconds"] >= 0


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


def test_ollama_prompt_observation_flags_near_context_limit() -> None:
    generator = OllamaComplianceGenerator(model="test-model", num_ctx=100)

    observation = _record_prompt_observation(
        generator,
        "x" * 400,
        model="test-model",
        num_ctx=100,
        temperature=0.0,
    )

    assert observation["prompt_token_estimate"] == 100
    assert observation["near_context_limit"] is True
    assert generator.prompt_observations[-1] == observation


def test_agentic_internal_review_uses_internal_pair_prompt() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "contradiction",
          "severity": "high",
          "confidence": 0.89,
          "rationale": "One internal source requires retaining VAT invoice records while the other permits deleting them.",
          "recommended_action": "Update Source B so VAT record retention is consistent."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator)
    request = ComplianceReviewRequest(
        review_mode="internal_vs_internal",
        internal_documents=[
            internal_document(
                "finance-a",
                "Finance controls pack A",
                "Finance teams must keep VAT invoice records for audit review.",
            ),
            internal_document(
                "finance-b",
                "Finance controls pack B",
                "Finance teams may delete VAT invoice records after supplier setup.",
            ),
        ],
    )
    request.options.min_pair_relevance_score = 0.0

    pair = engine.review_document_pair(request.internal_documents[0], request.internal_documents[1], request)

    assert generator.prompts
    assert "Source A:" in generator.prompts[0]
    assert "External source:" not in generator.prompts[0]
    assert len(pair["findings"]) == 1
    finding = pair["findings"][0]
    assert finding.classification == "contradiction"
    assert "agent_internal_pair=true" in finding.signals
    assert finding.external_evidence.source_title == "Finance controls pack A"
    assert finding.internal_evidence.source_title == "Finance controls pack B"


def test_fast_internal_review_depth_skips_agent_generator() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "contradiction",
          "severity": "high",
          "confidence": 0.89,
          "rationale": "This response should not be used."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator)
    request = ComplianceReviewRequest(
        review_mode="internal_vs_internal",
        internal_documents=[
            internal_document(
                "finance-a",
                "Finance controls pack A",
                "Finance teams must keep VAT invoice records for audit review.",
            ),
            internal_document(
                "finance-b",
                "Finance controls pack B",
                "Finance teams may delete VAT invoice records after supplier setup.",
            ),
        ],
    )
    request.options.review_depth = "fast"
    request.options.min_pair_relevance_score = 0.0

    pair = engine.review_document_pair(request.internal_documents[0], request.internal_documents[1], request)

    assert generator.prompts == []
    assert pair["findings"]
    assert all("agent_internal_pair=true" not in finding.signals for finding in pair["findings"])


def test_balanced_internal_review_depth_caps_agent_calls() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": false,
          "classification": "not_related",
          "severity": "low",
          "confidence": 0.61,
          "rationale": "The pair is not related."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator)
    request = ComplianceReviewRequest(
        review_mode="internal_vs_internal",
        internal_documents=[
            internal_document(
                "finance-a",
                "Finance controls pack A",
                "Finance teams must keep VAT invoice records. Finance teams must reconcile VAT invoice records.",
            ),
            internal_document(
                "finance-b",
                "Finance controls pack B",
                "Finance teams may delete VAT invoice records. Finance teams may archive VAT invoice records.",
            ),
        ],
    )
    request.options.review_depth = "balanced"
    request.options.max_agent_calls_per_pair = 1
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.0

    engine.review_document_pair(request.internal_documents[0], request.internal_documents[1], request)

    assert len(generator.prompts) == 1


def test_balanced_depth_uses_balanced_generator_profile() -> None:
    deep_generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "supported",
          "severity": "low",
          "confidence": 0.8,
          "rationale": "Deep generator should not be used for balanced."
        }
        """
    )
    balanced_generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "contradiction",
          "severity": "high",
          "confidence": 0.86,
          "rationale": "Balanced generator reviewed this pair."
        }
        """
    )
    engine = AgenticComplianceEngine(
        generator=deep_generator,
        model_name="deepseek-r1:32b",
        depth_generators={"balanced": balanced_generator, "deep": deep_generator},
        depth_model_names={"fast": "", "balanced": "deepseek-r1:8b", "deep": "deepseek-r1:32b"},
    )
    request = ComplianceReviewRequest(
        external_documents=[
            external_document("vat", "VAT guide", "Finance teams must keep VAT invoice records for audit.")
        ],
        internal_documents=[
            internal_document("pack", "Finance pack", "Finance teams may delete VAT invoice records after setup.")
        ],
    )
    request.options.review_depth = "balanced"
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert balanced_generator.prompts
    assert deep_generator.prompts == []
    assert pair["findings"][0].classification == "contradiction"
    assert engine.model_profile_for_request(request) == "balanced=ollama:deepseek-r1:8b"


def test_deep_throttle_uses_throttled_generator_profile() -> None:
    deep_generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "supported",
          "severity": "low",
          "confidence": 0.8,
          "rationale": "Unthrottled deep generator should not be used."
        }
        """
    )
    throttled_generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "contradiction",
          "severity": "high",
          "confidence": 0.86,
          "rationale": "Throttled deep generator reviewed this pair."
        }
        """
    )
    engine = AgenticComplianceEngine(
        generator=deep_generator,
        model_name="deepseek-r1:32b",
        depth_generators={"deep": deep_generator, "deep_throttled": throttled_generator},
        depth_model_names={"fast": "", "deep": "deepseek-r1:32b", "deep_throttled": "deepseek-r1:32b"},
    )
    request = ComplianceReviewRequest(
        external_documents=[
            external_document("vat", "VAT guide", "Finance teams must keep VAT invoice records for audit.")
        ],
        internal_documents=[
            internal_document("pack", "Finance pack", "Finance teams may delete VAT invoice records after setup.")
        ],
    )
    request.options.review_depth = "deep"
    request.options.throttle_deep = True
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert throttled_generator.prompts
    assert deep_generator.prompts == []
    assert pair["findings"][0].classification == "contradiction"
    assert engine.model_profile_for_request(request) == "deep_throttled=ollama:deepseek-r1:32b"


def test_throttled_ollama_profile_defaults_to_cpu_safe_options(monkeypatch) -> None:
    for name in (
        "KP_COMPLIANCE_DEEP_THROTTLED_LLM_NUM_BATCH",
        "KP_COMPLIANCE_DEEP_THROTTLED_LLM_NUM_GPU",
        "KP_COMPLIANCE_DEEP_THROTTLED_LLM_NUM_THREAD",
        "KP_COMPLIANCE_DEEP_THROTTLED_LLM_COOLDOWN_SECONDS",
    ):
        monkeypatch.delenv(name, raising=False)

    generator = _ollama_generator_from_env(
        "DEEP_THROTTLED",
        base_url="http://ollama.test",
        model="deepseek-r1:32b",
        default_num_ctx=4096,
        default_timeout=120,
        throttle_enabled=True,
    )

    assert generator.num_ctx == 4096
    assert generator.extra_options["num_batch"] == 16
    assert generator.extra_options["num_gpu"] == 0
    assert generator.extra_options["num_thread"] == 4
    assert generator.cooldown_seconds == 3


def test_agentic_review_parses_reasoning_model_json() -> None:
    generator = FakeGenerator(
        """
        <think>
        The two passages discuss the same VAT invoice record obligation.
        </think>
        ```json
        {
          "same_obligation": true,
          "classification": "supported",
          "severity": "low",
          "confidence": 0.88,
          "rationale": "Both passages require keeping VAT invoice records.",
          "recommended_action": "No change required."
        }
        ```
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
                "Finance teams must keep VAT invoice records for audit.",
            )
        ],
    )

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert generator.prompts
    assert pair["findings"][0].classification == "supported"
    assert pair["findings"][0].confidence == 0.88


def test_agentic_review_keeps_supported_coverage_with_shared_governed_anchor() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "supported",
          "severity": "low",
          "confidence": 0.87,
          "rationale": "Both passages require keeping VAT invoice records.",
          "recommended_action": "No change required."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator)
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "vat-notice-700",
                "VAT guide (VAT Notice 700)",
                "Finance teams must keep a record of the VAT invoices they receive for audit evidence.",
            )
        ],
        internal_documents=[
            internal_document(
                "finance-pack",
                "Finance controls pack",
                "Finance teams must keep VAT invoice records as valid evidence after reclaiming input tax.",
            )
        ],
    )

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert generator.prompts
    assert len(pair["findings"]) == 1
    assert pair["findings"][0].classification == "supported"


def test_agentic_review_suppresses_weak_supported_coverage_without_anchor() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "supported",
          "severity": "low",
          "confidence": 0.9,
          "rationale": "Both passages discuss VAT calculations.",
          "recommended_action": "No change required."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator)
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "vat-notice-700",
                "VAT guide (VAT Notice 700)",
                "You can then work out the amount of VAT you can treat as input tax.",
            )
        ],
        internal_documents=[
            internal_document(
                "synthetic-vat-pack",
                "Synthetic VAT Conflict Learning Pack",
                "Users must work out what proportion of service use is for business purposes as per VAT regulations.",
            )
        ],
    )
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert generator.prompts
    assert pair["findings"] == []


def test_agentic_review_suppresses_supported_coverage_with_edit_recommendation() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "supported",
          "severity": "low",
          "confidence": 0.86,
          "rationale": "The passages align on VAT invoice retention.",
          "recommended_action": "Review internal processes to ensure all VAT invoices are retained as required by law.",
          "proposed_internal_text": "Finance teams must keep all VAT invoices as required by law."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator)
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "vat-notice-700",
                "VAT guide (VAT Notice 700)",
                "To reclaim VAT you must hold valid evidence that you have received a taxable supply.",
            )
        ],
        internal_documents=[
            internal_document(
                "synthetic-vat-pack",
                "Synthetic VAT Conflict Learning Pack",
                "Finance teams must keep VAT invoices as valid evidence after reclaiming input tax.",
            )
        ],
    )
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert generator.prompts
    assert pair["findings"] == []


def test_agentic_review_keeps_strong_supported_coverage_with_generic_action_language() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "supported",
          "severity": "low",
          "confidence": 0.86,
          "rationale": "The internal wording implements the same meaningful-image text alternative requirement.",
          "recommended_action": "Ensure the image approval checklist keeps this control visible."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator)
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "image-accessibility",
                "Accessibility guidance",
                "Meaningful images must have text alternatives that describe their purpose.",
            )
        ],
        internal_documents=[
            internal_document(
                "image-pack",
                "Article image setup pack",
                "Meaningful article images must include alt text that explains the image purpose before approval.",
            )
        ],
    )
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert generator.prompts
    assert len(pair["findings"]) == 1
    assert pair["findings"][0].classification == "supported"
    assert not any(reason.startswith("supported_coverage_gate:") for reason in pair["diagnostics"]["gate_demotion_reasons"])


def test_agentic_review_keeps_supported_coverage_for_aligned_negative_requirement() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "supported",
          "severity": "low",
          "confidence": 0.85,
          "rationale": "Both passages require operation without mouse-only interaction.",
          "recommended_action": "No action needed; both align well."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator)
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "keyboard-accessibility",
                "Accessibility guidance",
                "All functionality must be operable with a keyboard without requiring a mouse.",
            )
        ],
        internal_documents=[
            internal_document(
                "form-controls",
                "Form component design pack",
                "Interactive form controls must support keyboard operation and must not require mouse-only actions.",
            )
        ],
    )
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert generator.prompts
    assert len(pair["findings"]) == 1
    assert pair["findings"][0].classification == "supported"
    assert not any(reason.startswith("direct_conflict_guard:") for reason in pair["diagnostics"]["gate_demotion_reasons"])


def test_agentic_review_suppresses_goods_services_supported_mismatch() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "supported",
          "severity": "low",
          "confidence": 0.85,
          "rationale": "Both passages discuss VAT reclaim for private use.",
          "recommended_action": "No action needed; both align well."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator)
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "vat-notice-700",
                "VAT guide (VAT Notice 700)",
                "If you choose, you may reclaim all the tax on the goods as input tax and then account for output tax.",
            )
        ],
        internal_documents=[
            internal_document(
                "synthetic-vat-pack",
                "Synthetic VAT Conflict Learning Pack",
                "If a service is used for both business and private purposes, the full VAT amount may be reclaimed.",
            )
        ],
    )
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert generator.prompts
    assert pair["findings"] == []


def test_agentic_review_keeps_low_alignment_contradiction_with_shared_anchor() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "contradiction",
          "severity": "medium",
          "confidence": 0.85,
          "rationale": "External evidence requires keeping invoice evidence, while internal wording permits deleting VAT invoice records.",
          "recommended_action": "Align internal VAT record retention wording."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator)
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "vat-notice-700",
                "VAT guide (VAT Notice 700)",
                "If you treat a payment as a disbursement for VAT purposes then you must keep evidence, "
                "such as an order form or a copy invoice.",
            )
        ],
        internal_documents=[
            internal_document(
                "synthetic-vat-pack",
                "Synthetic VAT Conflict Learning Pack",
                "Finance teams may delete VAT invoice records immediately after matching payment.",
            )
        ],
    )
    request.options.min_pair_relevance_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert generator.prompts
    assert len(pair["findings"]) == 1
    assert pair["findings"][0].classification == "contradiction"


def test_agentic_review_consolidates_action_findings_by_internal_wording() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "contradiction",
          "severity": "medium",
          "confidence": 0.85,
          "rationale": "External evidence requires keeping invoice evidence, while internal wording permits deleting VAT invoice records.",
          "recommended_action": "Align internal VAT record retention wording."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator)
    external = EvidenceDocument(
        id="vat-notice-700",
        title="VAT guide (VAT Notice 700)",
        source_type="external",
        url="https://www.gov.uk/guidance/vat-guide-notice-700",
        content_sha256="hash-vat",
        sections=[
            EvidenceSection(
                id="vat-disbursements",
                heading="Disbursement evidence",
                text="If you treat a payment as a disbursement for VAT purposes then you must keep evidence, such as a copy invoice.",
            ),
            EvidenceSection(
                id="vat-invoice-copies",
                heading="Invoice copies",
                text="Unless an exception applies, you must keep a copy of all VAT invoices that you issue.",
            ),
        ],
    )
    request = ComplianceReviewRequest(
        external_documents=[external],
        internal_documents=[
            internal_document(
                "synthetic-vat-pack",
                "Synthetic VAT Conflict Learning Pack",
                "Finance teams may delete VAT invoice records immediately after matching payment.",
            )
        ],
    )
    request.options.min_pair_relevance_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert len(generator.prompts) == 2
    assert len(pair["findings"]) == 1
    finding = pair["findings"][0]
    assert finding.classification == "contradiction"
    assert "consolidated_related_findings=2" in finding.signals


def test_agentic_review_suppresses_low_alignment_contradiction_decision() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "contradiction",
          "severity": "high",
          "confidence": 0.82,
          "rationale": "The internal wording weakens the external wording.",
          "recommended_action": "Review the policy."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator)
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "vat-notice-700",
                "VAT guide (VAT Notice 700)",
                "The VAT report must include invoice appendix details for audit review before quarterly filing.",
            )
        ],
        internal_documents=[
            internal_document(
                "pack-7",
                "Pack 7: Article Lists Criteria Logic and Controlled List Usage",
                "The invoice appendix may be archived with process documentation after supplier setup is complete.",
            )
        ],
    )
    request.options.min_pair_relevance_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert generator.prompts
    assert pair["findings"] == []


def test_agentic_review_suppresses_vat_list_permission_false_positive() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "contradiction",
          "severity": "low",
          "confidence": 0.8,
          "rationale": "The passages appear to describe different permission scopes.",
          "recommended_action": "Review and reconcile the scope of permissions."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator)
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "vat-notice-700",
                "VAT guide (VAT Notice 700)",
                "You may do this for all your affected supplies or only some of them.",
            )
        ],
        internal_documents=[
            internal_document(
                "pack-7",
                "Pack 7: Article Lists Criteria Logic and Controlled List Usage",
                "Some lists can be limited to authorised profiles where only certain users should see or use them.",
            )
        ],
    )
    request.options.min_pair_relevance_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert pair["findings"] == []


def test_agentic_review_suppresses_rate_change_timing_false_positive() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "contradiction",
          "severity": "high",
          "confidence": 0.9,
          "rationale": "The passages appear to conflict on VAT rate changes.",
          "recommended_action": "Review the VAT rate change rule."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator)
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "vat-notice-700",
                "VAT guide (VAT Notice 700)",
                "When the amount of VAT to be charged goes down, you can charge tax at the new rate on goods "
                "removed or services performed after the date of the change, even though payment has been received.",
            )
        ],
        internal_documents=[
            internal_document(
                "synthetic-vat-pack",
                "Synthetic VAT Conflict Learning Pack",
                "When a VAT rate changes, invoices must show the old VAT rate for supplies made before the change date.",
            )
        ],
    )
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert generator.prompts
    assert pair["findings"] == []


def test_agentic_review_does_not_rescue_broad_rate_change_contradiction() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "contradiction",
          "severity": "high",
          "confidence": 0.88,
          "rationale": "The external source mandates old-rate invoice display while the internal passage allows dated rate setup.",
          "recommended_action": "Review the VAT rate wording."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator)
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "vat-notice-700",
                "VAT guide (VAT Notice 700)",
                "The VAT invoice must show the old rate of tax.",
            )
        ],
        internal_documents=[
            internal_document(
                "pack-6",
                "Pack 6: Article Integration Tax Handling Product Change and Article Lists",
                "They can be handled by closing the old rate and opening a new, dated parameter-level rate definition.",
            )
        ],
    )
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert generator.prompts
    assert pair["findings"] == []


def test_agentic_review_reclassifies_omitted_exception_as_missing_detail() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "contradiction",
          "severity": "high",
          "confidence": 0.88,
          "rationale": "The internal policy does not include the external exception.",
          "recommended_action": "Revise the internal passage."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator)
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "vat-notice-700",
                "VAT guide (VAT Notice 700)",
                "Unless you make retail supplies and issue less detailed VAT invoices, you must keep a copy of all "
                "VAT invoices that you issue.",
            )
        ],
        internal_documents=[
            internal_document(
                "synthetic-vat-pack",
                "Synthetic VAT Conflict Learning Pack",
                "Finance teams must keep all VAT invoices as per legal requirements, even after reclaiming input tax.",
            )
        ],
    )
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert generator.prompts
    assert len(pair["findings"]) == 1
    finding = pair["findings"][0]
    assert finding.classification == "missing_detail"
    assert finding.severity == "medium"


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
    assert pair["classification"] == "contradiction"
    assert pair["findings"][0].classification == "contradiction"


def test_agentic_review_retains_rejected_not_related_candidate_when_requested() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": false,
          "classification": "not_related",
          "severity": "low",
          "confidence": 0.88,
          "rationale": "The passages mention business use, but one is VAT apportionment and the other is list logic.",
          "advisor_summary": "These are different governance topics.",
          "why_it_matters": "The pair should not become a missing obligation finding.",
          "recommended_action": "No action.",
          "proposed_internal_text": "",
          "confidence_interpretation": "High confidence.",
          "evidence_highlights": ["VAT business use", "list business use"]
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator, model_name="fake")
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "vat-business-use",
                "VAT guide",
                "You must work out what proportion of the use of the services is for business purposes.",
            )
        ],
        internal_documents=[
            internal_document(
                "list-pack",
                "Article list controls",
                "List logic must always be matched to the real business use case.",
            )
        ],
    )
    request.options.include_missing_obligations = True
    request.options.include_not_related_pairs = True
    request.options.min_pair_relevance_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert pair["classification"] == "not_related"
    assert pair["findings"][0].classification == "not_related"
    assert pair["diagnostics"]["missing_obligation_fallback_count"] == 0
    assert pair["diagnostics"]["rejected_candidate_finding_count"] == 1


def test_agentic_review_uses_packaging_anchor_rescue_for_too_vague_pair() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "too_vague",
          "severity": "medium",
          "confidence": 0.84,
          "rationale": "The internal wording mentions packaging details but does not require material-category reporting.",
          "recommended_action": "Add the material-category reporting requirement."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator, model_name="fake")
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "packaging-material",
                "Packaging reporting",
                "Packaging weights must be reported separately by material category.",
            )
        ],
        internal_documents=[
            internal_document(
                "product-pack",
                "Product setup pack",
                "Capture packaging details in the product record.",
            )
        ],
    )
    request.options.min_pair_relevance_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert generator.prompts
    assert pair["classification"] == "too_vague"
    assert pair["diagnostics"]["anchor_candidate_count"] == 1
    assert pair["diagnostics"]["missing_obligation_fallback_count"] == 0


def test_agentic_review_uses_embedding_rescue_for_low_lexical_candidate() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "missing_detail",
          "severity": "medium",
          "confidence": 0.82,
          "rationale": "The passages cover the same approval evidence topic but the internal wording misses the retention detail.",
          "recommended_action": "Clarify how long approval evidence must be held."
        }
        """
    )
    embedder = FakeEmbedder()
    engine = AgenticComplianceEngine(generator=generator, model_name="fake", embedder=embedder)
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "approval-evidence",
                "Approval evidence rule",
                "Controllers must retain approval evidence for each access review.",
            )
        ],
        internal_documents=[
            internal_document(
                "permission-checks",
                "Permission checks pack",
                "Owners should hold sign-off artefacts after permission checks.",
            )
        ],
    )
    request.options.min_pair_relevance_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert generator.prompts
    assert len(embedder.texts) == 2
    assert pair["classification"] == "missing_detail"
    assert pair["diagnostics"]["semantic_candidate_count"] == 1
    assert pair["diagnostics"]["semantic_attempt_count"] == 1
    assert pair["diagnostics"]["max_semantic_score"] == 1.0
    assert pair["diagnostics"]["missing_obligation_fallback_count"] == 0


def test_agentic_review_resolves_low_alignment_no_candidate_as_not_related() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "contradiction",
          "severity": "high",
          "confidence": 0.9,
          "rationale": "This response should not be used.",
          "recommended_action": "No action."
        }
        """
    )
    engine = AgenticComplianceEngine(
        generator=generator,
        model_name="fake",
        embedder=LowSimilarityEmbedder(),
        min_semantic_candidate_score=0.58,
    )
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "bribery-procedures",
                "Bribery Act",
                "A commercial organisation must maintain anti-bribery procedures for associated persons.",
            )
        ],
        internal_documents=[
            internal_document(
                "stock-lists",
                "Stock list controls",
                "Seasonal stock lists can be limited to merchandising profiles.",
            )
        ],
    )
    request.options.include_missing_obligations = True
    request.options.include_not_related_pairs = True
    request.options.min_pair_relevance_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert generator.prompts == []
    assert pair["classification"] == "not_related"
    assert pair["findings"][0].classification == "not_related"
    assert pair["diagnostics"]["no_candidate_resolution"] == "not_related"
    assert pair["diagnostics"]["no_candidate_not_related_count"] == 1
    assert pair["diagnostics"]["missing_obligation_fallback_count"] == 0


def test_agentic_review_screens_no_candidate_pair_before_deep_adjudication() -> None:
    generator = SequencedFakeGenerator(
        [
            """
            {
              "same_obligation": true,
              "confidence": 0.82,
              "rationale": "Both passages concern improper financial advantages."
            }
            """,
            """
            {
              "same_obligation": true,
              "classification": "contradiction",
              "severity": "high",
              "confidence": 0.88,
              "rationale": "External evidence prohibits improper advantages while internal wording permits facilitation payments.",
              "recommended_action": "Remove the facilitation payment permission."
            }
            """,
        ]
    )
    engine = AgenticComplianceEngine(
        generator=generator,
        model_name="fake",
        depth_generators={"balanced": generator, "deep": generator},
        depth_model_names={"balanced": "fake-balanced", "deep": "fake-deep"},
        embedder=MediumSimilarityEmbedder(),
        min_semantic_candidate_score=0.58,
    )
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "approval-control",
                "Approval control",
                "The approval control must not permit small acceleration payments for routine supplier onboarding.",
            )
        ],
        internal_documents=[
            internal_document(
                "supplier-pack",
                "Supplier controls pack",
                "Routine supplier onboarding can use small acceleration payments where the approval delay is minor.",
            )
        ],
    )
    request.options.review_depth = "deep"
    request.options.include_missing_obligations = True
    request.options.include_not_related_pairs = True
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.9

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert len(generator.prompts) == 2
    assert "decide only whether" in generator.prompts[0]
    assert pair["classification"] == "contradiction"
    assert pair["diagnostics"]["same_obligation_screen_count"] == 1
    assert pair["diagnostics"]["same_obligation_screen_pass_count"] == 1
    assert pair["diagnostics"]["adjudication_count"] == 1
    assert pair["diagnostics"]["semantic_candidate_count"] == 0
    assert pair["diagnostics"]["candidate_count"] == 1


def test_agentic_review_screen_error_returns_human_review_not_missing_obligation() -> None:
    generator = FakeGenerator("not json")
    engine = AgenticComplianceEngine(
        generator=generator,
        model_name="fake",
        depth_generators={"balanced": generator, "deep": generator},
        depth_model_names={"balanced": "fake-balanced", "deep": "fake-deep"},
        embedder=MediumSimilarityEmbedder(),
        min_semantic_candidate_score=0.58,
    )
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "approval-control",
                "Approval control",
                "The approval control must not permit small acceleration payments for routine supplier onboarding.",
            )
        ],
        internal_documents=[
            internal_document(
                "supplier-pack",
                "Supplier controls pack",
                "Routine supplier onboarding can use small acceleration payments where the approval delay is minor.",
            )
        ],
    )
    request.options.review_depth = "deep"
    request.options.include_missing_obligations = True
    request.options.include_not_related_pairs = True
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.9

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert pair["classification"] == "needs_human_review"
    assert pair["findings"][0].classification == "needs_human_review"
    assert pair["diagnostics"]["same_obligation_screen_count"] == 1
    assert pair["diagnostics"]["same_obligation_screen_error_count"] == 1
    assert pair["diagnostics"]["same_obligation_screen_errors"][0].startswith("ValueError:")
    assert pair["diagnostics"]["no_candidate_resolution"] == "screen_error_needs_human_review"
    assert pair["diagnostics"]["missing_obligation_fallback_count"] == 0


def test_agentic_review_falls_back_to_primary_screen_after_balanced_error() -> None:
    balanced_generator = FakeGenerator("not json")
    deep_generator = SequencedFakeGenerator(
        [
            """
            {
              "same_obligation": true,
              "confidence": 0.84,
              "rationale": "Both passages concern facilitation payments and improper financial advantage."
            }
            """,
            """
            {
              "same_obligation": true,
              "classification": "contradiction",
              "severity": "high",
              "confidence": 0.88,
              "rationale": "External evidence prohibits improper advantages while internal wording permits payments.",
              "recommended_action": "Remove the facilitation payment permission."
            }
            """,
        ]
    )
    engine = AgenticComplianceEngine(
        generator=deep_generator,
        model_name="fake",
        depth_generators={"balanced": balanced_generator, "deep": deep_generator},
        depth_model_names={"balanced": "fake-balanced", "deep": "fake-deep"},
        embedder=MediumSimilarityEmbedder(),
        min_semantic_candidate_score=0.58,
    )
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "approval-control",
                "Approval control",
                "The approval control must not permit small acceleration payments for routine supplier onboarding.",
            )
        ],
        internal_documents=[
            internal_document(
                "supplier-pack",
                "Supplier controls pack",
                "Routine supplier onboarding can use small acceleration payments where the approval delay is minor.",
            )
        ],
    )
    request.options.review_depth = "deep"
    request.options.include_missing_obligations = True
    request.options.include_not_related_pairs = True
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.9

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert pair["classification"] == "contradiction"
    assert pair["diagnostics"]["same_obligation_screen_count"] == 1
    assert pair["diagnostics"]["same_obligation_screen_fallback_count"] == 1
    assert pair["diagnostics"]["same_obligation_screen_error_count"] == 0
    assert pair["diagnostics"]["same_obligation_screen_pass_count"] == 1
    assert len(deep_generator.prompts) == 2


def test_agentic_review_screen_reject_keeps_in_scope_missing_obligation() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": false,
          "confidence": 0.2,
          "rationale": "Supplier approval records do not state the input tax evidence rule."
        }
        """
    )
    engine = AgenticComplianceEngine(
        generator=generator,
        model_name="fake",
        depth_generators={"balanced": generator, "deep": generator},
        depth_model_names={"balanced": "fake-balanced", "deep": "fake-deep"},
        embedder=MediumSimilarityEmbedder(),
        min_semantic_candidate_score=0.58,
    )
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "vat-guide",
                "VAT guide Notice 700",
                "Input tax claims must be supported by valid VAT evidence.",
            )
        ],
        internal_documents=[
            internal_document(
                "vat-operations-pack",
                "VAT operations pack",
                "Supplier approval steps should be maintained by the finance team.",
            )
        ],
    )
    request.options.review_depth = "deep"
    request.options.include_missing_obligations = True
    request.options.include_not_related_pairs = True
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.9

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert pair["classification"] == "missing_obligation"
    assert pair["diagnostics"]["no_candidate_resolution"] == "screen_rejected_missing_obligation"
    assert pair["diagnostics"]["missing_obligation_fallback_count"] == 1
    assert pair["diagnostics"]["no_candidate_not_related_count"] == 0


def test_agentic_review_screen_reject_keeps_unrelated_pair_not_related() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": false,
          "confidence": 0.8,
          "rationale": "Supplier contract design is unrelated to packaging material reporting."
        }
        """
    )
    engine = AgenticComplianceEngine(
        generator=generator,
        model_name="fake",
        depth_generators={"balanced": generator, "deep": generator},
        depth_model_names={"balanced": "fake-balanced", "deep": "fake-deep"},
        embedder=MediumSimilarityEmbedder(),
        min_semantic_candidate_score=0.58,
    )
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "packaging-guidance",
                "Packaging waste producer responsibility guidance",
                "Packaging weights must be reported separately by material category.",
            )
        ],
        internal_documents=[
            internal_document(
                "supplier-pack",
                "Supplier master data pack",
                "Where a supplier has materially different fulfilment rules, multiple commercial contracts may be needed.",
            )
        ],
    )
    request.options.review_depth = "deep"
    request.options.include_missing_obligations = True
    request.options.include_not_related_pairs = True
    request.options.min_pair_relevance_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert pair["classification"] == "not_related"
    assert pair["diagnostics"]["no_candidate_resolution"] == "screen_rejected_not_related"
    assert pair["diagnostics"]["missing_obligation_fallback_count"] == 0
    assert pair["diagnostics"]["no_candidate_not_related_count"] == 1


def test_agentic_review_screen_reject_does_not_use_external_title_as_source_family() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": false,
          "confidence": 0.82,
          "rationale": "Age-restricted article lists are unrelated to packaging record retention."
        }
        """
    )
    engine = AgenticComplianceEngine(
        generator=generator,
        model_name="fake",
        depth_generators={"balanced": generator, "deep": generator},
        depth_model_names={"balanced": "fake-balanced", "deep": "fake-deep"},
        embedder=MediumSimilarityEmbedder(),
        min_semantic_candidate_score=0.58,
    )
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "packaging-guidance",
                "Packaging waste producer responsibility guidance",
                "Businesses must retain packaging calculation records after submission.",
            )
        ],
        internal_documents=[
            internal_document(
                "article-list-pack",
                "Article list controls pack",
                "Age-restricted products should be grouped into controlled lists with restricted user access.",
            )
        ],
    )
    request.options.review_depth = "deep"
    request.options.include_missing_obligations = True
    request.options.include_not_related_pairs = True
    request.options.min_pair_relevance_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert pair["classification"] == "not_related"
    assert pair["diagnostics"]["no_candidate_resolution"] == "screen_rejected_not_related"
    assert pair["diagnostics"]["missing_obligation_fallback_count"] == 0
    assert pair["diagnostics"]["no_candidate_not_related_count"] == 1


def test_agentic_review_screen_reject_polarity_override_reaches_deep_adjudication() -> None:
    balanced_generator = FakeGenerator(
        """
        {
          "same_obligation": false,
          "confidence": 0.4,
          "rationale": "The wording is not a close semantic match."
        }
        """
    )
    deep_generator = FakeGenerator(
        """
        {
          "same_obligation": false,
          "classification": "not_related",
          "severity": "low",
          "confidence": 0.72,
          "rationale": "The model missed the polarity conflict."
        }
        """
    )
    engine = AgenticComplianceEngine(
        generator=deep_generator,
        model_name="fake",
        depth_generators={"balanced": balanced_generator, "deep": deep_generator},
        depth_model_names={"balanced": "fake-balanced", "deep": "fake-deep"},
        embedder=MediumSimilarityEmbedder(),
        min_semantic_candidate_score=0.58,
    )
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "approval-control",
                "Approval control",
                "The approval control must not permit small acceleration payments for routine supplier onboarding.",
            )
        ],
        internal_documents=[
            internal_document(
                "supplier-pack",
                "Supplier controls pack",
                "Routine supplier onboarding can use small acceleration payments where the approval delay is minor.",
            )
        ],
    )
    request.options.review_depth = "deep"
    request.options.include_missing_obligations = True
    request.options.include_not_related_pairs = True
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.9

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert pair["classification"] == "contradiction"
    assert pair["diagnostics"]["same_obligation_screen_override_count"] == 1
    assert pair["diagnostics"]["adjudication_count"] == 1
    assert any(reason.startswith("direct_conflict_guard:") for reason in pair["diagnostics"]["gate_demotion_reasons"])


def test_agentic_review_keeps_confident_same_obligation_contradiction_with_sparse_overlap() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "contradiction",
          "severity": "high",
          "confidence": 0.86,
          "rationale": "The external requires cancellation rights before binding; the internal delays them.",
          "recommended_action": "Restore the cancellation-rights wording before publication."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator, model_name="fake")
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "consumer-rights-guidance",
                "Consumer rights guidance",
                "Customers must receive cancellation rights before they are bound by a distance contract.",
            )
        ],
        internal_documents=[
            internal_document(
                "customer-policy-pack",
                "Customer policy pack",
                "Cancellation rights can be sent only after the order is dispatched.",
            )
        ],
    )
    request.options.review_depth = "deep"
    request.options.include_not_related_pairs = True
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert pair["classification"] == "contradiction"
    assert not any(
        reason.startswith("contradiction_safety_gate:")
        for reason in pair["diagnostics"]["gate_demotion_reasons"]
    )


def test_agentic_review_training_evidence_negation_is_contradiction() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": false,
          "classification": "not_related",
          "severity": "low",
          "confidence": 0.72,
          "rationale": "The model missed the training evidence conflict."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator, model_name="fake")
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "bribery-guidance",
                "Adequate procedures guidance",
                "Commercial organisations must communicate anti-bribery training to third parties that perform services for them.",
            )
        ],
        internal_documents=[
            internal_document(
                "anti-bribery-pack",
                "Anti-bribery controls pack",
                "No training evidence is required for third parties after contract approval.",
            )
        ],
    )
    request.options.review_depth = "deep"
    request.options.include_not_related_pairs = True
    request.options.min_pair_relevance_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert pair["classification"] == "contradiction"
    assert pair["diagnostics"]["candidate_count"] == 1
    assert any(reason.startswith("direct_conflict_guard:") for reason in pair["diagnostics"]["gate_demotion_reasons"])


def test_agentic_review_vat_input_tax_supplier_records_gap_is_missing_obligation() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": false,
          "classification": "not_related",
          "severity": "low",
          "confidence": 0.76,
          "rationale": "Supplier approval records do not directly mention input tax evidence."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator, model_name="fake")
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "vat-guide",
                "VAT guide Notice 700",
                "You must keep certain records to be able to reclaim input tax.",
            )
        ],
        internal_documents=[
            internal_document(
                "supplier-pack",
                "Supplier master data pack",
                "Supplier records should include payment terms, contract references and banking validation before approval.",
            )
        ],
    )
    request.options.review_depth = "deep"
    request.options.include_missing_obligations = True
    request.options.include_not_related_pairs = True
    request.options.min_pair_relevance_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert pair["classification"] == "missing_obligation"
    assert pair["diagnostics"]["gate_demotion_reason"].startswith("class_boundary_guard:not_related->missing_obligation")


def test_agentic_review_class_boundary_restores_too_vague_from_not_related() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": false,
          "classification": "not_related",
          "severity": "low",
          "confidence": 0.74,
          "rationale": "The internal passage is too generic."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator, model_name="fake")
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "packaging-guidance",
                "Packaging guidance",
                "Packaging weights must be reported separately by material category.",
            )
        ],
        internal_documents=[
            internal_document(
                "packaging-pack",
                "Packaging pack",
                "Capture packaging details in the product record.",
            )
        ],
    )
    request.options.review_depth = "deep"
    request.options.include_not_related_pairs = True
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert pair["classification"] == "too_vague"
    assert pair["findings"][0].classification == "too_vague"
    assert pair["diagnostics"]["gate_demotion_reason"].startswith("class_boundary_guard:not_related->too_vague")


def test_agentic_review_class_boundary_restores_missing_detail_from_not_related() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": false,
          "classification": "not_related",
          "severity": "low",
          "confidence": 0.74,
          "rationale": "The internal passage does not mention household scope."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator, model_name="fake")
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "packaging-guidance",
                "Packaging guidance",
                "Reported packaging data must distinguish household packaging from non-household packaging where the rules require it.",
            )
        ],
        internal_documents=[
            internal_document(
                "packaging-pack",
                "Packaging pack",
                "Packaging data must be submitted using the approved reporting template.",
            )
        ],
    )
    request.options.review_depth = "deep"
    request.options.include_not_related_pairs = True
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert pair["classification"] == "missing_detail"
    assert pair["findings"][0].classification == "missing_detail"
    assert pair["diagnostics"]["gate_demotion_reason"].startswith("class_boundary_guard:not_related->missing_detail")


def test_agentic_review_rate_change_correction_too_vague_becomes_missing_detail() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "too_vague",
          "severity": "medium",
          "confidence": 0.74,
          "rationale": "The internal wording omits invoice correction detail."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator, model_name="fake")
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "vat-guide",
                "VAT guide",
                "When a VAT rate change affects a supply, the correct rate depends on the tax point and may require an invoice correction.",
            )
        ],
        internal_documents=[
            internal_document(
                "vat-pack",
                "VAT rate controls pack",
                "Use the old VAT rate when the supply happened before the rate change date.",
            )
        ],
    )
    request.options.review_depth = "deep"
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert pair["classification"] == "missing_detail"
    assert pair["diagnostics"]["gate_demotion_reason"].startswith("class_boundary_guard:too_vague->missing_detail")


def test_agentic_review_credit_note_gap_becomes_missing_obligation() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": false,
          "classification": "not_related",
          "severity": "low",
          "confidence": 0.7,
          "rationale": "The internal passage discusses dated tax parameters."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator, model_name="fake")
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "vat-guide",
                "VAT guide",
                "If VAT has been charged at the wrong rate, the VAT account and invoice evidence must be corrected.",
            )
        ],
        internal_documents=[
            internal_document(
                "vat-pack",
                "Tax parameter pack",
                "VAT rates can be added as dated parameter records in the tax setup tool.",
            )
        ],
    )
    request.options.review_depth = "deep"
    request.options.include_missing_obligations = True
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert pair["classification"] == "missing_obligation"
    assert pair["diagnostics"]["gate_demotion_reason"].startswith("class_boundary_guard:not_related->missing_obligation")


def test_agentic_review_packaging_deadline_gap_becomes_missing_obligation() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": false,
          "classification": "not_related",
          "severity": "low",
          "confidence": 0.7,
          "rationale": "The internal passage does not define the deadline."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator, model_name="fake")
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "packaging-guidance",
                "Packaging waste producer responsibility guidance",
                "Packaging submissions must be completed by the applicable reporting deadline.",
            )
        ],
        internal_documents=[
            internal_document(
                "packaging-pack",
                "Packaging data pack",
                "Packaging data should be available to the reporting team when requested.",
            )
        ],
    )
    request.options.review_depth = "deep"
    request.options.include_missing_obligations = True
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert pair["classification"] == "missing_obligation"
    assert pair["diagnostics"]["gate_demotion_reason"].startswith("class_boundary_guard:not_related->missing_obligation")


def test_agentic_review_packaging_category_detail_becomes_missing_detail() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": false,
          "classification": "not_related",
          "severity": "low",
          "confidence": 0.7,
          "rationale": "The internal passage omits material categories."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator, model_name="fake")
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "packaging-guidance",
                "Packaging waste producer responsibility guidance",
                "Packaging data must identify material categories such as plastic, paper, glass and metal.",
            )
        ],
        internal_documents=[
            internal_document(
                "packaging-pack",
                "Packaging controls pack",
                "Packaging weights must be recorded for each item.",
            )
        ],
    )
    request.options.review_depth = "deep"
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert pair["classification"] == "missing_detail"
    assert pair["diagnostics"]["gate_demotion_reason"].startswith("class_boundary_guard:not_related->missing_detail")


def test_agentic_review_packaging_reusable_detail_becomes_missing_detail() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": false,
          "classification": "not_related",
          "severity": "low",
          "confidence": 0.7,
          "rationale": "The internal passage names packaging but not reusable packaging."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator, model_name="fake")
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "packaging-guidance",
                "Packaging waste producer responsibility guidance",
                "Reusable packaging must be treated according to the applicable packaging category and evidence rules.",
            )
        ],
        internal_documents=[
            internal_document(
                "packaging-pack",
                "Packaging controls pack",
                "Packaging should be included in the packaging dataset.",
            )
        ],
    )
    request.options.review_depth = "deep"
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert pair["classification"] == "missing_detail"
    assert pair["diagnostics"]["gate_demotion_reason"].startswith("class_boundary_guard:not_related->missing_detail")


def test_direct_conflict_guard_does_not_promote_plain_missing_detail_gap() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": false,
          "classification": "not_related",
          "severity": "low",
          "confidence": 0.7,
          "rationale": "The internal passage discusses VAT parameter setup rather than invoice correction."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator, model_name="fake")
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "vat-guide",
                "VAT guide",
                "If VAT has been charged at the wrong rate, the VAT account and invoice evidence must be corrected.",
            )
        ],
        internal_documents=[
            internal_document(
                "vat-pack",
                "VAT pack",
                "VAT rates can be added as dated parameter records in the tax setup tool.",
            )
        ],
    )
    request.options.review_depth = "deep"
    request.options.include_not_related_pairs = True
    request.options.min_pair_relevance_score = 0.0
    request.options.min_alignment_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert pair["classification"] != "contradiction"
    assert not any(reason.startswith("direct_conflict_guard:") for reason in pair["diagnostics"]["gate_demotion_reasons"])


def test_agentic_review_does_not_default_empty_pair_to_supported() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "supported",
          "severity": "low",
          "confidence": 0.8,
          "rationale": "This response should not be used."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator, model_name="fake")
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "bribery-guidance",
                "Bribery guidance",
                "A person is associated with a commercial organisation if they perform services for that organisation.",
            )
        ],
        internal_documents=[
            internal_document(
                "anti-bribery-pack",
                "Anti-bribery pack",
                "Anti-bribery due diligence only applies to direct employees, not to consultants or service providers.",
            )
        ],
    )
    request.options.include_supported_findings = True
    request.options.min_pair_relevance_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert generator.prompts == []
    assert pair["classification"] == "needs_human_review"
    assert pair["findings"] == []


def test_agentic_supported_gate_blocks_generic_obligation_dismissal() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "supported",
          "severity": "low",
          "confidence": 0.84,
          "rationale": "The passages both mention anti-bribery checks for agents.",
          "recommended_action": "No action required."
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator, model_name="fake")
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "bribery-checks",
                "Bribery Act",
                "A commercial organisation must perform anti-bribery checks for agents.",
            )
        ],
        internal_documents=[
            internal_document(
                "bribery-pack",
                "Anti-bribery controls",
                "The organisation can ignore anti-bribery checks for agents.",
            )
        ],
    )
    request.options.min_pair_relevance_score = 0.0

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert generator.prompts
    assert pair["classification"] == "contradiction"
    assert pair["findings"][0].classification == "contradiction"
    assert "polarity" in pair["findings"][0].advisor_summary.lower()


def test_disable_safety_gates_preserves_raw_contradiction_for_ab_testing() -> None:
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "contradiction",
          "severity": "high",
          "confidence": 0.9,
          "rationale": "The internal wording denies the external VAT rate requirement.",
          "advisor_summary": "The rate-change rule conflicts.",
          "why_it_matters": "Incorrect VAT invoice rates create compliance risk.",
          "recommended_action": "Review the internal rate-change rule.",
          "proposed_internal_text": "",
          "confidence_interpretation": "High confidence.",
          "evidence_highlights": ["old rate must show", "old rate must not show"]
        }
        """
    )
    engine = AgenticComplianceEngine(generator=generator, model_name="fake")
    request = ComplianceReviewRequest(
        external_documents=[
            external_document(
                "vat-rate",
                "VAT guide",
                "The VAT invoice must show the old rate of tax for supplies made before the rate change date.",
            )
        ],
        internal_documents=[
            internal_document(
                "rate-pack",
                "VAT rate controls",
                "The old VAT rate must not be shown on customer VAT invoices.",
            )
        ],
    )
    request.options.include_missing_obligations = True
    request.options.include_not_related_pairs = True
    request.options.min_pair_relevance_score = 0.0

    gated_pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)
    request.options.disable_safety_gates = True
    ungated_pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert gated_pair["classification"] == "contradiction"
    assert gated_pair["diagnostics"]["gate_demotion_reason"] == ""
    assert ungated_pair["classification"] == "contradiction"
    assert ungated_pair["diagnostics"]["gate_demotion_reason"] == ""


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
    assert status["audit"]["prompt_version"] == "governance-review-agent-v8.6"


def test_env_engine_reports_configured_deepseek_model(monkeypatch) -> None:
    monkeypatch.setenv("KP_COMPLIANCE_AGENT_ENABLED", "1")
    monkeypatch.setenv("KP_COMPLIANCE_LLM_MODEL", "deepseek-r1:14b")

    client = TestClient(create_app())

    capabilities = client.get("/v1/capabilities").json()
    assert "ollama:deepseek-r1:8b" in capabilities["model_backends"]
    assert "ollama:deepseek-r1:14b" in capabilities["model_backends"]
    assert any("deepseek-r1:14b" in note for note in capabilities["notes"])


def test_env_engine_defaults_to_balanced_and_deep_profiles(monkeypatch) -> None:
    monkeypatch.setenv("KP_COMPLIANCE_AGENT_ENABLED", "1")
    monkeypatch.delenv("KP_COMPLIANCE_LLM_MODEL", raising=False)
    monkeypatch.delenv("KP_COMPLIANCE_BALANCED_LLM_MODEL", raising=False)
    monkeypatch.delenv("KP_COMPLIANCE_DEEP_LLM_MODEL", raising=False)
    monkeypatch.delenv("KP_LLM_MODEL", raising=False)

    client = TestClient(create_app())

    capabilities = client.get("/v1/capabilities").json()
    assert "ollama:deepseek-r1:8b" in capabilities["model_backends"]
    assert "ollama:qwen2.5:14b-instruct" in capabilities["model_backends"]
    assert any("deepseek-r1:8b" in note for note in capabilities["notes"])
    assert any("qwen2.5:14b-instruct" in note for note in capabilities["notes"])


def test_synthetic_vat_conflict_fixture_can_trigger_contradiction() -> None:
    fixture_text = Path("docs/data-and-governance/test-fixtures/synthetic-vat-conflict-learning-pack.md").read_text()
    generator = FakeGenerator(
        """
        {
          "same_obligation": true,
          "classification": "contradiction",
          "severity": "high",
          "confidence": 0.9,
          "rationale": "The internal fixture permits deleting VAT invoice records that the external source requires keeping.",
          "recommended_action": "Remove the incorrect VAT record deletion rule."
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
                "synthetic-vat-conflict",
                "Synthetic VAT Conflict Learning Pack",
                fixture_text,
            )
        ],
    )

    pair = engine.review_document_pair(request.external_documents[0], request.internal_documents[0], request)

    assert generator.prompts
    assert pair["findings"]
    finding = pair["findings"][0]
    assert finding.classification == "contradiction"
    assert finding.severity == "high"
    assert "delete VAT invoice records" in finding.internal_evidence.text


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
