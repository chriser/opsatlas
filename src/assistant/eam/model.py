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
FindingType = Literal["gap", "overlap", "clash"]
FindingSeverity = Literal["high", "medium", "low"]

MAX_EAM_FINDINGS = 80
MAX_PAIRWISE_FINDINGS = 48
MIN_SHARED_ENTITIES_FOR_OVERLAP = 2


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


class EamDomainCoverage(BaseModel):
    """Coverage status for one EAM domain."""

    model_config = ConfigDict(extra="forbid")

    domain_id: str
    label: str
    status: str
    node_count: int
    lifecycle_stage_count: int
    average_evidence_strength: int
    node_ids: list[str] = Field(default_factory=list)


class EamCoverage(BaseModel):
    """Overall EAM coverage summary."""

    model_config = ConfigDict(extra="forbid")

    score: int
    covered_domain_count: int
    partial_domain_count: int
    uncovered_domain_count: int
    domains: list[EamDomainCoverage]


class EamFinding(BaseModel):
    """Gap, overlap or clash finding with canvas-linkable ids."""

    model_config = ConfigDict(extra="forbid")

    id: str
    finding_type: FindingType
    severity: FindingSeverity
    title: str
    description: str
    node_ids: list[str] = Field(default_factory=list)
    entity_ids: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    recommended_action: str


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
    coverage: EamCoverage
    findings: list[EamFinding]
    finding_counts: dict[str, int]
    meta: dict


def build_eam_model(ontology_store: OntologyStore, taxonomy: TaxonomyConfig | None = None) -> EamModel:
    """Build a read-only EAM projection from ontology objects and links."""

    taxonomy = taxonomy or TaxonomyConfig.load()
    processes = ontology_store.find("process")
    nodes = [_node_from_process(ontology_store, taxonomy, process) for process in processes]
    node_by_process_id = {node.id: node for node in nodes}
    cells = _build_cells(taxonomy, nodes)
    edges = _shared_entity_edges(ontology_store, node_by_process_id)
    entity_maps = _process_entity_maps(ontology_store, nodes)
    coverage = _coverage(taxonomy, nodes)
    findings = _findings(taxonomy, nodes, cells, entity_maps)
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
        coverage=coverage,
        findings=findings,
        finding_counts={
            "gap": sum(1 for finding in findings if finding.finding_type == "gap"),
            "overlap": sum(1 for finding in findings if finding.finding_type == "overlap"),
            "clash": sum(1 for finding in findings if finding.finding_type == "clash"),
        },
        meta={
            "domain_count": len(taxonomy.domains),
            "lifecycle_stage_count": len(taxonomy.lifecycle_stages),
            "edge_count": len(edges),
            "unclassified_node_count": sum(1 for node in nodes if node.domain_id == "unclassified"),
            "finding_count": len(findings),
            "finding_limit": MAX_EAM_FINDINGS,
            "pairwise_finding_limit": MAX_PAIRWISE_FINDINGS,
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


def _coverage(taxonomy: TaxonomyConfig, nodes: list[EamNode]) -> EamCoverage:
    domains: list[EamDomainCoverage] = []
    for domain in taxonomy.domains:
        domain_nodes = [node for node in nodes if node.domain_id == domain.id]
        stage_count = len({node.lifecycle_id for node in domain_nodes})
        average_strength = round(sum(node.evidence_strength for node in domain_nodes) / len(domain_nodes)) if domain_nodes else 0
        if not domain_nodes:
            status = "uncovered"
        elif average_strength >= 65 and stage_count >= 2:
            status = "covered"
        else:
            status = "partial"
        domains.append(
            EamDomainCoverage(
                domain_id=domain.id,
                label=domain.label,
                status=status,
                node_count=len(domain_nodes),
                lifecycle_stage_count=stage_count,
                average_evidence_strength=average_strength,
                node_ids=[node.id for node in sorted(domain_nodes, key=lambda item: item.name.lower())],
            )
        )
    covered = sum(1 for domain in domains if domain.status == "covered")
    partial = sum(1 for domain in domains if domain.status == "partial")
    uncovered = sum(1 for domain in domains if domain.status == "uncovered")
    score = round(((covered * 100) + (partial * 50)) / len(domains)) if domains else 0
    return EamCoverage(
        score=score,
        covered_domain_count=covered,
        partial_domain_count=partial,
        uncovered_domain_count=uncovered,
        domains=domains,
    )


def _findings(
    taxonomy: TaxonomyConfig,
    nodes: list[EamNode],
    cells: list[EamCell],
    entity_maps: dict[str, dict[str, dict[str, str]]],
) -> list[EamFinding]:
    gap_findings = _gap_findings(taxonomy, nodes, cells)
    pairwise_findings = _rank_findings(_overlap_and_clash_findings(nodes, entity_maps))[:MAX_PAIRWISE_FINDINGS]
    return _rank_findings(gap_findings + pairwise_findings)[:MAX_EAM_FINDINGS]


def _gap_findings(taxonomy: TaxonomyConfig, nodes: list[EamNode], cells: list[EamCell]) -> list[EamFinding]:
    findings: list[EamFinding] = []
    coverage = _coverage(taxonomy, nodes)
    for domain in coverage.domains:
        if domain.status != "uncovered":
            continue
        findings.append(
            EamFinding(
                id=_finding_id("gap", domain.domain_id),
                finding_type="gap",
                severity="high",
                title=f"No approved process evidence for {domain.label}",
                description="The EAM taxonomy expects this operating domain, but no ontology process is currently classified into it.",
                evidence=[f"Domain {domain.label} has 0 process nodes"],
                recommended_action=f"Add or approve source evidence that describes the {domain.label} operating area.",
            )
        )

    covered_domains = {node.domain_id for node in nodes}
    for cell in cells:
        if not cell.is_gap or cell.domain_id not in covered_domains:
            continue
        domain = next(item for item in taxonomy.domains if item.id == cell.domain_id)
        stage = next(item for item in taxonomy.lifecycle_stages if item.id == cell.lifecycle_id)
        findings.append(
            EamFinding(
                id=_finding_id("gap", cell.domain_id, cell.lifecycle_id),
                finding_type="gap",
                severity="medium",
                title=f"{domain.label} has no {stage.label} evidence",
                description="This domain exists in the ontology projection, but this lifecycle stage has no process node yet.",
                evidence=[f"Empty cell: {domain.label} / {stage.label}"],
                recommended_action=(
                    "Confirm whether the lifecycle stage is genuinely absent or whether the source evidence needs clearer wording."
                ),
            )
        )
    return findings


def _overlap_and_clash_findings(nodes: list[EamNode], entity_maps: dict[str, dict[str, dict[str, str]]]) -> list[EamFinding]:
    findings: list[EamFinding] = []
    sorted_nodes = sorted(nodes, key=lambda node: node.id)
    for left, right in combinations(sorted_nodes, 2):
        left_entities = entity_maps.get(left.id, {})
        right_entities = entity_maps.get(right.id, {})
        shared_roles = _shared_entities(left_entities.get("roles", {}), right_entities.get("roles", {}))
        shared_systems = _shared_entities(left_entities.get("systems", {}), right_entities.get("systems", {}))
        shared_controls = _shared_entities(left_entities.get("controls", {}), right_entities.get("controls", {}))
        shared_count = len(shared_roles) + len(shared_systems) + len(shared_controls)

        if shared_count >= MIN_SHARED_ENTITIES_FOR_OVERLAP:
            entity_ids = sorted({*shared_roles, *shared_systems, *shared_controls})
            findings.append(
                EamFinding(
                    id=_finding_id("overlap", left.id, right.id),
                    finding_type="overlap",
                    severity="medium" if shared_systems and shared_controls else "low",
                    title=f"{left.name} overlaps with {right.name}",
                    description="The two process nodes share ontology entities and may need explicit boundary or reuse notes.",
                    node_ids=[left.id, right.id],
                    entity_ids=entity_ids,
                    evidence=_shared_evidence("roles", shared_roles)
                    + _shared_evidence("systems", shared_systems)
                    + _shared_evidence("controls", shared_controls),
                    recommended_action="Confirm whether this is intentional reuse, duplicate process coverage or a boundary issue.",
                )
            )

        release_or_integration = left.lifecycle_id in {"activate", "integrate"} and right.lifecycle_id in {"activate", "integrate"}
        if shared_systems and release_or_integration and not shared_controls:
            findings.append(
                EamFinding(
                    id=_finding_id("clash", "release-system", left.id, right.id),
                    finding_type="clash",
                    severity="high",
                    title="Shared release or integration system has no shared control",
                    description="Both process nodes sit in release/integration stages and share a system without shared control evidence.",
                    node_ids=[left.id, right.id],
                    entity_ids=sorted(shared_systems),
                    evidence=_shared_evidence("systems", shared_systems),
                    recommended_action="Define release sequencing and control ownership before relying on this EAM path.",
                )
            )
        if shared_controls and not shared_roles:
            findings.append(
                EamFinding(
                    id=_finding_id("clash", "control-owner", left.id, right.id),
                    finding_type="clash",
                    severity="medium",
                    title="Shared control has no shared owner evidence",
                    description="The process nodes share a control, but the ontology does not show a shared owner role.",
                    node_ids=[left.id, right.id],
                    entity_ids=sorted(shared_controls),
                    evidence=_shared_evidence("controls", shared_controls),
                    recommended_action="Confirm who signs off the shared control and whether both processes use the same criteria.",
                )
            )
    return findings


def _rank_findings(findings: list[EamFinding]) -> list[EamFinding]:
    return sorted(
        findings,
        key=lambda finding: (
            _severity_rank(finding.severity),
            _type_rank(finding.finding_type),
            -len(finding.node_ids),
            -len(finding.entity_ids),
            finding.title,
        ),
    )


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


def _process_entity_maps(store: OntologyStore, nodes: list[EamNode]) -> dict[str, dict[str, dict[str, str]]]:
    maps: dict[str, dict[str, dict[str, str]]] = {}
    for node in nodes:
        maps[node.id] = {
            "roles": {item.id: _entity_name(item) for item in store.traverse(node.id, "process_has_role")},
            "systems": {item.id: _entity_name(item) for item in store.traverse(node.id, "process_uses_system")},
            "controls": {item.id: _entity_name(item) for item in store.traverse(node.id, "process_enforced_by")},
        }
    return maps


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


def _shared_entities(left: dict[str, str], right: dict[str, str]) -> dict[str, str]:
    return {entity_id: left[entity_id] for entity_id in sorted(left.keys() & right.keys())}


def _shared_evidence(label: str, entities: dict[str, str]) -> list[str]:
    if not entities:
        return []
    return [f"Shared {label}: " + ", ".join(entities[item_id] for item_id in sorted(entities, key=lambda value: entities[value].lower()))]


def _severity_rank(severity: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(severity, 3)


def _type_rank(finding_type: str) -> int:
    return {"clash": 0, "gap": 1, "overlap": 2}.get(finding_type, 3)


def _finding_id(*parts: str) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"eam-finding-{digest}"


def _edge_id(edge_type: str, left_id: str, right_id: str, entity_ids: list[str]) -> str:
    digest = hashlib.sha1("|".join([edge_type, left_id, right_id, *entity_ids]).encode("utf-8")).hexdigest()[:12]
    return f"eam-edge-{edge_type}-{digest}"
