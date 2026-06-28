"""Bounded governance-review agent for compliance pair adjudication."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from .engine import (
    DeterministicComplianceEngine,
    _alignment_score,
    _best_obligation,
    _classify_pair,
    _document_relevance_score,
    _finding_id,
    _missing_obligation_finding,
    _not_related_finding,
    _severity_rank,
    _unsupported_claim_finding,
    _with_advisor_fields,
    extract_internal_claims,
    extract_obligations,
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

AGENT_PROMPT_VERSION = "governance-review-agent-v2"
LOW_SIGNAL_SHARED_TERMS = {
    "business",
    "case",
    "cases",
    "new",
    "old",
    "rate",
    "rates",
    "some",
    "use",
    "used",
    "uses",
    "using",
}
MIN_CONCRETE_CONTRADICTION_TERMS = 3
ALLOWED_CLASSIFICATIONS = {
    "not_related",
    "supported",
    "contradiction",
    "too_vague",
    "missing_detail",
    "needs_human_review",
}
ALLOWED_SEVERITIES = {"low", "medium", "high"}


class ComplianceGenerator(Protocol):
    def generate(self, prompt: str) -> str: ...


class OllamaComplianceGenerator:
    def __init__(
        self,
        *,
        model: str = "qwen2.5:7b-instruct",
        base_url: str = "http://127.0.0.1:11434",
        num_ctx: int = 8192,
        temperature: float = 0.0,
        timeout: float = 120.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.num_ctx = num_ctx
        self.temperature = temperature
        self.timeout = timeout

    def generate(self, prompt: str) -> str:
        payload = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_ctx": self.num_ctx, "temperature": self.temperature},
            }
        ).encode()
        request = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read())
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
        scored = [(claim, _alignment_score(obligation.key_terms, claim.key_terms)) for claim in claims]
        return [
            (claim, score)
            for claim, score in sorted(scored, key=lambda item: item[1], reverse=True)
            if score >= min_alignment_score
        ][: self.max_candidates_per_obligation]

    def adjudicate(self, obligation: ExtractedObligation, claim: ExtractedInternalClaim, score: float) -> AgentDecision:
        prompt = _adjudication_prompt(obligation, claim, score)
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
    ) -> None:
        super().__init__()
        self.agent = GovernanceReviewAgent(generator, max_candidates_per_obligation=max_candidates_per_obligation)
        if model_name:
            self.model_profile = f"local-llm-adjudicator:{model_name}"
            self.model_backends = [f"ollama:{model_name}", "deterministic-fallback"]
            self.capability_note = (
                f"Governance Review Agent is enabled using {model_name}: "
                "candidate pairs are adjudicated by a local LLM before findings are returned."
            )

    def review_document_pair(self, external: EvidenceDocument, internal: EvidenceDocument, request: ComplianceReviewRequest) -> dict:
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

        for obligation in obligations:
            candidates = self.agent.candidate_claims(
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
                try:
                    decision = self.agent.adjudicate(obligation, claim, score)
                except (OSError, TimeoutError, urllib.error.URLError, ValueError, json.JSONDecodeError):
                    decision = _fallback_decision(obligation, claim, score)
                decision = _apply_contradiction_safety_gate(
                    decision,
                    obligation,
                    claim,
                    score,
                    request.options.min_contradiction_alignment_score,
                )
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


def _apply_contradiction_safety_gate(
    decision: AgentDecision,
    obligation: ExtractedObligation,
    claim: ExtractedInternalClaim,
    score: float,
    min_contradiction_alignment_score: float,
) -> AgentDecision:
    if decision.classification != "contradiction" or score >= min_contradiction_alignment_score:
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


def _concrete_shared_terms(obligation: ExtractedObligation, claim: ExtractedInternalClaim) -> set[str]:
    return (set(obligation.key_terms) & set(claim.key_terms)) - LOW_SIGNAL_SHARED_TERMS


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
  "rationale": "one concise sentence",
  "advisor_summary": "one or two plain-English sentences for a human reviewer",
  "why_it_matters": "one sentence explaining the governance risk or why no change is needed",
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
