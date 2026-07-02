"""Bounded governance-review agent for compliance pair adjudication."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from threading import Lock
from typing import Protocol

from .engine import (
    DeterministicComplianceEngine,
    _alignment_score,
    _best_obligation,
    _claim_as_obligation,
    _classify_pair,
    _dedupe_findings,
    _document_relevance_score,
    _duplicate_section_findings,
    _finding_id,
    _missing_obligation_finding,
    _not_related_finding,
    _severity_rank,
    _unsupported_claim_finding,
    _with_advisor_fields,
    extract_internal_claims,
    extract_obligations,
)
from .engine import (
    review_document_pair as _deterministic_external_pair,
)
from .engine import (
    review_internal_document_pair as _deterministic_internal_pair,
)
from .models import (
    ComplianceFinding,
    ComplianceReviewRequest,
    EvidenceDocument,
    ExtractedInternalClaim,
    ExtractedObligation,
    FindingClassification,
    FindingSeverity,
)

AGENT_PROMPT_VERSION = "governance-review-agent-v3"
LOW_SIGNAL_SHARED_TERMS = {
    "business",
    "case",
    "cases",
    "calculation",
    "calculations",
    "calculate",
    "charged",
    "new",
    "old",
    "rate",
    "rates",
    "some",
    "tax",
    "use",
    "used",
    "uses",
    "using",
    "vat",
    "work",
    "worked",
    "working",
}
MIN_CONCRETE_CONTRADICTION_TERMS = 3
MIN_SUPPORTED_STRONG_ALIGNMENT_SCORE = 0.45
ALLOWED_CLASSIFICATIONS = {
    "not_related",
    "supported",
    "contradiction",
    "duplicate",
    "too_vague",
    "missing_detail",
    "needs_human_review",
}
ALLOWED_SEVERITIES = {"low", "medium", "high"}
EXCEPTION_QUALIFIER_PATTERN = re.compile(r"\b(unless|except|except where|other than|save for|excluding)\b", re.I)
BROAD_REQUIREMENT_PATTERN = re.compile(r"\b(all|every|always|without exception|in every case)\b", re.I)
REQUIREMENT_PATTERN = re.compile(r"\b(must|shall|required|requires|keep|retain|record|records)\b", re.I)
SUPPLY_TIMING_TERMS_PATTERN = re.compile(r"\b(suppl(?:y|ies|ied)|goods removed|services performed)\b", re.I)
INVOICE_RECORD_PATTERN = re.compile(r"\b(invoice|invoices|copy invoice|vat invoice|vat invoices)\b", re.I)
RECORD_EVIDENCE_PATTERN = re.compile(
    r"\b(record|records|evidence|retain|retaining|retention|keep|keeping|copy|copies|hold|holding)\b",
    re.I,
)
BUSINESS_USE_PATTERN = re.compile(
    r"\b(business|private|non-business)\b.{0,80}\b(use|uses|purpose|purposes|proportion|percentage)|"
    r"\b(proportion|percentage)\b.{0,80}\b(business|private|non-business)\b",
    re.I,
)
RATE_CHANGE_PATTERN = re.compile(r"\b(rate|rates|old rate|new rate|tax point|change date)\b", re.I)
RATE_CHANGE_OBJECT_PATTERN = re.compile(r"\b(invoice|invoices|supply|supplies|goods removed|services performed|tax point)\b", re.I)
INPUT_TAX_EVIDENCE_PATTERN = re.compile(r"\b(input tax|deduction|reclaim|reclaimed|recover)\b", re.I)
DISBURSEMENT_EVIDENCE_PATTERN = re.compile(r"\b(disbursement|disbursements|principal|agent)\b", re.I)
HIGH_RISK_RESCUE_ANCHOR_TAGS = frozenset(
    {
        "invoice_records",
        "business_use_proportion",
        "input_tax_evidence",
        "disbursement_evidence",
    }
)
RATE_CHANGE_ANCHOR_TAGS = frozenset({"vat_rate_change"})
MIN_RATE_CHANGE_SUPPORTED_ALIGNMENT_SCORE = 0.32


class ComplianceGenerator(Protocol):
    def generate(self, prompt: str) -> str: ...


class OllamaComplianceGenerator:
    _global_lock = Lock()

    def __init__(
        self,
        *,
        model: str = "qwen2.5:7b-instruct",
        base_url: str = "http://127.0.0.1:11434",
        num_ctx: int = 8192,
        temperature: float = 0.0,
        timeout: float = 120.0,
        extra_options: dict[str, int | float | str | bool] | None = None,
        cooldown_seconds: float = 0.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.num_ctx = num_ctx
        self.temperature = temperature
        self.timeout = timeout
        self.extra_options = extra_options or {}
        self.cooldown_seconds = cooldown_seconds

    def generate(self, prompt: str) -> str:
        options: dict[str, int | float | str | bool] = {"num_ctx": self.num_ctx, "temperature": self.temperature}
        options.update(self.extra_options)
        payload = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": options,
            }
        ).encode()
        request = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        # Local Ollama calls compete for the same GPU. Serialising compliance calls
        # keeps concurrent review jobs from stacking load on top of one another.
        with self._global_lock:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read())
            if self.cooldown_seconds > 0:
                time.sleep(self.cooldown_seconds)
        generated = payload.get("response")
        if not isinstance(generated, str):
            raise ValueError("Ollama response did not include generated text.")
        return generated.strip()


@dataclass(frozen=True)
class AgentDecision:
    same_obligation: bool
    classification: FindingClassification
    severity: FindingSeverity
    confidence: float
    rationale: str
    recommended_action: str = ""
    advisor_summary: str = ""
    why_it_matters: str = ""
    proposed_internal_text: str = ""
    confidence_interpretation: str = ""
    evidence_highlights: tuple[str, ...] = ()


class GovernanceReviewAgent:
    """Small, bounded reviewer: no tools, no autonomous actions, JSON output only."""

    def __init__(self, generator: ComplianceGenerator, *, max_candidates_per_obligation: int = 3) -> None:
        self.generator = generator
        self.max_candidates_per_obligation = max_candidates_per_obligation

    def candidate_claims(
        self,
        obligation: ExtractedObligation,
        claims: list[ExtractedInternalClaim],
        *,
        min_alignment_score: float,
    ) -> list[tuple[ExtractedInternalClaim, float]]:
        scored = []
        for claim in claims:
            lexical_score = _alignment_score(obligation.key_terms, claim.key_terms)
            shared_anchors = _shared_governed_anchor_tags(
                obligation.evidence.text,
                claim.evidence.text,
                allowed=HIGH_RISK_RESCUE_ANCHOR_TAGS,
            )
            if lexical_score < min_alignment_score and not shared_anchors:
                continue
            score = _candidate_alignment_score(obligation, claim, lexical_score)
            if shared_anchors and score < min_alignment_score:
                score = min_alignment_score
            if score >= min_alignment_score:
                scored.append((claim, score))
        return [
            (claim, score)
            for claim, score in sorted(scored, key=lambda item: item[1], reverse=True)
        ][: self.max_candidates_per_obligation]

    def adjudicate(self, obligation: ExtractedObligation, claim: ExtractedInternalClaim, score: float) -> AgentDecision:
        prompt = _adjudication_prompt(obligation, claim, score)
        raw = self.generator.generate(prompt)
        return _parse_agent_decision(raw)

    def adjudicate_internal(
        self,
        reference: ExtractedInternalClaim,
        candidate: ExtractedInternalClaim,
        score: float,
    ) -> AgentDecision:
        prompt = _internal_adjudication_prompt(reference, candidate, score)
        raw = self.generator.generate(prompt)
        return _parse_agent_decision(raw)


class AgenticComplianceEngine(DeterministicComplianceEngine):
    audit_engine = "governance-review-agent"
    model_profile = "local-llm-adjudicator"
    prompt_version = AGENT_PROMPT_VERSION
    audit_assumptions = [
        "Queued pairwise workflow: each external source is checked against each approved internal source in isolation.",
        "Governance Review Agent first decides whether candidate passages discuss the same obligation.",
        "Contradictions are only returned when the agent identifies same-obligation conflict.",
        "If local LLM adjudication is unavailable, candidate pairs are demoted to human-review triage.",
        "No legal conclusion is final without human review.",
    ]
    modes = ["queued-pairwise-review", "governance-review-agent", "deterministic-fallback"]
    model_backends = ["ollama", "deterministic-fallback"]
    capability_note = (
        "Governance Review Agent is enabled: candidate pairs are adjudicated by a local LLM before findings are returned."
    )

    def __init__(
        self,
        generator: ComplianceGenerator,
        *,
        max_candidates_per_obligation: int = 3,
        model_name: str = "",
        depth_generators: dict[str, ComplianceGenerator] | None = None,
        depth_model_names: dict[str, str] | None = None,
    ) -> None:
        super().__init__()
        self.agent = GovernanceReviewAgent(generator, max_candidates_per_obligation=max_candidates_per_obligation)
        self.depth_agents = {
            depth: GovernanceReviewAgent(depth_generator, max_candidates_per_obligation=max_candidates_per_obligation)
            for depth, depth_generator in (depth_generators or {}).items()
        }
        self.depth_model_names = depth_model_names or {}
        if model_name:
            self.model_profile = f"local-llm-adjudicator:{model_name}"
            self.model_backends = [f"ollama:{model_name}", "deterministic-fallback"]
            self.capability_note = (
                f"Governance Review Agent is enabled using {model_name}: "
                "candidate pairs are adjudicated by a local LLM before findings are returned."
            )
        if self.depth_model_names:
            self.model_profile = ";".join(
                f"{depth}=ollama:{name}" if name else f"{depth}=deterministic-fallback"
                for depth, name in sorted(self.depth_model_names.items())
            )
            self.model_backends = [
                *(f"ollama:{name}" for name in dict.fromkeys(self.depth_model_names.values()) if name),
                "deterministic-fallback",
            ]
            self.capability_note = (
                "Governance Review Agent depth routing is enabled: "
                + ", ".join(
                    f"{depth} uses {name or 'deterministic fallback'}"
                    for depth, name in sorted(self.depth_model_names.items())
                )
                + "."
            )

    def model_profile_for_request(self, request: ComplianceReviewRequest) -> str:
        depth = request.options.review_depth
        if depth == "fast":
            return "fast=deterministic-fallback"
        if depth == "deep" and request.options.throttle_deep:
            model_name = self.depth_model_names.get("deep_throttled") or self.depth_model_names.get("deep")
            if model_name:
                return f"deep_throttled=ollama:{model_name}"
        model_name = self.depth_model_names.get(depth)
        if model_name:
            return f"{depth}=ollama:{model_name}"
        return self.model_profile

    def _agent_for_request(self, request: ComplianceReviewRequest) -> GovernanceReviewAgent:
        if request.options.review_depth == "deep" and request.options.throttle_deep:
            return self.depth_agents.get("deep_throttled", self.depth_agents.get("deep", self.agent))
        return self.depth_agents.get(request.options.review_depth, self.agent)

    def review_document_pair(self, external: EvidenceDocument, internal: EvidenceDocument, request: ComplianceReviewRequest) -> dict:
        if request.review_mode == "internal_vs_internal":
            return self.review_internal_document_pair(external, internal, request)
        if request.options.review_depth == "fast":
            return _deterministic_external_pair(external, internal, request)

        relevance_score = _document_relevance_score(external, internal)
        obligations = extract_obligations([external])
        internal_claims = extract_internal_claims([internal])
        if relevance_score < request.options.min_pair_relevance_score:
            findings = [_not_related_finding(external, internal, relevance_score)] if request.options.include_not_related_pairs else []
            return {
                "status": "not_related",
                "classification": "not_related",
                "relevance_score": relevance_score,
                "rationale": "External and internal documents do not appear to discuss the same obligation strongly enough to compare.",
                "findings": findings,
                "obligation_count": len(obligations),
                "internal_claim_count": len(internal_claims),
            }

        findings, matched_claim_ids = self._review_obligations(obligations, internal_claims, request)
        if request.options.include_unsupported_internal_claims:
            findings.extend(_unsupported_claims(internal_claims, obligations, matched_claim_ids, request))

        findings.sort(key=lambda item: (_severity_rank(item.severity), -item.confidence, item.classification, item.id))
        findings = findings[: request.options.max_findings]
        classification = findings[0].classification if findings else "supported"
        return {
            "status": "completed",
            "classification": classification,
            "relevance_score": relevance_score,
            "rationale": "Governance Review Agent checked candidate obligation pairs for same-obligation relevance before classification.",
            "findings": findings,
            "obligation_count": len(obligations),
            "internal_claim_count": len(internal_claims),
        }

    def _review_obligations(
        self,
        obligations: list[ExtractedObligation],
        claims: list[ExtractedInternalClaim],
        request: ComplianceReviewRequest,
    ) -> tuple[list[ComplianceFinding], set[str]]:
        findings: list[ComplianceFinding] = []
        matched_claim_ids: set[str] = set()
        budget = _max_agent_calls(request)
        agent = self._agent_for_request(request)

        for obligation in obligations:
            if budget == 0:
                break
            candidates = agent.candidate_claims(
                obligation,
                claims,
                min_alignment_score=request.options.min_alignment_score,
            )
            if not candidates:
                if request.options.include_missing_obligations:
                    findings.append(_missing_obligation_finding(obligation, 0.0))
                continue

            accepted = False
            for claim, score in candidates:
                if budget == 0:
                    break
                if budget is not None:
                    budget -= 1
                try:
                    decision = agent.adjudicate(obligation, claim, score)
                except (OSError, TimeoutError, urllib.error.URLError, ValueError, json.JSONDecodeError):
                    decision = _fallback_decision(obligation, claim, score)
                decision = _apply_contradiction_safety_gate(
                    decision,
                    obligation,
                    claim,
                    score,
                    request.options.min_contradiction_alignment_score,
                )
                decision = _apply_supported_coverage_gate(decision, obligation, claim, score)
                if not decision.same_obligation or decision.classification == "not_related":
                    continue
                matched_claim_ids.add(claim.id)
                accepted = True
                if decision.classification == "supported" and not request.options.include_supported_findings:
                    break
                findings.append(_agent_finding(obligation, claim, decision, score))
                break

            if not accepted and request.options.include_missing_obligations:
                best_score = candidates[0][1] if candidates else 0.0
                findings.append(_missing_obligation_finding(obligation, best_score))

        return findings, matched_claim_ids

    def review_internal_document_pair(
        self,
        source_a: EvidenceDocument,
        source_b: EvidenceDocument,
        request: ComplianceReviewRequest,
    ) -> dict:
        if request.options.review_depth == "fast":
            return _deterministic_internal_pair(source_a, source_b, request)

        relevance_score = _document_relevance_score(source_a, source_b)
        claims_a = extract_internal_claims([source_a])
        claims_b = extract_internal_claims([source_b])
        if relevance_score < request.options.min_pair_relevance_score:
            findings = [_not_related_finding(source_a, source_b, relevance_score)] if request.options.include_not_related_pairs else []
            return {
                "status": "not_related",
                "classification": "not_related",
                "relevance_score": relevance_score,
                "rationale": "Internal sources do not appear to discuss the same process, rule or control strongly enough to compare.",
                "findings": findings,
                "obligation_count": len(claims_a),
                "internal_claim_count": len(claims_b),
            }

        findings = _duplicate_section_findings(source_a, source_b)
        budget = [_max_agent_calls(request)]
        findings.extend(self._review_internal_claims(claims_a, claims_b, request, budget=budget))
        findings.extend(self._review_internal_claims(claims_b, claims_a, request, budget=budget))
        findings = _dedupe_findings(findings)
        findings.sort(key=lambda item: (_severity_rank(item.severity), -item.confidence, item.classification, item.id))
        findings = findings[: request.options.max_findings]
        classification = findings[0].classification if findings else "supported"
        return {
            "status": "completed",
            "classification": classification,
            "relevance_score": relevance_score,
            "rationale": (
                "Governance Review Agent compared internal source pairs for semantic consistency, duplicate guidance "
                "and missing operational detail."
            ),
            "findings": findings,
            "obligation_count": len(claims_a),
            "internal_claim_count": len(claims_b),
        }

    def _review_internal_claims(
        self,
        reference_claims: list[ExtractedInternalClaim],
        candidate_claims: list[ExtractedInternalClaim],
        request: ComplianceReviewRequest,
        *,
        budget: list[int | None] | None = None,
    ) -> list[ComplianceFinding]:
        findings: list[ComplianceFinding] = []
        agent = self._agent_for_request(request)
        for reference in reference_claims:
            if budget is not None and budget[0] == 0:
                break
            reference_as_obligation = _claim_as_obligation(reference)
            candidates = agent.candidate_claims(
                reference_as_obligation,
                candidate_claims,
                min_alignment_score=request.options.min_alignment_score,
            )
            for candidate, score in candidates:
                if budget is not None and budget[0] == 0:
                    break
                if budget is not None and budget[0] is not None:
                    budget[0] -= 1
                try:
                    decision = agent.adjudicate_internal(reference, candidate, score)
                except (OSError, TimeoutError, urllib.error.URLError, ValueError, json.JSONDecodeError):
                    decision = _fallback_internal_decision(reference, candidate, score)
                decision = _apply_internal_contradiction_safety_gate(
                    decision,
                    reference,
                    candidate,
                    score,
                    request.options.min_contradiction_alignment_score,
                )
                decision = _apply_supported_coverage_gate(decision, _claim_as_obligation(reference), candidate, score)
                if not decision.same_obligation or decision.classification == "not_related":
                    continue
                if decision.classification == "supported" and not request.options.include_supported_findings:
                    break
                findings.append(_agent_internal_finding(reference, candidate, decision, score))
                break
        return findings


def _unsupported_claims(
    claims: list[ExtractedInternalClaim],
    obligations: list[ExtractedObligation],
    matched_claim_ids: set[str],
    request: ComplianceReviewRequest,
) -> list[ComplianceFinding]:
    findings = []
    for claim in claims:
        if claim.id in matched_claim_ids:
            continue
        best_obligation, score = _best_obligation(claim, obligations)
        if best_obligation is not None and score >= request.options.min_alignment_score:
            continue
        findings.append(_unsupported_claim_finding(claim, score))
    return findings


def _max_agent_calls(request: ComplianceReviewRequest) -> int | None:
    if request.options.review_depth == "fast":
        return 0
    if request.options.max_agent_calls_per_pair > 0:
        return request.options.max_agent_calls_per_pair
    if request.options.review_depth == "balanced":
        return 2
    return None


def _fallback_decision(obligation: ExtractedObligation, claim: ExtractedInternalClaim, score: float) -> AgentDecision:
    finding = _classify_pair(obligation, claim, score)
    classification: FindingClassification = finding.classification
    severity: FindingSeverity = finding.severity
    confidence = min(finding.confidence, 0.5)
    if finding.classification == "contradiction":
        classification = "needs_human_review"
        severity = "medium"
        confidence = min(finding.confidence, 0.48)
    return AgentDecision(
        same_obligation=True,
        classification=classification,
        severity=severity,
        confidence=confidence,
        rationale=(
            f"{finding.rationale} Local LLM adjudication was unavailable, "
            "so this pair is triaged for human review rather than treated as a confirmed conflict."
        ),
        recommended_action="Review manually because the local LLM adjudicator was unavailable.",
        advisor_summary=finding.advisor_summary,
        why_it_matters=finding.why_it_matters,
        proposed_internal_text=finding.proposed_internal_text,
        confidence_interpretation=finding.confidence_interpretation,
        evidence_highlights=tuple(finding.evidence_highlights),
    )


def _fallback_internal_decision(
    reference: ExtractedInternalClaim,
    candidate: ExtractedInternalClaim,
    score: float,
) -> AgentDecision:
    finding = _classify_pair(_claim_as_obligation(reference), candidate, score)
    classification: FindingClassification = finding.classification
    severity: FindingSeverity = finding.severity
    confidence = min(finding.confidence, 0.5)
    if score >= 0.86 and _normalised_text(reference.evidence.text) != _normalised_text(candidate.evidence.text):
        classification = "duplicate"
        severity = "low"
        confidence = min(0.82, max(confidence, score))
    elif finding.classification == "contradiction":
        classification = "needs_human_review"
        severity = "medium"
        confidence = min(finding.confidence, 0.48)
    return AgentDecision(
        same_obligation=True,
        classification=classification,
        severity=severity,
        confidence=confidence,
        rationale=(
            f"{finding.rationale} Local LLM adjudication was unavailable, "
            "so this internal pair is triaged conservatively."
        ),
        recommended_action="Review manually because the local LLM adjudicator was unavailable.",
        advisor_summary=finding.advisor_summary,
        why_it_matters=finding.why_it_matters,
        proposed_internal_text=finding.proposed_internal_text,
        confidence_interpretation=finding.confidence_interpretation,
        evidence_highlights=tuple(finding.evidence_highlights),
    )


def _apply_contradiction_safety_gate(
    decision: AgentDecision,
    obligation: ExtractedObligation,
    claim: ExtractedInternalClaim,
    score: float,
    min_contradiction_alignment_score: float,
) -> AgentDecision:
    if decision.classification != "contradiction":
        return decision
    context_decision = _contextual_contradiction_gate(decision, obligation, claim)
    if context_decision != decision:
        return context_decision
    if score >= min_contradiction_alignment_score:
        return decision
    if _shared_governed_anchor_tags(
        obligation.evidence.text,
        claim.evidence.text,
        allowed=HIGH_RISK_RESCUE_ANCHOR_TAGS,
    ):
        return decision
    concrete_overlap = _concrete_shared_terms(obligation, claim)
    if len(concrete_overlap) >= MIN_CONCRETE_CONTRADICTION_TERMS:
        return decision
    return AgentDecision(
        same_obligation=False,
        classification="not_related",
        severity="low",
        confidence=min(decision.confidence, 0.55),
        rationale=(
            "The model proposed a contradiction, but the candidate pair did not share enough concrete obligation "
            "terms to treat it as the same governed requirement."
        ),
        recommended_action="No compliance action unless a reviewer can identify the same concrete obligation.",
        advisor_summary="The passages do not share enough concrete obligation detail to treat this as a confirmed conflict.",
        why_it_matters="This prevents broad or generic wording from becoming a false compliance contradiction.",
        confidence_interpretation="Low confidence after the safety gate; treat as not related.",
    )


def _apply_internal_contradiction_safety_gate(
    decision: AgentDecision,
    reference: ExtractedInternalClaim,
    candidate: ExtractedInternalClaim,
    score: float,
    min_contradiction_alignment_score: float,
) -> AgentDecision:
    if decision.classification != "contradiction":
        return decision
    context_decision = _contextual_contradiction_gate(decision, _claim_as_obligation(reference), candidate)
    if context_decision != decision:
        return context_decision
    if score >= min_contradiction_alignment_score:
        return decision
    if _shared_governed_anchor_tags(
        reference.evidence.text,
        candidate.evidence.text,
        allowed=HIGH_RISK_RESCUE_ANCHOR_TAGS,
    ):
        return decision
    concrete_overlap = _concrete_shared_terms(_claim_as_obligation(reference), candidate)
    if len(concrete_overlap) >= MIN_CONCRETE_CONTRADICTION_TERMS:
        return decision
    return AgentDecision(
        same_obligation=False,
        classification="not_related",
        severity="low",
        confidence=min(decision.confidence, 0.55),
        rationale=(
            "The model proposed an internal contradiction, but the candidate pair did not share enough concrete "
            "process, rule or control terms to treat it as the same governed statement."
        ),
        recommended_action="No governance action unless a reviewer can identify the same concrete internal rule.",
        advisor_summary="The passages do not share enough concrete operational detail to treat this as a confirmed conflict.",
        why_it_matters="This prevents generic business wording from becoming a false internal-source contradiction.",
        confidence_interpretation="Low confidence after the safety gate; treat as not related.",
    )


def _concrete_shared_terms(obligation: ExtractedObligation, claim: ExtractedInternalClaim) -> set[str]:
    return (set(obligation.key_terms) & set(claim.key_terms)) - LOW_SIGNAL_SHARED_TERMS


def _candidate_alignment_score(
    obligation: ExtractedObligation,
    claim: ExtractedInternalClaim,
    lexical_score: float,
) -> float:
    score = lexical_score
    concrete_overlap = _concrete_shared_terms(obligation, claim)
    if len(concrete_overlap) < 2:
        score -= 0.08
    if _has_supply_timing_mismatch(obligation.evidence.text, claim.evidence.text):
        score -= 0.12
    return round(max(0.0, score), 3)


def _contextual_contradiction_gate(
    decision: AgentDecision,
    obligation: ExtractedObligation,
    claim: ExtractedInternalClaim,
) -> AgentDecision:
    if _has_supply_timing_mismatch(obligation.evidence.text, claim.evidence.text):
        return AgentDecision(
            same_obligation=False,
            classification="not_related",
            severity="low",
            confidence=min(decision.confidence, 0.55),
            rationale=(
                "The model proposed a contradiction, but the passages apply to different timing contexts around "
                "the supply or rate-change date."
            ),
            recommended_action="No compliance edit is suggested unless a reviewer confirms the same timing condition.",
            advisor_summary=(
                "The passages mention the same broad topic, but one is scoped to supplies before a change and the "
                "other to supplies after a change."
            ),
            why_it_matters="Timing qualifiers can reverse the meaning of VAT-rate guidance; weak timing matches create false positives.",
            confidence_interpretation="Low confidence after temporal-context gate; treat as not related.",
        )
    if _external_has_exception_that_internal_omits(obligation.evidence.text, claim.evidence.text):
        return AgentDecision(
            same_obligation=True,
            classification="missing_detail",
            severity="medium",
            confidence=min(decision.confidence, 0.78),
            rationale=(
                "The external passage includes an exception or qualifier, while the internal wording is broader. "
                "This is better treated as missing detail than a direct contradiction."
            ),
            recommended_action="Add the external exception or qualifier to the internal guidance where the topic applies.",
            advisor_summary="Internal wording covers the topic but may be too broad because it omits an external exception.",
            why_it_matters="Missing exceptions can make otherwise aligned guidance sound stricter or broader than the source allows.",
            proposed_internal_text=decision.proposed_internal_text,
            confidence_interpretation="Moderate confidence; review the exception wording before editing approved knowledge.",
            evidence_highlights=decision.evidence_highlights,
        )
    return decision


def _apply_supported_coverage_gate(
    decision: AgentDecision,
    obligation: ExtractedObligation,
    claim: ExtractedInternalClaim,
    score: float,
) -> AgentDecision:
    if decision.classification != "supported":
        return decision
    shared_anchors = _shared_governed_anchor_tags(
        obligation.evidence.text,
        claim.evidence.text,
        allowed=HIGH_RISK_RESCUE_ANCHOR_TAGS,
    )
    rate_change_anchors = _shared_governed_anchor_tags(
        obligation.evidence.text,
        claim.evidence.text,
        allowed=RATE_CHANGE_ANCHOR_TAGS,
    )
    concrete_overlap = _concrete_shared_terms(obligation, claim)
    if shared_anchors:
        return decision
    if (
        rate_change_anchors
        and score >= MIN_RATE_CHANGE_SUPPORTED_ALIGNMENT_SCORE
        and not _has_supply_timing_mismatch(obligation.evidence.text, claim.evidence.text)
    ):
        return decision
    if score >= MIN_SUPPORTED_STRONG_ALIGNMENT_SCORE and len(concrete_overlap) >= MIN_CONCRETE_CONTRADICTION_TERMS:
        return decision
    return AgentDecision(
        same_obligation=False,
        classification="not_related",
        severity="low",
        confidence=min(decision.confidence, 0.55),
        rationale=(
            "The model proposed supported coverage, but the passages did not share a concrete governed object "
            "strongly enough to treat this as assurance evidence."
        ),
        recommended_action="No supported coverage action is suggested for this weak evidence pair.",
        advisor_summary="The passages share broad wording but not a concrete enough governed rule for supported coverage.",
        why_it_matters="Coverage evidence should be cleaner than exploratory matching, otherwise it can overstate assurance.",
        confidence_interpretation="Low confidence after supported-coverage gate; omitted from coverage evidence.",
    )


def _has_supply_timing_mismatch(left_text: str, right_text: str) -> bool:
    left_before = _mentions_supply_timing(left_text, "before")
    left_after = _mentions_supply_timing(left_text, "after")
    right_before = _mentions_supply_timing(right_text, "before")
    right_after = _mentions_supply_timing(right_text, "after")
    return (left_before and right_after) or (left_after and right_before)


def _mentions_supply_timing(text: str, direction: str) -> bool:
    if "change" not in text.lower() or not SUPPLY_TIMING_TERMS_PATTERN.search(text):
        return False
    direction_pattern = re.escape(direction)
    return bool(
        re.search(
            rf"\b(suppl(?:y|ies|ied)|goods removed|services performed)\b.{{0,120}}\b{direction_pattern}\b.{{0,80}}\b(change|date)\b",
            text,
            re.I,
        )
        or re.search(
            rf"\b{direction_pattern}\b.{{0,80}}\b(change|date)\b.{{0,120}}\b(suppl(?:y|ies|ied)|goods removed|services performed)\b",
            text,
            re.I,
        )
    )


def _external_has_exception_that_internal_omits(external_text: str, internal_text: str) -> bool:
    return bool(
        EXCEPTION_QUALIFIER_PATTERN.search(external_text)
        and BROAD_REQUIREMENT_PATTERN.search(internal_text)
        and REQUIREMENT_PATTERN.search(internal_text)
    )


def _shared_governed_anchor_tags(
    left_text: str,
    right_text: str,
    *,
    allowed: frozenset[str] | None = None,
) -> set[str]:
    shared = _governed_anchor_tags(left_text) & _governed_anchor_tags(right_text)
    return shared if allowed is None else shared & allowed


def _governed_anchor_tags(text: str) -> set[str]:
    tags: set[str] = set()
    if INVOICE_RECORD_PATTERN.search(text) and RECORD_EVIDENCE_PATTERN.search(text):
        tags.add("invoice_records")
    if BUSINESS_USE_PATTERN.search(text):
        tags.add("business_use_proportion")
    if RATE_CHANGE_PATTERN.search(text) and RATE_CHANGE_OBJECT_PATTERN.search(text):
        tags.add("vat_rate_change")
    if INPUT_TAX_EVIDENCE_PATTERN.search(text) and RECORD_EVIDENCE_PATTERN.search(text):
        tags.add("input_tax_evidence")
    if DISBURSEMENT_EVIDENCE_PATTERN.search(text) and RECORD_EVIDENCE_PATTERN.search(text):
        tags.add("disbursement_evidence")
    return tags


def _agent_finding(
    obligation: ExtractedObligation,
    claim: ExtractedInternalClaim,
    decision: AgentDecision,
    score: float,
) -> ComplianceFinding:
    signals = [
        f"agent_prompt_version={AGENT_PROMPT_VERSION}",
        "agent_same_obligation=true",
        f"external_modality={obligation.modality}",
        f"internal_modality={claim.modality}",
        f"recommended_action={decision.recommended_action}" if decision.recommended_action else "recommended_action=review",
    ]
    return _with_advisor_fields(ComplianceFinding(
        id=_finding_id(f"agent-{decision.classification}", obligation.id, claim.id),
        classification=decision.classification,
        severity=decision.severity,
        confidence=round(decision.confidence, 3),
        alignment_score=score,
        rationale=decision.rationale,
        obligation_id=obligation.id,
        internal_claim_id=claim.id,
        external_evidence=obligation.evidence,
        internal_evidence=claim.evidence,
        signals=signals,
        advisor_summary=decision.advisor_summary,
        why_it_matters=decision.why_it_matters,
        recommended_action=decision.recommended_action,
        proposed_internal_text=decision.proposed_internal_text,
        confidence_interpretation=decision.confidence_interpretation,
        evidence_highlights=list(decision.evidence_highlights),
    ))


def _agent_internal_finding(
    reference: ExtractedInternalClaim,
    candidate: ExtractedInternalClaim,
    decision: AgentDecision,
    score: float,
) -> ComplianceFinding:
    signals = [
        f"agent_prompt_version={AGENT_PROMPT_VERSION}",
        "agent_internal_pair=true",
        f"source_a_modality={reference.modality}",
        f"source_b_modality={candidate.modality}",
        f"recommended_action={decision.recommended_action}" if decision.recommended_action else "recommended_action=review",
    ]
    return _with_advisor_fields(ComplianceFinding(
        id=_finding_id(f"agent-internal-{decision.classification}", reference.id, candidate.id),
        classification=decision.classification,
        severity=decision.severity,
        confidence=round(decision.confidence, 3),
        alignment_score=score,
        rationale=decision.rationale,
        obligation_id=reference.id,
        internal_claim_id=candidate.id,
        external_evidence=reference.evidence,
        internal_evidence=candidate.evidence,
        signals=signals,
        advisor_summary=decision.advisor_summary,
        why_it_matters=decision.why_it_matters,
        recommended_action=decision.recommended_action,
        proposed_internal_text=decision.proposed_internal_text,
        confidence_interpretation=decision.confidence_interpretation,
        evidence_highlights=list(decision.evidence_highlights),
    ))


def _adjudication_prompt(obligation: ExtractedObligation, claim: ExtractedInternalClaim, score: float) -> str:
    return f"""You are a careful governance compliance reviewer.

Task:
1. First decide whether the external passage and internal passage are about the same legal or business obligation.
2. If they are not about the same obligation, return classification "not_related".
3. Only return "contradiction" when both passages address the same obligation
   and the internal wording conflicts with, weakens, permits, or denies what the
   external source requires.
4. Do not treat generic discourse or modal words as topic overlap. Words such as
   "but", "still", "may", "must", "needed", "required", "should", "can" are not enough.
5. Same-obligation requires the same concrete governed object, business domain,
   actor/action and outcome. Similar abstract ideas are not enough.
6. Examples of not_related pairs:
   - VAT supply flexibility versus article-list user authorisation
   - VAT private-use percentage calculation versus generic list business-use logic
   - VAT invoice display requirements versus dated internal parameter setup
7. If uncertain, return "not_related" or "needs_human_review"; do not force a contradiction.
8. Do not give legal advice. Produce a governance triage result for human review.
9. If you use private reasoning, do not include it in the response. Return final JSON only.

Allowed classification values:
- not_related
- supported
- contradiction
- too_vague
- missing_detail
- needs_human_review

Return only valid JSON with this schema:
{{
  "same_obligation": true,
  "classification": "supported",
  "severity": "low",
  "confidence": 0.0,
  "rationale": "two to three plain-English sentences explaining exactly what differs or aligns",
  "advisor_summary": "two plain-English sentences for a human reviewer, naming the concrete rule or process area",
  "why_it_matters": "one or two sentences explaining the governance risk or why no change is needed",
  "recommended_action": "one concise action",
  "proposed_internal_text": "replacement internal wording when an edit is useful; empty string otherwise",
  "confidence_interpretation": "one sentence explaining how strongly to rely on the score",
  "evidence_highlights": ["short external highlight", "short internal highlight"]
}}

External source: {obligation.evidence.source_title}
External citation: {obligation.evidence.citation or obligation.evidence.heading}
External modality: {obligation.modality}
External passage:
{obligation.evidence.text}

Internal source: {claim.evidence.source_title}
Internal citation: {claim.evidence.citation or claim.evidence.heading}
Internal modality: {claim.modality}
Internal passage:
{claim.evidence.text}

Deterministic lexical alignment score: {score}
"""


def _internal_adjudication_prompt(
    reference: ExtractedInternalClaim,
    candidate: ExtractedInternalClaim,
    score: float,
) -> str:
    return f"""You are a careful internal governance reviewer comparing two internal knowledge-source passages.

Task:
1. First decide whether Source A and Source B are about the same concrete process, rule, control, system, role,
   timing requirement, data requirement, or operating decision.
2. If they are not about the same concrete governed statement, return classification "not_related".
3. Return "contradiction" only when both passages address the same concrete governed statement and cannot both be true.
4. Return "missing_detail" when Source B covers the same governed statement but omits a material qualifier, control,
   condition, timing, system, owner, or exception that appears in Source A.
5. Return "too_vague" when Source B is materially weaker or less precise than Source A on the same governed statement.
6. Return "duplicate" when both passages repeat the same substantive guidance in a way that looks like duplicated content.
   Do not mark repeated headings, templates, table labels, Q&A scaffolding, or generic structure as duplicate.
7. Return "supported" when the passages are consistent and complementary.
8. If uncertain, return "not_related" or "needs_human_review"; do not force a contradiction.
9. Do not give legal advice. Produce a governance triage result for human review.
10. If you use private reasoning, do not include it in the response. Return final JSON only.

Allowed classification values:
- not_related
- supported
- contradiction
- duplicate
- too_vague
- missing_detail
- needs_human_review

Return only valid JSON with this schema:
{{
  "same_obligation": true,
  "classification": "supported",
  "severity": "low",
  "confidence": 0.0,
  "rationale": "two to three plain-English sentences explaining exactly what differs or aligns",
  "advisor_summary": "two plain-English sentences for a human reviewer, naming the concrete rule or process area",
  "why_it_matters": "one or two sentences explaining the governance risk or why no change is needed",
  "recommended_action": "one concise action",
  "proposed_internal_text": "replacement wording for Source B when an edit is useful; empty string otherwise",
  "confidence_interpretation": "one sentence explaining how strongly to rely on the score",
  "evidence_highlights": ["short Source A highlight", "short Source B highlight"]
}}

Source A: {reference.evidence.source_title}
Source A citation: {reference.evidence.citation or reference.evidence.heading}
Source A modality: {reference.modality}
Source A passage:
{reference.evidence.text}

Source B: {candidate.evidence.source_title}
Source B citation: {candidate.evidence.citation or candidate.evidence.heading}
Source B modality: {candidate.modality}
Source B passage:
{candidate.evidence.text}

Deterministic lexical alignment score: {score}
"""


def _parse_agent_decision(raw: str) -> AgentDecision:
    payload = _extract_json(raw)
    same_obligation = bool(payload.get("same_obligation"))
    classification = str(payload.get("classification", "needs_human_review")).strip().lower()
    if classification not in ALLOWED_CLASSIFICATIONS:
        classification = "needs_human_review"
    if not same_obligation:
        classification = "not_related"
    severity = str(payload.get("severity", "medium")).strip().lower()
    if severity not in ALLOWED_SEVERITIES:
        severity = "medium"
    if classification in {"supported", "not_related"}:
        severity = "low"
    confidence = _clamp_float(payload.get("confidence", 0.5), 0.0, 0.95)
    rationale = str(payload.get("rationale", "")).strip()
    if not rationale:
        rationale = "The governance reviewer could not provide a detailed rationale."
    recommended_action = str(payload.get("recommended_action", "")).strip()
    advisor_summary = str(payload.get("advisor_summary", "")).strip()
    why_it_matters = str(payload.get("why_it_matters", "")).strip()
    proposed_internal_text = str(payload.get("proposed_internal_text", "")).strip()
    confidence_interpretation = str(payload.get("confidence_interpretation", "")).strip()
    raw_highlights = payload.get("evidence_highlights", [])
    evidence_highlights = (
        tuple(str(item).strip() for item in raw_highlights if str(item).strip())
        if isinstance(raw_highlights, list)
        else ()
    )
    return AgentDecision(
        same_obligation=same_obligation,
        classification=classification,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        confidence=confidence,
        rationale=rationale,
        recommended_action=recommended_action,
        advisor_summary=advisor_summary,
        why_it_matters=why_it_matters,
        proposed_internal_text=proposed_internal_text,
        confidence_interpretation=confidence_interpretation,
        evidence_highlights=evidence_highlights,
    )


def _extract_json(raw: str) -> dict:
    stripped = _strip_reasoning_text(raw)
    stripped = _strip_code_fence(stripped)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = _first_json_object(stripped)
    if not isinstance(parsed, dict):
        raise ValueError("Agent output must be a JSON object.")
    return parsed


def _strip_reasoning_text(raw: str) -> str:
    without_closed_think = re.sub(r"<think>.*?</think>", "", raw, flags=re.I | re.S)
    if "</think>" in without_closed_think.lower():
        return re.split(r"</think>", without_closed_think, flags=re.I)[-1].strip()
    return without_closed_think.strip()


def _strip_code_fence(raw: str) -> str:
    stripped = raw.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.I)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _first_json_object(raw: str) -> dict:
    decoder = json.JSONDecoder()
    for index, char in enumerate(raw):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(raw[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("Agent output did not contain a JSON object.")


def _clamp_float(value, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return minimum
    return max(minimum, min(maximum, number))


def _normalised_text(text: str) -> str:
    return " ".join(text.lower().split())
