"""In-memory review store for the standalone compliance reasoning service."""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from .models import ComplianceReviewResult, ReviewAudit, ReviewStatus


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

    def create_status(self, job_id: str) -> ReviewStatus:
        status = ReviewStatus(job_id=job_id, status="queued", created_at=utc_now(), audit=ReviewAudit())
        with self._lock:
            self._statuses[job_id] = status
        return status

    def save(self, result: ComplianceReviewResult) -> ComplianceReviewResult:
        with self._lock:
            self._records[result.status.job_id] = result
            self._statuses[result.status.job_id] = result.status
        return result

    def get_result(self, job_id: str) -> ComplianceReviewResult | None:
        with self._lock:
            return self._records.get(job_id)

    def get_status(self, job_id: str) -> ReviewStatus | None:
        with self._lock:
            result = self._records.get(job_id)
            if result is not None:
                return result.status
            return self._statuses.get(job_id)
