"""Bulk learning-pack import tests."""

from __future__ import annotations

import json

from assistant.ingestion.store import SectionStore
from assistant.sources.bulk_import import import_folder, report_markdown, write_report
from assistant.sources.register import SourceRegister

GOOD_PACK = """# Supplier Setup

Supplier setup requires due diligence checks before activation.

## Roles

The buyer prepares the request and the support team reviews it.
"""

HEADING_ONLY = "# Empty Pack\n\n## No Body\n"


def test_bulk_import_dry_run_does_not_register_sources(tmp_path):
    folder = tmp_path / "packs"
    folder.mkdir()
    (folder / "supplier.md").write_text(GOOD_PACK, encoding="utf-8")
    register = SourceRegister(tmp_path / "data")

    report = import_folder(folder, register, SectionStore(register.base_dir), dry_run=True)

    assert report.dry_run is True
    assert report.imported == 0
    assert report.rows[0].status == "ready"
    assert register.list() == []


def test_bulk_import_imports_good_files_and_reports_duplicates(tmp_path):
    folder = tmp_path / "packs"
    folder.mkdir()
    (folder / "supplier-a.md").write_text(GOOD_PACK, encoding="utf-8")
    (folder / "supplier-b.md").write_text(GOOD_PACK, encoding="utf-8")
    register = SourceRegister(tmp_path / "data")
    store = SectionStore(register.base_dir)

    report = import_folder(folder, register, store, approve=True)

    assert report.imported == 1
    assert report.duplicates == 1
    assert report.process_records == 1
    assert len(register.list()) == 1
    assert register.list()[0].approval_status == "approved"
    assert report.rows[0].status == "imported"
    assert report.rows[1].status == "duplicate"


def test_bulk_import_reports_failed_ingestion_without_stopping_batch(tmp_path):
    folder = tmp_path / "packs"
    folder.mkdir()
    (folder / "bad.md").write_text(HEADING_ONLY, encoding="utf-8")
    (folder / "good.md").write_text(GOOD_PACK, encoding="utf-8")
    register = SourceRegister(tmp_path / "data")
    store = SectionStore(register.base_dir)

    report = import_folder(folder, register, store)

    assert report.imported == 1
    assert report.failed == 1
    failed = next(row for row in report.rows if row.status == "failed")
    assert failed.source_id
    assert "No ingestible sections" in failed.error


def test_bulk_import_report_writes_json_and_markdown(tmp_path):
    folder = tmp_path / "packs"
    folder.mkdir()
    (folder / "supplier.md").write_text(GOOD_PACK, encoding="utf-8")
    register = SourceRegister(tmp_path / "data")
    report = import_folder(folder, register, SectionStore(register.base_dir))
    report_path = tmp_path / "reports" / "import.json"

    write_report(report, report_path)

    assert json.loads(report_path.read_text(encoding="utf-8"))["imported"] == 1
    assert "Bulk Learning Pack Import Report" in report_path.with_suffix(".md").read_text(encoding="utf-8")
    assert "| imported |" in report_markdown(report)
