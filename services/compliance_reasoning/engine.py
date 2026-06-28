"""Deterministic baseline compliance reasoning engine.

This module deliberately avoids model dependencies. It gives the standalone
service a runnable contract and a transparent baseline before we add retrieval,
NLI and local LLM adjudication.
"""

from __future__ import annotations

import hashlib
import re
import time
from collections.abc import Iterable
from datetime import datetime, timezone

from .cache import PairResultCache, cached_findings, pair_cache_key
from .models import (
    ComplianceFinding,
    ComplianceReviewRequest,
    ComplianceReviewResult,
    EvidenceDocument,
    EvidenceSection,
    ExtractedInternalClaim,
    ExtractedObligation,
    ReviewAudit,
    ReviewMode,
    ReviewPairProgress,
    ReviewStatus,
    StatementModality,
    TextEvidence,
)
from .store import ComplianceReviewStore

STOP_WORDS = {
    "about",
    "above",
    "after",
    "again",
    "against",
    "also",
    "and",
    "actor",
    "are",
    "able",
    "before",
    "being",
    "business",
    "certain",
    "but",
    "between",
    "can",
    "could",
    "does",
    "doing",
    "during",
    "each",
    "from",
    "for",
    "has",
    "have",
    "into",
    "may",
    "more",
    "must",
    "need",
    "needed",
    "needs",
    "only",
    "old",
    "other",
    "over",
    "same",
    "shall",
    "should",
    "some",
    "still",
    "such",
    "than",
    "that",
    "the",
    "their",
    "then",
    "there",
    "these",
    "this",
    "them",
    "those",
    "through",
    "under",
    "until",
    "unspecified",
    "were",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
    "use",
    "used",
    "uses",
    "using",
    "you",
    "your",
}

MODAL_PATTERNS: tuple[tuple[StatementModality, re.Pattern[str]], ...] = (
    ("prohibition", re.compile(r"\b(must not|shall not|must never|not permitted|prohibited|forbidden)\b", re.I)),
    ("obligation", re.compile(r"\b(must|shall|required to|requires|need to|needs to|has to|have to|is mandatory|are mandatory)\b", re.I)),
    ("permission", re.compile(r"\b(may|can|permitted|allowed|optional|not required)\b", re.I)),
    ("recommendation", re.compile(r"\b(should|recommended|expected to|best practice)\b", re.I)),
)

CONDITION_PATTERN = re.compile(r"\b(if|where|when|unless|except where|provided that)\b(.+)$", re.I)
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+|\n+")
TOKEN_PATTERN = re.compile(r"[a-z][a-z0-9-]{2,}", re.I)
MIN_SHARED_ALIGNMENT_TERMS = 2


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DeterministicComplianceEngine:
    """LLM-ready queued pairwise engine with a conservative deterministic fallback."""

    audit_engine = "queued-pairwise-review"
    engine_version = "0.1.0"
    model_profile = "llm-ready-deterministic-fallback"
    prompt_version = ""
    audit_assumptions = [
        "Queued pairwise workflow: each external source is checked against each approved internal source in isolation.",
        "Current local mode is deterministic fallback; configure the LLM adapter for long-context semantic adjudication.",
        "Unrelated document pairs are suppressed by default and should not be treated as compliance findings.",
        "No legal conclusion is final without human review.",
    ]

    def prepare_pairs(self, request: ComplianceReviewRequest) -> list[ReviewPairProgress]:
        pairs: list[ReviewPairProgress] = []
        for left, right in _document_pairs(request):
            pairs.append(
                ReviewPairProgress(
                    pair_id=_pair_id(left, right, request.review_mode),
                    external_document_id=left.id,
                    external_title=left.title,
                    internal_document_id=right.id,
                    internal_title=right.title,
                    input_weight=_pair_input_weight(left, right),
                )
            )
        return pairs

    def run_queued_job(
        self,
        job_id: str,
        request: ComplianceReviewRequest,
        store: ComplianceReviewStore,
        cache: PairResultCache | None = None,
    ) -> None:
        try:
            audit = ReviewAudit(
                engine=self.audit_engine,
                engine_version=self.engine_version,
                model_profile=self.model_profile,
                prompt_version=self.prompt_version,
                review_mode=request.review_mode,
                external_document_count=len(request.external_documents),
                internal_document_count=len(request.internal_documents),
                source_hashes=_source_hashes([*request.external_documents, *request.internal_documents]),
                assumptions=self.audit_assumptions,
            )
            store.mark_running(job_id, audit)
            for external, internal in _document_pairs(request):
                pair_id = _pair_id(external, internal, request.review_mode)
                store.mark_pair_running(job_id, pair_id)
                cache_status = "bypassed" if request.options.force_rerun else "miss"
                cache_key = pair_cache_key(external, internal, request, engine=self)
                cached = None if request.options.force_rerun or cache is None else cache.get(cache_key)
                if cached is not None:
                    store.complete_pair(
                        job_id,
                        pair_id,
                        status=cached.get("status", "completed"),
                        classification=cached.get("classification", ""),
                        relevance_score=float(cached.get("relevance_score", 0.0)),
                        rationale=cached.get("rationale", ""),
                        findings=cached_findings(cached),
                        obligation_count=int(cached.get("obligation_count", 0)),
                        internal_claim_count=int(cached.get("internal_claim_count", 0)),
                        cache_status="hit",
                    )
                    continue
                started = time.perf_counter()
                pair = self.review_document_pair(external, internal, request)
                duration_seconds = time.perf_counter() - started
                if cache is not None:
                    cache.set(cache_key, pair, duration_seconds=duration_seconds)
                store.complete_pair(
                    job_id,
                    pair_id,
                    status=pair["status"],
                    classification=pair["classification"],
                    relevance_score=pair["relevance_score"],
                    rationale=pair["rationale"],
                    findings=pair["findings"],
                    obligation_count=pair["obligation_count"],
                    internal_claim_count=pair["internal_claim_count"],
                    cache_status=cache_status,
                )
            store.complete(job_id, max_findings=request.options.max_findings)
        except Exception as exc:  # pragma: no cover - defensive job boundary
            store.fail(job_id, str(exc))

    def review_document_pair(self, external: EvidenceDocument, internal: EvidenceDocument, request: ComplianceReviewRequest) -> dict:
        if request.review_mode == "internal_vs_internal":
            return review_internal_document_pair(external, internal, request)
        return review_document_pair(external, internal, request)

    def run(self, job_id: str, request: ComplianceReviewRequest, created_at: str | None = None) -> ComplianceReviewResult:
        created = created_at or utc_now()
        obligations = extract_obligations(request.external_documents)
        internal_claims = extract_internal_claims(request.internal_documents)
        findings = compare_obligations_to_claims(obligations, internal_claims, request)
        completed = utc_now()
        audit = ReviewAudit(
            external_document_count=len(request.external_documents),
            internal_document_count=len(request.internal_documents),
            review_mode=request.review_mode,
            source_hashes=_source_hashes([*request.external_documents, *request.internal_documents]),
            assumptions=[
                "Deterministic baseline only; no legal conclusion is final without human review.",
                "Sentence-level modal extraction is used until the model-backed obligation extractor is added.",
                "Term-overlap alignment is used until embedding, reranking and NLI components are added.",
            ],
        )
        status = ReviewStatus(
            job_id=job_id,
            status="completed",
            created_at=created,
            completed_at=completed,
            obligation_count=len(obligations),
            internal_claim_count=len(internal_claims),
            finding_count=len(findings),
            audit=audit,
            review_mode=request.review_mode,
        )
        return ComplianceReviewResult(
            status=status,
            obligations=obligations,
            internal_claims=internal_claims,
            findings=findings,
        )


def extract_obligations(documents: Iterable[EvidenceDocument]) -> list[ExtractedObligation]:
    obligations: list[ExtractedObligation] = []
    for document in documents:
        for section in _sections(document):
            for sentence in _sentences(section.text):
                modal = _detect_modality(sentence)
                if modal is None or modal[0] not in {"obligation", "prohibition", "permission"}:
                    continue
                modality, match = modal
                actor, action, condition = _actor_action_condition(sentence, match)
                if not action:
                    continue
                evidence = _evidence(document, section, sentence)
                obligations.append(
                    ExtractedObligation(
                        id=_statement_id("obl", document.id, section.id, sentence),
                        modality=modality,
                        actor=actor,
                        action=action,
                        condition=condition,
                        key_terms=_key_terms(f"{actor} {action} {condition}"),
                        evidence=evidence,
                    )
                )
    return obligations


def extract_internal_claims(documents: Iterable[EvidenceDocument]) -> list[ExtractedInternalClaim]:
    claims: list[ExtractedInternalClaim] = []
    for document in documents:
        for section in _sections(document):
            for sentence in _sentences(section.text):
                modal = _detect_modality(sentence)
                if modal is None:
                    continue
                modality, match = modal
                actor, action, condition = _actor_action_condition(sentence, match)
                if not action:
                    continue
                evidence = _evidence(document, section, sentence)
                claims.append(
                    ExtractedInternalClaim(
                        id=_statement_id("claim", document.id, section.id, sentence),
                        modality=modality,
                        actor=actor,
                        action=action,
                        condition=condition,
                        key_terms=_key_terms(f"{actor} {action} {condition}"),
                        evidence=evidence,
                    )
                )
    return claims


def compare_obligations_to_claims(
    obligations: list[ExtractedObligation],
    claims: list[ExtractedInternalClaim],
    request: ComplianceReviewRequest,
) -> list[ComplianceFinding]:
    findings: list[ComplianceFinding] = []
    matched_claim_ids: set[str] = set()

    for obligation in obligations:
        best_claim, score = _best_claim(obligation, claims)
        if best_claim is None or score < request.options.min_alignment_score:
            if request.options.include_missing_obligations:
                findings.append(_missing_obligation_finding(obligation, score))
            continue

        matched_claim_ids.add(best_claim.id)
        finding = _classify_pair(obligation, best_claim, score)
        if finding.classification == "supported" and not request.options.include_supported_findings:
            continue
        findings.append(finding)

    if request.options.include_unsupported_internal_claims:
        for claim in claims:
            if claim.id in matched_claim_ids:
                continue
            best_obligation, score = _best_obligation(claim, obligations)
            if best_obligation is not None and score >= request.options.min_alignment_score:
                continue
            findings.append(_unsupported_claim_finding(claim, score))

    findings.sort(key=lambda item: (_severity_rank(item.severity), -item.confidence, item.classification, item.id))
    return findings[: request.options.max_findings]


def review_document_pair(external: EvidenceDocument, internal: EvidenceDocument, request: ComplianceReviewRequest) -> dict:
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

    pair_request = request.model_copy(deep=True)
    pair_request.external_documents = [external]
    pair_request.internal_documents = [internal]
    findings = compare_obligations_to_claims(obligations, internal_claims, pair_request)
    classification = findings[0].classification if findings else "supported"
    return {
        "status": "completed",
        "classification": classification,
        "relevance_score": relevance_score,
        "rationale": "External and internal documents passed the pair relevance gate and were compared for obligation consistency.",
        "findings": findings,
        "obligation_count": len(obligations),
        "internal_claim_count": len(internal_claims),
    }


def review_internal_document_pair(source_a: EvidenceDocument, source_b: EvidenceDocument, request: ComplianceReviewRequest) -> dict:
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
    findings.extend(_compare_internal_claims(claims_a, claims_b, request))
    findings.extend(_compare_internal_claims(claims_b, claims_a, request))
    findings = _dedupe_findings(findings)
    findings.sort(key=lambda item: (_severity_rank(item.severity), -item.confidence, item.classification, item.id))
    findings = findings[: request.options.max_findings]
    classification = findings[0].classification if findings else "supported"
    return {
        "status": "completed",
        "classification": classification,
        "relevance_score": relevance_score,
        "rationale": "Internal sources passed the pair relevance gate and were compared for consistency, duplicate wording and governed-rule alignment.",
        "findings": findings,
        "obligation_count": len(claims_a),
        "internal_claim_count": len(claims_b),
    }


def _compare_internal_claims(
    reference_claims: list[ExtractedInternalClaim],
    candidate_claims: list[ExtractedInternalClaim],
    request: ComplianceReviewRequest,
) -> list[ComplianceFinding]:
    findings: list[ComplianceFinding] = []
    for reference in reference_claims:
        reference_obligation = _claim_as_obligation(reference)
        candidate, score = _best_claim(reference_obligation, candidate_claims)
        if candidate is None or score < request.options.min_alignment_score:
            if request.options.include_missing_obligations and reference.modality in {"obligation", "prohibition"}:
                finding = _missing_obligation_finding(reference_obligation, score)
                finding.classification = "missing_detail"
                finding.rationale = "One internal source contains a governed rule that is not clearly covered in the compared internal source."
                finding = _with_advisor_fields(finding)
                findings.append(finding)
            continue
        finding = _classify_pair(reference_obligation, candidate, score)
        if finding.classification == "supported" and not request.options.include_supported_findings:
            continue
        findings.append(finding)
    return findings


def _claim_as_obligation(claim: ExtractedInternalClaim) -> ExtractedObligation:
    return ExtractedObligation(
        id=claim.id.replace("claim-", "obl-internal-", 1),
        modality=claim.modality,
        actor=claim.actor,
        action=claim.action,
        condition=claim.condition,
        key_terms=claim.key_terms,
        evidence=claim.evidence,
    )


def _duplicate_section_findings(source_a: EvidenceDocument, source_b: EvidenceDocument) -> list[ComplianceFinding]:
    findings: list[ComplianceFinding] = []
    for left in _sections(source_a):
        left_terms = _key_terms(left.text)
        if len(left_terms) < 8:
            continue
        for right in _sections(source_b):
            right_terms = _key_terms(right.text)
            if len(right_terms) < 8:
                continue
            score = _alignment_score(left_terms, right_terms)
            if score < 0.88:
                continue
            findings.append(
                _internal_pair_finding(
                    "duplicate",
                    "low",
                    min(0.86, 0.45 + score),
                    score,
                    "Two internal sources contain highly similar substantive wording; review whether one should be trimmed or referenced instead of repeated.",
                    _evidence(source_a, left, left.text),
                    _evidence(source_b, right, right.text),
                    ["internal_pair_duplicate_candidate", f"shared_terms={score}"],
                )
            )
    return findings


def _internal_pair_finding(
    classification: str,
    severity: str,
    confidence: float,
    score: float,
    rationale: str,
    reference_evidence: TextEvidence,
    candidate_evidence: TextEvidence,
    signals: list[str],
) -> ComplianceFinding:
    return _with_advisor_fields(ComplianceFinding(
        id=_finding_id(classification, reference_evidence.section_id, candidate_evidence.section_id),
        classification=classification,  # type: ignore[arg-type]
        severity=severity,  # type: ignore[arg-type]
        confidence=round(confidence, 3),
        alignment_score=score,
        rationale=rationale,
        external_evidence=reference_evidence,
        internal_evidence=candidate_evidence,
        signals=signals,
    ))


def _dedupe_findings(findings: list[ComplianceFinding]) -> list[ComplianceFinding]:
    out: dict[str, ComplianceFinding] = {}
    for finding in findings:
        left_section = finding.external_evidence.section_id if finding.external_evidence else ""
        right_section = finding.internal_evidence.section_id if finding.internal_evidence else ""
        if finding.classification in {"contradiction", "duplicate", "supported", "not_related", "needs_human_review"}:
            pair_key = "|".join(sorted([left_section, right_section]))
            key = "|".join([finding.classification, pair_key])
        else:
            key = "|".join([
                finding.classification,
                left_section,
                right_section,
                finding.internal_evidence.text if finding.internal_evidence else "",
            ])
        existing = out.get(key)
        if existing is None or _severity_rank(finding.severity) < _severity_rank(existing.severity):
            out[key] = finding
    return list(out.values())


def _sections(document: EvidenceDocument) -> list[EvidenceSection]:
    if document.sections:
        return document.sections
    return [EvidenceSection(id=f"{document.id}-body", heading=document.title, text="")]


def _sentences(text: str) -> list[str]:
    normalized = " ".join(text.replace("\r", "\n").split())
    return [part.strip(" -:\t") for part in SENTENCE_SPLIT_PATTERN.split(normalized) if part.strip(" -:\t")]


def _document_text(document: EvidenceDocument) -> str:
    return "\n".join([document.title, *(section.text for section in document.sections)])


def _document_relevance_score(external: EvidenceDocument, internal: EvidenceDocument) -> float:
    external_terms = _key_terms(_document_text(external))
    internal_terms = _key_terms(_document_text(internal))
    return _alignment_score(external_terms, internal_terms)


def _detect_modality(sentence: str) -> tuple[StatementModality, re.Match[str]] | None:
    for modality, pattern in MODAL_PATTERNS:
        match = pattern.search(sentence)
        if match:
            return modality, match
    return None


def _actor_action_condition(sentence: str, match: re.Match[str]) -> tuple[str, str, str]:
    before = sentence[: match.start()].strip(" ,;:.")
    after = sentence[match.end() :].strip(" ,;:.")
    phrase = match.group(1).lower()
    if phrase in {"is mandatory", "are mandatory"}:
        action = before or after
        actor = _actor_from_text(before)
    elif phrase in {"optional", "not required"}:
        action = before or after
        actor = _actor_from_text(before)
    else:
        actor = _actor_from_text(before)
        action = after

    condition = ""
    condition_match = CONDITION_PATTERN.search(action)
    if condition_match:
        condition = condition_match.group(0).strip()
        action = action[: condition_match.start()].strip(" ,;:.")
    return actor or "unspecified actor", action.strip(" ,;:.") or sentence.strip(" ,;:."), condition


def _actor_from_text(text: str) -> str:
    clean = text.strip(" ,;:.")
    if not clean:
        return "unspecified actor"
    chunks = re.split(r"\b(and|or|where|when|if|that|which)\b|[,;:]", clean, maxsplit=1, flags=re.I)
    candidate = chunks[0].strip(" ,;:.") if chunks else clean
    words = candidate.split()
    if len(words) > 7:
        candidate = " ".join(words[-7:])
    return candidate or "unspecified actor"


def _evidence(document: EvidenceDocument, section: EvidenceSection, sentence: str) -> TextEvidence:
    return TextEvidence(
        source_id=document.id,
        source_title=document.title,
        section_id=section.id or f"{document.id}-{section.ordinal}",
        heading=section.heading,
        citation=section.citation,
        text=sentence,
        url=document.url,
        version=document.version,
        content_sha256=document.content_sha256,
    )


def _key_terms(text: str) -> list[str]:
    terms = []
    for token in TOKEN_PATTERN.findall(text.lower()):
        token = token.strip("-")
        if len(token) < 3 or token in STOP_WORDS:
            continue
        terms.append(token)
    return sorted(dict.fromkeys(terms))


def _best_claim(obligation: ExtractedObligation, claims: list[ExtractedInternalClaim]) -> tuple[ExtractedInternalClaim | None, float]:
    scored = [(claim, _alignment_score(obligation.key_terms, claim.key_terms)) for claim in claims]
    if not scored:
        return None, 0.0
    claim, score = max(scored, key=lambda item: item[1])
    return claim, score


def _best_obligation(claim: ExtractedInternalClaim, obligations: list[ExtractedObligation]) -> tuple[ExtractedObligation | None, float]:
    scored = [(obligation, _alignment_score(claim.key_terms, obligation.key_terms)) for obligation in obligations]
    if not scored:
        return None, 0.0
    obligation, score = max(scored, key=lambda item: item[1])
    return obligation, score


def _alignment_score(left: list[str], right: list[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set or not right_set:
        return 0.0
    overlap = left_set & right_set
    if len(overlap) < MIN_SHARED_ALIGNMENT_TERMS:
        return 0.0
    union = left_set | right_set
    jaccard = len(overlap) / len(union)
    coverage = len(overlap) / min(len(left_set), len(right_set))
    return round((jaccard * 0.55) + (coverage * 0.45), 3)


def _classify_pair(obligation: ExtractedObligation, claim: ExtractedInternalClaim, score: float) -> ComplianceFinding:
    signals = [
        f"external_modality={obligation.modality}",
        f"internal_modality={claim.modality}",
        f"shared_terms={', '.join(sorted(set(obligation.key_terms) & set(claim.key_terms))[:8])}",
    ]
    if _is_direct_conflict(obligation, claim):
        return _finding(
            obligation,
            claim,
            "contradiction",
            "high",
            min(0.74, 0.42 + score),
            score,
            "External evidence appears to impose a stronger requirement than the aligned internal wording permits or denies.",
            signals,
        )
    if obligation.modality == "obligation" and claim.modality == "recommendation":
        return _finding(
            obligation,
            claim,
            "too_vague",
            "medium",
            min(0.7, 0.38 + score),
            score,
            "External evidence reads as mandatory, while the internal wording is framed as recommendation or expectation.",
            signals,
        )
    if obligation.modality == "prohibition" and claim.modality != "prohibition":
        return _finding(
            obligation,
            claim,
            "needs_human_review",
            "medium",
            min(0.68, 0.34 + score),
            score,
            "External evidence appears prohibitive, but the aligned internal wording does not clearly carry that prohibition.",
            signals,
        )
    return _finding(
        obligation,
        claim,
        "supported",
        "low",
        min(0.7, 0.36 + score),
        score,
        "Internal wording appears to cover the external requirement at this baseline level of comparison.",
        signals,
    )


def _is_direct_conflict(obligation: ExtractedObligation, claim: ExtractedInternalClaim) -> bool:
    claim_text = f"{claim.action} {claim.evidence.text}".lower()
    if obligation.modality in {"obligation", "prohibition"} and claim.modality == "permission":
        return True
    if obligation.modality == "obligation" and re.search(r"\b(optional|not required|not mandatory|may choose|can choose)\b", claim_text):
        return True
    if obligation.modality == "prohibition" and re.search(r"\b(may|can|allowed|permitted)\b", claim_text):
        return True
    return False


def _missing_obligation_finding(obligation: ExtractedObligation, score: float) -> ComplianceFinding:
    return _with_advisor_fields(ComplianceFinding(
        id=_finding_id("missing", obligation.id, ""),
        classification="missing_obligation",
        severity="high",
        confidence=round(max(0.58, 0.9 - score), 3),
        alignment_score=score,
        rationale="No sufficiently aligned internal claim was found for this external obligation.",
        obligation_id=obligation.id,
        external_evidence=obligation.evidence,
        signals=[f"external_modality={obligation.modality}", "no_internal_claim_above_threshold"],
    ))


def _unsupported_claim_finding(claim: ExtractedInternalClaim, score: float) -> ComplianceFinding:
    return _with_advisor_fields(ComplianceFinding(
        id=_finding_id("unsupported", "", claim.id),
        classification="unsupported_claim",
        severity="low",
        confidence=round(max(0.45, 0.72 - score), 3),
        alignment_score=score,
        rationale="Internal wording makes a governed claim, but no aligned external obligation was found in the provided evidence.",
        internal_claim_id=claim.id,
        internal_evidence=claim.evidence,
        signals=[f"internal_modality={claim.modality}", "no_external_obligation_above_threshold"],
    ))


def _not_related_finding(external: EvidenceDocument, internal: EvidenceDocument, score: float) -> ComplianceFinding:
    return _with_advisor_fields(ComplianceFinding(
        id=_finding_id("not_related", external.id, internal.id),
        classification="not_related",
        severity="low",
        confidence=round(max(0.5, 1 - score), 3),
        alignment_score=score,
        rationale="External and internal documents were checked as a pair but do not appear to discuss the same obligation.",
        signals=["pair_relevance_below_threshold", f"external={external.title}", f"internal={internal.title}"],
    ))


def _finding(
    obligation: ExtractedObligation,
    claim: ExtractedInternalClaim,
    classification,
    severity,
    confidence: float,
    score: float,
    rationale: str,
    signals: list[str],
) -> ComplianceFinding:
    return _with_advisor_fields(ComplianceFinding(
        id=_finding_id(classification, obligation.id, claim.id),
        classification=classification,
        severity=severity,
        confidence=round(confidence, 3),
        alignment_score=score,
        rationale=rationale,
        obligation_id=obligation.id,
        internal_claim_id=claim.id,
        external_evidence=obligation.evidence,
        internal_evidence=claim.evidence,
        signals=signals,
    ))


def _with_advisor_fields(finding: ComplianceFinding) -> ComplianceFinding:
    if not finding.advisor_summary:
        finding.advisor_summary = _advisor_summary(finding)
    if not finding.why_it_matters:
        finding.why_it_matters = _why_it_matters(finding.classification)
    if not finding.recommended_action:
        finding.recommended_action = _recommended_action(finding)
    if not finding.proposed_internal_text:
        finding.proposed_internal_text = _proposed_internal_text(finding)
    if not finding.confidence_interpretation:
        finding.confidence_interpretation = _confidence_interpretation(finding.confidence)
    if not finding.evidence_highlights:
        finding.evidence_highlights = _evidence_highlights(finding)
    return finding


def _advisor_summary(finding: ComplianceFinding) -> str:
    label = finding.classification.replace("_", " ")
    if finding.classification == "duplicate" and finding.external_evidence and finding.internal_evidence:
        return (
            f"Two internal sources contain very similar wording: '{_clip(finding.external_evidence.text, 100)}' "
            f"and '{_clip(finding.internal_evidence.text, 100)}'."
        )
    if finding.classification == "contradiction" and finding.external_evidence and finding.internal_evidence:
        return (
            f"The external evidence appears to require '{_clip(finding.external_evidence.text, 120)}', "
            f"while the internal wording says '{_clip(finding.internal_evidence.text, 120)}'."
        )
    if finding.classification == "supported":
        return "The internal wording appears to support the external obligation for this reviewed passage."
    if finding.classification == "missing_obligation":
        return "The external source contains an obligation that does not yet have clear aligned internal wording."
    if finding.classification == "not_related":
        return "The two sources were checked, but the passages do not appear to govern the same requirement."
    return f"The review classified this item as {label}: {finding.rationale}"


def _why_it_matters(classification: str) -> str:
    return {
        "supported": "Supported findings can be acknowledged as evidence that internal wording currently aligns with the external source.",
        "contradiction": "Contradictions can lead the assistant to give advice that conflicts with external guidance or legislation.",
        "missing_obligation": (
            "Missing obligations create coverage gaps where internal content may omit a requirement users should know about."
        ),
        "missing_detail": "Missing detail can make an answer technically incomplete even when the general topic is covered.",
        "duplicate": "Duplicate internal wording can create maintenance drift when one source is updated and the other is not.",
        "too_vague": "Vague wording can weaken a mandatory requirement into an optional or unclear internal process.",
        "outdated": "Outdated wording may point users to rules that no longer match current external evidence.",
        "unsupported_claim": "Unsupported internal claims should be checked before the assistant relies on them.",
        "needs_human_review": "The model found enough signal for review but not enough certainty for an automated conclusion.",
        "not_related": "No action is usually needed unless a human reviewer sees a specific obligation overlap.",
    }.get(classification, "Human review is required before changing approved knowledge.")


def _recommended_action(finding: ComplianceFinding) -> str:
    if finding.classification == "supported":
        return "Acknowledge the support finding if the evidence still looks correct."
    if finding.classification == "contradiction":
        return "Review the internal wording and update it so it no longer weakens or reverses the external requirement."
    if finding.classification == "missing_obligation":
        return "Add internal wording that explains how this external obligation applies, or mark it out of scope with a reason."
    if finding.classification == "duplicate":
        return "Review whether the repeated internal wording should be trimmed, merged or replaced with a cross-reference."
    if finding.classification == "not_related":
        return "No compliance edit is suggested unless the reviewer identifies a shared concrete obligation."
    return "Review the internal evidence and decide whether to edit, dismiss, accept risk or escalate to an SME."


def _proposed_internal_text(finding: ComplianceFinding) -> str:
    if finding.classification not in {"contradiction", "missing_detail", "too_vague", "missing_obligation"}:
        return ""
    if finding.external_evidence is None:
        return ""
    prefix = "Where this topic applies, internal guidance should state that"
    text = finding.external_evidence.text.strip()
    if not text:
        return ""
    return f"{prefix} {text[0].lower()}{text[1:]}"


def _confidence_interpretation(confidence: float) -> str:
    if confidence >= 0.85:
        return "High model confidence; still requires human approval before source edits."
    if confidence >= 0.65:
        return "Moderate model confidence; review the evidence carefully before acting."
    return "Low confidence; treat this as triage rather than a confirmed compliance issue."


def _evidence_highlights(finding: ComplianceFinding) -> list[str]:
    highlights = []
    if finding.external_evidence:
        highlights.append(f"External: {_clip(finding.external_evidence.text, 180)}")
    if finding.internal_evidence:
        highlights.append(f"Internal: {_clip(finding.internal_evidence.text, 180)}")
    return highlights


def _clip(value: str, limit: int) -> str:
    compact = " ".join(value.split())
    return compact if len(compact) <= limit else f"{compact[: limit - 1].rstrip()}…"


def _statement_id(prefix: str, document_id: str, section_id: str, sentence: str) -> str:
    digest = hashlib.sha256(f"{prefix}|{document_id}|{section_id}|{sentence}".encode()).hexdigest()[:18]
    return f"{prefix}-{digest}"


def _finding_id(prefix: str, obligation_id: str, claim_id: str) -> str:
    digest = hashlib.sha256(f"{prefix}|{obligation_id}|{claim_id}".encode()).hexdigest()[:18]
    return f"finding-{digest}"


def _document_pairs(request: ComplianceReviewRequest) -> list[tuple[EvidenceDocument, EvidenceDocument]]:
    if request.review_mode == "internal_vs_internal":
        documents = request.internal_documents
        return [
            (documents[left], documents[right])
            for left in range(len(documents))
            for right in range(left + 1, len(documents))
        ]
    return [
        (external, internal)
        for external in request.external_documents
        for internal in request.internal_documents
    ]


def _pair_id(external: EvidenceDocument, internal: EvidenceDocument, review_mode: ReviewMode = "external_vs_internal") -> str:
    digest = hashlib.sha256(f"{review_mode}|{external.id}|{internal.id}".encode()).hexdigest()[:18]
    return f"pair-{digest}"


def _pair_input_weight(external: EvidenceDocument, internal: EvidenceDocument) -> float:
    char_count = len(_document_text(external)) + len(_document_text(internal))
    section_count = max(1, len(external.sections) + len(internal.sections))
    # A lightweight proxy for how expensive a pair may be. It deliberately stays
    # approximate; ETA should feel honest, not falsely precise.
    return round(max(1.0, min(30.0, (char_count / 4000) + (section_count * 0.1))), 2)


def _source_hashes(documents: Iterable[EvidenceDocument]) -> dict[str, str]:
    out = {}
    for document in documents:
        if document.content_sha256:
            out[document.id] = document.content_sha256
        else:
            payload = "|".join(section.text for section in document.sections)
            out[document.id] = hashlib.sha256(payload.encode()).hexdigest()
    return out


def _severity_rank(severity: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(severity, 3)
