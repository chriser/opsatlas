"""Persistent pair-result cache for expensive compliance reviews."""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ComplianceFinding, ComplianceReviewRequest, EvidenceDocument

CACHE_SCHEMA_VERSION = "pair-cache-v1"


class PairResultCache:
    """Small JSON cache keyed by source, model, prompt and material options."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def get(self, key: str) -> dict[str, Any] | None:
        with self._lock:
            payload = self._read()
            record = payload.get(key)
            if not isinstance(record, dict):
                return None
            result = record.get("result")
            return result if isinstance(result, dict) else None

    def set(self, key: str, result: dict[str, Any], *, duration_seconds: float = 0.0) -> None:
        serialised = _serialise_pair_result(result)
        with self._lock:
            payload = self._read()
            payload[key] = {
                "schema": CACHE_SCHEMA_VERSION,
                "cached_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": round(max(0.0, duration_seconds), 3),
                "result": serialised,
            }
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}


def pair_cache_key(
    external: EvidenceDocument,
    internal: EvidenceDocument,
    request: ComplianceReviewRequest,
    *,
    engine: object,
) -> str:
    options = request.options.model_dump()
    options.pop("force_rerun", None)
    profile_resolver = getattr(engine, "model_profile_for_request", None)
    model_profile = str(profile_resolver(request)) if callable(profile_resolver) else getattr(engine, "model_profile", "")
    material = {
        "schema": CACHE_SCHEMA_VERSION,
        "review_mode": request.review_mode,
        "external": _document_fingerprint(external),
        "internal": _document_fingerprint(internal),
        "engine": getattr(engine, "audit_engine", ""),
        "engine_version": getattr(engine, "engine_version", "0.1.0"),
        "model_profile": model_profile,
        "prompt_version": getattr(engine, "prompt_version", ""),
        "options": options,
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()
    return f"pair-cache-{digest[:32]}"


def cached_findings(result: dict[str, Any]) -> list[ComplianceFinding]:
    findings = result.get("findings", [])
    if not isinstance(findings, list):
        return []
    return [item if isinstance(item, ComplianceFinding) else ComplianceFinding(**item) for item in findings]


def _document_fingerprint(document: EvidenceDocument) -> dict[str, str]:
    content_hash = document.content_sha256
    if not content_hash:
        payload = "\n".join(section.text for section in document.sections)
        content_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return {
        "id": document.id,
        "snapshot_id": document.snapshot_id,
        "version": document.version,
        "content_sha256": content_hash,
    }


def _serialise_pair_result(result: dict[str, Any]) -> dict[str, Any]:
    serialised = dict(result)
    serialised["findings"] = [
        item.model_dump() if isinstance(item, ComplianceFinding) else item
        for item in result.get("findings", [])
    ]
    return serialised
