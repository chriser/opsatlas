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
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

from .storage import atomic_write_text, locked

FILE_NAME = "space-statements.json"
AS_FOUND = "OpsAtlas (the words in use when statements came under governance)"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def note_key(note) -> str:
    """A note's key, from its topics: stable when another note is added or removed (keyed by position, removing one
    note moved another's approved words onto the wrong topics; red team, REF F10)."""
    slug = "-".join(re.findall(r"[a-z0-9]+", " ".join(sorted(note.topics)).casefold()))[:80]
    return f"note.{slug or 'untitled'}"


def texts_of(config) -> dict[str, str]:
    """The fixed sentences a space configuration says, by key."""
    out = {"refusal": config.refusal, "scope_message": config.guardrails.scope_message or "",
           "referral": config.referral.sentence or ""}
    out.update({note_key(note): note.sentence for note in config.notes if note.topics})
    return {key: text for key, text in out.items() if text and text.strip()}


class SpaceStatements:
    def __init__(self, base_dir: str | Path) -> None:
        self.path = Path(base_dir) / FILE_NAME
        self._lock = threading.Lock()
        # Whether governance starts with this start: only then are the words in use recorded as approved, as found.
        self.new = not os.path.lexists(self.path)

    def _read(self) -> dict:
        """The statements; none on a first start. A file that cannot be read stops the space, as an unreadable
        space-config.json does: taking it for empty would record whatever the configuration now says, approved or
        not, as approved (found by the random scenarios and the red team, REF F10)."""
        if not os.path.lexists(self.path):
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"{self.path}: the space's governed statements cannot be read ({exc}); restore the file") from exc
        if not isinstance(data, dict):
            raise ValueError(f"{self.path}: expected an object")
        return data

    def _write(self, data: dict) -> None:
        atomic_write_text(self.path, json.dumps(data, indent=1, ensure_ascii=False))

    def sync(self, texts: dict[str, str], adopt_new: bool = False) -> None:
        """Bring the statements in line with what the configuration says. Words that differ from every kept version
        become a pending version. A key's first version is approved only when governance starts with this start
        (``adopt_new``): a sentence added later waits for approval like any other change."""
        with self._lock, locked(self.path):
            data = self._read()
            changed = self._carry_positional_notes(data, texts)
            for key, text in texts.items():
                versions = data.setdefault(key, [])
                if any(v["text"] == text for v in versions):
                    continue
                approved = adopt_new and not versions
                versions.append({"version": len(versions) + 1, "text": text, "sha256": hashlib.sha256(text.encode()).hexdigest(),
                                 "proposed_at": _now(), "approved": approved, "approved_by": AS_FOUND if approved else None,
                                 "approved_at": _now() if approved else None})
                changed = True
            if changed:
                self._write(data)

    @staticmethod
    def _carry_positional_notes(data: dict, texts: dict[str, str]) -> bool:
        """Notes were first keyed by position ("note.0"); one whose approved words a current note still says moves, with
        its history, to that note's key."""
        moved = False
        for old in [k for k in data if re.fullmatch(r"note\.\d+", k)]:
            approved = [v["text"] for v in data[old] if v["approved"]]
            target = next((k for k, text in texts.items() if k.startswith("note.") and k not in data
                           and approved and text == approved[-1]), None)
            if target:
                data[target] = data.pop(old)
                moved = True
        return moved

    def approved(self, key: str) -> dict | None:
        versions = [v for v in self._read().get(key, []) if v["approved"]]
        return {"key": key, **versions[-1]} if versions else None

    def listing(self) -> list[dict]:
        data = self._read()
        return [{"key": key, "approved": next((v for v in reversed(versions) if v["approved"]), None),
                 "pending": [v for v in versions if not v["approved"]]} for key, versions in sorted(data.items())]

    def approve(self, key: str, version: int, person: str) -> dict:
        with self._lock, locked(self.path):
            data = self._read()
            row = next((v for v in data.get(key, []) if v["version"] == version), None)
            if row is None:
                raise KeyError(key)
            row.update(approved=True, approved_by=person, approved_at=_now())
            self._write(data)
            return {"key": key, **row}

    def governed(self, config):
        """The configuration speaking its approved words. A sentence with only pending versions is not said: the
        refusal and the off-topic message fall back to the platform's defaults, a referral or note says nothing."""
        from .space_config import DEFAULT_REFUSAL, DEFAULT_SCOPE
        data = self._read()

        def words(key: str, current: str, default: str) -> str:
            versions = data.get(key)
            if not versions:
                return current  # not under governance (no sync yet): the configuration's own words
            approved = [v["text"] for v in versions if v["approved"]]
            return approved[-1] if approved else default
        notes = [note.model_copy(update={"sentence": words(note_key(note), note.sentence, "")}) if note.topics else note
                 for note in config.notes]
        return config.model_copy(update={
            "refusal": words("refusal", config.refusal, DEFAULT_REFUSAL),
            "guardrails": config.guardrails.model_copy(update={
                "scope_message": words("scope_message", config.guardrails.scope_message or "", DEFAULT_SCOPE)}),
            "referral": config.referral.model_copy(update={"sentence": words("referral", config.referral.sentence or "", "")}),
            "notes": notes})

    def cite(self, key: str) -> dict | None:
        """What an answer records when it says this statement: its key, version and hash."""
        row = self.approved(key)
        return {"key": key, "version": row["version"], "sha256": row["sha256"]} if row else None
