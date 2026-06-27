"""Deterministic baseline compliance reasoning engine.

This module deliberately avoids model dependencies. It gives the standalone
service a runnable contract and a transparent baseline before we add retrieval,
NLI and local LLM adjudication.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from datetime import datetime, timezone

from .models import (
    ComplianceFinding,
    ComplianceReviewRequest,
    ComplianceReviewResult,
    EvidenceDocument,
    EvidenceSection,
    ExtractedInternalClaim,
    ExtractedObligation,
    ReviewAudit,
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
    "actor",
    "before",
    "being",
    "between",
    "could",
    "does",
    "doing",
    "during",
    "each",
    "from",
    "for",
    "have",
    "into",
    "more",
    "must",
    "need",
    "needs",
    "only",
    "other",
    "over",
    "same",
    "shall",
    "should",
    "such",
    "than",
    "that",
    "the",
    "their",
    "then",
    "there",
    "these",
    "this",
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


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DeterministicComplianceEngine:
    """LLM-ready queued pairwise engine with a conservative deterministic fallback."""

    def prepare_pairs(self, request: ComplianceReviewRequest) -> list[ReviewPairProgress]:
        pairs: list[ReviewPairProgress] = []
        for external in request.external_documents:
            for internal in request.internal_documents:
                pairs.append(
                    ReviewPairProgress(
                        pair_id=_pair_id(external, internal),
                        external_document_id=external.id,
                        external_title=external.title,
                        internal_document_id=internal.id,
                        internal_title=internal.title,
                    )
                )
        return pairs

    def run_queued_job(self, job_id: str, request: ComplianceReviewRequest, store: ComplianceReviewStore) -> None:
        try:
            audit = ReviewAudit(
                external_document_count=len(request.external_documents),
                internal_document_count=len(request.internal_documents),
                source_hashes=_source_hashes([*request.external_documents, *request.internal_documents]),
                assumptions=[
                    "Queued pairwise workflow: each external source is checked against each approved internal source in isolation.",
                    "Current local mode is deterministic fallback; configure the LLM adapter in the next slice for "
                    "long-context semantic adjudication.",
                    "Unrelated document pairs are suppressed by default and should not be treated as compliance findings.",
                    "No legal conclusion is final without human review.",
                ],
            )
            store.mark_running(job_id, audit)
            for external in request.external_documents:
                for internal in request.internal_documents:
                    pair_id = _pair_id(external, internal)
                    store.mark_pair_running(job_id, pair_id)
                    pair = review_document_pair(external, internal, request)
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
                    )
            store.complete(job_id)
        except Exception as exc:  # pragma: no cover - defensive job boundary
            store.fail(job_id, str(exc))

    def run(self, job_id: str, request: ComplianceReviewRequest, created_at: str | None = None) -> ComplianceReviewResult:
        created = created_at or utc_now()
        obligations = extract_obligations(request.external_documents)
        internal_claims = extract_internal_claims(request.internal_documents)
        findings = compare_obligations_to_claims(obligations, internal_claims, request)
        completed = utc_now()
        audit = ReviewAudit(
            external_document_count=len(request.external_documents),
            internal_document_count=len(request.internal_documents),
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
    return ComplianceFinding(
        id=_finding_id("missing", obligation.id, ""),
        classification="missing_obligation",
        severity="high",
        confidence=round(max(0.58, 0.9 - score), 3),
        alignment_score=score,
        rationale="No sufficiently aligned internal claim was found for this external obligation.",
        obligation_id=obligation.id,
        external_evidence=obligation.evidence,
        signals=[f"external_modality={obligation.modality}", "no_internal_claim_above_threshold"],
    )


def _unsupported_claim_finding(claim: ExtractedInternalClaim, score: float) -> ComplianceFinding:
    return ComplianceFinding(
        id=_finding_id("unsupported", "", claim.id),
        classification="unsupported_claim",
        severity="low",
        confidence=round(max(0.45, 0.72 - score), 3),
        alignment_score=score,
        rationale="Internal wording makes a governed claim, but no aligned external obligation was found in the provided evidence.",
        internal_claim_id=claim.id,
        internal_evidence=claim.evidence,
        signals=[f"internal_modality={claim.modality}", "no_external_obligation_above_threshold"],
    )


def _not_related_finding(external: EvidenceDocument, internal: EvidenceDocument, score: float) -> ComplianceFinding:
    return ComplianceFinding(
        id=_finding_id("not_related", external.id, internal.id),
        classification="not_related",
        severity="low",
        confidence=round(max(0.5, 1 - score), 3),
        alignment_score=score,
        rationale="External and internal documents were checked as a pair but do not appear to discuss the same obligation.",
        signals=["pair_relevance_below_threshold", f"external={external.title}", f"internal={internal.title}"],
    )


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
    return ComplianceFinding(
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
    )


def _statement_id(prefix: str, document_id: str, section_id: str, sentence: str) -> str:
    digest = hashlib.sha256(f"{prefix}|{document_id}|{section_id}|{sentence}".encode()).hexdigest()[:18]
    return f"{prefix}-{digest}"


def _finding_id(prefix: str, obligation_id: str, claim_id: str) -> str:
    digest = hashlib.sha256(f"{prefix}|{obligation_id}|{claim_id}".encode()).hexdigest()[:18]
    return f"finding-{digest}"


def _pair_id(external: EvidenceDocument, internal: EvidenceDocument) -> str:
    digest = hashlib.sha256(f"{external.id}|{internal.id}".encode()).hexdigest()[:18]
    return f"pair-{digest}"


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
