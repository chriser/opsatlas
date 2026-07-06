"""Knowledge-gap clustering and onboarding-friction analytics."""

from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict

from .classify import classify_topic
from .log import UsageEntry
from .methods import KNOWLEDGE_GAP_CANDIDATE_RULE, KNOWLEDGE_GAP_QUALITY_RULE

_STOPWORDS = {
    "a", "about", "an", "and", "are", "can", "do", "does", "for", "how", "i", "in", "is", "it",
    "of", "on", "or", "the", "this", "to", "what", "when", "where", "which", "who", "why",
}
_TOPIC_LABELS = {
    "checks": "Control and approval gaps",
    "finance_mapping": "Finance mapping gaps",
    "validation": "Validation and handover gaps",
    "open_decisions": "Decision-rationale gaps",
    "roles": "Role and ownership gaps",
    "onboarding": "Onboarding process gaps",
    "general": "General knowledge gaps",
}
_PROCESS_BY_TOPIC = {
    "checks": "Supplier setup controls",
    "finance_mapping": "Supplier finance mapping",
    "validation": "Supplier setup validation",
    "open_decisions": "Process design decisions",
    "roles": "Process ownership",
    "onboarding": "Supplier onboarding",
}


def build_gap_clusters(entries: list[UsageEntry]) -> dict:
    candidates = [_candidate(entry, index) for index, entry in enumerate(entries) if _is_gap_candidate(entry)]
    grouped: dict[str, list[dict]] = defaultdict(list)
    for candidate in candidates:
        grouped[candidate["topic"]].append(candidate)

    clusters = []
    for topic, rows in sorted(grouped.items()):
        term_counts = Counter(term for row in rows for term in row["tokens"])
        representative_questions = [row["question"] for row in sorted(rows, key=lambda item: item["timestamp"])[:3]]
        friction_score = _friction_score(rows)
        clusters.append({
            "id": _cluster_id(topic, rows),
            "label": _TOPIC_LABELS.get(topic, _TOPIC_LABELS["general"]),
            "topic": topic,
            "process_area": _PROCESS_BY_TOPIC.get(topic, "General knowledge"),
            "source_gap": _source_gap(rows),
            "question_count": len(rows),
            "representative_questions": representative_questions,
            "terms": [term for term, _ in term_counts.most_common(6)],
            "friction_score": friction_score,
            "confidence": "high" if len(rows) >= 3 else "review",
        })

    return {
        "total_candidates": len(candidates),
        "cluster_count": len(clusters),
        "silhouette_score": round(_silhouette_score(candidates), 3),
        "clusters": sorted(clusters, key=lambda item: (-item["friction_score"], item["label"])),
        "rubric": {
            "candidate_rule": KNOWLEDGE_GAP_CANDIDATE_RULE,
            "quality_rule": KNOWLEDGE_GAP_QUALITY_RULE,
        },
    }


def _is_gap_candidate(entry: UsageEntry) -> bool:
    if entry.refused and not entry.category:
        return True
    return not entry.refused and entry.confidence not in {"grounded", "high"}


def _candidate(entry: UsageEntry, index: int) -> dict:
    topic = classify_topic(entry.question)
    return {
        "index": index,
        "timestamp": entry.timestamp,
        "question": entry.question.strip(),
        "topic": topic,
        "tokens": _tokens(entry.question),
        "kind": "coverage_gap" if entry.refused else "weak_evidence",
    }


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]{3,}", text.lower())
        if token not in _STOPWORDS
    }


def _friction_score(rows: list[dict]) -> int:
    coverage_gaps = sum(1 for row in rows if row["kind"] == "coverage_gap")
    weak_evidence = len(rows) - coverage_gaps
    return min(100, coverage_gaps * 25 + weak_evidence * 15 + max(0, len(rows) - 1) * 5)


def _source_gap(rows: list[dict]) -> str:
    if any(row["kind"] == "coverage_gap" for row in rows):
        return "No approved source answered at least one representative question in this cluster."
    return "The assistant answered, but confidence was weak enough to warrant stronger source coverage."


def _cluster_id(topic: str, rows: list[dict]) -> str:
    digest = hashlib.sha1("|".join(str(row["index"]) for row in rows).encode()).hexdigest()[:10]
    return f"{topic}-{digest}"


def _silhouette_score(candidates: list[dict]) -> float:
    topics = {candidate["topic"] for candidate in candidates}
    if len(candidates) < 3 or len(topics) < 2:
        return 0.0

    scores = []
    for candidate in candidates:
        same = [other for other in candidates if other["topic"] == candidate["topic"] and other["index"] != candidate["index"]]
        other_topics = sorted(topics - {candidate["topic"]})
        a = _average_distance(candidate, same) if same else 0.0
        b = min(_average_distance(candidate, [other for other in candidates if other["topic"] == topic]) for topic in other_topics)
        scores.append((b - a) / max(a, b) if max(a, b) else 0.0)
    return sum(scores) / len(scores)


def _average_distance(candidate: dict, others: list[dict]) -> float:
    if not others:
        return 0.0
    return sum(_token_distance(candidate["tokens"], other["tokens"]) for other in others) / len(others)


def _token_distance(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    return 1 - (len(left & right) / len(left | right))
