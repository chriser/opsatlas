"""Durable latest completed compliance review snapshot."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any


class ComplianceLatestReviewStore:
    """Persist the last completed external review for UI reloads.

    The standalone reasoning service keeps jobs in process memory. The bridge
    stores the completed status and findings so the Control Panel can show the
    last real review after a backend restart without reusing stale React state.
    """

    def __init__(self, base_dir: str | Path) -> None:
        self.path = Path(base_dir) / "compliance_reasoning_latest_review.json"
        self._lock = threading.Lock()

    def get(self) -> dict[str, Any]:
        with self._lock:
            return self._read()

    def save(self, *, status: dict[str, Any], findings: list[Any]) -> dict[str, Any]:
        payload = {
            "status": status,
            "obligations": [],
            "internal_claims": [],
            "findings": findings,
        }
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"status": None, "obligations": [], "internal_claims": [], "findings": []}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        except (OSError, json.JSONDecodeError):
            return {"status": None, "obligations": [], "internal_claims": [], "findings": []}
        if not isinstance(payload, dict):
            return {"status": None, "obligations": [], "internal_claims": [], "findings": []}
        payload.setdefault("obligations", [])
        payload.setdefault("internal_claims", [])
        payload.setdefault("findings", [])
        return payload
