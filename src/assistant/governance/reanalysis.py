"""Governance re-analysis audit snapshots."""

from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..external.registry import PublicContentRegistry
from ..regulatory.discovery import discover_regulatory_candidates
from ..regulatory.review import RegulatoryReviewStore
from ..regulatory.taxonomy import THEME_BY_ID
from ..sources.register import SourceRegister
from .accepted import issue_key
from .intelligence import KnowledgeIntelligence


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_json(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:18]


class GovernanceReanalysisStore:
    """File-backed history of explicit governance re-analysis runs."""

    def __init__(self, base_dir: str | Path) -> None:
        self.path = Path(base_dir) / "governance_reanalysis_runs.json"
        self._lock = threading.Lock()

    def _read(self) -> list[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text() or "[]")

    def latest(self) -> dict | None:
        runs = self._read()
        return runs[-1] if runs else None

    def save(self, report: dict) -> dict:
        with self._lock:
            runs = self._read()
            runs.append(report)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(runs[-25:], indent=2))
        return report


def build_reanalysis_report(
    register: SourceRegister,
    intelligence: KnowledgeIntelligence,
    section_store,
    review_store: RegulatoryReviewStore,
    public_registry: PublicContentRegistry,
    accepted=None,
    previous: dict | None = None,
) -> dict:
    """Run all governance checks and return a durable, non-destructive audit summary."""

    analysed_at = _now()
    intelligence_report = intelligence.run()
    regulatory_report = discover_regulatory_candidates(register, section_store, review_store, public_registry)
    snapshots = [snapshot for snapshot in public_registry.list_snapshots(include_text=True)]
    coverage = _external_coverage(regulatory_report["candidates"], snapshots)
    issue_keys = sorted(
        issue_key(issue["source_id"], issue["check"], issue["detail"])
        for issues in intelligence_report["issues"].values()
        for issue in issues
    )
    candidate_signatures = {
        candidate["id"]: _candidate_signature(candidate)
        for candidate in regulatory_report["candidates"]
    }
    previous_issue_keys = set(previous.get("issue_keys", [])) if previous else set()
    previous_candidate_signatures = previous.get("candidate_signatures", {}) if previous else {}
    current_issue_keys = set(issue_keys)

    new_candidate_ids = sorted(set(candidate_signatures) - set(previous_candidate_signatures))
    changed_candidate_ids = sorted(
        candidate_id
        for candidate_id, signature in candidate_signatures.items()
        if candidate_id in previous_candidate_signatures and previous_candidate_signatures[candidate_id] != signature
    )
    reviewed_count = sum(
        1 for review in review_store.all().values()
        if review.status and review.status != "unreviewed"
    )
    accepted_count = len(accepted.all()) if accepted is not None else 0
    matched_external_count = sum(1 for item in coverage if item["status"] == "matched")

    report = {
        "has_run": True,
        "run_id": f"governance-reanalysis-{_hash_json([analysed_at, issue_keys, candidate_signatures])}",
        "analysed_at": analysed_at,
        "needs_reanalysis": False,
        "pending_external_snapshot_count": 0,
        "pending_internal_change_count": 0,
        "total_source_count": len(register.list()),
        "approved_source_count": sum(1 for source in register.list() if source.approval_status == "approved"),
        "health": intelligence_report["health"],
        "active_issue_count": intelligence_report["total_issues"],
        "new_issue_count": len(current_issue_keys - previous_issue_keys),
        "resolved_issue_count": len(previous_issue_keys - current_issue_keys),
        "candidate_count": regulatory_report["candidate_count"],
        "new_candidate_count": len(new_candidate_ids),
        "changed_candidate_count": len(changed_candidate_ids),
        "review_counts": regulatory_report["review_counts"],
        "external_source_count": len({snapshot.source_id for snapshot in snapshots}),
        "external_snapshot_count": len(snapshots),
        "external_matched_count": matched_external_count,
        "external_unmatched_count": len(coverage) - matched_external_count,
        "previous_decisions_preserved": accepted_count + reviewed_count,
        "coverage": coverage,
        "issue_keys": issue_keys,
        "candidate_signatures": candidate_signatures,
        "external_snapshot_ids": sorted(snapshot.id for snapshot in snapshots),
        "source_fingerprints": _source_fingerprints(register),
        "new_candidate_ids": new_candidate_ids,
        "changed_candidate_ids": changed_candidate_ids,
    }
    return report


def latest_reanalysis_status(
    store: GovernanceReanalysisStore,
    register: SourceRegister,
    public_registry: PublicContentRegistry,
) -> dict:
    latest = store.latest()
    if latest is None:
        return {
            "has_run": False,
            "needs_reanalysis": True,
            "pending_external_snapshot_count": len(public_registry.list_snapshots(include_text=False)),
            "pending_internal_change_count": len(register.list()),
        }

    current_snapshot_ids = {
        row["id"] if isinstance(row, dict) else row.id
        for row in public_registry.list_snapshots(include_text=False)
    }
    previous_snapshot_ids = set(latest.get("external_snapshot_ids", []))
    current_source_fingerprints = _source_fingerprints(register)
    previous_source_fingerprints = latest.get("source_fingerprints", {})
    pending_sources = [
        source_id
        for source_id, fingerprint in current_source_fingerprints.items()
        if previous_source_fingerprints.get(source_id) != fingerprint
    ]
    enriched = dict(latest)
    enriched["has_run"] = True
    enriched["pending_external_snapshot_count"] = len(current_snapshot_ids - previous_snapshot_ids)
    enriched["pending_internal_change_count"] = len(pending_sources)
    enriched["needs_reanalysis"] = bool(
        enriched["pending_external_snapshot_count"] or enriched["pending_internal_change_count"]
    )
    return enriched


def _source_fingerprints(register: SourceRegister) -> dict[str, str]:
    return {
        source.id: f"{source.approval_status}:{source.processing_state}:{source.section_count}:{source.content_sha256}"
        for source in register.list()
    }


def _candidate_signature(candidate: dict) -> str:
    payload = {
        "theme": candidate["theme"],
        "source_id": candidate["source_id"],
        "score": candidate["score"],
        "matched_terms": candidate["matched_terms"],
        "passages": [
            {
                "heading": passage["heading"],
                "ordinal": passage["ordinal"],
                "matched_terms": passage["matched_terms"],
            }
            for passage in candidate["passages"]
        ],
        "external_matches": [
            {
                "url": match["url"],
                "version": match["version"],
                "matched_terms": match["matched_terms"],
            }
            for match in candidate["external_matches"]
        ],
    }
    return _hash_json(payload)


def _external_coverage(candidates: list[dict], snapshots: list) -> list[dict]:
    rows = []
    for snapshot in snapshots:
        matched_candidates = []
        all_terms: set[str] = set()
        haystack = f"{snapshot.title}\n{snapshot.text}".lower()
        for candidate in candidates:
            theme = THEME_BY_ID.get(candidate["theme"])
            terms = set(candidate["matched_terms"])
            if theme is not None:
                terms.update(theme.terms)
            matched_terms = sorted(term for term in terms if _contains_term(haystack, term))
            if not matched_terms:
                continue
            all_terms.update(matched_terms)
            matched_candidates.append(
                {
                    "candidate_id": candidate["id"],
                    "label": candidate["label"],
                    "source_id": candidate["source_id"],
                    "source_title": candidate["source_title"],
                    "matched_terms": matched_terms,
                }
            )
        rows.append(
            {
                "source_id": snapshot.source_id,
                "snapshot_id": snapshot.id,
                "title": snapshot.title,
                "url": snapshot.url,
                "provider": snapshot.provider,
                "version": snapshot.version,
                "snapshot_date": snapshot.snapshot_date,
                "update_date": snapshot.update_date,
                "status": "matched" if matched_candidates else "unmatched",
                "matched_candidate_count": len(matched_candidates),
                "matched_terms": sorted(all_terms),
                "matched_candidates": matched_candidates[:6],
            }
        )
    return sorted(rows, key=lambda row: (row["status"] != "matched", row["title"].lower(), -row["version"]))


def _contains_term(text: str, term: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(term.lower())}(?!\w)", text))
