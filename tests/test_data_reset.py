from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.data_reset import (
    CONFIRMATION_PHRASE,
    backup_data,
    plan_tranches,
    reset_caches,
    reset_data,
    restore_backup,
)


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def test_reset_data_requires_confirmation_and_preserves_backup(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    backup_root = tmp_path / "backups"
    (data_dir / "sources").mkdir(parents=True)
    (data_dir / "sections").mkdir()
    (data_dir / "external").mkdir()
    (data_dir / "source_register.json").write_text('[{"title": "Pilot pack"}]\n', encoding="utf-8")
    (data_dir / "sources" / "pack.md").write_text("# Pilot", encoding="utf-8")
    (data_dir / "sections" / "pack.json").write_text("[]\n", encoding="utf-8")
    (data_dir / "external" / "public_sources.json").write_text('[{"url": "https://example.test"}]\n', encoding="utf-8")

    with pytest.raises(PermissionError):
        reset_data(data_dir, backup_root, confirm_gated="wrong")

    dry_run = reset_data(data_dir, backup_root, confirm_gated=CONFIRMATION_PHRASE, dry_run=True)
    assert dry_run.dry_run is True
    assert (data_dir / "sources" / "pack.md").exists()
    assert not backup_root.exists()

    result = reset_data(data_dir, backup_root, confirm_gated=CONFIRMATION_PHRASE, label="final-reset")

    assert result.backup_path is not None
    assert (result.backup_path / "data" / "sources" / "pack.md").read_text(encoding="utf-8") == "# Pilot"
    assert _read_json(data_dir / "source_register.json") == []
    assert _read_json(data_dir / "external" / "public_sources.json") == []
    assert _read_json(data_dir / "compliance_reasoning_latest_review.json") == {
        "status": None,
        "obligations": [],
        "internal_claims": [],
        "findings": [],
    }
    assert not (data_dir / "sources" / "pack.md").exists()
    assert (data_dir / "sections").is_dir()


def test_reset_caches_preserves_sources_and_clears_review_state(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    backup_root = tmp_path / "backups"
    (data_dir / "sources").mkdir(parents=True)
    (data_dir / "source_register.json").write_text('[{"title": "Final pack"}]\n', encoding="utf-8")
    (data_dir / "sources" / "pack.md").write_text("# Final", encoding="utf-8")
    (data_dir / "embeddings.json").write_text('{"source-1": [0.1]}\n', encoding="utf-8")
    (data_dir / "governance_reanalysis_runs.json").write_text('[{"status": "completed"}]\n', encoding="utf-8")
    (data_dir / "compliance_reasoning_latest_review.json").write_text('{"status": "completed"}\n', encoding="utf-8")

    result = reset_caches(data_dir, backup_root, confirm_gated=CONFIRMATION_PHRASE)

    assert result.backup_path is not None
    assert _read_json(data_dir / "source_register.json") == [{"title": "Final pack"}]
    assert (data_dir / "sources" / "pack.md").read_text(encoding="utf-8") == "# Final"
    assert _read_json(data_dir / "embeddings.json") == {}
    assert _read_json(data_dir / "governance_reanalysis_runs.json") == []
    assert _read_json(data_dir / "compliance_reasoning_latest_review.json")["status"] is None


def test_restore_backup_replaces_current_data(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    backup_root = tmp_path / "backups"
    data_dir.mkdir()
    (data_dir / "source_register.json").write_text('[{"title": "Original"}]\n', encoding="utf-8")
    backup = backup_data(data_dir, backup_root, label="original")

    (data_dir / "source_register.json").write_text('[{"title": "Changed"}]\n', encoding="utf-8")
    (data_dir / "new-runtime-file.json").write_text("{}\n", encoding="utf-8")

    restored = restore_backup(data_dir, backup_root, backup.backup_path or backup_root, confirm_gated=CONFIRMATION_PHRASE)

    assert restored.backup_path is not None
    assert _read_json(data_dir / "source_register.json") == [{"title": "Original"}]
    assert not (data_dir / "new-runtime-file.json").exists()
    assert (restored.backup_path / "data" / "new-runtime-file.json").exists()


def test_plan_tranches_writes_manifest_and_materialised_batches(tmp_path: Path) -> None:
    source_dir = tmp_path / "final-corpus"
    nested = source_dir / "nested"
    nested.mkdir(parents=True)
    (source_dir / "pack-1.md").write_text("# One", encoding="utf-8")
    (source_dir / "pack-2.pdf").write_text("pdf", encoding="utf-8")
    (nested / "pack-3.docx").write_text("docx", encoding="utf-8")
    (source_dir / "ignore.png").write_text("png", encoding="utf-8")

    output = tmp_path / "output" / "tranches.json"
    materialise_dir = tmp_path / "output" / "tranches"
    manifest = plan_tranches(source_dir, batch_size=2, output=output, materialise_dir=materialise_dir)

    assert manifest["file_count"] == 3
    assert manifest["tranche_count"] == 2
    assert output.exists()
    assert output.with_suffix(".md").exists()
    assert (materialise_dir / "tranche-01").is_dir()
    assert (materialise_dir / "tranche-02").is_dir()
    assert "scripts/import_packs.py" in manifest["tranches"][0]["import_command"]
