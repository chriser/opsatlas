"""Usage log and scorecard.

Records every assistant query and derives quality metrics and knowledge gaps
(questions the assistant could not answer from approved knowledge).
"""

from __future__ import annotations

import json
import threading
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from ..storage import write_json
from .classify import classify_topic


class UsageEntry(BaseModel):
    id: str = ""  # given when recorded, so an answer can be rated (REF S20); older entries have none
    timestamp: str
    question: str
    mode: str
    answer_path: str = "rag"
    citation_type_counts: dict[str, int] = Field(default_factory=dict)
    deterministic_evidence_ratio: float = 0.0
    generative_evidence_ratio: float = 0.0
    deterministic_evidence_flag: bool = False
    refused: bool
    category: str | None = None
    actor_type: str = "operator"  # "persona": asked by the simulator, kept out of the statistics (ARCH F4)
    actor_id: str | None = None  # who asked, by stable id (REF S9)
    space: str | None = None  # in which knowledge space (REF S9)
    confidence: str = "none"
    citation_count: int = 0
    channel: str = "written"  # written, voice, typed or digital_sme (REF S20)
    gap_eligible: bool = True  # False: a social, interview or failed turn, which cannot show a knowledge gap (REF S20)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_recorded: ContextVar[list[str] | None] = ContextVar("usage_recorded", default=None)


@contextmanager
def recording() -> Iterator[list[str]]:
    """The ids of the usage entries recorded inside the block, so a route can hand an answer's id back for rating
    without the answer service passing it along (REF S20)."""
    ids: list[str] = []
    token = _recorded.set(ids)
    try:
        yield ids
    finally:
        _recorded.reset(token)


class UsageLog:
    def __init__(self, base_dir: str | Path, extra: Callable[[], list[UsageEntry]] | None = None) -> None:
        self.path = Path(base_dir) / "usage_log.json"
        self._lock = threading.Lock()
        # Usage kept elsewhere and read, not copied, into the analytics: in the Sales workspace, Tibi's turns (REF S20).
        self.extra = extra

    def _read(self) -> list[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text() or "[]")

    def append(self, entry: UsageEntry) -> UsageEntry:
        if not entry.id:
            entry = entry.model_copy(update={"id": f"ans-{uuid4().hex[:12]}"})
        with self._lock:
            rows = self._read()
            rows.append(entry.model_dump())
            self.path.parent.mkdir(parents=True, exist_ok=True)
            write_json(self.path, rows, indent=2)
        if (ids := _recorded.get()) is not None:
            ids.append(entry.id)
        return entry

    def get(self, entry_id: str) -> UsageEntry | None:
        """One recorded entry by id; the extra usage is not looked in (REF S20)."""
        for row in self._read():
            if entry_id and row.get("id") == entry_id:
                return UsageEntry(**row)
        return None

    def entries(self, include_simulated: bool = False) -> list[UsageEntry]:
        """The usage entries, without the simulator's questions unless asked for: they were counted as real usage.
        With the extra usage, if any (REF S20)."""
        rows = [UsageEntry(**r) for r in self._read()] + (self.extra() if self.extra is not None else [])
        return rows if include_simulated else [r for r in rows if r.actor_type != "persona"]


def build_scorecard(entries: list[UsageEntry]) -> dict:
    total = len(entries)
    answered = [e for e in entries if not e.refused]
    refused = [e for e in entries if e.refused]
    guardrail = [e for e in entries if e.category]
    grounded = [e for e in answered if e.confidence == "grounded"]

    def rate(n: int) -> float:
        return round(n / total, 3) if total else 0.0

    # Knowledge gaps: genuine misses (refused, not a guardrail block), de-duplicated.
    gaps: list[str] = []
    seen: set[str] = set()
    for e in entries:
        key = e.question.strip().lower()
        if e.refused and not e.category and e.gap_eligible and key and key not in seen:
            seen.add(key)
            gaps.append(e.question.strip())

    return {
        "total_queries": total,
        "answered": len(answered),
        "refused": len(refused),
        "guardrail_blocks": len(guardrail),
        "answer_rate": rate(len(answered)),
        "refusal_rate": rate(len(refused)),
        "grounded_rate": rate(len(grounded)),
        "avg_citations": round(sum(e.citation_count for e in answered) / len(answered), 2) if answered else 0.0,
        "knowledge_gaps": gaps[:20],
        "by_topic": dict(Counter(classify_topic(e.question) for e in entries).most_common()),
        "by_answer_path": dict(Counter(e.answer_path for e in entries).most_common()),
        "by_channel": _by_channel(entries),
    }


def _by_channel(entries: list[UsageEntry]) -> dict:
    """Each channel's share of the totals above: written answers and Tibi's turns, counted once each (REF S20)."""
    out = {}
    for channel, count in Counter(e.channel for e in entries).most_common():
        rows = [e for e in entries if e.channel == channel]
        answered = sum(1 for e in rows if not e.refused)
        out[channel] = {
            "queries": count,
            "answered": answered,
            "refused": count - answered,
            "answer_rate": round(answered / count, 3),
            "refusal_rate": round((count - answered) / count, 3),
        }
    return out
