"""Durable latest completed compliance review snapshot."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from ..storage import write_json


class ComplianceLatestReviewStore:
    """The last completed compliance review of a data directory.

    The compliance-reasoning service wrote it through a bridge, both removed from Sales on 30 September 2026
    (OpsAtlas Classic keeps them). A data copy that carries a review still feeds its findings, obligations and
    claims into the facts map (ontology.sync); nothing in Sales writes a new one.
    """

    def __init__(self, base_dir: str | Path) -> None:
        self.path = Path(base_dir) / "compliance_reasoning_latest_review.json"
        self._lock = threading.Lock()

    def get(self) -> dict[str, Any]:
        with self._lock:
            return self._read()

    def save(
        self,
        *,
        status: dict[str, Any],
        findings: list[Any],
        obligations: list[Any] | None = None,
        internal_claims: list[Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "status": status,
            "obligations": obligations or [],
            "internal_claims": internal_claims or [],
            "findings": findings,
        }
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            write_json(self.path, payload, indent=2)
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
