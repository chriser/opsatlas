"""Human review state for regulatory candidates."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

REVIEW_STATUSES = ("unreviewed", "relevant", "irrelevant", "needs_research")


class RegulatoryReview(BaseModel):
    candidate_id: str
    status: str = "unreviewed"
    note: str = ""
    reviewed_at: str = ""


class RegulatoryReviewStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.path = Path(base_dir) / "regulatory_reviews.json"
        self._lock = threading.Lock()

    def _read(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text() or "{}")

    def all(self) -> dict[str, RegulatoryReview]:
        return {key: RegulatoryReview(**value) for key, value in self._read().items()}

    def get(self, candidate_id: str) -> RegulatoryReview:
        row = self._read().get(candidate_id)
        if row is None:
            return RegulatoryReview(candidate_id=candidate_id)
        return RegulatoryReview(**row)

    def set(self, candidate_id: str, status: str, note: str = "") -> RegulatoryReview:
        if status not in REVIEW_STATUSES:
            allowed = ", ".join(REVIEW_STATUSES)
            raise ValueError(f"Unsupported regulatory review status '{status}'. Allowed: {allowed}.")
        review = RegulatoryReview(
            candidate_id=candidate_id,
            status=status,
            note=note,
            reviewed_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            rows = self._read()
            rows[candidate_id] = review.model_dump()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(rows, indent=2))
        return review
