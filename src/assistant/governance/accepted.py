"""Operator-accepted knowledge issues.

When an operator accepts an issue (a deliberate, informed decision that it is fine
as-is), it is recorded here so it drops out of the active issue list but stays
auditable and is surfaced as an 'accepted' label on the source. File-backed JSON.
"""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path


def issue_key(source_id: str, check: str, detail: str) -> str:
    return hashlib.sha256(f"{source_id}|{check}|{detail}".encode()).hexdigest()[:16]


class AcceptedStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.path = Path(base_dir) / "accepted_issues.json"
        self._lock = threading.Lock()

    def _load(self) -> set[str]:
        if not self.path.exists():
            return set()
        return set(json.loads(self.path.read_text() or "[]"))

    def all(self) -> set[str]:
        return self._load()

    def is_accepted(self, source_id: str, check: str, detail: str) -> bool:
        return issue_key(source_id, check, detail) in self._load()

    def accept(self, source_id: str, check: str, detail: str) -> None:
        with self._lock:
            keys = self._load()
            keys.add(issue_key(source_id, check, detail))
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(sorted(keys), indent=2))
