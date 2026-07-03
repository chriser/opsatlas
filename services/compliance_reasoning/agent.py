"""Bounded governance-review agent for compliance pair adjudication."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from threading import Lock
from typing import Any, Protocol

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

AGENT_PROMPT_VERSION = "governance-review-agent-v7"
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
MIN_SUPPORTED_ANCHOR_ALIGNMENT_SCORE = 0.25
ALLOWED_CLASSIFICATIONS = {
    "not_related",
    "supported",
    "contradiction",
    "missing_obligation",
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
    r"\b(proportion|percentage)\b.{0,80}\b(business|private|non-business)\b|"
    r"\bmixed\s+use\b",
    re.I,
)
RATE_CHANGE_PATTERN = re.compile(r"\b(rate|rates|old rate|new rate|tax point|change date)\b", re.I)
RATE_CHANGE_OBJECT_PATTERN = re.compile(r"\b(invoice|invoices|supply|supplies|goods removed|services performed|tax point)\b", re.I)
INPUT_TAX_EVIDENCE_PATTERN = re.compile(r"\b(input tax|deduction|reclaim|reclaimed|recover)\b", re.I)
DISBURSEMENT_EVIDENCE_PATTERN = re.compile(r"\b(disbursement|disbursements|principal|agent)\b", re.I)
VAT_EVIDENCE_PATTERN = re.compile(r"\b(vat|tax)\b.{0,80}\b(evidence|paperwork|audit|certificate|invoice|record|records)\b", re.I)
PACKAGING_PATTERN = re.compile(r"\bpackag(?:e|es|ing)\b", re.I)
PACKAGING_MATERIAL_PATTERN = re.compile(
    r"\b(material|materials|plastic|paper|glass|metal|weight|weights|category|categories|detail|details)\b",
    re.I,
)
PACKAGING_THRESHOLD_PATTERN = re.compile(r"\b(threshold|producer responsibility|legal entity|activity data|annual)\b", re.I)
PACKAGING_EVIDENCE_PATTERN = re.compile(
    r"\b(evidence|record|records|retain|retained|calculation|calculations|workbook|files|declaration|declarations|audit|note|notes)\b",
    re.I,
)
PACKAGING_SUBMISSION_PATTERN = re.compile(r"\b(submission|submissions|submit|reported|reporting|template|data)\b", re.I)
PACKAGING_DEADLINE_PATTERN = re.compile(r"\b(deadline|due date|submission date|completed by)\b", re.I)
PACKAGING_THIRD_PARTY_PATTERN = re.compile(r"\b(third-party|third party|fulfilment|fulfillment|logistics|provider|ships goods)\b", re.I)
PACKAGING_SUPPLIER_PATTERN = re.compile(r"\b(supplier|suppliers|purchased|bought|procured)\b", re.I)
PACKAGING_HOUSEHOLD_PATTERN = re.compile(r"\b(household|non-household)\b", re.I)
PACKAGING_REUSABLE_PATTERN = re.compile(r"\breusable\b", re.I)
GOODS_PATTERN = re.compile(r"\b(goods|good|product|products)\b", re.I)
SERVICES_PATTERN = re.compile(r"\b(service|services)\b", re.I)
WHOLLY_BUSINESS_USE_PATTERN = re.compile(
    r"\bwholly\b.{0,80}\bbusiness\b.{0,40}\buse\b|\bacquired\b.{0,80}\bwholly\b.{0,80}\bbusiness\b",
    re.I,
)
BOTH_BUSINESS_PRIVATE_USE_PATTERN = re.compile(r"\bboth\b.{0,80}\bbusiness\b.{0,80}\bprivate\b|\bbusiness\s+and\s+private\b", re.I)
SUPPORTED_NOOP_ACTION_PATTERN = re.compile(
    r"\b(no action|no change|no edit|nothing to change|already aligns?|content aligns?|both align|aligns well)\b",
    re.I,
)
SUPPORTED_CHANGE_ACTION_PATTERN = re.compile(
    r"\b(review|revise|update|clarif|amend|add|include|ensure|reconcile|replace|expand|modify)\b",
    re.I,
)
DISMISSAL_OR_NEGATION_PATTERN = re.compile(
    r"\b(ignore|can ignore|may ignore|not required|not mandatory|does not apply|do not apply|not apply|"
    r"never|must not|should not|shall not|not be shown|not included|excluded|optional|may be deleted|can be deleted)\b",
    re.I,
)
HIGH_RISK_RESCUE_ANCHOR_TAGS = frozenset(
    {
        "invoice_records",
        "vat_evidence",
        "business_use_proportion",
        "input_tax_evidence",
        "disbursement_evidence",
    }
)
RATE_CHANGE_ANCHOR_TAGS = frozenset({"vat_rate_change_invoice"})
CANDIDATE_RESCUE_ANCHOR_TAGS = frozenset(
    {
        *HIGH_RISK_RESCUE_ANCHOR_TAGS,
        "vat_rate_change",
        "vat_rate_change_invoice",
        "packaging_material",
        "packaging_threshold",
        "packaging_evidence",
        "packaging_submission",
        "packaging_deadline",
        "packaging_third_party",
        "packaging_supplier",
        "packaging_household",
        "packaging_reusable",
    }
)
MIN_RATE_CHANGE_SUPPORTED_ALIGNMENT_SCORE = 0.32
MIN_SEMANTIC_CANDIDATE_SCORE = 0.58
NO_CANDIDATE_NOT_RELATED_MAX_SCORE = 0.45
ACTIONABLE_CONSOLIDATION_CLASSIFICATIONS = frozenset(
    {
        "contradiction",
        "missing_obligation",
        "missing_detail",
        "too_vague",
        "outdated",
        "unsupported_claim",
        "needs_human_review",
    }
)
CONSOLIDATED_CLASSIFICATION_RANK = {
    "contradiction": 0,
    "missing_detail": 1,
    "too_vague": 2,
    "needs_human_review": 3,
    "missing_obligation": 4,
    "outdated": 5,
    "unsupported_claim": 6,
    "duplicate": 7,
    "supported": 8,
    "not_related": 9,
}
PROMPT_CONTEXT_WARNING_THRESHOLD = 0.8


class ComplianceGenerator(Protocol):
    def generate(self, prompt: str) -> str: ...


class ComplianceEmbedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


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
        self.prompt_observations: list[dict[str, int | float | str | bool]] = []

    def generate(self, prompt: str) -> str:
        _record_prompt_observation(
            self,
            prompt,
            model=self.model,
            num_ctx=self.num_ctx,
            temperature=self.temperature,
        )
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


class OllamaComplianceEmbedder:
    """Small Ollama embedding adapter used only to widen candidate recall."""

    def __init__(
        self,
        *,
        model: str = "nomic-embed-text",
        base_url: str = "http://127.0.0.1:11434",
        timeout: float = 30.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._cache: dict[str, list[float]] = {}

    def embed(self, text: str) -> list[float]:
        cache_key = _normalised_text(text)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached
        payload = json.dumps({"model": self.model, "prompt": text}).encode()
        request = urllib.request.Request(
            f"{self.base_url}/api/embeddings",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            vector = json.loads(response.read())["embedding"]
        if not isinstance(vector, list):
            raise ValueError("Ollama embedding response did not include an embedding vector.")
        self._cache[cache_key] = [float(value) for value in vector]
        return self._cache[cache_key]


def _estimate_prompt_tokens(prompt: str) -> int:
    # Cheap model-agnostic estimate; good enough to flag context pressure.
    return max(1, int(len(prompt) / 4))


def _record_prompt_observation(
    generator: object,
    prompt: str,
    *,
    model: str,
    num_ctx: int,
    temperature: float,
) -> dict[str, int | float | str | bool]:
    token_estimate = _estimate_prompt_tokens(prompt)
    threshold = int(num_ctx * PROMPT_CONTEXT_WARNING_THRESHOLD) if num_ctx > 0 else 0
    observation: dict[str, int | float | str | bool] = {
        "model": model,
        "prompt_token_estimate": token_estimate,
        "num_ctx": num_ctx,
        "temperature": temperature,
        "near_context_limit": bool(threshold and token_estimate >= threshold),
        "context_warning_threshold": PROMPT_CONTEXT_WARNING_THRESHOLD,
    }
    observations = getattr(generator, "prompt_observations", None)
    if isinstance(observations, list):
        observations.append(observation)
    return observation


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

    def __init__(
        self,
        generator: ComplianceGenerator,
        *,
        max_candidates_per_obligation: int = 3,
        embedder: ComplianceEmbedder | None = None,
        min_semantic_candidate_score: float = MIN_SEMANTIC_CANDIDATE_SCORE,
    ) -> None:
        self.generator = generator
        self.max_candidates_per_obligation = max_candidates_per_obligation
        self.embedder = embedder
        self.min_semantic_candidate_score = min_semantic_candidate_score
        self.embedding_disabled = False
        self.last_candidate_diagnostics: dict[str, int | float] = _empty_candidate_diagnostics()

    def candidate_claims(
        self,
        obligation: ExtractedObligation,
        claims: list[ExtractedInternalClaim],
        *,
        min_alignment_score: float,
    ) -> list[tuple[ExtractedInternalClaim, float]]:
        scored = []
        diagnostics = _empty_candidate_diagnostics()
        for claim in claims:
            lexical_score = _alignment_score(obligation.key_terms, claim.key_terms)
            diagnostics["candidate_comparison_count"] += 1
            diagnostics["max_lexical_score"] = max(float(diagnostics["max_lexical_score"]), lexical_score)
            shared_high_risk_anchors = _shared_governed_anchor_tags(
                obligation.evidence.text,
                claim.evidence.text,
                allowed=HIGH_RISK_RESCUE_ANCHOR_TAGS,
            )
            shared_candidate_anchors = _shared_governed_anchor_tags(
                obligation.evidence.text,
                claim.evidence.text,
                allowed=CANDIDATE_RESCUE_ANCHOR_TAGS,
            )
            if shared_candidate_anchors:
                diagnostics["shared_anchor_overlap_count"] += 1
            semantic_score = 0.0
            semantic_rescue = False
            if lexical_score < min_alignment_score and not shared_candidate_anchors:
                semantic_score = self._semantic_alignment_score(
                    obligation.evidence.text,
                    claim.evidence.text,
                    diagnostics=diagnostics,
                )
                semantic_rescue = semantic_score >= self.min_semantic_candidate_score
            diagnostics["max_semantic_score"] = max(float(diagnostics["max_semantic_score"]), semantic_score)
            diagnostics["max_alignment_score"] = max(
                float(diagnostics["max_alignment_score"]),
                lexical_score,
                semantic_score,
            )
            if lexical_score < min_alignment_score and not shared_candidate_anchors and not semantic_rescue:
                continue
            score = _candidate_alignment_score(obligation, claim, lexical_score)
            if shared_high_risk_anchors and score < min_alignment_score:
                score = min_alignment_score
            elif shared_candidate_anchors and score < min_alignment_score:
                score = min_alignment_score
            if shared_candidate_anchors:
                score = max(score, MIN_SUPPORTED_ANCHOR_ALIGNMENT_SCORE)
            if semantic_rescue:
                score = max(score, min_alignment_score, round(semantic_score, 3))
            if score >= min_alignment_score:
                if lexical_score >= min_alignment_score:
                    diagnostics["lexical_candidate_count"] += 1
                if shared_candidate_anchors:
                    diagnostics["anchor_candidate_count"] += 1
                if semantic_rescue:
                    diagnostics["semantic_candidate_count"] += 1
                scored.append((claim, score))
        diagnostics["candidate_source_count"] = len(scored)
        self.last_candidate_diagnostics = diagnostics
        return [
            (claim, score)
            for claim, score in sorted(scored, key=lambda item: item[1], reverse=True)
        ][: self.max_candidates_per_obligation]

    def _semantic_alignment_score(self, left_text: str, right_text: str, *, diagnostics: dict[str, int | float]) -> float:
        if self.embedder is None or self.embedding_disabled:
            return 0.0
        diagnostics["semantic_attempt_count"] += 1
        try:
            return _cosine_similarity(self.embedder.embed(left_text), self.embedder.embed(right_text))
        except (OSError, TimeoutError, urllib.error.URLError, ValueError, json.JSONDecodeError, KeyError, TypeError):
            self.embedding_disabled = True
            diagnostics["embedding_error_count"] += 1
            return 0.0

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
        embedder: ComplianceEmbedder | None = None,
        min_semantic_candidate_score: float = MIN_SEMANTIC_CANDIDATE_SCORE,
    ) -> None:
        super().__init__()
        embedding_model_name = str(getattr(embedder, "model", "") or "")
        if embedding_model_name:
            self.prompt_version = f"{AGENT_PROMPT_VERSION}+semantic:{embedding_model_name}@{min_semantic_candidate_score:.2f}"
        self.agent = GovernanceReviewAgent(
            generator,
            max_candidates_per_obligation=max_candidates_per_obligation,
            embedder=embedder,
            min_semantic_candidate_score=min_semantic_candidate_score,
        )
        self.depth_agents = {
            depth: GovernanceReviewAgent(
                depth_generator,
                max_candidates_per_obligation=max_candidates_per_obligation,
                embedder=embedder,
                min_semantic_candidate_score=min_semantic_candidate_score,
            )
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
                "diagnostics": _finalise_pair_diagnostics(_new_pair_diagnostics(no_alignment_reason="pair_relevance_gate")),
            }

        findings, matched_claim_ids, diagnostics = self._review_obligations(obligations, internal_claims, request)
        if request.options.include_unsupported_internal_claims:
            findings.extend(_unsupported_claims(internal_claims, obligations, matched_claim_ids, request))

        findings = _consolidate_pair_findings(findings)
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
            "diagnostics": _finalise_pair_diagnostics(diagnostics),
        }

    def _review_obligations(
        self,
        obligations: list[ExtractedObligation],
        claims: list[ExtractedInternalClaim],
        request: ComplianceReviewRequest,
    ) -> tuple[list[ComplianceFinding], set[str], dict[str, Any]]:
        findings: list[ComplianceFinding] = []
        matched_claim_ids: set[str] = set()
        diagnostics = _new_pair_diagnostics()
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
            _merge_candidate_diagnostics(diagnostics, agent.last_candidate_diagnostics)
            diagnostics["candidate_count"] += len(candidates)
            if not candidates:
                diagnostics["no_candidate_obligation_count"] += 1
                diagnostics["no_alignment_reason"] = diagnostics["no_alignment_reason"] or "no_candidate_above_alignment_threshold"
                no_candidate_resolution = _resolve_no_candidate_obligation(
                    obligation,
                    claims,
                    agent.last_candidate_diagnostics,
                    request,
                )
                _record_no_candidate_resolution(diagnostics, no_candidate_resolution)
                if no_candidate_resolution == "not_related":
                    best_claim, best_score = _best_no_candidate_claim(obligation, claims)
                    findings.append(_no_candidate_not_related_finding(obligation, best_claim, best_score))
                    diagnostics["no_candidate_not_related_count"] += 1
                elif request.options.include_missing_obligations:
                    findings.append(_missing_obligation_fallback_finding(obligation, 0.0, reason="no_candidate"))
                    diagnostics["missing_obligation_fallback_count"] += 1
                continue

            accepted = False
            best_rejected: tuple[ExtractedInternalClaim, float, AgentDecision] | None = None
            for claim, score in candidates:
                if budget == 0:
                    break
                if budget is not None:
                    budget -= 1
                diagnostics["llm_called"] = True
                diagnostics["adjudication_count"] += 1
                try:
                    decision = agent.adjudicate(obligation, claim, score)
                except (OSError, TimeoutError, urllib.error.URLError, ValueError, json.JSONDecodeError):
                    decision = _fallback_decision(obligation, claim, score)
                    diagnostics["fallback_decision_count"] += 1
                diagnostics["model_decision_classifications"].append(decision.classification)
                if not request.options.disable_safety_gates:
                    before_gate = decision
                    decision = _apply_contradiction_safety_gate(
                        decision,
                        obligation,
                        claim,
                        score,
                        request.options.min_contradiction_alignment_score,
                    )
                    _record_gate_change(diagnostics, "contradiction_safety_gate", before_gate, decision)
                    before_supported_gate = decision
                    decision = _apply_supported_coverage_gate(decision, obligation, claim, score)
                    _record_gate_change(diagnostics, "supported_coverage_gate", before_supported_gate, decision)
                diagnostics["final_decision_classifications"].append(decision.classification)
                if decision.classification == "missing_obligation":
                    accepted = True
                    findings.append(_agent_finding(obligation, claim, decision, score))
                    break
                if not decision.same_obligation or decision.classification == "not_related":
                    diagnostics["non_accepted_decision_count"] += 1
                    diagnostics["rejected_decision_classifications"].append(decision.classification)
                    if best_rejected is None or score > best_rejected[1]:
                        best_rejected = (claim, score, decision)
                    continue
                matched_claim_ids.add(claim.id)
                accepted = True
                diagnostics["accepted_decision_classifications"].append(decision.classification)
                if decision.classification == "supported" and not request.options.include_supported_findings:
                    break
                findings.append(_agent_finding(obligation, claim, decision, score))
                break

            if not accepted and best_rejected is not None and request.options.include_not_related_pairs:
                claim, score, decision = best_rejected
                findings.append(_agent_finding(obligation, claim, decision, score))
                diagnostics["rejected_candidate_finding_count"] += 1
            elif not accepted and request.options.include_missing_obligations:
                best_score = candidates[0][1] if candidates else 0.0
                findings.append(_missing_obligation_fallback_finding(obligation, best_score, reason="no_accepted_candidate"))
                diagnostics["missing_obligation_fallback_count"] += 1

        return findings, matched_claim_ids, diagnostics

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
                "diagnostics": _finalise_pair_diagnostics(_new_pair_diagnostics(no_alignment_reason="pair_relevance_gate")),
            }

        findings = _duplicate_section_findings(source_a, source_b)
        budget = [_max_agent_calls(request)]
        diagnostics = _new_pair_diagnostics()
        findings.extend(self._review_internal_claims(claims_a, claims_b, request, budget=budget, diagnostics=diagnostics))
        findings.extend(self._review_internal_claims(claims_b, claims_a, request, budget=budget, diagnostics=diagnostics))
        findings = _dedupe_findings(findings)
        findings = _consolidate_pair_findings(findings)
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
            "diagnostics": _finalise_pair_diagnostics(diagnostics),
        }

    def _review_internal_claims(
        self,
        reference_claims: list[ExtractedInternalClaim],
        candidate_claims: list[ExtractedInternalClaim],
        request: ComplianceReviewRequest,
        *,
        budget: list[int | None] | None = None,
        diagnostics: dict[str, Any] | None = None,
    ) -> list[ComplianceFinding]:
        findings: list[ComplianceFinding] = []
        agent = self._agent_for_request(request)
        diagnostics = diagnostics if diagnostics is not None else _new_pair_diagnostics()
        for reference in reference_claims:
            if budget is not None and budget[0] == 0:
                break
            reference_as_obligation = _claim_as_obligation(reference)
            candidates = agent.candidate_claims(
                reference_as_obligation,
                candidate_claims,
                min_alignment_score=request.options.min_alignment_score,
            )
            _merge_candidate_diagnostics(diagnostics, agent.last_candidate_diagnostics)
            diagnostics["candidate_count"] += len(candidates)
            if not candidates:
                diagnostics["no_candidate_obligation_count"] += 1
                diagnostics["no_alignment_reason"] = diagnostics["no_alignment_reason"] or "no_candidate_above_alignment_threshold"
            for candidate, score in candidates:
                if budget is not None and budget[0] == 0:
                    break
                if budget is not None and budget[0] is not None:
                    budget[0] -= 1
                diagnostics["llm_called"] = True
                diagnostics["adjudication_count"] += 1
                try:
                    decision = agent.adjudicate_internal(reference, candidate, score)
                except (OSError, TimeoutError, urllib.error.URLError, ValueError, json.JSONDecodeError):
                    decision = _fallback_internal_decision(reference, candidate, score)
                    diagnostics["fallback_decision_count"] += 1
                diagnostics["model_decision_classifications"].append(decision.classification)
                if not request.options.disable_safety_gates:
                    before_gate = decision
                    decision = _apply_internal_contradiction_safety_gate(
                        decision,
                        reference,
                        candidate,
                        score,
                        request.options.min_contradiction_alignment_score,
                    )
                    _record_gate_change(diagnostics, "internal_contradiction_safety_gate", before_gate, decision)
                    before_supported_gate = decision
                    decision = _apply_supported_coverage_gate(decision, _claim_as_obligation(reference), candidate, score)
                    _record_gate_change(diagnostics, "supported_coverage_gate", before_supported_gate, decision)
                diagnostics["final_decision_classifications"].append(decision.classification)
                if not decision.same_obligation or decision.classification == "not_related":
                    diagnostics["non_accepted_decision_count"] += 1
                    diagnostics["rejected_decision_classifications"].append(decision.classification)
                    continue
                diagnostics["accepted_decision_classifications"].append(decision.classification)
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


def _resolve_no_candidate_obligation(
    obligation: ExtractedObligation,
    claims: list[ExtractedInternalClaim],
    candidate_diagnostics: dict[str, int | float],
    request: ComplianceReviewRequest,
) -> str:
    if not request.options.include_not_related_pairs or not claims:
        return "fallback_missing_obligation"
    if int(candidate_diagnostics.get("semantic_attempt_count", 0)) == 0:
        return "fallback_missing_obligation"
    if int(candidate_diagnostics.get("shared_anchor_overlap_count", 0)) > 0:
        return "fallback_missing_obligation"
    max_alignment = float(candidate_diagnostics.get("max_alignment_score", 0.0))
    if max_alignment < NO_CANDIDATE_NOT_RELATED_MAX_SCORE:
        return "not_related"
    return "fallback_missing_obligation"


def _best_no_candidate_claim(
    obligation: ExtractedObligation,
    claims: list[ExtractedInternalClaim],
) -> tuple[ExtractedInternalClaim | None, float]:
    best_claim: ExtractedInternalClaim | None = None
    best_score = 0.0
    for claim in claims:
        score = _alignment_score(obligation.key_terms, claim.key_terms)
        if best_claim is None or score > best_score:
            best_claim = claim
            best_score = score
    return best_claim, best_score


def _new_pair_diagnostics(*, no_alignment_reason: str = "") -> dict[str, Any]:
    return {
        "llm_called": False,
        "candidate_count": 0,
        "candidate_comparison_count": 0,
        "lexical_candidate_count": 0,
        "anchor_candidate_count": 0,
        "semantic_candidate_count": 0,
        "semantic_attempt_count": 0,
        "max_lexical_score": 0.0,
        "max_semantic_score": 0.0,
        "max_alignment_score": 0.0,
        "shared_anchor_overlap_count": 0,
        "embedding_error_count": 0,
        "adjudication_count": 0,
        "fallback_decision_count": 0,
        "non_accepted_decision_count": 0,
        "no_candidate_obligation_count": 0,
        "no_candidate_not_related_count": 0,
        "missing_obligation_fallback_count": 0,
        "rejected_candidate_finding_count": 0,
        "no_candidate_resolutions": [],
        "gate_demotion_reasons": [],
        "model_decision_classifications": [],
        "final_decision_classifications": [],
        "accepted_decision_classifications": [],
        "rejected_decision_classifications": [],
        "no_alignment_reason": no_alignment_reason,
    }


def _empty_candidate_diagnostics() -> dict[str, int | float]:
    return {
        "candidate_source_count": 0,
        "candidate_comparison_count": 0,
        "lexical_candidate_count": 0,
        "anchor_candidate_count": 0,
        "semantic_candidate_count": 0,
        "semantic_attempt_count": 0,
        "max_lexical_score": 0.0,
        "max_semantic_score": 0.0,
        "max_alignment_score": 0.0,
        "shared_anchor_overlap_count": 0,
        "embedding_error_count": 0,
    }


def _merge_candidate_diagnostics(pair_diagnostics: dict[str, Any], candidate_diagnostics: dict[str, int | float]) -> None:
    for key in (
        "candidate_comparison_count",
        "lexical_candidate_count",
        "anchor_candidate_count",
        "semantic_candidate_count",
        "semantic_attempt_count",
        "shared_anchor_overlap_count",
        "embedding_error_count",
    ):
        pair_diagnostics[key] = int(pair_diagnostics.get(key, 0)) + int(candidate_diagnostics.get(key, 0))
    for key in ("max_lexical_score", "max_semantic_score", "max_alignment_score"):
        pair_diagnostics[key] = max(float(pair_diagnostics.get(key, 0.0)), float(candidate_diagnostics.get(key, 0.0)))


def _record_no_candidate_resolution(diagnostics: dict[str, Any], resolution: str) -> None:
    diagnostics.setdefault("no_candidate_resolutions", []).append(resolution)


def _finalise_pair_diagnostics(diagnostics: dict[str, Any]) -> dict[str, Any]:
    gate_reasons = [
        str(reason)
        for reason in diagnostics.get("gate_demotion_reasons", [])
        if str(reason).strip()
    ]
    return {
        "llm_called": bool(diagnostics.get("llm_called")),
        "candidate_count": int(diagnostics.get("candidate_count", 0)),
        "candidate_comparison_count": int(diagnostics.get("candidate_comparison_count", 0)),
        "lexical_candidate_count": int(diagnostics.get("lexical_candidate_count", 0)),
        "anchor_candidate_count": int(diagnostics.get("anchor_candidate_count", 0)),
        "semantic_candidate_count": int(diagnostics.get("semantic_candidate_count", 0)),
        "semantic_attempt_count": int(diagnostics.get("semantic_attempt_count", 0)),
        "max_lexical_score": round(float(diagnostics.get("max_lexical_score", 0.0)), 3),
        "max_semantic_score": round(float(diagnostics.get("max_semantic_score", 0.0)), 3),
        "max_alignment_score": round(float(diagnostics.get("max_alignment_score", 0.0)), 3),
        "shared_anchor_overlap_count": int(diagnostics.get("shared_anchor_overlap_count", 0)),
        "embedding_error_count": int(diagnostics.get("embedding_error_count", 0)),
        "adjudication_count": int(diagnostics.get("adjudication_count", 0)),
        "fallback_decision_count": int(diagnostics.get("fallback_decision_count", 0)),
        "non_accepted_decision_count": int(diagnostics.get("non_accepted_decision_count", 0)),
        "no_candidate_obligation_count": int(diagnostics.get("no_candidate_obligation_count", 0)),
        "no_candidate_not_related_count": int(diagnostics.get("no_candidate_not_related_count", 0)),
        "missing_obligation_fallback_count": int(diagnostics.get("missing_obligation_fallback_count", 0)),
        "rejected_candidate_finding_count": int(diagnostics.get("rejected_candidate_finding_count", 0)),
        "no_candidate_resolution": _first_diagnostic_string(diagnostics.get("no_candidate_resolutions", [])),
        "no_candidate_resolutions": _diagnostic_string_list(diagnostics.get("no_candidate_resolutions", [])),
        "gate_demotion_reason": gate_reasons[0] if gate_reasons else "",
        "gate_demotion_reasons": gate_reasons,
        "model_decision_classifications": _diagnostic_string_list(diagnostics.get("model_decision_classifications", [])),
        "final_decision_classifications": _diagnostic_string_list(diagnostics.get("final_decision_classifications", [])),
        "accepted_decision_classifications": _diagnostic_string_list(diagnostics.get("accepted_decision_classifications", [])),
        "rejected_decision_classifications": _diagnostic_string_list(diagnostics.get("rejected_decision_classifications", [])),
        "no_alignment_reason": str(diagnostics.get("no_alignment_reason", "")),
    }


def _diagnostic_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _first_diagnostic_string(value: Any) -> str:
    values = _diagnostic_string_list(value)
    return values[0] if values else ""


def _record_gate_change(
    diagnostics: dict[str, Any],
    gate_name: str,
    before: AgentDecision,
    after: AgentDecision,
) -> None:
    if before == after:
        return
    diagnostics.setdefault("gate_demotion_reasons", []).append(_gate_change_reason(gate_name, before, after))


def _gate_change_reason(gate_name: str, before: AgentDecision, after: AgentDecision) -> str:
    rationale = after.rationale.lower()
    if "different timing contexts" in rationale or "supplies before a change" in rationale:
        reason = "temporal_context_mismatch"
    elif "exception or qualifier" in rationale:
        reason = "exception_qualifier_missing"
    elif "not share enough concrete obligation terms" in rationale:
        reason = "low_concrete_obligation_overlap"
    elif "goods while the other is scoped to services" in rationale:
        reason = "goods_services_scope_mismatch"
    elif "different business/private-use scopes" in rationale:
        reason = "business_private_scope_mismatch"
    elif "recommended action or suggested wording" in rationale or "proposed an edit" in rationale:
        reason = "supported_requested_change"
    elif "did not share a concrete governed object" in rationale:
        reason = "weak_supported_anchor"
    else:
        reason = "classification_changed"
    return f"{gate_name}:{before.classification}->{after.classification}:{reason}"


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
    if _is_direct_rate_change_invoice_conflict(obligation.evidence.text, claim.evidence.text):
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
    if _is_direct_rate_change_invoice_conflict(reference.evidence.text, candidate.evidence.text):
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
    if _has_goods_services_mismatch(obligation.evidence.text, claim.evidence.text):
        return _unsupported_coverage_decision(
            decision,
            rationale=(
                "The model proposed supported coverage, but one passage is scoped to goods while the other is scoped "
                "to services. That context difference is too material for assurance evidence."
            ),
            advisor_summary="Goods-only and services-only VAT wording was not treated as clean supported coverage.",
        )
    if _has_business_use_scope_mismatch(obligation.evidence.text, claim.evidence.text):
        return _unsupported_coverage_decision(
            decision,
            rationale=(
                "The model proposed supported coverage, but one passage is scoped to wholly business-use items later "
                "put to private use while the other covers mixed business/private use from the start."
            ),
            advisor_summary="Different business/private-use scopes were not treated as clean supported coverage.",
        )
    if _has_vat_business_use_vs_list_logic_mismatch(obligation.evidence.text, claim.evidence.text):
        return _unsupported_coverage_decision(
            decision,
            rationale=(
                "The model proposed supported coverage, but one passage is about VAT business/private-use "
                "apportionment while the other is about list-logic business use."
            ),
            advisor_summary="VAT apportionment wording was not treated as support for generic article-list logic.",
        )
    if _has_generic_obligation_dismissal_conflict(obligation, claim):
        return AgentDecision(
            same_obligation=True,
            classification="contradiction",
            severity="high",
            confidence=min(max(decision.confidence, 0.74), 0.86),
            rationale=(
                "The model proposed supported coverage, but the external passage imposes a requirement while the "
                "internal passage dismisses, excludes or negates that requirement."
            ),
            recommended_action=(
                "Review and remove the dismissal or replace it with wording that preserves the external requirement."
            ),
            advisor_summary="Requirement-versus-dismissal polarity was treated as a contradiction, not supported coverage.",
            why_it_matters="A passage cannot be assurance evidence if it says the required activity can be ignored or does not apply.",
            proposed_internal_text=decision.proposed_internal_text,
            confidence_interpretation=(
                "High confidence polarity guard; human review should confirm the same obligation scope before editing."
            ),
            evidence_highlights=decision.evidence_highlights,
        )
    if _supported_decision_requests_change(decision):
        if _external_has_exception_that_internal_omits(obligation.evidence.text, claim.evidence.text):
            return AgentDecision(
                same_obligation=True,
                classification="missing_detail",
                severity="medium",
                confidence=min(decision.confidence, 0.72),
                rationale=(
                    "The model labelled this pair as supported, but it also proposed an edit and the external passage "
                    "contains an exception or qualifier missing from the broader internal wording."
                ),
                recommended_action="Review whether the external exception should be added to the internal guidance.",
                advisor_summary="The internal wording may be aligned in principle but missing a material qualifier.",
                why_it_matters="Supported coverage should not carry an edit suggestion; qualifier gaps need human review.",
                proposed_internal_text=decision.proposed_internal_text,
                confidence_interpretation="Moderate confidence; review before editing approved knowledge.",
                evidence_highlights=decision.evidence_highlights,
            )
        return _unsupported_coverage_decision(
            decision,
            rationale=(
                "The model proposed supported coverage, but its recommended action or suggested wording indicates the "
                "internal text may still need a change. This is not clean assurance evidence."
            ),
            advisor_summary="Supported findings must be no-action evidence; edit-style recommendations are suppressed.",
        )
    shared_anchors = _shared_governed_anchor_tags(
        obligation.evidence.text,
        claim.evidence.text,
        allowed=CANDIDATE_RESCUE_ANCHOR_TAGS,
    )
    rate_change_anchors = _shared_governed_anchor_tags(
        obligation.evidence.text,
        claim.evidence.text,
        allowed=RATE_CHANGE_ANCHOR_TAGS,
    )
    concrete_overlap = _concrete_shared_terms(obligation, claim)
    if shared_anchors and score >= MIN_SUPPORTED_ANCHOR_ALIGNMENT_SCORE:
        return decision
    if (
        rate_change_anchors
        and score >= MIN_RATE_CHANGE_SUPPORTED_ALIGNMENT_SCORE
        and not _has_supply_timing_mismatch(obligation.evidence.text, claim.evidence.text)
    ):
        return decision
    if score >= MIN_SUPPORTED_STRONG_ALIGNMENT_SCORE and len(concrete_overlap) >= MIN_CONCRETE_CONTRADICTION_TERMS:
        return decision
    return _unsupported_coverage_decision(
        decision,
        rationale=(
            "The model proposed supported coverage, but the passages did not share a concrete governed object "
            "strongly enough to treat this as assurance evidence."
        ),
        advisor_summary="The passages share broad wording but not a concrete enough governed rule for supported coverage.",
    )


def _unsupported_coverage_decision(
    decision: AgentDecision,
    *,
    rationale: str,
    advisor_summary: str,
) -> AgentDecision:
    return AgentDecision(
        same_obligation=False,
        classification="not_related",
        severity="low",
        confidence=min(decision.confidence, 0.55),
        rationale=rationale,
        recommended_action="No supported coverage action is suggested for this weak evidence pair.",
        advisor_summary=advisor_summary,
        why_it_matters="Coverage evidence should be cleaner than exploratory matching, otherwise it can overstate assurance.",
        confidence_interpretation="Low confidence after supported-coverage gate; omitted from coverage evidence.",
    )


def _supported_decision_requests_change(decision: AgentDecision) -> bool:
    if decision.proposed_internal_text.strip():
        return True
    action = decision.recommended_action.strip()
    if not action:
        return False
    if SUPPORTED_NOOP_ACTION_PATTERN.search(action):
        return False
    return bool(SUPPORTED_CHANGE_ACTION_PATTERN.search(action))


def _has_goods_services_mismatch(left_text: str, right_text: str) -> bool:
    left_goods = bool(GOODS_PATTERN.search(left_text))
    left_services = bool(SERVICES_PATTERN.search(left_text))
    right_goods = bool(GOODS_PATTERN.search(right_text))
    right_services = bool(SERVICES_PATTERN.search(right_text))
    return (
        (left_goods and not left_services and right_services and not right_goods)
        or (right_goods and not right_services and left_services and not left_goods)
    )


def _has_business_use_scope_mismatch(left_text: str, right_text: str) -> bool:
    left_wholly = bool(WHOLLY_BUSINESS_USE_PATTERN.search(left_text))
    right_wholly = bool(WHOLLY_BUSINESS_USE_PATTERN.search(right_text))
    left_both = bool(BOTH_BUSINESS_PRIVATE_USE_PATTERN.search(left_text))
    right_both = bool(BOTH_BUSINESS_PRIVATE_USE_PATTERN.search(right_text))
    return (left_wholly and right_both) or (right_wholly and left_both)


def _has_vat_business_use_vs_list_logic_mismatch(left_text: str, right_text: str) -> bool:
    return (
        (_is_vat_business_use_apportionment(left_text) and _is_list_logic_business_use(right_text))
        or (_is_vat_business_use_apportionment(right_text) and _is_list_logic_business_use(left_text))
    )


def _has_generic_obligation_dismissal_conflict(
    obligation: ExtractedObligation,
    claim: ExtractedInternalClaim,
) -> bool:
    if obligation.modality not in {"obligation", "prohibition"}:
        return False
    if not DISMISSAL_OR_NEGATION_PATTERN.search(claim.evidence.text):
        return False
    shared_anchors = _shared_governed_anchor_tags(
        obligation.evidence.text,
        claim.evidence.text,
        allowed=CANDIDATE_RESCUE_ANCHOR_TAGS,
    )
    concrete_overlap = _concrete_shared_terms(obligation, claim)
    return bool(shared_anchors or len(concrete_overlap) >= 1)


def _is_vat_business_use_apportionment(text: str) -> bool:
    lowered = text.lower()
    return (
        ("vat" in lowered or "input tax" in lowered or "tax" in lowered)
        and BUSINESS_USE_PATTERN.search(text) is not None
        and re.search(r"\b(proportion|percentage|private|reclaim|apportion|calculate)\b", text, re.I) is not None
    )


def _is_list_logic_business_use(text: str) -> bool:
    lowered = text.lower()
    return (
        ("list" in lowered or "lists" in lowered)
        and "business use" in lowered
        and re.search(r"\b(logic|case|profile|profiles|user|users|authorised|authorized)\b", text, re.I) is not None
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


def _is_direct_rate_change_invoice_conflict(left_text: str, right_text: str) -> bool:
    if not _shared_governed_anchor_tags(left_text, right_text, allowed=RATE_CHANGE_ANCHOR_TAGS):
        return False
    left = left_text.lower()
    right = right_text.lower()
    return (
        (_requires_old_or_applied_rate_on_invoice(left) and _denies_old_or_applied_rate_on_invoice(right))
        or (_requires_old_or_applied_rate_on_invoice(right) and _denies_old_or_applied_rate_on_invoice(left))
    )


def _requires_old_or_applied_rate_on_invoice(text: str) -> bool:
    has_invoice = "invoice" in text or "invoices" in text
    has_rate = "rate" in text
    if not has_invoice or not has_rate:
        return False
    return bool(
        re.search(r"\b(must|shall|required|requires|should)\b.{0,120}\b(old|applied|in force)\b.{0,40}\brate\b", text, re.I)
        or re.search(r"\b(old|applied|in force)\b.{0,40}\brate\b.{0,120}\b(must|shall|required|requires|should)\b", text, re.I)
        or re.search(
            r"\b(must|shall|required|requires|should)\b.{0,120}\brate\b.{0,80}\b(applied|in force|time of supply|date of supply)\b",
            text,
            re.I,
        )
    )


def _denies_old_or_applied_rate_on_invoice(text: str) -> bool:
    has_invoice = "invoice" in text or "invoices" in text
    if not has_invoice:
        return False
    return bool(
        re.search(r"\bold(?:\s+vat)?\s+rate\b.{0,120}\b(must not|should not|shall not|never|not be shown)\b", text, re.I)
        or re.search(r"\b(must not|should not|shall not|never)\b.{0,120}\bold(?:\s+vat)?\s+rate\b", text, re.I)
        or re.search(r"\balways\b.{0,80}\bnew(?:\s+vat)?\s+rate\b", text, re.I)
        or re.search(r"\bnew(?:\s+vat)?\s+rate\b.{0,120}\b(before|for supplies made before|even for supplies)\b", text, re.I)
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
    if VAT_EVIDENCE_PATTERN.search(text):
        tags.add("vat_evidence")
    if BUSINESS_USE_PATTERN.search(text):
        tags.add("business_use_proportion")
    lowered = text.lower()
    rate_change_topic = (
        "change" in lowered
        or "old rate" in lowered
        or "old vat rate" in lowered
        or "new rate" in lowered
        or "date of supply" in lowered
        or "supply took place" in lowered
        or "in force" in lowered
    )
    if RATE_CHANGE_PATTERN.search(text) and rate_change_topic:
        tags.add("vat_rate_change")
        if RATE_CHANGE_OBJECT_PATTERN.search(text):
            tags.add("vat_rate_change_invoice")
    if INPUT_TAX_EVIDENCE_PATTERN.search(text) and RECORD_EVIDENCE_PATTERN.search(text):
        tags.add("input_tax_evidence")
    if DISBURSEMENT_EVIDENCE_PATTERN.search(text) and RECORD_EVIDENCE_PATTERN.search(text):
        tags.add("disbursement_evidence")
    if PACKAGING_PATTERN.search(text):
        if PACKAGING_MATERIAL_PATTERN.search(text):
            tags.add("packaging_material")
        if PACKAGING_THRESHOLD_PATTERN.search(text):
            tags.add("packaging_threshold")
        if PACKAGING_EVIDENCE_PATTERN.search(text):
            tags.add("packaging_evidence")
        if PACKAGING_SUBMISSION_PATTERN.search(text):
            tags.add("packaging_submission")
        if PACKAGING_DEADLINE_PATTERN.search(text):
            tags.add("packaging_deadline")
        if PACKAGING_THIRD_PARTY_PATTERN.search(text):
            tags.add("packaging_third_party")
        if PACKAGING_SUPPLIER_PATTERN.search(text):
            tags.add("packaging_supplier")
        if PACKAGING_HOUSEHOLD_PATTERN.search(text):
            tags.add("packaging_household")
        if PACKAGING_REUSABLE_PATTERN.search(text):
            tags.add("packaging_reusable")
    return tags


def _consolidate_pair_findings(findings: list[ComplianceFinding]) -> list[ComplianceFinding]:
    grouped: dict[str, list[ComplianceFinding]] = {}
    passthrough: list[ComplianceFinding] = []
    for finding in findings:
        key = _finding_consolidation_key(finding)
        if not key:
            passthrough.append(finding)
            continue
        grouped.setdefault(key, []).append(finding)

    consolidated = list(passthrough)
    for items in grouped.values():
        best = min(items, key=_consolidation_rank)
        consolidated.append(_with_consolidation_signal(best, len(items)))
    return consolidated


def _finding_consolidation_key(finding: ComplianceFinding) -> str:
    if finding.internal_evidence is None:
        return ""
    normalized_internal = _normalised_text(finding.internal_evidence.text)
    if not normalized_internal:
        return ""
    if finding.classification in ACTIONABLE_CONSOLIDATION_CLASSIFICATIONS:
        return "|".join(["action", finding.internal_evidence.source_id, normalized_internal])
    if finding.classification == "supported":
        return "|".join(["supported", finding.internal_evidence.source_id, normalized_internal])
    return ""


def _consolidation_rank(finding: ComplianceFinding) -> tuple[int, int, float, float, int, str]:
    external_text_length = len(finding.external_evidence.text) if finding.external_evidence else 999_999
    return (
        CONSOLIDATED_CLASSIFICATION_RANK.get(finding.classification, 99),
        _severity_rank(finding.severity),
        -finding.confidence,
        -finding.alignment_score,
        external_text_length,
        finding.id,
    )


def _with_consolidation_signal(finding: ComplianceFinding, count: int) -> ComplianceFinding:
    if count <= 1:
        return finding
    signal_name = "consolidated_supported_findings" if finding.classification == "supported" else "consolidated_related_findings"
    updated = finding.model_copy(deep=True)
    updated.signals = [
        signal
        for signal in updated.signals
        if not signal.startswith("consolidated_related_findings=")
        and not signal.startswith("consolidated_supported_findings=")
    ]
    updated.signals.append(f"{signal_name}={count}")
    return updated


def _agent_finding(
    obligation: ExtractedObligation,
    claim: ExtractedInternalClaim,
    decision: AgentDecision,
    score: float,
) -> ComplianceFinding:
    signals = [
        f"agent_prompt_version={AGENT_PROMPT_VERSION}",
        f"agent_same_obligation={str(decision.same_obligation).lower()}",
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


def _missing_obligation_fallback_finding(
    obligation: ExtractedObligation,
    score: float,
    *,
    reason: str,
) -> ComplianceFinding:
    finding = _missing_obligation_finding(obligation, score).model_copy(deep=True)
    finding.signals = [
        *finding.signals,
        f"agent_prompt_version={AGENT_PROMPT_VERSION}",
        f"missing_obligation_source=fallback:{reason}",
    ]
    finding.rationale = (
        "No candidate internal passage reached Governance Review Agent adjudication for this external obligation. "
        "Treat this as a candidate-selection fallback, not as a model-confirmed missing obligation."
    )
    finding.confidence = min(finding.confidence, 0.62)
    finding.confidence_interpretation = (
        "Fallback confidence is intentionally capped because no candidate pair was adjudicated by the LLM."
    )
    finding.advisor_summary = "Potential missing obligation, but the reasoning model did not receive an aligned internal passage."
    finding.why_it_matters = (
        "This separates retrieval/alignment gaps from confirmed governance gaps so reviewers can tune candidate selection separately."
    )
    finding.recommended_action = "Review candidate alignment before treating this as a confirmed missing obligation."
    return _with_advisor_fields(finding)


def _no_candidate_not_related_finding(
    obligation: ExtractedObligation,
    claim: ExtractedInternalClaim | None,
    score: float,
) -> ComplianceFinding:
    internal_evidence = claim.evidence if claim is not None else None
    internal_claim_id = claim.id if claim is not None else ""
    return _with_advisor_fields(ComplianceFinding(
        id=_finding_id("no-candidate-not-related", obligation.id, internal_claim_id),
        classification="not_related",
        severity="low",
        confidence=round(max(0.62, 1 - score), 3),
        alignment_score=round(score, 3),
        rationale=(
            "No candidate internal passage reached the alignment threshold, and the best available wording did not "
            "share governed anchors or enough lexical/semantic similarity to treat this as a coverage gap."
        ),
        obligation_id=obligation.id,
        internal_claim_id=internal_claim_id,
        external_evidence=obligation.evidence,
        internal_evidence=internal_evidence,
        signals=[
            f"agent_prompt_version={AGENT_PROMPT_VERSION}",
            "no_candidate_resolution=not_related",
            f"external_modality={obligation.modality}",
        ],
        advisor_summary="The no-candidate resolver treated this pair as unrelated rather than a missing internal obligation.",
        why_it_matters=(
            "This prevents unrelated internal passages from inflating missing-obligation counts when candidate "
            "alignment finds no comparable wording."
        ),
        recommended_action="No compliance edit is suggested unless a reviewer can identify a same-topic internal passage.",
        confidence_interpretation="Deterministic low-relatedness decision; review if the document pair should have been in scope.",
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
2. If they are not about the same obligation and the internal passage is outside the same governance topic,
   return classification "not_related".
3. Return "too_vague" when the internal passage is on the same topic but is materially weaker, generic,
   high-level, or lacks the precision needed to show equivalent compliance.
4. Return "missing_detail" when the internal passage covers the same topic but omits a material qualifier,
   exception, evidence type, actor, timing rule, category, threshold, scope condition, or required data item.
5. Return "missing_obligation" only when the internal passage is in a neighbouring/same governance area but
   does not attempt to cover the concrete external obligation at all. Do not use "missing_obligation" for
   partial, generic or incomplete coverage; use "too_vague" or "missing_detail" instead.
6. Only return "contradiction" when both passages address the same obligation
   and the internal wording conflicts with, weakens, permits, or denies what the
   external source requires.
7. Do not treat generic discourse or modal words as topic overlap. Words such as
   "but", "still", "may", "must", "needed", "required", "should", "can" are not enough.
8. Same-obligation requires the same concrete governed object, business domain,
   actor/action and outcome. Similar abstract ideas are not enough.
9. Return "supported" only when no edit, review action or wording change is needed.
   If the internal wording needs clarification, an exception, narrower scope or
   a replacement sentence, return "missing_detail", "too_vague" or
   "needs_human_review" instead.
10. Do not treat goods-only VAT guidance as clean support for services-only
   internal wording, or vice versa, unless both passages explicitly cover both.
11. Generic class-boundary rules:
   - If internal wording is on the same concrete topic but uses broad, generic or imprecise language,
     return "too_vague".
   - If internal wording is on the same concrete topic but omits a required category, scope condition,
     evidence type, actor, timing rule, threshold, exception or data item, return "missing_detail".
   - If the internal document is a plausible neighbouring governance source but makes no attempt to
     cover the concrete external requirement, return "missing_obligation".
   - If the passages only share generic words or a broad business area but govern different actions,
     objects, actors, timing, permissions or outcomes, return "not_related".
12. If the external passage imposes a requirement and the internal passage says the activity can be
   ignored, is optional, does not apply, is not required, is excluded, or may be deleted, do not return
   "supported"; return "contradiction" when the concrete obligation is the same, otherwise
   "needs_human_review" or "not_related".
13. If uncertain, return "not_related" or "needs_human_review"; do not force a contradiction.
14. Do not give legal advice. Produce a governance triage result for human review.
15. If you use private reasoning, do not include it in the response. Return final JSON only.

Allowed classification values:
- not_related
- supported
- contradiction
- missing_obligation
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
7. Return "supported" only when the passages are consistent, complementary and no edit, review action or replacement
   wording is needed.
8. If the compared internal wording needs clarification, a missing qualifier, narrower scope or replacement wording,
   return "missing_detail", "too_vague" or "needs_human_review" instead of "supported".
9. If uncertain, return "not_related" or "needs_human_review"; do not force a contradiction.
10. Do not give legal advice. Produce a governance triage result for human review.
11. If you use private reasoning, do not include it in the response. Return final JSON only.

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
    if not same_obligation and classification != "missing_obligation":
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


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return round(max(0.0, min(1.0, dot / (left_norm * right_norm))), 3)
