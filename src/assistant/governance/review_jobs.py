"""Queued internal source review jobs for the Governance page."""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ..sources.register import SourceRegister
from .intelligence import KnowledgeIntelligence

InternalReviewStatusValue = Literal["queued", "running", "completed", "failed"]
InternalReviewCacheStatus = Literal["pending", "hit", "miss", "bypassed"]


class InternalReviewOptions(BaseModel):
    force_rerun: bool = False


class InternalReviewProgressItem(BaseModel):
    item_id: str
    title: str
    status: Literal["queued", "running", "completed", "failed"] = "queued"
    issue_count: int = 0


class InternalReviewStatus(BaseModel):
    job_id: str
    status: InternalReviewStatusValue = "queued"
    created_at: str
    started_at: str = ""
    completed_at: str = ""
    failure_reason: str = ""
    item_total: int = 0
    item_completed: int = 0
    progress_percent: int = 0
    elapsed_seconds: float = 0.0
    cache_status: InternalReviewCacheStatus = "pending"
    current_item: InternalReviewProgressItem | None = None
    items: list[InternalReviewProgressItem] = Field(default_factory=list)


class InternalReviewResult(BaseModel):
    status: InternalReviewStatus
    report: dict = Field(default_factory=dict)


class InternalReviewStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: dict[str, InternalReviewResult] = {}
        self.latest_job_id: str = ""

    def create(self, register: SourceRegister) -> InternalReviewResult:
        job_id = f"internal-review-{uuid.uuid4().hex[:12]}"
        items = [
            InternalReviewProgressItem(item_id=source.id, title=source.title)
            for source in register.list()
        ]
        status = InternalReviewStatus(
            job_id=job_id,
            created_at=_utc_now(),
            item_total=len(items),
            items=items,
        )
        result = InternalReviewResult(status=status)
        with self._lock:
            self._records[job_id] = result
            self.latest_job_id = job_id
        return result

    def get(self, job_id: str) -> InternalReviewResult | None:
        with self._lock:
            result = self._records.get(job_id)
            if result is not None:
                _refresh_status(result.status)
            return result

    def latest(self) -> InternalReviewResult | None:
        with self._lock:
            if not self.latest_job_id:
                return None
            result = self._records.get(self.latest_job_id)
            if result is not None:
                _refresh_status(result.status)
            return result

    def mark_running(self, job_id: str, cache_status: InternalReviewCacheStatus) -> None:
        with self._lock:
            result = self._records[job_id]
            result.status.status = "running"
            result.status.started_at = _utc_now()
            result.status.cache_status = cache_status
            if result.status.items:
                result.status.current_item = result.status.items[0]
                result.status.current_item.status = "running"
            _refresh_status(result.status)

    def complete(self, job_id: str, report: dict, cache_status: InternalReviewCacheStatus) -> None:
        with self._lock:
            result = self._records[job_id]
            result.report = report
            result.status.status = "completed"
            result.status.completed_at = _utc_now()
            result.status.cache_status = cache_status
            counts = _issue_counts_by_source(report)
            for item in result.status.items:
                item.status = "completed"
                item.issue_count = counts.get(item.item_id, 0)
            result.status.item_completed = result.status.item_total
            result.status.progress_percent = 100
            result.status.current_item = None
            _refresh_status(result.status)

    def fail(self, job_id: str, reason: str) -> None:
        with self._lock:
            result = self._records[job_id]
            result.status.status = "failed"
            result.status.completed_at = _utc_now()
            result.status.failure_reason = reason
            result.status.current_item = None
            _refresh_status(result.status)


class InternalReviewCache:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def get(self, key: str) -> dict | None:
        with self._lock:
            payload = self._read()
            record = payload.get(key)
            if not isinstance(record, dict):
                return None
            report = record.get("report")
            return report if isinstance(report, dict) else None

    def set(self, key: str, report: dict, *, duration_seconds: float) -> None:
        with self._lock:
            payload = self._read()
            payload[key] = {
                "schema": "internal-review-cache-v1",
                "cached_at": _utc_now(),
                "duration_seconds": round(max(0.0, duration_seconds), 3),
                "report": report,
            }
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _read(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8") or "{}")
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}


def start_internal_review_job(
    *,
    store: InternalReviewStore,
    cache: InternalReviewCache,
    register: SourceRegister,
    intelligence: KnowledgeIntelligence,
    options: InternalReviewOptions,
    on_complete=None,
) -> InternalReviewResult:
    result = store.create(register)
    key = internal_review_cache_key(register, intelligence)
    worker = threading.Thread(
        target=_run_internal_review,
        args=(result.status.job_id, key, store, cache, intelligence, options, on_complete),
        daemon=True,
    )
    worker.start()
    return result


def internal_review_cache_key(register: SourceRegister, intelligence: KnowledgeIntelligence) -> str:
    material = {
        "schema": "internal-review-cache-v1",
        "engine": "knowledge-intelligence-v2",
        "generator": type(intelligence.generator).__name__ if intelligence.generator is not None else "",
        "sources": [
            {
                "id": source.id,
                "title": source.title,
                "version": source.version,
                "content_sha256": source.content_sha256,
                "processing_state": source.processing_state,
                "approval_status": source.approval_status,
                "section_count": source.section_count,
            }
            for source in register.list()
        ],
    }
    digest = hashlib.sha256(json.dumps(material, sort_keys=True).encode("utf-8")).hexdigest()
    return f"internal-review-{digest[:32]}"


def _run_internal_review(
    job_id: str,
    cache_key: str,
    store: InternalReviewStore,
    cache: InternalReviewCache,
    intelligence: KnowledgeIntelligence,
    options: InternalReviewOptions,
    on_complete,
) -> None:
    cache_status: InternalReviewCacheStatus = "bypassed" if options.force_rerun else "miss"
    try:
        cached = None if options.force_rerun else cache.get(cache_key)
        if cached is not None:
            store.mark_running(job_id, "hit")
            store.complete(job_id, cached, "hit")
            if on_complete is not None:
                on_complete(cached)
            return
        store.mark_running(job_id, cache_status)
        started = time.perf_counter()
        report = intelligence.run()
        cache.set(cache_key, report, duration_seconds=time.perf_counter() - started)
        store.complete(job_id, report, cache_status)
        if on_complete is not None:
            on_complete(report)
    except Exception as exc:  # pragma: no cover - defensive job boundary
        store.fail(job_id, str(exc))


def _issue_counts_by_source(report: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for issues in report.get("issues", {}).values():
        if not isinstance(issues, list):
            continue
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            source_id = issue.get("source_id")
            if isinstance(source_id, str) and source_id:
                counts[source_id] = counts.get(source_id, 0) + 1
            source_b_id = issue.get("source_b_id")
            if isinstance(source_b_id, str) and source_b_id:
                counts[source_b_id] = counts.get(source_b_id, 0) + 1
    return counts


def _refresh_status(status: InternalReviewStatus) -> None:
    end = status.completed_at if status.status in {"completed", "failed"} else _utc_now()
    status.elapsed_seconds = _duration_seconds(status.started_at or status.created_at, end)
    if status.status in {"queued", "running"}:
        status.item_completed = sum(1 for item in status.items if item.status == "completed")
        status.progress_percent = _progress_percent(status.item_completed, status.item_total)


def _progress_percent(completed: int, total: int) -> int:
    if total <= 0:
        return 100
    return min(100, int(round((completed / total) * 100)))


def _duration_seconds(start: str, end: str) -> float:
    try:
        start_at = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_at = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    return round(max(0.0, (end_at - start_at).total_seconds()), 3)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
