"""Enterprise Activity Model projection over the ontology graph."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import UTC, datetime
from itertools import combinations
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..ontology.store import OntologyObject, OntologyStore
from .taxonomy import TaxonomyConfig, TaxonomyEntry, TaxonomyMatch

ConfidenceBand = Literal["green", "amber", "red"]
EamEdgeType = Literal["system", "control", "dependency"]


class EamNode(BaseModel):
    """One process node projected onto the EAM grid."""

    model_config = ConfigDict(extra="forbid")

    id: str
    process_id: str
    name: str
    domain_id: str
    domain_label: str
    lifecycle_id: str
    lifecycle_label: str
    domain_confidence: float
    lifecycle_confidence: float
    matched_domain_keywords: list[str] = Field(default_factory=list)
    matched_lifecycle_keywords: list[str] = Field(default_factory=list)
    role_count: int
    system_count: int
    control_count: int
    dependency_count: int = 0
    source_refs: list[str] = Field(default_factory=list)
    evidence_strength: int
    confidence_band: ConfidenceBand


class EamCell(BaseModel):
    """A domain x lifecycle stage grid cell."""

    model_config = ConfigDict(extra="forbid")

    domain_id: str
    lifecycle_id: str
    node_ids: list[str] = Field(default_factory=list)
    is_gap: bool = False


class EamEdge(BaseModel):
    """Shared-entity edge between two process nodes."""

    model_config = ConfigDict(extra="forbid")

    id: str
    edge_type: EamEdgeType
    from_node_id: str
    to_node_id: str
    shared_entity_ids: list[str] = Field(default_factory=list)
    shared_entity_labels: list[str] = Field(default_factory=list)


class EntityRollup(BaseModel):
    """Roll-up for a role, system or control entity."""

    model_config = ConfigDict(extra="forbid")

    id: str
    object_type: str
    name: str
    process_count: int
    linked_process_ids: list[str] = Field(default_factory=list)
    linked_entity_counts: dict[str, int] = Field(default_factory=dict)


class EamModel(BaseModel):
    """Projection model shared by EAM views and future APIs."""

    model_config = ConfigDict(extra="forbid")

    taxonomy_version: str
    generated_at: str
    source_count: int
    process_count: int
    domains: list[TaxonomyEntry]
    lifecycle_stages: list[TaxonomyEntry]
    nodes: list[EamNode]
    cells: list[EamCell]
    edges: list[EamEdge]
    entity_rollups: dict[str, list[EntityRollup]]
    meta: dict


def build_eam_model(ontology_store: OntologyStore, taxonomy: TaxonomyConfig | None = None) -> EamModel:
    """Build a read-only EAM projection from ontology objects and links."""

    taxonomy = taxonomy or TaxonomyConfig.load()
    processes = ontology_store.find("process")
    nodes = [_node_from_process(ontology_store, taxonomy, process) for process in processes]
    node_by_process_id = {node.id: node for node in nodes}
    cells = _build_cells(taxonomy, nodes)
    edges = _shared_entity_edges(ontology_store, node_by_process_id)
    rollups = {
        "roles": _entity_rollups(ontology_store, "role", "process_has_role"),
        "systems": _entity_rollups(ontology_store, "system", "process_uses_system"),
        "controls": _entity_rollups(ontology_store, "control", "process_enforced_by"),
    }
    source_ids = {source_ref for node in nodes for source_ref in node.source_refs}
    return EamModel(
        taxonomy_version=taxonomy.version,
        generated_at=datetime.now(UTC).isoformat(),
        source_count=len(source_ids),
        process_count=len(nodes),
        domains=taxonomy.domains,
        lifecycle_stages=taxonomy.lifecycle_stages,
        nodes=sorted(nodes, key=lambda node: (node.domain_id, node.lifecycle_id, node.name.lower())),
        cells=cells,
        edges=edges,
        entity_rollups=rollups,
        meta={
            "domain_count": len(taxonomy.domains),
            "lifecycle_stage_count": len(taxonomy.lifecycle_stages),
            "edge_count": len(edges),
            "unclassified_node_count": sum(1 for node in nodes if node.domain_id == "unclassified"),
        },
    )


def _node_from_process(store: OntologyStore, taxonomy: TaxonomyConfig, process: OntologyObject) -> EamNode:
    roles = store.traverse(process.id, "process_has_role")
    systems = store.traverse(process.id, "process_uses_system")
    controls = store.traverse(process.id, "process_enforced_by")
    sources = store.traverse(process.id, "process_derived_from")
    domain_match = taxonomy.classify_domain(_process_text(process))
    lifecycle_match = taxonomy.classify_lifecycle(_process_text(process))
    domain_id, domain_label, domain_confidence, domain_keywords = _match_parts(domain_match)
    lifecycle_id, lifecycle_label, lifecycle_confidence, lifecycle_keywords = _match_parts(lifecycle_match)
    evidence_strength = _evidence_strength(roles, systems, controls, sources, process.properties.get("key_facts", []))
    return EamNode(
        id=process.id,
        process_id=process.primary_key_value,
        name=str(process.properties.get("name") or process.primary_key_value),
        domain_id=domain_id,
        domain_label=domain_label,
        lifecycle_id=lifecycle_id,
        lifecycle_label=lifecycle_label,
        domain_confidence=domain_confidence,
        lifecycle_confidence=lifecycle_confidence,
        matched_domain_keywords=domain_keywords,
        matched_lifecycle_keywords=lifecycle_keywords,
        role_count=len(roles),
        system_count=len(systems),
        control_count=len(controls),
        source_refs=[source.primary_key_value for source in sources],
        evidence_strength=evidence_strength,
        confidence_band=_confidence_band(evidence_strength, min(domain_confidence, lifecycle_confidence)),
    )


def _process_text(process: OntologyObject) -> str:
    values: list[str] = [
        process.primary_key_value,
        str(process.properties.get("name") or ""),
        str(process.properties.get("domain") or ""),
    ]
    for key in ("capabilities", "business_rules", "key_facts"):
        value = process.properties.get(key, [])
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        else:
            values.append(str(value))
    return " ".join(values)


def _match_parts(match: TaxonomyMatch | None) -> tuple[str, str, float, list[str]]:
    if match is None:
        return "unclassified", "Unclassified", 0.0, []
    return match.item_id, match.label, match.confidence, match.matched_keywords


def _evidence_strength(
    roles: list[OntologyObject],
    systems: list[OntologyObject],
    controls: list[OntologyObject],
    sources: list[OntologyObject],
    key_facts: object,
) -> int:
    facts = key_facts if isinstance(key_facts, list) else []
    score = (
        20
        + min(24, len(roles) * 8)
        + min(24, len(systems) * 8)
        + min(24, len(controls) * 8)
        + min(12, len(sources) * 6)
        + min(20, len(facts) * 2)
    )
    return min(100, score)


def _confidence_band(evidence_strength: int, classification_confidence: float) -> ConfidenceBand:
    if evidence_strength >= 65 and classification_confidence >= 0.4:
        return "green"
    if evidence_strength >= 40 and classification_confidence >= 0.2:
        return "amber"
    return "red"


def _build_cells(taxonomy: TaxonomyConfig, nodes: list[EamNode]) -> list[EamCell]:
    node_ids_by_cell: dict[tuple[str, str], list[str]] = defaultdict(list)
    for node in sorted(nodes, key=lambda item: item.name.lower()):
        node_ids_by_cell[(node.domain_id, node.lifecycle_id)].append(node.id)

    cells: list[EamCell] = []
    for domain in taxonomy.domains:
        for stage in taxonomy.lifecycle_stages:
            node_ids = node_ids_by_cell.get((domain.id, stage.id), [])
            cells.append(EamCell(domain_id=domain.id, lifecycle_id=stage.id, node_ids=node_ids, is_gap=not node_ids))
    return cells


def _shared_entity_edges(store: OntologyStore, node_by_process_id: dict[str, EamNode]) -> list[EamEdge]:
    edges_by_pair: dict[tuple[str, str, EamEdgeType], dict[str, str]] = {}
    for object_type, link_type, edge_type in [
        ("system", "process_uses_system", "system"),
        ("control", "process_enforced_by", "control"),
    ]:
        for entity in store.find(object_type):
            processes = [item for item in store.traverse(entity.id, link_type, direction="in") if item.id in node_by_process_id]
            for left, right in combinations(sorted(processes, key=lambda item: item.id), 2):
                key = (left.id, right.id, edge_type)
                edges_by_pair.setdefault(key, {})[entity.id] = _entity_name(entity)

    edges: list[EamEdge] = []
    for (left_id, right_id, edge_type), entities in sorted(edges_by_pair.items()):
        edges.append(
            EamEdge(
                id=_edge_id(edge_type, left_id, right_id, sorted(entities)),
                edge_type=edge_type,
                from_node_id=left_id,
                to_node_id=right_id,
                shared_entity_ids=sorted(entities),
                shared_entity_labels=[entities[item_id] for item_id in sorted(entities, key=lambda value: entities[value].lower())],
            )
        )
    return edges


def _entity_rollups(store: OntologyStore, object_type: str, link_type: str) -> list[EntityRollup]:
    rows: list[EntityRollup] = []
    for entity in store.find(object_type):
        processes = store.traverse(entity.id, link_type, direction="in")
        linked_counts = _linked_entity_counts(store, processes)
        rows.append(
            EntityRollup(
                id=entity.id,
                object_type=entity.object_type,
                name=_entity_name(entity),
                process_count=len(processes),
                linked_process_ids=[process.id for process in processes],
                linked_entity_counts=linked_counts,
            )
        )
    return sorted(rows, key=lambda row: (-row.process_count, row.name.lower()))


def _linked_entity_counts(store: OntologyStore, processes: list[OntologyObject]) -> dict[str, int]:
    linked: dict[str, set[str]] = {"roles": set(), "systems": set(), "controls": set()}
    for process in processes:
        linked["roles"].update(item.id for item in store.traverse(process.id, "process_has_role"))
        linked["systems"].update(item.id for item in store.traverse(process.id, "process_uses_system"))
        linked["controls"].update(item.id for item in store.traverse(process.id, "process_enforced_by"))
    return {key: len(value) for key, value in linked.items()}


def _entity_name(entity: OntologyObject) -> str:
    return str(entity.properties.get("name") or entity.properties.get("title") or entity.primary_key_value)


def _edge_id(edge_type: str, left_id: str, right_id: str, entity_ids: list[str]) -> str:
    digest = hashlib.sha1("|".join([edge_type, left_id, right_id, *entity_ids]).encode("utf-8")).hexdigest()[:12]
    return f"eam-edge-{edge_type}-{digest}"
