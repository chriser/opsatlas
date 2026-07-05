"""Deterministic routing for ontology-first answers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from .query import OntologyQueryService

QuestionClass = Literal["structured", "narrative", "unknown"]

_NARRATIVE_RE = re.compile(r"\b(why|how|explain|describe|walk me through|summari[sz]e)\b", re.IGNORECASE)
_STRUCTURED_RE = re.compile(r"\b(who|which|what|list|show|how many|count)\b", re.IGNORECASE)


@dataclass(frozen=True)
class OntologyAnswerPlan:
    intent: str
    evidence: list[dict[str, Any]]


def classify_question(question: str, schema: dict[str, Any] | None = None) -> QuestionClass:
    """Classify the question without using an LLM."""

    del schema
    text = question.strip()
    if not text:
        return "unknown"
    if _NARRATIVE_RE.search(text):
        return "narrative"
    if _STRUCTURED_RE.search(text):
        return "structured"
    return "unknown"


def build_structured_answer_plan(question: str, query: OntologyQueryService) -> OntologyAnswerPlan | None:
    """Resolve a structured question into object-only evidence."""

    lower = question.lower()
    if any(term in lower for term in ("who owns", "who is responsible", "which roles", "what roles", "owner")):
        process = _best_object(query, "process", question)
        if process is None:
            return None
        process = query.get_object(process["id"]) or process
        roles = _neighbor_objects(process, "process_has_role", "out")
        if not roles:
            return None
        return OntologyAnswerPlan(
            intent="process_roles",
            evidence=[
                _evidence(process, _process_summary(process, roles=roles)),
                *[_evidence(role, _object_summary(role)) for role in roles],
            ],
        )

    if "process" in lower and any(term in lower for term in ("use", "uses", "using", "touch", "touches")):
        system = _best_object(query, "system", question)
        if system is None:
            return None
        processes = _linked_objects(query, system["id"], "process_uses_system", "in")
        if not processes:
            return None
        return OntologyAnswerPlan(
            intent="system_processes",
            evidence=[
                _evidence(system, _system_summary(system, processes=processes)),
                *[_evidence(process, _object_summary(process)) for process in processes],
            ],
        )

    if any(term in lower for term in ("what systems", "which systems", "systems used")):
        process = _best_object(query, "process", question)
        if process is None:
            return None
        process = query.get_object(process["id"]) or process
        systems = _neighbor_objects(process, "process_uses_system", "out")
        if not systems:
            return None
        return OntologyAnswerPlan(
            intent="process_systems",
            evidence=[
                _evidence(process, _process_summary(process, systems=systems)),
                *[_evidence(system, _object_summary(system)) for system in systems],
            ],
        )

    if any(term in lower for term in ("what controls", "which controls", "controls apply", "govern")):
        process = _best_object(query, "process", question)
        if process is None:
            return None
        process = query.get_object(process["id"]) or process
        controls = _neighbor_objects(process, "process_enforced_by", "out")
        if not controls:
            return None
        return OntologyAnswerPlan(
            intent="process_controls",
            evidence=[
                _evidence(process, _process_summary(process, controls=controls)),
                *[_evidence(control, _object_summary(control)) for control in controls],
            ],
        )

    return None


def matching_process_evidence(question: str, query: OntologyQueryService) -> dict[str, Any] | None:
    """Return one compact ontology process evidence item for RAG+ontology fallback."""

    process = _best_object(query, "process", question)
    if process is None:
        return None
    detail = query.get_object(process["id"]) or process
    roles = _neighbor_objects(detail, "process_has_role", "out")
    systems = _neighbor_objects(detail, "process_uses_system", "out")
    controls = _neighbor_objects(detail, "process_enforced_by", "out")
    return _evidence(detail, _process_summary(detail, roles=roles, systems=systems, controls=controls))


def _best_object(query: OntologyQueryService, object_type: str, question: str) -> dict[str, Any] | None:
    candidates = query.find_objects(object_type)
    question_tokens = _tokens(question)
    best: dict[str, Any] | None = None
    best_score = 0
    for candidate in candidates:
        score = len(question_tokens & _tokens(_object_search_text(candidate)))
        if score > best_score:
            best = candidate
            best_score = score
    return best if best_score >= 1 else None


def _neighbor_objects(item: dict[str, Any], link_type: str, direction: Literal["out", "in"]) -> list[dict[str, Any]]:
    neighbors = item.get("neighbors")
    if not isinstance(neighbors, dict):
        return []
    grouped = neighbors.get(link_type)
    if not isinstance(grouped, dict):
        return []
    values = grouped.get(direction)
    return values if isinstance(values, list) else []


def _linked_objects(
    query: OntologyQueryService,
    object_id: str,
    link_type: str,
    direction: Literal["out", "in"],
) -> list[dict[str, Any]]:
    return query.traverse(object_id, link_type, direction=direction)


def _evidence(item: dict[str, Any], text: str) -> dict[str, Any]:
    return {
        "source_id": item["id"],
        "source_title": item["citation"],
        "heading": item["object_type"],
        "ordinal": 0,
        "text": text,
        "citation_type": "ontology_object",
    }


def _process_summary(
    process: dict[str, Any],
    *,
    roles: list[dict[str, Any]] | None = None,
    systems: list[dict[str, Any]] | None = None,
    controls: list[dict[str, Any]] | None = None,
) -> str:
    props = process["properties"]
    parts = [f"Process: {props.get('name', process['primary_key_value'])}."]
    if props.get("domain"):
        parts.append(f"Domain: {props['domain']}.")
    if roles:
        parts.append("Roles/owners: " + "; ".join(_label(item) for item in roles) + ".")
    if systems:
        parts.append("Systems: " + "; ".join(_label(item) for item in systems) + ".")
    if controls:
        parts.append("Controls: " + "; ".join(_label(item) for item in controls) + ".")
    if props.get("capabilities"):
        parts.append("Capabilities: " + "; ".join(props["capabilities"]) + ".")
    if props.get("business_rules"):
        parts.append("Business rules: " + " ".join(props["business_rules"]))
    return " ".join(parts)


def _system_summary(system: dict[str, Any], *, processes: list[dict[str, Any]]) -> str:
    return f"System: {_label(system)}. Processes using this system: {'; '.join(_label(item) for item in processes)}."


def _object_summary(item: dict[str, Any]) -> str:
    return f"{item['citation']}. Properties: {_property_summary(item.get('properties', {}))}."


def _property_summary(properties: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in properties.items():
        if value in ("", None, []):
            continue
        if isinstance(value, list):
            parts.append(f"{key}={'; '.join(str(item) for item in value)}")
        else:
            parts.append(f"{key}={value}")
    return ", ".join(parts)


def _object_search_text(item: dict[str, Any]) -> str:
    values = [item.get("primary_key_value", ""), item.get("citation", "")]
    for value in item.get("properties", {}).values():
        if isinstance(value, list):
            values.extend(str(child) for child in value)
        else:
            values.append(str(value))
    return " ".join(values)


def _label(item: dict[str, Any]) -> str:
    properties = item.get("properties", {})
    return str(properties.get("name") or properties.get("title") or item.get("primary_key_value") or item["id"])


def _tokens(text: str) -> set[str]:
    return {_normalise_token(token) for token in re.findall(r"[a-z0-9]+", text.lower())}


def _normalise_token(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]
    return token
