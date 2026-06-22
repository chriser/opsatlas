"""Deterministic regulatory candidate discovery from approved knowledge sections."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict

from pydantic import BaseModel

from ..external.registry import PublicContentRegistry
from ..ingestion.sections import Section
from ..ingestion.store import SectionStore
from ..sources.models import SourceRecord
from ..sources.register import SourceRegister
from .review import RegulatoryReviewStore
from .taxonomy import THEMES, RegulatoryTheme


class CandidatePassage(BaseModel):
    source_id: str
    source_title: str
    heading: str
    ordinal: int
    excerpt: str
    matched_terms: list[str]


class ExternalContextMatch(BaseModel):
    title: str
    url: str
    version: int
    update_date: str = ""
    matched_terms: list[str]


class RegulatoryCandidate(BaseModel):
    id: str
    theme: str
    label: str
    source_id: str
    source_title: str
    confidence: str
    score: int
    reason: str
    matched_terms: list[str]
    passages: list[CandidatePassage]
    external_matches: list[ExternalContextMatch] = []
    review_status: str = "unreviewed"
    review_note: str = ""
    reviewed_at: str = ""


def candidate_id(source_id: str, theme_id: str) -> str:
    return hashlib.sha256(f"{source_id}|{theme_id}".encode()).hexdigest()[:18]


def discover_regulatory_candidates(
    register: SourceRegister,
    section_store: SectionStore,
    review_store: RegulatoryReviewStore,
    public_registry: PublicContentRegistry | None = None,
) -> dict:
    candidates: list[RegulatoryCandidate] = []
    approved_sources = [source for source in register.list() if source.approval_status == "approved"]
    for source in approved_sources:
        sections = section_store.list_for_source(source.id)
        candidates.extend(_candidates_for_source(source, sections, review_store, public_registry))
    candidates.sort(key=lambda candidate: (-candidate.score, candidate.source_title, candidate.label))
    return {
        "candidate_count": len(candidates),
        "review_counts": _review_counts(candidates),
        "taxonomy": [{"id": theme.id, "label": theme.label, "terms": theme.terms} for theme in THEMES],
        "candidates": [candidate.model_dump() for candidate in candidates],
    }


def _candidates_for_source(
    source: SourceRecord,
    sections: list[Section],
    review_store: RegulatoryReviewStore,
    public_registry: PublicContentRegistry | None,
) -> list[RegulatoryCandidate]:
    by_theme: dict[str, list[CandidatePassage]] = defaultdict(list)
    term_sets: dict[str, set[str]] = defaultdict(set)
    for section in sections:
        text = f"{section.heading}\n{section.text}"
        for theme in THEMES:
            terms = _matched_terms(text, theme.terms)
            if terms:
                by_theme[theme.id].append(_passage(source, section, terms))
                term_sets[theme.id].update(terms)

    candidates = []
    for theme in THEMES:
        passages = by_theme.get(theme.id, [])
        if not passages:
            continue
        terms = sorted(term_sets[theme.id])
        score = _score(passages, terms)
        cid = candidate_id(source.id, theme.id)
        review = review_store.get(cid)
        candidates.append(
            RegulatoryCandidate(
                id=cid,
                theme=theme.id,
                label=theme.label,
                source_id=source.id,
                source_title=source.title,
                confidence=_confidence(score),
                score=score,
                reason=_reason(theme, terms),
                matched_terms=terms,
                passages=passages[:4],
                external_matches=_external_matches(theme, terms, public_registry),
                review_status=review.status,
                review_note=review.note,
                reviewed_at=review.reviewed_at,
            )
        )
    return candidates


def _matched_terms(text: str, terms: list[str]) -> list[str]:
    found = []
    lowered = text.lower()
    for term in terms:
        pattern = rf"(?<!\w){re.escape(term.lower())}(?!\w)"
        if re.search(pattern, lowered):
            found.append(term)
    return found


def _passage(source: SourceRecord, section: Section, terms: list[str]) -> CandidatePassage:
    return CandidatePassage(
        source_id=source.id,
        source_title=source.title,
        heading=section.heading,
        ordinal=section.ordinal,
        excerpt=_excerpt(section.text, terms),
        matched_terms=terms,
    )


def _excerpt(text: str, terms: list[str], max_chars: int = 320) -> str:
    clean = " ".join(text.split())
    start = 0
    lowered = clean.lower()
    positions = [lowered.find(term.lower()) for term in terms if lowered.find(term.lower()) >= 0]
    if positions:
        start = max(0, min(positions) - 80)
    excerpt = clean[start : start + max_chars].strip()
    if start > 0:
        excerpt = f"...{excerpt}"
    if start + max_chars < len(clean):
        excerpt = f"{excerpt}..."
    return excerpt


def _score(passages: list[CandidatePassage], terms: list[str]) -> int:
    return min(100, len(passages) * 18 + len(terms) * 12)


def _confidence(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _reason(theme: RegulatoryTheme, terms: list[str]) -> str:
    return f"Candidate only: approved knowledge {theme.reason_template}. Matched terms: {', '.join(terms)}."


def _external_matches(
    theme: RegulatoryTheme,
    terms: list[str],
    public_registry: PublicContentRegistry | None,
) -> list[ExternalContextMatch]:
    if public_registry is None:
        return []
    matches: list[ExternalContextMatch] = []
    for snapshot in public_registry.list_snapshots(include_text=True):
        haystack = f"{snapshot.title}\n{snapshot.text}".lower()
        matched = [term for term in set(theme.terms + terms) if re.search(rf"(?<!\w){re.escape(term.lower())}(?!\w)", haystack)]
        if matched:
            matches.append(
                ExternalContextMatch(
                    title=snapshot.title,
                    url=snapshot.url,
                    version=snapshot.version,
                    update_date=snapshot.update_date,
                    matched_terms=sorted(matched),
                )
            )
    return matches[:3]


def _review_counts(candidates: list[RegulatoryCandidate]) -> dict[str, int]:
    counts = {"unreviewed": 0, "relevant": 0, "irrelevant": 0, "needs_research": 0}
    for candidate in candidates:
        counts[candidate.review_status] = counts.get(candidate.review_status, 0) + 1
    return counts
