#!/usr/bin/env python
"""Safe OpsAtlas local-data backup and clean-slate reset utility."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

CONFIRMATION_PHRASE = "RESET_OPSATLAS_DATA"

BASELINE_FILES: dict[str, Any] = {
    "source_register.json": [],
    "accepted_issues.json": [],
    "action_log.json": [],
    "pending_actions.json": [],
    "process_registry.json": [],
    "governance_reanalysis_runs.json": [],
    "governance_internal_review_cache.json": {},
    "compliance_reasoning_pair_cache.json": {},
    "compliance_reasoning_latest_review.json": {
        "status": None,
        "obligations": [],
        "internal_claims": [],
        "findings": [],
    },
    "compliance_resolutions.json": [],
    "agent_runs.json": [],
    "audit_trace.json": [],
    "usage_log.json": [],
    "analytics_events.jsonl": "",
    "simulation_runs.json": [],
    "regulatory_reviews.json": {},
    "external/public_sources.json": [],
    "external/public_snapshots.json": [],
}

CACHE_RESET_FILES: dict[str, Any] = {
    "embeddings.json": {},
    "governance_internal_review_cache.json": {},
    "compliance_reasoning_pair_cache.json": {},
    "compliance_reasoning_latest_review.json": {
        "status": None,
        "obligations": [],
        "internal_claims": [],
        "findings": [],
    },
    "governance_reanalysis_runs.json": [],
}

BASELINE_DIRS = ("sources", "sections", "external")
PACK_EXTENSIONS = {".md", ".txt", ".json", ".pdf", ".docx"}


@dataclass(frozen=True)
class OperationResult:
    operation: str
    data_dir: Path
    backup_path: Path | None
    changed_paths: list[Path]
    dry_run: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "data_dir": str(self.data_dir),
            "backup_path": str(self.backup_path) if self.backup_path is not None else "",
            "changed_paths": [str(path) for path in self.changed_paths],
            "dry_run": self.dry_run,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=os.environ.get("KP_DATA_DIR", "data"), help="Runtime data directory.")
    parser.add_argument("--backup-root", default="backups/data-reset", help="Directory where timestamped backups are written.")
    parser.add_argument("--env-file", default=str(ROOT / ".env"), help="Optional .env file to load before resolving defaults.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup", help="Back up the runtime data directory without changing it.")
    backup_parser.add_argument("--label", default="", help="Optional label for the backup folder.")

    reset_parser = subparsers.add_parser("reset", help="Back up and reset all local runtime data.")
    reset_parser.add_argument("--confirm-gated", default="", metavar="PHRASE", help=f"Required phrase: {CONFIRMATION_PHRASE}")
    reset_parser.add_argument("--dry-run", action="store_true", help="Show what would be cleared without changing data.")
    reset_parser.add_argument("--label", default="clean-slate", help="Optional label for the backup folder.")

    cache_parser = subparsers.add_parser("reset-caches", help="Back up and clear review/embedding caches while preserving sources.")
    cache_parser.add_argument("--confirm-gated", default="", metavar="PHRASE", help=f"Required phrase: {CONFIRMATION_PHRASE}")
    cache_parser.add_argument("--dry-run", action="store_true", help="Show what would be cleared without changing data.")
    cache_parser.add_argument("--label", default="cache-reset", help="Optional label for the backup folder.")

    restore_parser = subparsers.add_parser("restore", help="Back up current data and restore from a previous backup.")
    restore_parser.add_argument("backup", help="Backup folder produced by this script, or its nested data folder.")
    restore_parser.add_argument("--confirm-gated", default="", metavar="PHRASE", help=f"Required phrase: {CONFIRMATION_PHRASE}")
    restore_parser.add_argument("--dry-run", action="store_true", help="Show restore steps without changing data.")

    tranche_parser = subparsers.add_parser("plan-tranches", help="Create a staged loading manifest for a folder of final corpus files.")
    tranche_parser.add_argument("folder", help="Folder containing final source files.")
    tranche_parser.add_argument("--batch-size", type=int, default=10, help="Number of source files per tranche.")
    tranche_parser.add_argument("--output", default="", help="Optional JSON manifest path.")
    tranche_parser.add_argument("--materialise-dir", default="", help="Optional directory where tranche folders are copied.")
    tranche_parser.add_argument("--no-recursive", action="store_true", help="Only scan direct children of the folder.")

    args = parser.parse_args()
    load_env(Path(args.env_file))
    data_dir = Path(args.data_dir)
    backup_root = Path(args.backup_root)

    if args.command == "backup":
        result = backup_data(data_dir, backup_root, label=args.label)
        print(json.dumps(result.as_dict(), indent=2))
        return 0
    if args.command == "reset":
        result = reset_data(
            data_dir,
            backup_root,
            confirm_gated=args.confirm_gated,
            dry_run=args.dry_run,
            label=args.label,
        )
        print(json.dumps(result.as_dict(), indent=2))
        return 0
    if args.command == "reset-caches":
        result = reset_caches(
            data_dir,
            backup_root,
            confirm_gated=args.confirm_gated,
            dry_run=args.dry_run,
            label=args.label,
        )
        print(json.dumps(result.as_dict(), indent=2))
        return 0
    if args.command == "restore":
        result = restore_backup(
            data_dir,
            backup_root,
            Path(args.backup),
            confirm_gated=args.confirm_gated,
            dry_run=args.dry_run,
        )
        print(json.dumps(result.as_dict(), indent=2))
        return 0
    if args.command == "plan-tranches":
        manifest = plan_tranches(
            Path(args.folder),
            batch_size=args.batch_size,
            output=Path(args.output) if args.output else None,
            materialise_dir=Path(args.materialise_dir) if args.materialise_dir else None,
            recursive=not args.no_recursive,
        )
        print(json.dumps(manifest, indent=2))
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def backup_data(data_dir: Path, backup_root: Path, *, label: str = "") -> OperationResult:
    data_dir = data_dir.resolve()
    backup_root = backup_root.resolve()
    _validate_safe_data_dir(data_dir)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_root / f"{timestamp}-{_slug(label or data_dir.name)}"
    if backup_path.exists():
        raise FileExistsError(f"Backup path already exists: {backup_path}")
    backup_path.mkdir(parents=True)
    copied_to = backup_path / "data"
    if data_dir.exists():
        shutil.copytree(data_dir, copied_to)
    else:
        copied_to.mkdir()
    _write_json(
        backup_path / "manifest.json",
        {
            "schema": "opsatlas-data-backup-v1",
            "created_at": datetime.now(UTC).isoformat(),
            "source_data_dir": str(data_dir),
            "backup_data_dir": str(copied_to),
            "file_count": _count_files(copied_to),
            "byte_count": _count_bytes(copied_to),
        },
    )
    return OperationResult("backup", data_dir, backup_path, [backup_path])


def reset_data(
    data_dir: Path,
    backup_root: Path,
    *,
    confirm_gated: str,
    dry_run: bool = False,
    label: str = "clean-slate",
) -> OperationResult:
    data_dir = data_dir.resolve()
    _validate_safe_data_dir(data_dir)
    _require_confirmation(confirm_gated)
    changed = _runtime_paths(data_dir)
    if dry_run:
        return OperationResult("reset", data_dir, None, changed, dry_run=True)
    backup = backup_data(data_dir, backup_root, label=label).backup_path
    _wipe_directory_contents(data_dir)
    _initialise_baseline(data_dir, BASELINE_FILES)
    return OperationResult("reset", data_dir, backup, changed)


def reset_caches(
    data_dir: Path,
    backup_root: Path,
    *,
    confirm_gated: str,
    dry_run: bool = False,
    label: str = "cache-reset",
) -> OperationResult:
    data_dir = data_dir.resolve()
    _validate_safe_data_dir(data_dir)
    _require_confirmation(confirm_gated)
    changed = [data_dir / relative for relative in CACHE_RESET_FILES]
    if dry_run:
        return OperationResult("reset-caches", data_dir, None, changed, dry_run=True)
    backup = backup_data(data_dir, backup_root, label=label).backup_path
    _initialise_baseline(data_dir, CACHE_RESET_FILES)
    return OperationResult("reset-caches", data_dir, backup, changed)


def restore_backup(
    data_dir: Path,
    backup_root: Path,
    backup: Path,
    *,
    confirm_gated: str,
    dry_run: bool = False,
) -> OperationResult:
    data_dir = data_dir.resolve()
    backup = backup.resolve()
    backup_data_dir = backup / "data" if (backup / "data").is_dir() else backup
    _validate_safe_data_dir(data_dir)
    _require_confirmation(confirm_gated)
    if not backup_data_dir.is_dir():
        raise FileNotFoundError(f"Backup data folder not found: {backup_data_dir}")
    changed = _runtime_paths(data_dir)
    if dry_run:
        return OperationResult("restore", data_dir, None, changed, dry_run=True)
    current_backup = backup_data(data_dir, backup_root, label="pre-restore").backup_path
    _wipe_directory_contents(data_dir)
    shutil.copytree(backup_data_dir, data_dir, dirs_exist_ok=True)
    return OperationResult("restore", data_dir, current_backup, changed)


def plan_tranches(
    folder: Path,
    *,
    batch_size: int = 10,
    output: Path | None = None,
    materialise_dir: Path | None = None,
    recursive: bool = True,
) -> dict[str, Any]:
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1.")
    folder = folder.resolve()
    if not folder.is_dir():
        raise FileNotFoundError(f"Source folder not found: {folder}")
    pattern = "**/*" if recursive else "*"
    files = sorted(
        path
        for path in folder.glob(pattern)
        if path.is_file() and path.suffix.lower() in PACK_EXTENSIONS
    )
    batches = [
        files[index : index + batch_size]
        for index in range(0, len(files), batch_size)
    ]
    manifest = {
        "schema": "opsatlas-data-load-tranche-manifest-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "source_folder": str(folder),
        "batch_size": batch_size,
        "file_count": len(files),
        "tranche_count": len(batches),
        "tranches": [
            {
                "name": f"tranche-{index + 1:02d}",
                "file_count": len(batch),
                "files": [str(path.relative_to(folder)) for path in batch],
            }
            for index, batch in enumerate(batches)
        ],
    }
    if materialise_dir is not None:
        materialise_dir = materialise_dir.resolve()
        _materialise_tranches(folder, batches, materialise_dir)
        manifest["materialised_dir"] = str(materialise_dir)
        for tranche in manifest["tranches"]:
            tranche["import_command"] = (
                f".venv/bin/python scripts/import_packs.py "
                f"{materialise_dir / tranche['name']} --approve --report "
                f"output/final-load-{tranche['name']}.json"
            )
    if output is not None:
        _write_json(output, manifest)
        _write_tranche_markdown(output.with_suffix(".md"), manifest)
    return manifest


def _initialise_baseline(data_dir: Path, files: dict[str, Any]) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    for directory in BASELINE_DIRS:
        (data_dir / directory).mkdir(parents=True, exist_ok=True)
    for relative, payload in files.items():
        path = data_dir / relative
        if isinstance(payload, str):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(payload, encoding="utf-8")
        else:
            _write_json(path, payload)


def _wipe_directory_contents(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    for child in data_dir.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _runtime_paths(data_dir: Path) -> list[Path]:
    if data_dir.exists():
        return sorted(data_dir.iterdir())
    return []


def _materialise_tranches(folder: Path, batches: list[list[Path]], materialise_dir: Path) -> None:
    if materialise_dir.exists():
        raise FileExistsError(f"Materialise directory already exists: {materialise_dir}")
    for index, batch in enumerate(batches, start=1):
        tranche_dir = materialise_dir / f"tranche-{index:02d}"
        tranche_dir.mkdir(parents=True)
        for source in batch:
            relative = source.relative_to(folder)
            destination = tranche_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


def _write_tranche_markdown(path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# OpsAtlas Final Corpus Load Tranches",
        "",
        f"- Source folder: `{manifest['source_folder']}`",
        f"- Files: {manifest['file_count']}",
        f"- Tranches: {manifest['tranche_count']}",
        "",
    ]
    for tranche in manifest["tranches"]:
        lines.append(f"## {tranche['name']}")
        lines.append("")
        if "import_command" in tranche:
            lines.append(f"Command: `{tranche['import_command']}`")
            lines.append("")
        for file_name in tranche["files"]:
            lines.append(f"- `{file_name}`")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _require_confirmation(value: str) -> None:
    if value != CONFIRMATION_PHRASE:
        raise PermissionError(f"Refusing destructive operation. Pass --confirm-gated {CONFIRMATION_PHRASE}.")


def _validate_safe_data_dir(data_dir: Path) -> None:
    resolved = data_dir.resolve()
    forbidden = {Path("/").resolve(), ROOT.resolve(), ROOT.parent.resolve()}
    if resolved in forbidden:
        raise ValueError(f"Refusing unsafe data directory: {resolved}")
    if resolved == Path.home().resolve():
        raise ValueError(f"Refusing to use the home directory as data directory: {resolved}")


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-").lower()
    return slug or "backup"


def _count_files(path: Path) -> int:
    return sum(1 for item in path.rglob("*") if item.is_file())


def _count_bytes(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


if __name__ == "__main__":
    raise SystemExit(main())
