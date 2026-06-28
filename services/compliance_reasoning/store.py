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
            result.status.started_at = utc_now()
            result.status.audit = audit
            _refresh_timing(result.status)
            self._statuses[job_id] = result.status

    def mark_pair_running(self, job_id: str, pair_id: str) -> None:
        with self._lock:
            result = self._records[job_id]
            pair = _pair_by_id(result.status.pairs, pair_id)
            pair.status = "running"
            pair.started_at = utc_now()
            result.status.current_pair = pair
            _refresh_timing(result.status)
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
        cache_status: str = "miss",
    ) -> None:
        with self._lock:
            result = self._records[job_id]
            pair = _pair_by_id(result.status.pairs, pair_id)
            completed_at = utc_now()
            pair.status = status
            pair.classification = classification
            pair.relevance_score = relevance_score
            pair.rationale = rationale
            pair.finding_count = len(findings or [])
            pair.cache_status = cache_status
            pair.completed_at = completed_at
            pair.duration_seconds = _duration_seconds(pair.started_at, pair.completed_at)
            result.status.pair_completed = sum(1 for item in result.status.pairs if item.status in {"completed", "failed", "not_related"})
            result.status.progress_percent = _progress_percent(result.status.pair_completed, result.status.pair_total)
            result.status.current_pair = None
            result.status.obligation_count += obligation_count
            result.status.internal_claim_count += internal_claim_count
            result.findings.extend(findings or [])
            result.status.finding_count = len(result.findings)
            _refresh_timing(result.status)
            self._records[job_id] = result
            self._statuses[job_id] = result.status

    def complete(self, job_id: str, *, max_findings: int | None = None) -> None:
        with self._lock:
            result = self._records[job_id]
            if max_findings is not None:
                result.findings.sort(key=_finding_rank)
                result.findings = result.findings[:max_findings]
            result.status.status = "completed"
            result.status.completed_at = utc_now()
            result.status.current_pair = None
            result.status.progress_percent = 100 if result.status.pair_total else 100
            result.status.finding_count = len(result.findings)
            _refresh_timing(result.status)
            result.status.estimated_remaining_seconds = 0.0
            self._records[job_id] = result
            self._statuses[job_id] = result.status

    def fail(self, job_id: str, reason: str) -> None:
        with self._lock:
            result = self._records[job_id]
            result.status.status = "failed"
            result.status.failure_reason = reason
            result.status.completed_at = utc_now()
            result.status.current_pair = None
            _refresh_timing(result.status)
            self._records[job_id] = result
            self._statuses[job_id] = result.status

    def get_result(self, job_id: str) -> ComplianceReviewResult | None:
        with self._lock:
            result = self._records.get(job_id)
            if result is not None:
                _refresh_timing(result.status)
            return result

    def get_status(self, job_id: str) -> ReviewStatus | None:
        with self._lock:
            result = self._records.get(job_id)
            if result is not None:
                _refresh_timing(result.status)
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


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _duration_seconds(start: str, end: str) -> float:
    start_at = _parse_time(start)
    end_at = _parse_time(end)
    if start_at is None or end_at is None:
        return 0.0
    return round(max(0.0, (end_at - start_at).total_seconds()), 3)


def _refresh_timing(status: ReviewStatus) -> None:
    anchor = status.started_at or status.created_at
    end = status.completed_at if status.status in {"completed", "failed"} else utc_now()
    status.elapsed_seconds = _duration_seconds(anchor, end)
    status.current_pair_elapsed_seconds = (
        _duration_seconds(status.current_pair.started_at, utc_now())
        if status.current_pair is not None and status.current_pair.started_at
        else 0.0
    )
    status.cache_hit_count = sum(1 for pair in status.pairs if pair.cache_status == "hit")
    status.cache_miss_count = sum(1 for pair in status.pairs if pair.cache_status == "miss")
    status.cache_bypass_count = sum(1 for pair in status.pairs if pair.cache_status == "bypassed")
    if status.status in {"completed", "failed"}:
        status.estimated_remaining_seconds = 0.0
        status.estimated_remaining_label = "Completed" if status.status == "completed" else "Stopped"
        status.eta_confidence = "unknown"
        return
    completed_pairs = [
        pair
        for pair in status.pairs
        if pair.status in {"completed", "not_related"} and pair.cache_status in {"miss", "bypassed"} and pair.duration_seconds > 0
    ]
    completed_weight = sum(max(pair.input_weight, 0.1) for pair in completed_pairs)
    if completed_weight <= 0:
        status.estimated_remaining_seconds = 0.0
        status.estimated_remaining_label = "Learning from first reviewed pair"
        status.eta_confidence = "unknown"
        return
    seconds_per_weight = sum(pair.duration_seconds for pair in completed_pairs) / completed_weight
    remaining_weight = sum(
        max(pair.input_weight, 0.1)
        for pair in status.pairs
        if pair.status in {"queued", "running"} and pair.cache_status != "hit"
    )
    status.estimated_remaining_seconds = round(max(0.0, seconds_per_weight * remaining_weight), 1)
    status.eta_confidence = "medium" if len(completed_pairs) >= 4 else "low"
    current_pair_is_slow = (
        status.current_pair_elapsed_seconds > max(900.0, status.estimated_remaining_seconds * 0.5)
        and status.current_pair is not None
    )
    if current_pair_is_slow:
        status.estimated_remaining_label = "Long-running pair; timing uncertain"
        status.eta_confidence = "low"
    elif status.eta_confidence == "low":
        status.estimated_remaining_label = f"Early estimate: {_duration_label(status.estimated_remaining_seconds)}"
    else:
        low = status.estimated_remaining_seconds * 0.75
        high = status.estimated_remaining_seconds * 1.75
        status.estimated_remaining_label = f"Approx. {_duration_label(low)} to {_duration_label(high)}"


def _duration_label(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m"
    return f"{seconds}s"


def _severity_rank(severity: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(severity, 3)


def _finding_rank(item: ComplianceFinding) -> tuple[int, int, float, float, str]:
    classification_rank = {
        "contradiction": 0,
        "too_vague": 1,
        "needs_human_review": 2,
        "missing_detail": 3,
        "missing_obligation": 4,
        "unsupported_claim": 5,
        "outdated": 6,
        "supported": 7,
        "not_related": 8,
    }
    return (
        classification_rank.get(item.classification, 99),
        _severity_rank(item.severity),
        -item.confidence,
        -item.alignment_score,
        item.id,
    )
