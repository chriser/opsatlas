"""Bulk source-pack import using the normal register and ingestion services."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ..ingestion.service import NotIngestableError, ingest_source
from ..ingestion.store import SectionStore
from ..process.registry import ProcessRegistry
from .models import ALLOWED_EXTENSIONS
from .register import SourceRegister
from .service import UploadError, register_upload


class BulkImportRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    filename: str
    title: str
    status: str
    source_id: str = ""
    existing_source_id: str = ""
    section_count: int = 0
    content_sha256: str = ""
    error: str = ""


class BulkImportReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    folder: str
    dry_run: bool
    approve: bool
    total_files: int
    imported: int
    duplicates: int
    failed: int
    skipped: int
    process_records: int
    rows: list[BulkImportRow]


def import_folder(
    folder: str | Path,
    register: SourceRegister,
    section_store: SectionStore,
    *,
    approve: bool = False,
    dry_run: bool = False,
    recursive: bool = True,
    rebuild_process_registry: bool = True,
) -> BulkImportReport:
    folder_path = Path(folder)
    if not folder_path.exists() or not folder_path.is_dir():
        raise ValueError(f"Import folder does not exist: {folder_path}")

    existing_by_hash = {record.content_sha256: record for record in register.list()}
    rows: list[BulkImportRow] = []
    files = _candidate_files(folder_path, recursive=recursive)

    for path in files:
        rel = str(path.relative_to(folder_path))
        title = path.stem.replace("_", " ").replace("-", " ").strip() or path.name
        extension = path.suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            rows.append(BulkImportRow(path=rel, filename=path.name, title=title, status="skipped", error="Unsupported file type."))
            continue

        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        duplicate = existing_by_hash.get(digest)
        if duplicate is not None:
            rows.append(BulkImportRow(
                path=rel,
                filename=path.name,
                title=title,
                status="duplicate",
                existing_source_id=duplicate.id,
                section_count=duplicate.section_count,
                content_sha256=digest,
            ))
            continue

        if dry_run:
            rows.append(BulkImportRow(path=rel, filename=path.name, title=title, status="ready", content_sha256=digest))
            continue

        record = None
        try:
            record = register_upload(register, path.name, content, title=title)
            existing_by_hash[digest] = record
            ingested = ingest_source(register, section_store, record.id)
            if approve:
                ingested = register.update(ingested.id, approval_status="approved") or ingested
            rows.append(BulkImportRow(
                path=rel,
                filename=path.name,
                title=ingested.title,
                status="imported",
                source_id=ingested.id,
                section_count=ingested.section_count,
                content_sha256=ingested.content_sha256,
            ))
        except (UploadError, NotIngestableError, UnicodeDecodeError, OSError) as exc:
            rows.append(BulkImportRow(
                path=rel,
                filename=path.name,
                title=title,
                status="failed",
                source_id=record.id if record is not None else "",
                content_sha256=digest,
                error=str(exc),
            ))

    process_records = 0
    if rebuild_process_registry and approve and not dry_run:
        process_records = len(ProcessRegistry(register.base_dir).build_from_sources(register))

    return BulkImportReport(
        folder=str(folder_path),
        dry_run=dry_run,
        approve=approve,
        total_files=len(files),
        imported=sum(1 for row in rows if row.status == "imported"),
        duplicates=sum(1 for row in rows if row.status == "duplicate"),
        failed=sum(1 for row in rows if row.status == "failed"),
        skipped=sum(1 for row in rows if row.status == "skipped"),
        process_records=process_records,
        rows=rows,
    )


def _candidate_files(folder: Path, *, recursive: bool) -> list[Path]:
    iterator = folder.rglob("*") if recursive else folder.iterdir()
    return sorted(path for path in iterator if path.is_file() and not path.name.startswith("."))


def report_markdown(report: BulkImportReport) -> str:
    lines = [
        "# Bulk Learning Pack Import Report",
        "",
        f"- Folder: `{report.folder}`",
        f"- Mode: {'dry run' if report.dry_run else 'import'}",
        f"- Approval: {'approved on import' if report.approve else 'left pending'}",
        f"- Files scanned: {report.total_files}",
        f"- Imported: {report.imported}",
        f"- Duplicates: {report.duplicates}",
        f"- Failed: {report.failed}",
        f"- Skipped: {report.skipped}",
        f"- Process records after rebuild: {report.process_records}",
        "",
        "| Status | File | Sections | Source | Notes |",
        "|---|---|---:|---|---|",
    ]
    for row in report.rows:
        source = row.source_id or row.existing_source_id or ""
        notes = row.error or ("duplicate content" if row.status == "duplicate" else "")
        lines.append(f"| {row.status} | {row.path} | {row.section_count} | {source} | {notes} |")
    return "\n".join(lines) + "\n"


def write_report(report: BulkImportReport, path: str | Path) -> None:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report.model_dump(), indent=2), encoding="utf-8")
    report_path.with_suffix(".md").write_text(report_markdown(report), encoding="utf-8")
