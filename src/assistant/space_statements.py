"""Channel text that makes claims comes under knowledge governance (REF S22).

A space says some things in fixed words rather than from its documents: its refusal, its off-topic message, its
referral to the sales team, its notes on its own topics, and (for the Product Guide) Tibi's directions for contributing
product knowledge. Those words reach users like any answer, so they are governed like knowledge: each has versions,
each version an approval, and an answer that uses one says which version (``statements`` on the answer and in its
receipt).

The space's configuration file stays where the words are written (ARCH H2: the owner edits it). What is used is the
latest approved version: when the file says something new, that becomes a pending version, and the space keeps
speaking the approved words until someone who may approve documents in the space approves it. The words in use when
statements came under governance were recorded once as version 1, approved as found.

One file per space: ``<space>/space-statements.json``.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

FILE_NAME = "space-statements.json"
AS_FOUND = "OpsAtlas (the words in use when statements came under governance)"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def texts_of(config) -> dict[str, str]:
    """The fixed sentences a space configuration says, by key."""
    out = {"refusal": config.refusal, "scope_message": config.guardrails.scope_message or "",
           "referral": config.referral.sentence or ""}
    out.update({f"note.{i}": note.sentence for i, note in enumerate(config.notes)})
    return {key: text for key, text in out.items() if text and text.strip()}


class SpaceStatements:
    def __init__(self, base_dir: str | Path) -> None:
        self.path = Path(base_dir) / FILE_NAME
        self._lock = threading.Lock()

    def _read(self) -> dict:
        """The statements; none on a first start. A file that cannot be read stops the space, as an unreadable
        space-config.json does: taking it for empty would record whatever the configuration now says, approved or
        not, as approved (found by the random scenarios, REF F10)."""
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"{self.path}: the space's governed statements cannot be read ({exc}); restore the file") from exc
        if not isinstance(data, dict):
            raise ValueError(f"{self.path}: expected an object")
        return data

    def _write(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".statements-")
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out, indent=1, ensure_ascii=False)
        os.replace(tmp, self.path)

    def sync(self, texts: dict[str, str]) -> None:
        """Bring the statements in line with what the configuration says: a key seen for the first time is recorded as
        approved (the words already in use); words that differ from every kept version become a pending version."""
        with self._lock:
            data = self._read()
            changed = False
            for key, text in texts.items():
                versions = data.setdefault(key, [])
                if any(v["text"] == text for v in versions):
                    continue
                first = not versions
                versions.append({"version": len(versions) + 1, "text": text, "sha256": hashlib.sha256(text.encode()).hexdigest(),
                                 "proposed_at": _now(), "approved": first, "approved_by": AS_FOUND if first else None,
                                 "approved_at": _now() if first else None})
                changed = True
            if changed:
                self._write(data)

    def approved(self, key: str) -> dict | None:
        versions = [v for v in self._read().get(key, []) if v["approved"]]
        return {"key": key, **versions[-1]} if versions else None

    def listing(self) -> list[dict]:
        data = self._read()
        return [{"key": key, "approved": next((v for v in reversed(versions) if v["approved"]), None),
                 "pending": [v for v in versions if not v["approved"]]} for key, versions in sorted(data.items())]

    def approve(self, key: str, version: int, person: str) -> dict:
        with self._lock:
            data = self._read()
            row = next((v for v in data.get(key, []) if v["version"] == version), None)
            if row is None:
                raise KeyError(key)
            row.update(approved=True, approved_by=person, approved_at=_now())
            self._write(data)
            return {"key": key, **row}

    def governed(self, config):
        """The configuration speaking its approved words: a pending sentence is not used until it is approved."""
        def words(key: str, current: str) -> str:
            row = self.approved(key)
            return row["text"] if row else current
        notes = [note.model_copy(update={"sentence": words(f"note.{i}", note.sentence)}) for i, note in enumerate(config.notes)]
        scope = words("scope_message", config.guardrails.scope_message or "") or config.guardrails.scope_message
        referral = words("referral", config.referral.sentence or "") or config.referral.sentence
        return config.model_copy(update={
            "refusal": words("refusal", config.refusal),
            "guardrails": config.guardrails.model_copy(update={"scope_message": scope}),
            "referral": config.referral.model_copy(update={"sentence": referral}),
            "notes": notes})

    def cite(self, key: str) -> dict | None:
        """What an answer records when it says this statement: its key, version and hash."""
        row = self.approved(key)
        return {"key": key, "version": row["version"], "sha256": row["sha256"]} if row else None
