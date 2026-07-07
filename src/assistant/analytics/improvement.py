"""Improvement-action lifecycle for analytics-driven documentation work."""

from __future__ import annotations

import json
import threading
from collections import Counter
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


def build_improvement_loop_metrics(actions: list[ImprovementAction], *, now: datetime | None = None) -> dict:
    """Build deterministic improvement-loop management metrics."""

    reference = now or datetime.now(timezone.utc)
    total = len(actions)
    status_counts = Counter(action.status for action in actions)
    trigger_counts = Counter(action.trigger_type for action in actions)
    cadence_counts = Counter(action.review_cadence for action in actions)
    closed = [action for action in actions if action.status == "closed"]
    actioned = [action for action in actions if action.status in {"actioned", "closed"}]
    active = [action for action in actions if action.status not in {"closed", "wont_fix"}]
    open_ages = [_age_days(action.created_at, reference) for action in active]
    closure_days = [
        _days_between(action.created_at, action.closed_at)
        for action in closed
        if action.closed_at.strip()
    ]
    trigger_ref_counts = Counter((action.trigger_type, action.trigger_ref) for action in actions)
    duplicate_refs = sum(count - 1 for count in trigger_ref_counts.values() if count > 1)
    review_due = [_review_due_row(action, reference) for action in active]
    review_due = [row for row in review_due if row is not None]
    review_due.sort(key=lambda row: (-row["days_overdue"], row["updated_at"], row["id"]))
    return {
        "action_count": total,
        "status_counts": {status: status_counts.get(status, 0) for status in _ALLOWED_TRANSITIONS},
        "trigger_counts": dict(sorted(trigger_counts.items())),
        "cadence_counts": dict(sorted(cadence_counts.items())),
        "owner_workload": [
            {"owner_role": owner, "open_actions": count}
            for owner, count in sorted(Counter(action.owner_role for action in active).items())
        ],
        "rates": {
            "actioned_rate": _rate(len(actioned), total),
            "closure_rate": _rate(status_counts.get("closed", 0), total),
            "wont_fix_rate": _rate(status_counts.get("wont_fix", 0), total),
            "repeat_trigger_rate": _rate(duplicate_refs, total),
        },
        "age": {
            "average_open_age_days": _mean(open_ages),
            "oldest_open_age_days": max(open_ages, default=0.0),
            "mean_time_to_close_days": _mean(closure_days),
        },
        "review_due_count": len(review_due),
        "review_due": review_due[:20],
        "rubric": {
            "actioned_rate": "Actions in actioned or closed status divided by all improvement actions.",
            "repeat_trigger_rate": "Repeated trigger references beyond the first divided by all improvement actions.",
            "review_due": "Open, in-progress or actioned items whose cadence window has elapsed since the last update.",
            "mean_time_to_close_days": "Average days from created_at to closed_at for closed items.",
        },
    }


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


def _review_due_row(action: ImprovementAction, now: datetime) -> dict | None:
    cadence_days = {"weekly": 7, "monthly": 30}.get(action.review_cadence)
    if cadence_days is None:
        return None
    days_since_update = _age_days(action.updated_at, now)
    if days_since_update < cadence_days:
        return None
    return {
        "id": action.id,
        "trigger_type": action.trigger_type,
        "trigger_ref": action.trigger_ref,
        "owner_role": action.owner_role,
        "status": action.status,
        "review_cadence": action.review_cadence,
        "updated_at": action.updated_at,
        "days_since_update": days_since_update,
        "days_overdue": round(days_since_update - cadence_days, 2),
        "recommended_action": action.recommended_action,
    }


def _age_days(timestamp: str, now: datetime) -> float:
    parsed = _parse_dt(timestamp)
    return round(max(0.0, (now - parsed).total_seconds() / 86400), 2)


def _days_between(start: str, end: str) -> float:
    return round(max(0.0, (_parse_dt(end) - _parse_dt(start)).total_seconds() / 86400), 2)


def _parse_dt(timestamp: str) -> datetime:
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _rate(numerator: int | float, denominator: int | float) -> float:
    return round(float(numerator) / float(denominator), 4) if denominator else 0.0


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0
