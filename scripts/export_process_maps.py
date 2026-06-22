#!/usr/bin/env python
"""Export process registry records as Lucid-ready JSON and Mermaid drafts."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def main() -> int:
    from assistant.process.maps import build_process_maps
    from assistant.process.registry import ProcessRegistry
    from assistant.sources.register import SourceRegister

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=os.environ.get("KP_DATA_DIR", "data"), help="Knowledge Platform data directory.")
    parser.add_argument("--output-dir", default="exports/process-maps", help="Directory for JSON and Mermaid map drafts.")
    parser.add_argument("--env-file", default=str(ROOT / ".env"), help="Optional .env file to load first.")
    args = parser.parse_args()

    load_env(Path(args.env_file))
    register = SourceRegister(args.data_dir)
    registry = ProcessRegistry(register.base_dir)
    records = registry.build_from_sources(register)
    drafts = build_process_maps(records)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    for draft in drafts:
        stem = _safe_name(draft.name or draft.process_id)
        (out / f"{stem}.json").write_text(json.dumps(draft.model_dump(), indent=2), encoding="utf-8")
        (out / f"{stem}.mmd").write_text(draft.mermaid + "\n", encoding="utf-8")
    print(f"Exported {len(drafts)} process map draft(s) to {out}")
    return 0


def _safe_name(value: str) -> str:
    keep = [ch.lower() if ch.isalnum() else "-" for ch in value]
    return "-".join(part for part in "".join(keep).split("-") if part)[:80] or "process-map"


if __name__ == "__main__":
    raise SystemExit(main())
