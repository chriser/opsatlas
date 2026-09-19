"""Bounded standalone evidence adapter; has no Atlas filesystem or DB access."""

import copy
import hashlib
import json
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures/supplier.json"


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


class FixtureEvidence:
    def __init__(self, path: Path = FIXTURE):
        self.path = path

    def snapshot(self):
        raw = json.loads(self.path.read_text())
        if raw.get("mode") != "synthetic_fixture" or raw.get("schema") != 1:
            raise ValueError("Unsupported evidence pack")
        sources = []
        for source in raw.get("sources", [])[:8]:
            if source.get("eligible") is not True or source.get("approval") != "fixture-approved":
                continue
            if not isinstance(source.get("text"), str) or not 1 <= len(source["text"]) <= 4000:
                raise ValueError("Invalid evidence passage")
            sources.append(
                {
                    **source,
                    "sha256": hashlib.sha256(source["text"].encode()).hexdigest(),
                    "start": 0,
                    "end": len(source["text"]),
                    "retrieval_method": "pinned_fixture",
                }
            )
        pack = {key: copy.deepcopy(raw[key]) for key in ("schema", "id", "mode", "title", "scope", "notice")}
        pack["sources"] = sources
        pack["hash"] = digest(pack)
        return pack

    def current(self, snapshot):
        try:
            return self.snapshot()["hash"] == snapshot["hash"]
        except (OSError, ValueError, KeyError):
            return False
