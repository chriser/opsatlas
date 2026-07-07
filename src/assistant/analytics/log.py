"""Usage log and scorecard.

Records every assistant query and derives quality metrics and knowledge gaps
(questions the assistant could not answer from approved knowledge).
"""

from __future__ import annotations

import json
import threading
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from .classify import classify_topic


class UsageEntry(BaseModel):
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
    confidence: str = "none"
    citation_count: int = 0


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class UsageLog:
    def __init__(self, base_dir: str | Path) -> None:
        self.path = Path(base_dir) / "usage_log.json"
        self._lock = threading.Lock()

    def _read(self) -> list[dict]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text() or "[]")

    def append(self, entry: UsageEntry) -> None:
        with self._lock:
            rows = self._read()
            rows.append(entry.model_dump())
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(rows, indent=2))

    def entries(self) -> list[UsageEntry]:
        return [UsageEntry(**r) for r in self._read()]


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
        if e.refused and not e.category and key and key not in seen:
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
    }
