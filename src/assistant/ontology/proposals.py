"""Pending ontology action proposals."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .agent import AgentRunTrace, ProposedAction

ProposalStatus = Literal["pending", "approved", "declined"]


class PendingActionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    action: str
    params: dict[str, Any] = Field(default_factory=dict)
    rationale: str
    agent_run_id: str
    status: ProposalStatus = "pending"
    created_at: str
    execution_id: str = ""
    approved_at: str = ""
    declined_at: str = ""
    declined_reason: str = ""


class PendingActionStore:
    """Thread-safe JSON store for agent-proposed actions awaiting a human."""

    def __init__(self, base_dir: str | Path, filename: str = "pending_actions.json") -> None:
        self.path = Path(base_dir) / filename
        self._lock = threading.Lock()

    def add_from_trace(self, trace: AgentRunTrace) -> list[PendingActionProposal]:
        created: list[PendingActionProposal] = []
        for proposal in trace.proposed_actions:
            created.append(self.add(proposal, trace.run_id, created_at=trace.created_at))
        return created

    def add(self, proposal: ProposedAction, agent_run_id: str, *, created_at: str | None = None) -> PendingActionProposal:
        pending = PendingActionProposal(
            proposal_id=proposal.proposal_id,
            action=proposal.action,
            params=proposal.params,
            rationale=proposal.rationale,
            agent_run_id=agent_run_id,
            created_at=created_at or _now(),
        )
        with self._lock:
            rows = self._read_unlocked()
            by_id = {row["proposal_id"]: row for row in rows}
            if pending.proposal_id in by_id:
                return PendingActionProposal.model_validate(by_id[pending.proposal_id])
            rows.append(pending.model_dump())
            self._write_unlocked(rows)
        return pending

    def list(self) -> list[PendingActionProposal]:
        with self._lock:
            rows = self._read_unlocked()
        return [PendingActionProposal.model_validate(row) for row in reversed(rows)]

    def get(self, proposal_id: str) -> PendingActionProposal | None:
        with self._lock:
            for row in self._read_unlocked():
                if row["proposal_id"] == proposal_id:
                    return PendingActionProposal.model_validate(row)
        return None

    def mark_approved(self, proposal_id: str, execution_id: str) -> PendingActionProposal:
        return self._update(proposal_id, {"status": "approved", "execution_id": execution_id, "approved_at": _now()})

    def decline(self, proposal_id: str, reason: str = "") -> PendingActionProposal:
        return self._update(proposal_id, {"status": "declined", "declined_reason": reason, "declined_at": _now()})

    def _update(self, proposal_id: str, fields: dict[str, Any]) -> PendingActionProposal:
        with self._lock:
            rows = self._read_unlocked()
            for row in rows:
                if row["proposal_id"] == proposal_id:
                    row.update(fields)
                    self._write_unlocked(rows)
                    return PendingActionProposal.model_validate(row)
        raise KeyError(f"Pending action proposal not found: {proposal_id}")

    def _read_unlocked(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8") or "[]")

    def _write_unlocked(self, rows: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def _now() -> str:
    return datetime.now(UTC).isoformat()
