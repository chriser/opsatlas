#!/usr/bin/env python
"""Import a folder of learning-pack files through the governed source pipeline."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from assistant.ingestion.store import SectionStore
from assistant.sources.bulk_import import import_folder, report_markdown, write_report
from assistant.sources.register import SourceRegister


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", help="Folder containing .md, .txt, .json, .pdf or .docx learning packs.")
    parser.add_argument("--data-dir", default=os.environ.get("KP_DATA_DIR", "data"), help="Knowledge Platform data directory.")
    parser.add_argument("--approve", action="store_true", help="Approve successfully ingested sources immediately.")
    parser.add_argument("--dry-run", action="store_true", help="Scan and report what would be imported without writing data.")
    parser.add_argument("--no-recursive", action="store_true", help="Only scan direct children of the folder.")
    parser.add_argument("--report", default="", help="Optional JSON report path. A matching .md report is also written.")
    parser.add_argument("--env-file", default=str(ROOT / ".env"), help="Optional .env file to load first.")
    args = parser.parse_args()

    load_env(Path(args.env_file))
    register = SourceRegister(args.data_dir)
    section_store = SectionStore(register.base_dir)
    report = import_folder(
        args.folder,
        register,
        section_store,
        approve=args.approve,
        dry_run=args.dry_run,
        recursive=not args.no_recursive,
    )
    if args.report:
        write_report(report, args.report)
        print(f"Wrote {args.report} and {Path(args.report).with_suffix('.md')}")
    print(report_markdown(report))
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
