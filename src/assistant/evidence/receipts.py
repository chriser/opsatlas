"""Evidence receipts (REF S18): what an answer rested on, kept with the answer so it can be shown later.

A receipt names, for every passage an answer cited, the source, the version of its text (the content-management version
number and the SHA-256 of that text), where in it the passage sits (heading and position, and the passage's own hash),
when it was retrieved, and the model, prompt version, space and person of the answer. Yesterday's answer can then be
shown to rest on yesterday's document, whatever the document says today.

One JSON line per answer in ``<space>/receipts/<YYYY-MM>.jsonl``: append-only, never rewritten. The question itself
stays in the usage log; the receipt carries its hash.
"""
from __future__ import annotations

import hashlib
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ReceiptStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.directory = Path(base_dir) / "receipts"
        self._lock = threading.Lock()

    def write(self, receipt: dict) -> str:
        receipt_id = f"rcpt-{uuid.uuid4().hex[:16]}"
        stamped = {"id": receipt_id, "at": datetime.now(timezone.utc).isoformat(), **receipt}
        line = json.dumps(stamped, ensure_ascii=False, sort_keys=True)
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            with (self.directory / f"{stamped['at'][:7]}.jsonl").open("a", encoding="utf-8") as out:
                out.write(line + "\n")
        return receipt_id

    def get(self, receipt_id: str) -> dict | None:
        if not receipt_id.startswith("rcpt-") or not self.directory.exists():
            return None
        for path in sorted(self.directory.glob("*.jsonl"), reverse=True):
            for line in path.read_text(encoding="utf-8").splitlines():
                if receipt_id in line:
                    row = json.loads(line)
                    if row.get("id") == receipt_id:
                        return row
        return None
