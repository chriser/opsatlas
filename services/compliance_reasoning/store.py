"""In-memory review store for the standalone compliance reasoning service."""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from .models import ComplianceFinding, ComplianceReviewResult, ReviewAudit, ReviewPairProgress, ReviewStatus


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ComplianceReviewStore:
    """Thread-safe process-local store for review results.

    The first service slice is intentionally lightweight. A later slice can swap
    this for a file, SQLite or external job store without changing the API.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: dict[str, ComplianceReviewResult] = {}
        self._statuses: dict[str, ReviewStatus] = {}

    def create_status(self, job_id: str, pairs: list[ReviewPairProgress] | None = None) -> ReviewStatus:
        pair_rows = pairs or []
        status = ReviewStatus(
            job_id=job_id,
            status="queued",
            created_at=utc_now(),
            pair_total=len(pair_rows),
            pairs=pair_rows,
            audit=ReviewAudit(),
        )
        result = ComplianceReviewResult(status=status)
        with self._lock:
            self._statuses[job_id] = status
            self._records[job_id] = result
        return status

    def save(self, result: ComplianceReviewResult) -> ComplianceReviewResult:
        with self._lock:
            self._records[result.status.job_id] = result
            self._statuses[result.status.job_id] = result.status
        return result

    def mark_running(self, job_id: str, audit: ReviewAudit) -> None:
        with self._lock:
            result = self._records[job_id]
            result.status.status = "running"
            result.status.audit = audit
            self._statuses[job_id] = result.status

    def mark_pair_running(self, job_id: str, pair_id: str) -> None:
        with self._lock:
            result = self._records[job_id]
            pair = _pair_by_id(result.status.pairs, pair_id)
            pair.status = "running"
            result.status.current_pair = pair
            self._statuses[job_id] = result.status

    def complete_pair(
        self,
        job_id: str,
        pair_id: str,
        *,
        status: str,
        classification: str = "",
        relevance_score: float = 0.0,
        rationale: str = "",
        findings: list[ComplianceFinding] | None = None,
        obligation_count: int = 0,
        internal_claim_count: int = 0,
    ) -> None:
        with self._lock:
            result = self._records[job_id]
            pair = _pair_by_id(result.status.pairs, pair_id)
            pair.status = status
            pair.classification = classification
            pair.relevance_score = relevance_score
            pair.rationale = rationale
            pair.finding_count = len(findings or [])
            result.status.pair_completed = sum(1 for item in result.status.pairs if item.status in {"completed", "failed", "not_related"})
            result.status.progress_percent = _progress_percent(result.status.pair_completed, result.status.pair_total)
            result.status.current_pair = None
            result.status.obligation_count += obligation_count
            result.status.internal_claim_count += internal_claim_count
            result.findings.extend(findings or [])
            result.status.finding_count = len(result.findings)
            self._records[job_id] = result
            self._statuses[job_id] = result.status

    def complete(self, job_id: str) -> None:
        with self._lock:
            result = self._records[job_id]
            result.status.status = "completed"
            result.status.completed_at = utc_now()
            result.status.current_pair = None
            result.status.progress_percent = 100 if result.status.pair_total else 100
            self._records[job_id] = result
            self._statuses[job_id] = result.status

    def fail(self, job_id: str, reason: str) -> None:
        with self._lock:
            result = self._records[job_id]
            result.status.status = "failed"
            result.status.failure_reason = reason
            result.status.completed_at = utc_now()
            result.status.current_pair = None
            self._records[job_id] = result
            self._statuses[job_id] = result.status

    def get_result(self, job_id: str) -> ComplianceReviewResult | None:
        with self._lock:
            return self._records.get(job_id)

    def get_status(self, job_id: str) -> ReviewStatus | None:
        with self._lock:
            result = self._records.get(job_id)
            if result is not None:
                return result.status
            return self._statuses.get(job_id)


def _pair_by_id(pairs: list[ReviewPairProgress], pair_id: str) -> ReviewPairProgress:
    for pair in pairs:
        if pair.pair_id == pair_id:
            return pair
    raise KeyError(pair_id)


def _progress_percent(completed: int, total: int) -> int:
    if total <= 0:
        return 100
    return min(100, int(round((completed / total) * 100)))
