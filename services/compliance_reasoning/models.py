"""API models for the standalone compliance reasoning service."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SourceType = Literal["external", "internal"]
ReviewStatusValue = Literal["queued", "running", "completed", "failed"]
PairReviewStatusValue = Literal["queued", "running", "completed", "failed", "not_related"]
PairCacheStatusValue = Literal["pending", "hit", "miss", "bypassed"]
StatementModality = Literal["obligation", "prohibition", "permission", "recommendation", "informational"]
FindingClassification = Literal[
    "supported",
    "contradiction",
    "missing_obligation",
    "missing_detail",
    "too_vague",
    "outdated",
    "unsupported_claim",
    "not_related",
    "needs_human_review",
]
FindingSeverity = Literal["low", "medium", "high"]


class EvidenceSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = ""
    heading: str = ""
    text: str
    citation: str = ""
    ordinal: int = 0


class EvidenceDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    source_type: SourceType
    url: str = ""
    version: str = ""
    snapshot_id: str = ""
    content_sha256: str = ""
    retrieved_at: str = ""
    sections: list[EvidenceSection] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class ReviewOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_supported_findings: bool = True
    include_unsupported_internal_claims: bool = False
    include_missing_obligations: bool = False
    include_not_related_pairs: bool = False
    min_alignment_score: float = 0.18
    min_pair_relevance_score: float = 0.12
    min_contradiction_alignment_score: float = 0.3
    max_findings: int = 50
    force_rerun: bool = False


class ComplianceReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_documents: list[EvidenceDocument] = Field(default_factory=list)
    internal_documents: list[EvidenceDocument] = Field(default_factory=list)
    options: ReviewOptions = Field(default_factory=ReviewOptions)
    metadata: dict[str, str] = Field(default_factory=dict)


class TextEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_title: str
    section_id: str
    heading: str = ""
    citation: str = ""
    text: str
    url: str = ""
    version: str = ""
    content_sha256: str = ""


class ExtractedObligation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    modality: StatementModality
    actor: str
    action: str
    condition: str = ""
    key_terms: list[str] = Field(default_factory=list)
    evidence: TextEvidence


class ExtractedInternalClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    modality: StatementModality
    actor: str
    action: str
    condition: str = ""
    key_terms: list[str] = Field(default_factory=list)
    evidence: TextEvidence


class ComplianceFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    classification: FindingClassification
    severity: FindingSeverity
    confidence: float
    alignment_score: float
    rationale: str
    obligation_id: str = ""
    internal_claim_id: str = ""
    external_evidence: TextEvidence | None = None
    internal_evidence: TextEvidence | None = None
    signals: list[str] = Field(default_factory=list)
    advisor_summary: str = ""
    why_it_matters: str = ""
    recommended_action: str = ""
    proposed_internal_text: str = ""
    confidence_interpretation: str = ""
    evidence_highlights: list[str] = Field(default_factory=list)


class ReviewPairProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pair_id: str
    external_document_id: str
    external_title: str
    internal_document_id: str
    internal_title: str
    status: PairReviewStatusValue = "queued"
    classification: FindingClassification | Literal[""] = ""
    relevance_score: float = 0.0
    finding_count: int = 0
    rationale: str = ""
    cache_status: PairCacheStatusValue = "pending"
    started_at: str = ""
    completed_at: str = ""
    duration_seconds: float = 0.0
    input_weight: float = 1.0


class ReviewAudit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engine: str = "queued-pairwise-review"
    engine_version: str = "0.1.0"
    model_profile: str = "llm-ready-deterministic-fallback"
    prompt_version: str = ""
    external_document_count: int = 0
    internal_document_count: int = 0
    source_hashes: dict[str, str] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)


class ReviewStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: ReviewStatusValue
    created_at: str
    started_at: str = ""
    completed_at: str = ""
    failure_reason: str = ""
    obligation_count: int = 0
    internal_claim_count: int = 0
    finding_count: int = 0
    pair_total: int = 0
    pair_completed: int = 0
    progress_percent: int = 0
    elapsed_seconds: float = 0.0
    estimated_remaining_seconds: float = 0.0
    estimated_remaining_label: str = "Estimating"
    eta_confidence: Literal["unknown", "low", "medium"] = "unknown"
    current_pair_elapsed_seconds: float = 0.0
    cache_hit_count: int = 0
    cache_miss_count: int = 0
    cache_bypass_count: int = 0
    current_pair: ReviewPairProgress | None = None
    pairs: list[ReviewPairProgress] = Field(default_factory=list)
    audit: ReviewAudit = Field(default_factory=ReviewAudit)


class ComplianceReviewResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ReviewStatus
    obligations: list[ExtractedObligation] = Field(default_factory=list)
    internal_claims: list[ExtractedInternalClaim] = Field(default_factory=list)
    findings: list[ComplianceFinding] = Field(default_factory=list)


class FindingListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str
    status: ReviewStatusValue
    findings: list[ComplianceFinding] = Field(default_factory=list)


class CapabilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service: str = "compliance-reasoning"
    version: str = "0.1.0"
    modes: list[str] = Field(default_factory=lambda: ["deterministic-baseline"])
    endpoints: list[str] = Field(default_factory=list)
    supported_findings: list[FindingClassification] = Field(default_factory=list)
    model_backends: list[str] = Field(default_factory=lambda: ["none"])
    notes: list[str] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: str
    metadata: dict[str, Any] = Field(default_factory=dict)
