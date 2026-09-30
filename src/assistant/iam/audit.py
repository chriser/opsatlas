"""The security audit record (IAM F2): who did what, to what, with which outcome, in order.

Kept apart from user-activity analytics, written in the same transaction as the IAM change it records, and
hash-chained so that a gap or an altered row is detectable. Chaining is not proof against the host administrator,
who controls the database: a shared deployment would export events to a separately controlled destination.
Secrets never enter it: fields whose names suggest one are redacted, and document text, prompts and conversation
words are not passed in.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from .store import IamStore

REDACTED = "[redacted]"
_SECRET_KEY = re.compile(r"password|secret|token|cookie|authorization|hash|csrf|digest|credential", re.I)
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: (REDACTED if _SECRET_KEY.search(str(k)) else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return _CONTROL.sub(" ", value)[:500]
    return value


class Audit:
    def __init__(self, store: IamStore) -> None:
        self.store = store

    def record(self, *, action: str, outcome: str = "success", actor_id: str | None = None, actor_type: str = "human",
               on_behalf_of: str | None = None, session_ref: str | None = None, reason: str = "",
               target_type: str | None = None, target_id: str | None = None, target_label: str | None = None,
               space_id: str | None = None, request_id: str | None = None, before: Any = None, after: Any = None,
               detail: Any = None, address: str | None = None) -> dict:
        store = self.store
        with store.transaction():
            last = store.one("SELECT hash FROM audit_events ORDER BY seq DESC LIMIT 1")
            prev_hash = last["hash"] if last else "0" * 64
            row = {
                "id": store.new_id("evt"), "at": store.stamp(), "actor_id": actor_id, "actor_type": actor_type,
                "on_behalf_of": on_behalf_of, "session_ref": session_ref, "action": action, "outcome": outcome,
                "reason": redact(reason or ""), "target_type": target_type, "target_id": target_id,
                "target_label": redact(target_label) if target_label else None, "space_id": space_id,
                "request_id": request_id, "policy_version": store.policy_version(),
                "before": json.dumps(redact(before)) if before is not None else None,
                "after": json.dumps(redact(after)) if after is not None else None,
                "detail": json.dumps(redact(detail)) if detail is not None else None,
                "address": address, "prev_hash": prev_hash,
            }
            row["hash"] = _digest(prev_hash, row)
            store.insert("audit_events", row)
        return row

    def events(self, *, limit: int = 100, before_seq: int | None = None, action: str | None = None,
               actor_id: str | None = None, space_id: str | None = None, outcome: str | None = None,
               target_id: str | None = None, since: str | None = None) -> list[dict]:
        clauses, params = [], []
        for column, value in (("action", action), ("actor_id", actor_id), ("space_id", space_id), ("outcome", outcome),
                              ("target_id", target_id)):
            if value:
                if column == "action" and value.endswith("*"):
                    clauses.append("action LIKE ?")
                    params.append(value[:-1] + "%")
                else:
                    clauses.append(f"{column} = ?")
                    params.append(value)
        if before_seq is not None:
            clauses.append("seq < ?")
            params.append(before_seq)
        if since:
            clauses.append("at >= ?")
            params.append(since)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self.store.all(f"SELECT * FROM audit_events {where} ORDER BY seq DESC LIMIT ?", [*params, max(1, min(limit, 500))])
        for row in rows:
            for key in ("before", "after", "detail"):
                row[key] = json.loads(row[key]) if row[key] else None
        return rows

    def verify_chain(self) -> tuple[bool, int]:
        """Every event's hash follows from the previous one: (intact, events checked)."""
        prev, checked = "0" * 64, 0
        for row in self.store.all("SELECT * FROM audit_events ORDER BY seq"):
            if row["prev_hash"] != prev or _digest(prev, row) != row["hash"]:
                return False, checked
            prev, checked = row["hash"], checked + 1
        return True, checked


_HASHED = ("id", "at", "actor_id", "actor_type", "on_behalf_of", "session_ref", "action", "outcome", "reason",
           "target_type", "target_id", "target_label", "space_id", "request_id", "policy_version", "before", "after",
           "detail", "address")


def _digest(prev_hash: str, row: dict) -> str:
    body = json.dumps({k: row.get(k) for k in _HASHED}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256((prev_hash + body).encode()).hexdigest()
