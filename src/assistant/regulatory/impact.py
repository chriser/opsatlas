"""Regulatory change-impact simulation over approved knowledge sources."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict

from ..external.registry import PublicContentRegistry
from ..ingestion.sections import Section
from ..ingestion.store import SectionStore
from ..sources.models import SourceRecord
from ..sources.register import SourceRegister
from .discovery import discover_regulatory_candidates
from .review import RegulatoryReviewStore


class ImpactPassage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    heading: str
    ordinal: int
    excerpt: str
    matched_terms: list[str]


class AffectedSourceImpact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_title: str
    impact_score: int
    impact_band: str
    matched_terms: list[str]
    process_areas: list[str]
    passages: list[ImpactPassage]
    recommended_action: str


class RegulatoryImpactSimulation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    theme: str
    label: str
    source_id: str
    source_title: str
    review_status: str
    simulated_at: str
    impact_score: int
    impact_band: str
    affected_source_count: int
    affected_process_areas: list[str]
    external_context_count: int
    external_context: list[dict]
    affected_sources: list[AffectedSourceImpact]
    recommended_actions: list[str]
    assumptions: list[str]


def simulate_regulatory_impact(
    register: SourceRegister,
    section_store: SectionStore,
    review_store: RegulatoryReviewStore,
    public_registry: PublicContentRegistry | None,
    candidate_id: str,
) -> RegulatoryImpactSimulation:
    discovery = discover_regulatory_candidates(register, section_store, review_store, public_registry)
    candidate = next((item for item in discovery["candidates"] if item["id"] == candidate_id), None)
    if candidate is None:
        raise ValueError(f"Regulatory candidate {candidate_id} was not found.")

    terms = list(dict.fromkeys(candidate["matched_terms"]))
    affected_sources = _affected_sources(register, section_store, candidate, terms)
    external_context = candidate.get("external_matches", [])
    impact_score = _overall_score(candidate["score"], affected_sources, len(external_context), candidate["review_status"])
    process_areas = sorted({area for source in affected_sources for area in source.process_areas})
    return RegulatoryImpactSimulation(
        candidate_id=candidate["id"],
        theme=candidate["theme"],
        label=candidate["label"],
        source_id=candidate["source_id"],
        source_title=candidate["source_title"],
        review_status=candidate["review_status"],
        simulated_at=datetime.now(timezone.utc).isoformat(),
        impact_score=impact_score,
        impact_band=_band(impact_score),
        affected_source_count=len(affected_sources),
        affected_process_areas=process_areas,
        external_context_count=len(external_context),
        external_context=external_context,
        affected_sources=affected_sources,
        recommended_actions=_recommended_actions(candidate, affected_sources, external_context),
        assumptions=[
            "Simulation is deterministic triage from approved ingested sources and public snapshot text.",
            "Matched terms indicate candidate impact only; they do not prove a regulatory obligation changed.",
            "Human review is required before source edits, operating-process changes or compliance conclusions.",
        ],
    )


def _affected_sources(
    register: SourceRegister,
    section_store: SectionStore,
    candidate: dict,
    terms: list[str],
) -> list[AffectedSourceImpact]:
    impacts: list[AffectedSourceImpact] = []
    approved_sources = [source for source in register.list() if source.approval_status == "approved"]
    for source in approved_sources:
        passages = _matching_passages(source, section_store.list_for_source(source.id), terms)
        if not passages and source.id != candidate["source_id"]:
            continue
        if not passages:
            passages = [
                ImpactPassage(
                    heading=passage["heading"],
                    ordinal=passage["ordinal"],
                    excerpt=passage["excerpt"],
                    matched_terms=passage["matched_terms"],
                )
                for passage in candidate.get("passages", [])
            ]
        matched_terms = sorted({term for passage in passages for term in passage.matched_terms})
        process_areas = _process_areas(candidate["theme"], passages)
        score = _source_score(candidate["score"], source.id == candidate["source_id"], passages, matched_terms)
        impacts.append(
            AffectedSourceImpact(
                source_id=source.id,
                source_title=source.title,
                impact_score=score,
                impact_band=_band(score),
                matched_terms=matched_terms,
                process_areas=process_areas,
                passages=passages[:3],
                recommended_action=_source_action(candidate["label"], source, process_areas),
            )
        )
    return sorted(impacts, key=lambda item: (-item.impact_score, item.source_title))


def _matching_passages(source: SourceRecord, sections: list[Section], terms: list[str]) -> list[ImpactPassage]:
    passages = []
    for section in sections:
        text = f"{section.heading}\n{section.text}"
        matched = _matched_terms(text, terms)
        if not matched:
            continue
        passages.append(
            ImpactPassage(
                heading=section.heading,
                ordinal=section.ordinal,
                excerpt=_excerpt(section.text, matched),
                matched_terms=matched,
            )
        )
    return passages


def _matched_terms(text: str, terms: list[str]) -> list[str]:
    lowered = text.lower()
    found = []
    for term in terms:
        if re.search(rf"(?<!\w){re.escape(term.lower())}(?!\w)", lowered):
            found.append(term)
    return found


def _excerpt(text: str, terms: list[str], max_chars: int = 280) -> str:
    clean = " ".join(text.split())
    lowered = clean.lower()
    positions = [lowered.find(term.lower()) for term in terms if lowered.find(term.lower()) >= 0]
    start = max(0, min(positions) - 70) if positions else 0
    excerpt = clean[start : start + max_chars].strip()
    if start > 0:
        excerpt = f"...{excerpt}"
    if start + max_chars < len(clean):
        excerpt = f"{excerpt}..."
    return excerpt


def _process_areas(theme: str, passages: list[ImpactPassage]) -> list[str]:
    theme_area = {
        "data_privacy": "Data privacy controls",
        "financial_tax": "Tax and finance controls",
        "health_safety": "Health and safety controls",
        "employment": "People and employment controls",
        "accessibility": "Accessibility and inclusion controls",
        "procurement": "Procurement and supplier controls",
    }.get(theme, "Regulatory controls")
    headings = {passage.heading.strip() for passage in passages if passage.heading.strip()}
    return sorted({theme_area, *list(headings)})[:5]


def _source_score(candidate_score: int, is_origin: bool, passages: list[ImpactPassage], terms: list[str]) -> int:
    score = int(candidate_score * 0.45) + len(passages) * 16 + len(terms) * 10
    if is_origin:
        score += 15
    return min(100, score)


def _overall_score(candidate_score: int, sources: list[AffectedSourceImpact], external_count: int, review_status: str) -> int:
    score = int(candidate_score * 0.5) + len(sources) * 12 + external_count * 8
    if sources:
        score += max(source.impact_score for source in sources) // 5
    if review_status == "relevant":
        score += 8
    elif review_status == "needs_research":
        score += 4
    elif review_status == "irrelevant":
        score -= 20
    return max(0, min(100, score))


def _band(score: int) -> str:
    if score >= 75:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


def _source_action(label: str, source: SourceRecord, process_areas: list[str]) -> str:
    primary_area = process_areas[0] if process_areas else "the affected process area"
    return f"Review {source.title} for {label.lower()} wording before relying on {primary_area.lower()} guidance."


def _recommended_actions(candidate: dict, affected_sources: list[AffectedSourceImpact], external_context: list[dict]) -> list[str]:
    actions = [
        f"Review {len(affected_sources)} affected approved source(s) before changing assistant-approved guidance.",
        "Keep the candidate in needs research until authoritative guidance has been checked by a human reviewer.",
    ]
    if external_context:
        actions.append("Compare affected source wording against the linked GOV.UK snapshot versions before editing knowledge packs.")
    else:
        actions.append("Add or refresh a GOV.UK snapshot for this theme before treating the impact as externally substantiated.")
    if candidate.get("review_status") == "relevant":
        actions.append("Prioritise a source update or validation note because the candidate has already been marked relevant.")
    return actions
