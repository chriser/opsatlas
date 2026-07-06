"""Populate the ontology graph from existing platform stores."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from ..compliance.latest import ComplianceLatestReviewStore
from ..process.registry import ProcessRegistry
from ..sources.models import SourceRecord
from ..sources.register import SourceRegister
from .store import OntologyObject, OntologyStore, object_id_for


def rebuild_ontology(
    register: SourceRegister,
    process_registry: ProcessRegistry,
    compliance_latest: ComplianceLatestReviewStore | None,
    store: OntologyStore,
) -> dict[str, Any]:
    """Rebuild ontology objects and links from approved platform state."""

    store.clear()
    source_objects = _sync_sources(register, store)
    process_objects = _sync_processes(register, process_registry, store, source_objects)
    compliance_summary = _sync_compliance(compliance_latest, store, source_objects, process_objects)
    counts = store.counts()
    return {
        "status": "rebuilt",
        "counts": counts,
        "sources": len(source_objects),
        "processes": len(process_objects),
        "compliance": compliance_summary,
    }


def _sync_sources(register: SourceRegister, store: OntologyStore) -> dict[str, OntologyObject]:
    sources: dict[str, OntologyObject] = {}
    for record in register.list():
        sources[record.id] = _upsert_source_from_record(store, record)
    return sources


def _upsert_source_from_record(store: OntologyStore, record: SourceRecord) -> OntologyObject:
    return store.upsert_object(
        "source",
        record.id,
        {
            "title": record.title,
            "filename": record.filename,
            "source_type": record.source_type,
            "approval_status": record.approval_status,
            "content_sha256": record.content_sha256,
            "version": record.version,
        },
        source_ref=f"source_register:{record.id}",
    )


def _sync_processes(
    register: SourceRegister,
    process_registry: ProcessRegistry,
    store: OntologyStore,
    source_objects: dict[str, OntologyObject],
) -> dict[str, OntologyObject]:
    processes: dict[str, OntologyObject] = {}
    for process in process_registry.derive_from_sources(register):
        process_object = store.upsert_object(
            "process",
            process.id,
            {
                "name": process.name,
                "domain": process.domain,
                "capabilities": process.capabilities,
                "business_rules": process.business_rules,
                "key_facts": _extract_process_key_facts(register, process),
            },
            source_ref=f"process_registry:{process.source_id}",
        )
        processes[process.id] = process_object
        source_object = source_objects.get(process.source_id)
        if source_object is not None:
            store.link("process_derived_from", process_object.id, source_object.id)

        for role in process.roles:
            role_object = _upsert_named_object(store, "role", role, source_ref=f"process_registry:{process.id}")
            if role_object is not None:
                store.link("process_has_role", process_object.id, role_object.id)
        for system in process.systems:
            system_object = _upsert_named_object(store, "system", system, source_ref=f"process_registry:{process.id}")
            if system_object is not None:
                store.link("process_uses_system", process_object.id, system_object.id)
        for control in process.controls:
            control_object = _upsert_named_object(store, "control", control, source_ref=f"process_registry:{process.id}")
            if control_object is not None:
                store.link("process_enforced_by", process_object.id, control_object.id)
    return processes


def _sync_compliance(
    compliance_latest: ComplianceLatestReviewStore | None,
    store: OntologyStore,
    source_objects: dict[str, OntologyObject],
    process_objects: dict[str, OntologyObject],
) -> dict[str, int]:
    if compliance_latest is None:
        return {"findings": 0, "obligations": 0, "internal_claims": 0}

    payload = compliance_latest.get()
    findings = [item for item in payload.get("findings", []) if isinstance(item, dict)]
    obligation_count = 0
    claim_count = 0
    finding_count = 0
    for finding in findings:
        finding_id = str(finding.get("id") or finding.get("finding_id") or _stable_hash("finding", finding))
        finding_object = store.upsert_object(
            "compliance_finding",
            finding_id,
            {
                "review_id": _review_id(payload),
                "classification": str(finding.get("classification") or "needs_human_review"),
                "severity": str(finding.get("severity") or ""),
                "status": str(finding.get("status") or "open"),
                "rationale": str(finding.get("rationale") or finding.get("advisor_summary") or ""),
                "alignment_score": _number_or_none(finding.get("alignment_score")),
            },
            source_ref=f"compliance_latest:{_review_id(payload)}",
        )
        finding_count += 1

        obligation = _upsert_evidence_claim(
            store,
            source_objects,
            finding.get("external_evidence"),
            object_type="obligation",
            object_id=str(finding.get("obligation_id") or ""),
            default_prefix="obligation",
            source_link_type="obligation_extracted_from",
        )
        if obligation is not None:
            obligation_count += 1
            store.link("finding_about_obligation", finding_object.id, obligation.id)

        claim = _upsert_evidence_claim(
            store,
            source_objects,
            finding.get("internal_evidence"),
            object_type="internal_claim",
            object_id=str(finding.get("internal_claim_id") or ""),
            default_prefix="claim",
            source_link_type="claim_extracted_from",
        )
        if claim is not None:
            claim_count += 1
            store.link("finding_about_claim", finding_object.id, claim.id)
            evidence = finding.get("internal_evidence")
            if isinstance(evidence, dict):
                process_object = process_objects.get(str(evidence.get("source_id") or ""))
                if process_object is not None:
                    store.link("finding_affects_process", finding_object.id, process_object.id)

    return {"findings": finding_count, "obligations": obligation_count, "internal_claims": claim_count}


def _upsert_evidence_claim(
    store: OntologyStore,
    source_objects: dict[str, OntologyObject],
    evidence: Any,
    *,
    object_type: str,
    object_id: str,
    default_prefix: str,
    source_link_type: str,
) -> OntologyObject | None:
    if not isinstance(evidence, dict):
        return None
    text = str(evidence.get("text") or "").strip()
    if not text:
        return None
    source_id = str(evidence.get("source_id") or "").strip()
    evidence_id = object_id.strip() or _stable_hash(default_prefix, {
        "source_id": source_id,
        "section_id": evidence.get("section_id", ""),
        "text": text,
    })
    source_title = str(evidence.get("source_title") or source_id or "Unknown source")
    claim = store.upsert_object(
        object_type,
        evidence_id,
        {
            f"{'obligation' if object_type == 'obligation' else 'claim'}_id": evidence_id,
            "modality": _modality(text),
            "actor": "",
            "action": text,
            "condition": str(evidence.get("heading") or ""),
            "key_terms": _key_terms(text),
            "source_section": str(evidence.get("section_id") or evidence.get("citation") or ""),
            "source_title": source_title,
        },
        source_ref=f"compliance_latest:{source_id}",
    )
    source_object = source_objects.get(source_id)
    if source_object is None and source_id:
        source_object = _upsert_external_source(store, source_id, evidence)
        source_objects[source_id] = source_object
    if source_object is not None:
        store.link(source_link_type, claim.id, source_object.id)
    return claim


def _upsert_external_source(store: OntologyStore, source_id: str, evidence: dict[str, Any]) -> OntologyObject:
    title = str(evidence.get("source_title") or source_id)
    return store.upsert_object(
        "source",
        source_id,
        {
            "title": title,
            "filename": str(evidence.get("url") or ""),
            "source_type": "external",
            "approval_status": "approved",
            "content_sha256": str(evidence.get("content_sha256") or ""),
        },
        source_ref=f"compliance_latest:{source_id}",
    )


def _extract_process_key_facts(register: SourceRegister, process: Any) -> list[str]:
    """Extract compact fact atoms for OAG evidence packets.

    The process registry intentionally keeps a small process-level model. OAG
    needs more granular evidence for owner/action and aggregate/list questions,
    so the ontology keeps short fact strings derived from approved source
    structure without creating a new object type for every row.
    """

    try:
        text = register.read_content(process.source_id).decode("utf-8", "replace")
    except (FileNotFoundError, KeyError):
        text = ""

    facts: list[str] = []
    for cells in _table_rows(_section(text, "Roles and responsibilities"), min_cells=2):
        role, responsibility = cells[0], cells[1]
        facts.append(f"Role responsibility: {role} - {responsibility}.")

    for cells in _table_rows(_section(text, "Systems and data dependencies"), min_cells=2):
        system, purpose, *rest = cells
        parts = [f"System dependency: {system}.", f"Purpose: {purpose}."]
        if rest:
            parts.append("Details: " + " ".join(item for item in rest if item) + ".")
        facts.append(" ".join(parts))

    for cells in _table_rows(_section(text, "Structured process steps"), min_cells=5):
        if len(cells) < 5:
            continue
        _, activity, role, happens, output, *rest = cells
        fact = f"Process step: {role} performs {activity}. {happens} Output: {output}."
        validation = rest[0] if rest else ""
        if validation and validation.lower() not in {"no", "n/a", "none"}:
            fact += f" Validation: {validation}."
        facts.append(fact)

    for cells in _table_rows(_section(text, "Realistic Q&A pairs"), min_cells=2):
        question, answer = cells[0], cells[1]
        facts.append(f"Q&A fact: {question} {answer}.")

    for rule in getattr(process, "business_rules", []):
        facts.append(f"Business rule: {rule}.")

    for rule in getattr(process, "rules", []):
        role = getattr(rule, "role", "") or "process"
        topic = getattr(rule, "topic", "")
        statement = getattr(rule, "rule", "")
        if statement:
            prefix = f"{role.replace('_', ' ')}"
            if topic:
                prefix += f" / {topic.replace('_', ' ')}"
            facts.append(f"Learning record: {prefix}: {statement}.")

    return _dedupe_fact_strings(facts, limit=48)


def _section(text: str, keyword: str) -> str:
    capturing = False
    buf: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if capturing:
                break
            capturing = keyword.lower() in line.lower()
            continue
        if capturing:
            buf.append(line)
    return "\n".join(buf)


def _table_rows(section: str, *, min_cells: int) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [_clean_cell(cell) for cell in stripped.strip("|").split("|")]
        if len(cells) < min_cells or not any(cells):
            continue
        if all(set(cell) <= set("-: ") for cell in cells if cell):
            continue
        rows.append(cells)
    if rows:
        rows = rows[1:]
    return rows


def _clean_cell(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _dedupe_fact_strings(facts: list[str], *, limit: int) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for fact in facts:
        compact = re.sub(r"\s+", " ", fact).strip()
        if not compact:
            continue
        key = compact.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(compact)
        if len(deduped) == limit:
            break
    return deduped


def _upsert_named_object(store: OntologyStore, object_type: str, name: str, *, source_ref: str) -> OntologyObject | None:
    display_name = " ".join(str(name).split())
    normalized_name = normalise_name(display_name)
    if not normalized_name:
        return None
    properties: dict[str, Any] = {"normalized_name": normalized_name, "name": display_name}
    if object_type == "control":
        properties["control_type"] = ""
    return store.upsert_object(object_type, normalized_name, properties, source_ref=source_ref)


def normalise_name(value: str) -> str:
    """Normalise deduplicated role/system/control names across packs."""

    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _review_id(payload: dict[str, Any]) -> str:
    status = payload.get("status")
    if isinstance(status, dict):
        return str(status.get("job_id") or "")
    return ""


def _number_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _modality(text: str) -> str:
    lower = text.lower()
    if any(term in lower for term in ("must not", "cannot", "can't", "prohibited", "not allowed")):
        return "prohibition"
    if any(term in lower for term in ("must", "shall", "required", "need to", "has to")):
        return "obligation"
    if any(term in lower for term in ("may", "can", "allowed")):
        return "permission"
    if any(term in lower for term in ("should", "recommend")):
        return "recommendation"
    return "informational"


def _key_terms(text: str) -> list[str]:
    stop = {
        "about",
        "after",
        "also",
        "and",
        "are",
        "before",
        "for",
        "from",
        "have",
        "into",
        "must",
        "not",
        "that",
        "the",
        "their",
        "this",
        "with",
        "you",
    }
    terms: list[str] = []
    for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower()):
        if token in stop or token in terms:
            continue
        terms.append(token)
        if len(terms) == 12:
            break
    return terms


def _stable_hash(prefix: str, payload: Any) -> str:
    digest = hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def ontology_id(object_type: str, primary_key_value: str) -> str:
    """Expose stable ontology IDs for tests and deterministic callers."""

    return object_id_for(object_type, primary_key_value)
