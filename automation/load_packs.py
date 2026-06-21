"""Bulk-load knowledge packs: upload -> ingest -> approve every file in a folder.

Loads into the app's persistent data dir (KP_DATA_DIR, default ./data), so the
control panel and assistant see them immediately. Idempotent: files already
registered (by filename) are skipped.

Usage:
  PYTHONPATH=src .venv/bin/python automation/load_packs.py --dir packs
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="packs", help="Folder of source documents to load")
    ap.add_argument("--data-dir", default=os.environ.get("KP_DATA_DIR", "data"))
    args = ap.parse_args()

    from assistant.ingestion.service import NotIngestableError, ingest_source
    from assistant.ingestion.store import SectionStore
    from assistant.sources.models import ALLOWED_EXTENSIONS
    from assistant.sources.register import SourceRegister
    from assistant.sources.service import UploadError, register_upload

    folder = Path(args.dir)
    if not folder.is_dir():
        raise SystemExit(f"Folder not found: {folder}")

    register = SourceRegister(args.data_dir)
    store = SectionStore(register.base_dir)
    existing = {r.filename for r in register.list()}

    loaded = skipped = sections = 0
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        if path.name in existing:
            print(f"  = {path.name} (already registered, skipped)")
            skipped += 1
            continue
        try:
            record = register_upload(register, path.name, path.read_bytes(), title=path.stem)
            record = ingest_source(register, store, record.id)
            register.update(record.id, approval_status="approved")
        except (UploadError, NotIngestableError) as exc:
            print(f"  ! {path.name}: {exc}")
            skipped += 1
            continue
        loaded += 1
        sections += record.section_count
        print(f"  + {path.name} -> ingested ({record.section_count} sections), approved")

    print(f"\nLoaded {loaded} document(s), {sections} sections; {skipped} skipped. Total in register: {len(register.list())}.")


if __name__ == "__main__":
    main()
