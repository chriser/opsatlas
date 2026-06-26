"""File-backed registry for public external-content snapshots."""

from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from .models import FetchedPublicContent, PublicContentSnapshot, PublicContentSource


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _source_id(provider: str, url: str) -> str:
    digest = hashlib.sha256(f"{provider}:{url}".encode()).hexdigest()[:14]
    return f"{provider}-{digest}"


def _snapshot_id(source_id: str, version: int, content_hash: str, snapshot_date: str) -> str:
    digest = hashlib.sha256(f"{source_id}:{version}:{content_hash}:{snapshot_date}".encode()).hexdigest()[:18]
    return f"snapshot-{digest}"


class PublicContentRegistry:
    """Stores selected public URLs and local text/metadata snapshots."""

    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir) / "external"
        self.sources_file = self.base_dir / "public_sources.json"
        self.snapshots_file = self.base_dir / "public_snapshots.json"
        self._lock = threading.Lock()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _read_sources(self) -> list[dict]:
        if not self.sources_file.exists():
            return []
        return json.loads(self.sources_file.read_text() or "[]")

    def _write_sources(self, rows: list[dict]) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.sources_file.write_text(json.dumps(rows, indent=2))

    def _read_snapshots(self) -> list[dict]:
        if not self.snapshots_file.exists():
            return []
        return json.loads(self.snapshots_file.read_text() or "[]")

    def _write_snapshots(self, rows: list[dict]) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.snapshots_file.write_text(json.dumps(rows, indent=2))

    def list_sources(self) -> list[PublicContentSource]:
        return [PublicContentSource(**row) for row in sorted(self._read_sources(), key=lambda r: (r.get("title") or r["url"]))]

    def get_source(self, source_id: str) -> PublicContentSource | None:
        return next((source for source in self.list_sources() if source.id == source_id), None)

    def list_snapshots(self, source_id: str | None = None, include_text: bool = True) -> list[PublicContentSnapshot | dict]:
        rows = self._read_snapshots()
        if source_id is not None:
            rows = [row for row in rows if row["source_id"] == source_id]
        rows = sorted(rows, key=lambda r: (r["snapshot_date"], r["version"]), reverse=True)
        if include_text:
            return [PublicContentSnapshot(**row) for row in rows]
        return [{k: v for k, v in row.items() if k != "text"} for row in rows]

    def upsert_source(
        self,
        *,
        provider: str,
        url: str,
        title: str = "",
        public_body: str = "",
        topics: list[str] | None = None,
        licence: str = "Open Government Licence v3.0",
        update_cadence: str = "manual",
        last_error: str = "",
    ) -> PublicContentSource:
        source_id = _source_id(provider, url)
        now = _now()
        with self._lock:
            rows = self._read_sources()
            for row in rows:
                if row["id"] == source_id:
                    row.update(
                        {
                            "title": title or row.get("title", ""),
                            "public_body": public_body or row.get("public_body", ""),
                            "topics": topics if topics is not None else row.get("topics", []),
                            "licence": licence,
                            "update_cadence": update_cadence,
                            "updated_at": now,
                            "last_error": last_error,
                        }
                    )
                    self._write_sources(rows)
                    return PublicContentSource(**row)
            row = PublicContentSource(
                id=source_id,
                provider=provider,
                url=url,
                title=title,
                public_body=public_body,
                topics=topics or [],
                licence=licence,
                update_cadence=update_cadence,
                created_at=now,
                updated_at=now,
                last_error=last_error,
            ).model_dump()
            rows.append(row)
            self._write_sources(rows)
            return PublicContentSource(**row)

    def record_failure(self, *, provider: str, url: str, error: str) -> PublicContentSource:
        return self.upsert_source(provider=provider, url=url, last_error=error)

    def delete_source(self, source_id: str) -> bool:
        with self._lock:
            source_rows = self._read_sources()
            next_sources = [row for row in source_rows if row["id"] != source_id]
            if len(next_sources) == len(source_rows):
                return False
            next_snapshots = [row for row in self._read_snapshots() if row["source_id"] != source_id]
            self._write_sources(next_sources)
            self._write_snapshots(next_snapshots)
            return True

    def add_snapshot(self, source_id: str, fetched: FetchedPublicContent) -> PublicContentSnapshot:
        with self._lock:
            source_rows = self._read_sources()
            if not any(row["id"] == source_id for row in source_rows):
                raise ValueError(f"Unknown public source: {source_id}")
            snapshots = self._read_snapshots()
            version = max((row["version"] for row in snapshots if row["source_id"] == source_id), default=0) + 1
            snapshot_date = _now()
            content_hash = hashlib.sha256(fetched.text.encode()).hexdigest()
            snapshot = PublicContentSnapshot(
                id=_snapshot_id(source_id, version, content_hash, snapshot_date),
                source_id=source_id,
                provider=fetched.provider,
                version=version,
                url=fetched.url,
                title=fetched.title,
                public_body=fetched.public_body,
                content_id=fetched.content_id,
                document_type=fetched.document_type,
                locale=fetched.locale,
                update_date=fetched.update_date,
                retrieved_at=fetched.retrieved_at,
                snapshot_date=snapshot_date,
                content_sha256=content_hash,
                text=fetched.text,
                metadata=fetched.metadata,
            )
            snapshots.append(snapshot.model_dump())
            for row in source_rows:
                if row["id"] == source_id:
                    row.update(
                        {
                            "title": fetched.title or row.get("title", ""),
                            "public_body": fetched.public_body or row.get("public_body", ""),
                            "updated_at": snapshot_date,
                            "snapshot_count": version,
                            "latest_snapshot_id": snapshot.id,
                            "latest_snapshot_date": snapshot.snapshot_date,
                            "latest_update_date": fetched.update_date,
                            "last_error": "",
                        }
                    )
                    break
            self._write_snapshots(snapshots)
            self._write_sources(source_rows)
            return snapshot
