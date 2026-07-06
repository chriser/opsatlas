"""Deterministic routing for ontology-first answers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from .query import OntologyQueryService

QuestionClass = Literal["structured", "narrative", "mixed", "unknown"]

_NARRATIVE_RE = re.compile(r"\b(why|how|explain|describe|walk me through|summari[sz]e)\b", re.IGNORECASE)
_STRUCTURED_RE = re.compile(r"\b(who|which|what|list|show|how many|count)\b", re.IGNORECASE)
_UNSUPPORTED_LOOKUP_RE = re.compile(
    r"\b(named employee|companies house|next year|future|commercially select|recommend a supplier)\b",
    re.IGNORECASE,
)
_ROLE_LOOKUP_PREFIX_RE = re.compile(
    r"^\s*who\s+(owns?|is responsible)\b",
    re.IGNORECASE,
)
_PROCESS_ROLE_RE = re.compile(r"\b(role|roles|owner|owners|owns|responsible)\b", re.IGNORECASE)
_AGGREGATE_RE = re.compile(r"^\s*(list|show)\b|\b(examples|which .+s|what .+s)\b", re.IGNORECASE)


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
    has_narrative = bool(_NARRATIVE_RE.search(text))
    has_structured = bool(_STRUCTURED_RE.search(text))
    if has_narrative and has_structured:
        return "mixed"
    if has_narrative:
        return "narrative"
    if has_structured:
        return "structured"
    return "unknown"


def is_unsupported_lookup(question: str) -> bool:
    """Return true when the question asks for facts the approved corpus cannot know."""

    return bool(_UNSUPPORTED_LOOKUP_RE.search(question.lower()))


def build_structured_answer_plan(question: str, query: OntologyQueryService) -> OntologyAnswerPlan | None:
    """Resolve a structured question into object-only evidence."""

    lower = question.lower()
    if is_unsupported_lookup(question):
        return None

    if (
        _ROLE_LOOKUP_PREFIX_RE.search(lower)
        or "which roles" in lower
        or "what roles" in lower
        or "owner" in lower
    ):
        process = _best_object(query, "process", question)
        if process is None:
            return None
        if not _is_process_level_role_question(question, process):
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

    if is_unsupported_lookup(question):
        return None
    evidence = _matching_process_evidence_items(question, query, limit=1)
    if not evidence:
        return None
    return evidence[0]


def matching_ontology_evidence(question: str, query: OntologyQueryService) -> list[dict[str, Any]]:
    """Return ontology snippets that can safely augment normal RAG evidence.

    Mixed questions often ask for one structured fact plus one explanatory answer.
    The structured plan alone is too narrow, while process evidence alone can omit
    the exact role/control object. Combining both keeps the model grounded without
    changing the answer mode to pure OAG.
    """

    if is_unsupported_lookup(question):
        return []
    evidence: list[dict[str, Any]] = []
    structured_plan = build_structured_answer_plan(question, query)
    if structured_plan is not None:
        evidence.extend(structured_plan.evidence)
    process_limit = 3 if _AGGREGATE_RE.search(question) else 1
    evidence.extend(_matching_process_evidence_items(question, query, limit=process_limit))
    return _dedupe_evidence(evidence)


def _is_process_level_role_question(question: str, process: dict[str, Any]) -> bool:
    """Keep pure OAG role answers for process ownership, not action ownership.

    The current ontology stores process-to-role membership, but not yet the
    action-level responsibility matrix. Questions like "Who owns Supplier Setup?"
    can be answered from that graph. Questions like "Who owns supplier-side
    ordering days?" need the original document wording as well, so they should
    fall through to RAG+ontology.
    """

    if "which roles" in question.lower() or "what roles" in question.lower():
        return True
    question_tokens = _tokens(question)
    name_tokens = _tokens(str(process.get("properties", {}).get("name") or process.get("primary_key_value") or ""))
    meaningful_name_tokens = {token for token in name_tokens if len(token) > 2}
    if meaningful_name_tokens and meaningful_name_tokens <= question_tokens:
        return True
    return bool(_PROCESS_ROLE_RE.search(question) and "process" in question_tokens)


def _best_object(query: OntologyQueryService, object_type: str, question: str) -> dict[str, Any] | None:
    ranked = _ranked_objects(query, object_type, question)
    return ranked[0] if ranked else None


def _matching_process_evidence_items(
    question: str,
    query: OntologyQueryService,
    *,
    limit: int,
) -> list[dict[str, Any]]:
    if is_unsupported_lookup(question):
        return []
    evidence: list[dict[str, Any]] = []
    for process in _ranked_objects(query, "process", question)[:limit]:
        detail = query.get_object(process["id"]) or process
        roles = _neighbor_objects(detail, "process_has_role", "out")
        systems = _neighbor_objects(detail, "process_uses_system", "out")
        controls = _neighbor_objects(detail, "process_enforced_by", "out")
        evidence.append(_evidence(detail, _process_summary(detail, roles=roles, systems=systems, controls=controls)))
    return evidence


def _ranked_objects(query: OntologyQueryService, object_type: str, question: str) -> list[dict[str, Any]]:
    candidates = query.find_objects(object_type)
    question_tokens = _tokens(question)
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for candidate in candidates:
        score = len(question_tokens & _tokens(_object_search_text(candidate)))
        if score >= 1:
            scored.append((score, _label(candidate), candidate))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [candidate for _, _, candidate in scored]


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


def _dedupe_evidence(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        key = (str(item.get("source_id", "")), str(item.get("heading", "")))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


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
