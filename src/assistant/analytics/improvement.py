"""Improvement-action lifecycle for analytics-driven documentation work."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

TriggerType = Literal["knowledge_gap", "failed_retrieval", "recurring_question"]
ReviewCadence = Literal["weekly", "monthly", "ad_hoc"]
ImprovementStatus = Literal["open", "in_progress", "actioned", "closed", "wont_fix"]

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "open": {"in_progress", "actioned", "wont_fix"},
    "in_progress": {"actioned", "closed", "wont_fix"},
    "actioned": {"closed", "wont_fix"},
    "closed": set(),
    "wont_fix": set(),
}


class ImprovementNote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: str
    note: str


class ImprovementAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    trigger_type: TriggerType
    trigger_ref: str
    recommended_action: str
    owner_role: str
    review_cadence: ReviewCadence = "weekly"
    status: ImprovementStatus = "open"
    linked_source_id: str = ""
    created_at: str
    updated_at: str
    closed_at: str = ""
    notes: list[ImprovementNote] = Field(default_factory=list)


class ImprovementActionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trigger_type: TriggerType
    trigger_ref: str = Field(min_length=1, max_length=200)
    recommended_action: str = Field(min_length=2, max_length=500)
    owner_role: str = Field(default="Knowledge owner", min_length=2, max_length=120)
    review_cadence: ReviewCadence = "weekly"
    note: str = Field(default="", max_length=500)


class ImprovementActionTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ImprovementStatus
    linked_source_id: str = Field(default="", max_length=200)
    note: str = Field(default="", max_length=500)


class ImprovementActionStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.path = Path(base_dir) / "improvement_actions.json"
        self._lock = threading.Lock()

    def list(self) -> list[ImprovementAction]:
        return [ImprovementAction.model_validate(row) for row in self._read()]

    def get(self, action_id: str) -> ImprovementAction | None:
        for action in self.list():
            if action.id == action_id:
                return action
        return None

    def create(self, payload: ImprovementActionCreate) -> ImprovementAction:
        now = _now()
        action = ImprovementAction(
            id=f"imp-{uuid4().hex[:12]}",
            trigger_type=payload.trigger_type,
            trigger_ref=payload.trigger_ref.strip(),
            recommended_action=payload.recommended_action.strip(),
            owner_role=payload.owner_role.strip(),
            review_cadence=payload.review_cadence,
            created_at=now,
            updated_at=now,
            notes=[ImprovementNote(timestamp=now, note=payload.note.strip())] if payload.note.strip() else [],
        )
        with self._lock:
            rows = self._read_unlocked()
            rows.append(action.model_dump())
            self._write_unlocked(rows)
        return action

    def transition(self, action_id: str, payload: ImprovementActionTransition) -> ImprovementAction:
        with self._lock:
            rows = self._read_unlocked()
            for index, row in enumerate(rows):
                action = ImprovementAction.model_validate(row)
                if action.id != action_id:
                    continue
                updated = _transition(action, payload)
                rows[index] = updated.model_dump()
                self._write_unlocked(rows)
                return updated
        raise KeyError(f"Unknown improvement action: {action_id}")

    def _read(self) -> list[dict]:
        with self._lock:
            return self._read_unlocked()

    def _read_unlocked(self) -> list[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8") or "[]")

    def _write_unlocked(self, rows: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def _transition(action: ImprovementAction, payload: ImprovementActionTransition) -> ImprovementAction:
    if payload.status == action.status:
        return _with_note(action, payload.note)
    if payload.status not in _ALLOWED_TRANSITIONS[action.status]:
        raise ValueError(f"Cannot transition improvement action from {action.status} to {payload.status}.")
    if payload.status == "closed" and not payload.linked_source_id.strip() and not action.linked_source_id:
        raise ValueError("Closing an improvement action requires linked_source_id.")
    now = _now()
    linked_source_id = payload.linked_source_id.strip() or action.linked_source_id
    notes = list(action.notes)
    if payload.note.strip():
        notes.append(ImprovementNote(timestamp=now, note=payload.note.strip()))
    return action.model_copy(
        update={
            "status": payload.status,
            "linked_source_id": linked_source_id,
            "updated_at": now,
            "closed_at": now if payload.status in {"closed", "wont_fix"} else "",
            "notes": notes,
        }
    )


def _with_note(action: ImprovementAction, note: str) -> ImprovementAction:
    if not note.strip():
        return action
    now = _now()
    return action.model_copy(
        update={
            "updated_at": now,
            "notes": [*action.notes, ImprovementNote(timestamp=now, note=note.strip())],
        }
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
