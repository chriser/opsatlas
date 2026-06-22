"""Validation for the second anonymised learning pack."""

from __future__ import annotations

import json
import re
from pathlib import Path

from assistant.ingestion.sections import build_sections
from assistant.process.parser import parse_process

PACK_DIR = Path("docs/data-and-governance/learning-packs/article-setup")
PACK = PACK_DIR / "article-setup-learning-pack.md"


def test_article_setup_pack_parses_as_process_record():
    text = PACK.read_text()
    record = parse_process("article-pack", "Article setup pack", text)

    assert record.name == "Article Setup and Tax Handling Process"
    assert record.domain == "article-master-data"
    assert record.process == "article-setup-tax-handling"
    assert "Tax configuration owner" in record.roles
    assert "Article master data workspace" in record.systems
    assert "tax-parameter-register" in record.dependencies
    assert "activation-gating" in record.controls
    assert len(record.business_rules) >= 6
    assert len(record.rules) == 7


def test_article_setup_pack_builds_retrievable_sections():
    sections = build_sections("article-pack", PACK.read_text())
    headings = {section.heading for section in sections}

    assert len(sections) >= 8
    assert any(heading.endswith("Key business rules") for heading in headings)
    assert any(heading.endswith("Realistic Q&A pairs") for heading in headings)
    assert any(heading.endswith("JSON-style learning records") for heading in headings)


def test_article_setup_pack_metadata_and_source_register_are_valid_json():
    metadata = json.loads((PACK_DIR / "metadata-register.json").read_text())
    source_entry = json.loads((PACK_DIR / "source-register-entry.json").read_text())

    assert metadata["pack_id"] == "ARTICLE_SETUP_PACK_002"
    assert len(metadata["record_ids"]) == 7
    assert source_entry["filename"] == "article-setup-learning-pack.md"
    assert source_entry["sensitivity"] == "anonymised"


def test_article_setup_pack_has_no_obvious_confidential_red_flags():
    scanned_files = [path for path in PACK_DIR.iterdir() if path.is_file() and path.name != "anonymisation-validation.md"]
    combined = "\n".join(path.read_text() for path in scanned_files)
    assert not re.search(r"@|https?://|www\\.|\\.com|\\.co\\.|£|\\$|€|password|secret|token|api[_-]?key", combined, re.I)
    assert not re.search(r"\b\d{6,}\b", combined)
