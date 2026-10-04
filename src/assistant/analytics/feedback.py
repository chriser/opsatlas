"""Feedback on written answers (REF S20): good, odd or wrong, with a note.

Tibi's turns are marked in the conversation log; written answers had no such control. A mark is kept per answer and
person in ``answer_feedback.jsonl``, one line per mark; the latest line for an answer and person counts.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Verdict = Literal["good", "odd", "wrong"]


class AnswerFeedbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Verdict
    note: str = Field(default="", max_length=1000)
    raise_action: bool = False  # an odd or wrong mark may raise an improvement action at once


class AnswerFeedbackStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.path = Path(base_dir) / "answer_feedback.jsonl"
        self._lock = threading.Lock()

    def record(self, answer_id: str, verdict: str, note: str, actor_id: str | None, action_id: str | None = None) -> dict:
        row = {
            "answer_id": answer_id,
            "verdict": verdict,
            "note": " ".join(note.split())[:1000],
            "actor_id": actor_id,
            "action_id": action_id,
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as out:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def latest(self) -> dict[tuple[str, str | None], dict]:
        """The latest mark per (answer, person)."""
        out: dict[tuple[str, str | None], dict] = {}
        if not self.path.exists():
            return out
        for line in self.path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            out[(row.get("answer_id"), row.get("actor_id"))] = row
        return out
