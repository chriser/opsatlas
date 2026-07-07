"""Recurring question analytics over the usage log."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import datetime

from .classify import classify_topic
from .log import UsageEntry

_STOPWORDS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "can",
    "do",
    "does",
    "for",
    "how",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "this",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
}


def build_recurring_questions(entries: list[UsageEntry], *, min_count: int = 2, similarity_threshold: float = 0.45) -> dict:
    candidates = [_question_candidate(entry, index) for index, entry in enumerate(entries) if entry.question.strip()]
    groups: list[list[dict]] = []
    for candidate in candidates:
        match = _best_group(candidate, groups, similarity_threshold)
        if match is None:
            groups.append([candidate])
        else:
            match.append(candidate)

    recurring_groups = [_group_row(group) for group in groups if len(group) >= min_count]
    recurring_groups.sort(key=lambda row: (-row["demand_frequency"], row["representative_question"]))
    return {
        "group_count": len(recurring_groups),
        "total_recurring_questions": sum(row["demand_frequency"] for row in recurring_groups),
        "min_count": min_count,
        "similarity_threshold": similarity_threshold,
        "groups": recurring_groups,
        "rubric": {
            "normalisation": "Lowercase tokenisation, light stemming and stopword removal.",
            "grouping": "Greedy lexical Jaccard grouping; deterministic and reviewable.",
            "trend": "Compares early and recent occurrence counts inside each group.",
        },
    }


def _question_candidate(entry: UsageEntry, index: int) -> dict:
    tokens = _tokens(entry.question)
    return {
        "index": index,
        "timestamp": entry.timestamp,
        "question": entry.question.strip(),
        "topic": classify_topic(entry.question),
        "tokens": tokens,
        "token_key": " ".join(sorted(tokens)),
        "refused": entry.refused,
        "confidence": entry.confidence,
        "answer_path": entry.answer_path,
    }


def _best_group(candidate: dict, groups: list[list[dict]], threshold: float) -> list[dict] | None:
    best_group = None
    best_score = 0.0
    for group in groups:
        score = max(_similarity(candidate["tokens"], item["tokens"]) for item in group)
        if score > best_score:
            best_score = score
            best_group = group
    return best_group if best_score >= threshold else None


def _group_row(group: list[dict]) -> dict:
    ordered = sorted(group, key=lambda item: (item["timestamp"], item["index"]))
    representative = _representative_question(ordered)
    topic_counts = Counter(item["topic"] for item in ordered)
    token_counts = Counter(token for item in ordered for token in item["tokens"])
    dates = [item["timestamp"][:10] for item in ordered if item["timestamp"]]
    return {
        "id": _group_id(ordered),
        "representative_question": representative,
        "demand_frequency": len(ordered),
        "first_seen": min(dates) if dates else "",
        "last_seen": max(dates) if dates else "",
        "trend": _trend(ordered),
        "topic": topic_counts.most_common(1)[0][0] if topic_counts else "general",
        "terms": [token for token, _ in token_counts.most_common(8)],
        "refusal_count": sum(1 for item in ordered if item["refused"]),
        "low_grounding_count": sum(1 for item in ordered if item["confidence"] not in {"grounded", "high"}),
        "answer_paths": dict(Counter(item["answer_path"] for item in ordered)),
        "questions": [item["question"] for item in ordered[:6]],
    }


def _representative_question(group: list[dict]) -> str:
    token_counts = Counter(token for item in group for token in item["tokens"])

    def score(item: dict) -> tuple[int, int]:
        return (sum(token_counts[token] for token in item["tokens"]), -len(item["question"]))

    return max(group, key=score)["question"]


def _trend(group: list[dict]) -> str:
    dated = [item for item in group if item["timestamp"]]
    if len(dated) < 3:
        return "steady"
    ordered = sorted(dated, key=lambda item: _parse_dt(item["timestamp"]))
    midpoint = len(ordered) // 2
    early = len(ordered[:midpoint])
    recent = len(ordered[midpoint:])
    if recent >= early + 2:
        return "rising"
    if early >= recent + 2:
        return "falling"
    return "steady"


def _tokens(text: str) -> set[str]:
    return {
        _stem(token)
        for token in re.findall(r"[a-z0-9]{3,}", text.lower())
        if token not in _STOPWORDS
    }


def _stem(token: str) -> str:
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) >= len(suffix) + 3:
            return token[: -len(suffix)]
    return token


def _similarity(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _group_id(group: list[dict]) -> str:
    digest = hashlib.sha1("|".join(item["token_key"] for item in group).encode()).hexdigest()[:10]
    return f"recurring-{digest}"


def _parse_dt(timestamp: str) -> datetime:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
