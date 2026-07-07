"""End-to-end retail operating-model coverage map over process records."""

from __future__ import annotations

from itertools import combinations

from pydantic import BaseModel, ConfigDict

from ..eam.taxonomy import TaxonomyConfig
from .models import ProcessRecord


class CoverageDomain(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain_id: str
    label: str
    description: str
    coverage_status: str
    evidence_strength_score: int
    process_count: int
    process_ids: list[str]
    source_titles: list[str]
    roles: list[str]
    systems: list[str]
    controls: list[str]
    dependencies: list[str]
    lifecycle_stages: list[str]
    missing_signals: list[str]


class CoverageProcessRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    process_id: str
    process_name: str
    source_title: str
    matched_domains: list[str]
    lifecycle_stages: list[str]
    roles: list[str]
    systems: list[str]
    controls: list[str]
    evidence_notes: list[str]


class OperatingModelCoverageMap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    process_count: int
    domain_count: int
    covered_domain_count: int
    partial_domain_count: int
    uncovered_domain_count: int
    coverage_score: int
    role_count: int
    system_count: int
    control_count: int
    domains: list[CoverageDomain]
    process_matrix: list[CoverageProcessRow]
    rubric: dict[str, str]


class GapOverlapFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    finding_id: str
    finding_type: str
    severity: str
    title: str
    description: str
    affected_process_ids: list[str]
    affected_processes: list[str]
    evidence: list[str]
    recommended_action: str


class ProcessGapOverlapReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    process_count: int
    finding_count: int
    gap_count: int
    overlap_count: int
    clash_count: int
    high_severity_count: int
    findings: list[GapOverlapFinding]
    rubric: dict[str, str]


DOMAIN_CATALOG = [
    {
        "domain_id": "supplier-vendor-master-data",
        "label": "Supplier and vendor master data",
        "description": "Supplier onboarding, supplier changes, due diligence, identifiers and activation readiness.",
        "terms": ["supplier", "vendor", "due diligence", "credit check", "supplier identifier"],
    },
    {
        "domain_id": "article-product-master-data",
        "label": "Article and product master data",
        "description": "Article setup, product attributes, article lists, hierarchy and product-change handling.",
        "terms": ["article", "product", "item", "sku", "article list", "product change"],
    },
    {
        "domain_id": "pricing-tax-and-commercial-controls",
        "label": "Pricing, tax and commercial controls",
        "description": "Tax handling, pricing dependencies, validation gates and commercial readiness controls.",
        "terms": ["tax", "pricing", "price", "commercial", "tax handling", "validation"],
    },
    {
        "domain_id": "compliance-restrictions-and-risk",
        "label": "Compliance, restrictions and risk",
        "description": "Age restrictions, legal thresholds, compliance owners, exceptions and risk controls.",
        "terms": ["compliance", "restriction", "age", "legal", "exception", "risk"],
    },
    {
        "domain_id": "systems-integration-and-downstream-flow",
        "label": "Systems integration and downstream flow",
        "description": "Operational/finance system mapping, downstream retail platforms, interfaces and reconciliation.",
        "terms": ["system", "integration", "downstream", "finance", "mapping", "reconciliation", "interface"],
    },
    {
        "domain_id": "operational-support-and-exceptions",
        "label": "Operational support and exceptions",
        "description": "Trading support, support teams, manual work, exceptions, queries and unresolved hand-offs.",
        "terms": ["support", "manual", "exception", "query", "handoff", "hand-off", "trading support"],
    },
    {
        "domain_id": "governance-evidence-and-change-control",
        "label": "Governance, evidence and change control",
        "description": "Approval evidence, controls, retained proof, source governance and change/update cadence.",
        "terms": ["approval", "evidence", "control", "governance", "change", "update", "review"],
    },
]


VALUE_CHAIN_EXECUTION_STAGE_LABELS = {"Source & Replenish", "Receive & Control", "Sell & Operate", "Reconcile & Close"}


def build_operating_model_coverage(records: list[ProcessRecord]) -> OperatingModelCoverageMap:
    domains = [_coverage_for_domain(record_set=records, domain=domain) for domain in DOMAIN_CATALOG]
    matrix = [_process_row(record) for record in records]
    covered = sum(1 for domain in domains if domain.coverage_status == "covered")
    partial = sum(1 for domain in domains if domain.coverage_status == "partial")
    uncovered = sum(1 for domain in domains if domain.coverage_status == "uncovered")
    coverage_score = round(((covered * 100) + (partial * 50)) / len(domains)) if domains else 0
    return OperatingModelCoverageMap(
        process_count=len(records),
        domain_count=len(domains),
        covered_domain_count=covered,
        partial_domain_count=partial,
        uncovered_domain_count=uncovered,
        coverage_score=coverage_score,
        role_count=len(_unique(item for record in records for item in record.roles)),
        system_count=len(_unique(item for record in records for item in record.systems)),
        control_count=len(_unique(item for record in records for item in record.controls)),
        domains=domains,
        process_matrix=sorted(matrix, key=lambda row: (-len(row.matched_domains), row.process_name)),
        rubric={
            "coverage_status": "Covered needs at least one matched process plus role/system/control evidence; partial has weaker evidence.",
            "evidence_strength_score": (
                "0-100 indicator from matched processes, value-chain stages, roles, systems, controls and dependencies."
            ),
            "coverage_score": "Weighted percentage: covered domains count as 100 and partial domains count as 50.",
            "boundary": "Coverage shows approved-source evidence breadth, not proof that the live operating model is complete.",
        },
    )


def build_process_gap_overlap_report(records: list[ProcessRecord]) -> ProcessGapOverlapReport:
    """Find deterministic process evidence gaps, overlaps and potential clashes."""

    findings = _domain_gap_findings(build_operating_model_coverage(records))
    findings.extend(_record_gap_findings(records))
    findings.extend(_pairwise_overlap_findings(records))
    findings.extend(_pairwise_clash_findings(records))
    sorted_findings = sorted(findings, key=lambda row: (_severity_rank(row.severity), _type_rank(row.finding_type), row.title))
    return ProcessGapOverlapReport(
        process_count=len(records),
        finding_count=len(sorted_findings),
        gap_count=sum(1 for row in sorted_findings if row.finding_type == "gap"),
        overlap_count=sum(1 for row in sorted_findings if row.finding_type == "overlap"),
        clash_count=sum(1 for row in sorted_findings if row.finding_type == "clash"),
        high_severity_count=sum(1 for row in sorted_findings if row.severity == "high"),
        findings=sorted_findings[:80],
        rubric={
            "gap": "Missing or weak evidence signals in the operating-model coverage map or process registry fields.",
            "overlap": "Two or more processes share systems, controls, dependencies or owner groups and may need boundary clarification.",
            "clash": "Potential sequencing, ownership or control conflict that should be reviewed before treating the model as complete.",
            "boundary": "Findings are deterministic triage cues from approved-source metadata, not proof of live operational failure.",
        },
    )


def _coverage_for_domain(record_set: list[ProcessRecord], domain: dict) -> CoverageDomain:
    matches = [record for record in record_set if _matches_domain(record, domain["terms"])]
    roles = _unique(item for record in matches for item in record.roles)
    systems = _unique(item for record in matches for item in record.systems)
    controls = _unique(item for record in matches for item in record.controls)
    dependencies = _unique(item for record in matches for item in record.dependencies)
    lifecycle_stages = _unique(stage for record in matches for stage in _lifecycle_stages(record))
    score = min(
        100,
        len(matches) * 22 + len(lifecycle_stages) * 8 + min(18, len(roles) * 3) + min(18, len(systems) * 4) + len(controls) * 5,
    )
    missing = _missing_signals(matches, roles, systems, controls, lifecycle_stages)
    return CoverageDomain(
        domain_id=domain["domain_id"],
        label=domain["label"],
        description=domain["description"],
        coverage_status=_coverage_status(matches, score, missing),
        evidence_strength_score=score,
        process_count=len(matches),
        process_ids=[record.id for record in matches],
        source_titles=_unique(record.source_title for record in matches),
        roles=roles,
        systems=systems,
        controls=controls,
        dependencies=dependencies,
        lifecycle_stages=lifecycle_stages,
        missing_signals=missing,
    )


def _process_row(record: ProcessRecord) -> CoverageProcessRow:
    matched_domains = [domain["label"] for domain in DOMAIN_CATALOG if _matches_domain(record, domain["terms"])]
    stages = _lifecycle_stages(record)
    notes = []
    if not matched_domains:
        notes.append("No operating-model domain keyword matched this process.")
    if not record.roles:
        notes.append("No role/owner evidence extracted.")
    if not record.systems:
        notes.append("No system evidence extracted.")
    if not record.controls:
        notes.append("No control evidence extracted.")
    return CoverageProcessRow(
        process_id=record.id,
        process_name=record.name,
        source_title=record.source_title,
        matched_domains=matched_domains,
        lifecycle_stages=stages,
        roles=record.roles,
        systems=record.systems,
        controls=record.controls,
        evidence_notes=notes or ["Record carries domain, value-chain stage and ownership evidence."],
    )


def _domain_gap_findings(coverage: OperatingModelCoverageMap) -> list[GapOverlapFinding]:
    findings = []
    for domain in coverage.domains:
        if domain.coverage_status == "covered":
            continue
        findings.append(
            GapOverlapFinding(
                finding_id=_finding_id("gap", [domain.domain_id]),
                finding_type="gap",
                severity="high" if domain.coverage_status == "uncovered" else "medium",
                title=f"{domain.label} coverage is {domain.coverage_status}",
                description=domain.description,
                affected_process_ids=domain.process_ids,
                affected_processes=domain.source_titles,
                evidence=domain.missing_signals,
                recommended_action=(
                    "Add or enrich approved source evidence for this domain before using it as a complete operating-model view."
                ),
            )
        )
    return findings


def _record_gap_findings(records: list[ProcessRecord]) -> list[GapOverlapFinding]:
    findings = []
    for record in records:
        missing = []
        if not record.roles:
            missing.append("No role/owner evidence extracted")
        if not record.systems:
            missing.append("No system evidence extracted")
        if not record.controls:
            missing.append("No control evidence extracted")
        if not _lifecycle_stages(record):
            missing.append("No value-chain stage matched")
        if len(missing) < 2:
            continue
        findings.append(
            GapOverlapFinding(
                finding_id=_finding_id("gap", [record.id]),
                finding_type="gap",
                severity="high" if len(missing) >= 3 else "medium",
                title=f"{record.name} has weak operating-model evidence",
                description="The process exists in the registry but lacks enough structured signals for confident coverage mapping.",
                affected_process_ids=[record.id],
                affected_processes=[record.name],
                evidence=missing,
                recommended_action=(
                    "Review the approved source and add explicit owner, system, control or value-chain evidence where available."
                ),
            )
        )
    return findings


def _pairwise_overlap_findings(records: list[ProcessRecord]) -> list[GapOverlapFinding]:
    findings = []
    for left, right in combinations(records, 2):
        shared_systems = _shared(left.systems, right.systems)
        shared_controls = _shared(left.controls, right.controls)
        shared_dependencies = _shared(left.dependencies, right.dependencies)
        shared_roles = _shared(left.roles, right.roles)
        if not (shared_systems or shared_controls or len(shared_roles) >= 2 or shared_dependencies):
            continue
        evidence = []
        if shared_systems:
            evidence.append("Shared systems: " + ", ".join(shared_systems))
        if shared_controls:
            evidence.append("Shared controls: " + ", ".join(shared_controls))
        if shared_dependencies:
            evidence.append("Shared dependencies: " + ", ".join(shared_dependencies))
        if len(shared_roles) >= 2:
            evidence.append("Shared owner groups: " + ", ".join(shared_roles))
        findings.append(
            GapOverlapFinding(
                finding_id=_finding_id("overlap", [left.id, right.id]),
                finding_type="overlap",
                severity="medium" if shared_systems and (shared_controls or shared_dependencies) else "low",
                title=f"{left.name} overlaps with {right.name}",
                description="The two process records share operating-model signals and may need explicit boundary or reuse notes.",
                affected_process_ids=[left.id, right.id],
                affected_processes=[left.name, right.name],
                evidence=evidence,
                recommended_action="Confirm whether this is intentional reuse, duplicate coverage or a process-boundary issue.",
            )
        )
    return findings


def _pairwise_clash_findings(records: list[ProcessRecord]) -> list[GapOverlapFinding]:
    findings = []
    for left, right in combinations(records, 2):
        shared_systems = _shared(left.systems, right.systems)
        shared_controls = _shared(left.controls, right.controls)
        shared_dependencies = _shared(left.dependencies, right.dependencies)
        shared_roles = _shared(left.roles, right.roles)
        left_stages = set(_lifecycle_stages(left))
        right_stages = set(_lifecycle_stages(right))
        shared_execution_stage = bool(left_stages & VALUE_CHAIN_EXECUTION_STAGE_LABELS) and bool(
            right_stages & VALUE_CHAIN_EXECUTION_STAGE_LABELS
        )

        if shared_systems and shared_execution_stage and not shared_controls:
            findings.append(
                _clash(
                    [left, right],
                    "Shared value-chain system has no common control evidence",
                    [
                        "Shared systems: " + ", ".join(shared_systems),
                        "Both records mention value-chain execution-stage signals",
                    ],
                    "Define operating-flow sequencing and shared control ownership for the affected system before relying on this model.",
                    severity="high",
                )
            )
        if shared_controls and not shared_roles:
            findings.append(
                _clash(
                    [left, right],
                    "Shared control appears without shared owner evidence",
                    ["Shared controls: " + ", ".join(shared_controls)],
                    "Confirm which owner signs off the shared control and whether both processes use the same acceptance criteria.",
                    severity="medium",
                )
            )
        if shared_dependencies and not shared_roles:
            findings.append(
                _clash(
                    [left, right],
                    "Shared dependency has no shared owner evidence",
                    ["Shared dependencies: " + ", ".join(shared_dependencies)],
                    "Clarify dependency ownership and escalation path across the two process records.",
                    severity="medium",
                )
            )
    return findings


def _clash(
    records: list[ProcessRecord],
    title: str,
    evidence: list[str],
    recommended_action: str,
    *,
    severity: str,
) -> GapOverlapFinding:
    return GapOverlapFinding(
        finding_id=_finding_id("clash", [record.id for record in records] + [title]),
        finding_type="clash",
        severity=severity,
        title=title,
        description="A deterministic rule found a possible process sequencing, ownership or control conflict.",
        affected_process_ids=[record.id for record in records],
        affected_processes=[record.name for record in records],
        evidence=evidence,
        recommended_action=recommended_action,
    )


def _matches_domain(record: ProcessRecord, terms: list[str]) -> bool:
    text = _record_text(record)
    return any(term in text for term in terms)


def _record_text(record: ProcessRecord) -> str:
    values = [
        record.name,
        record.domain,
        record.process,
        record.source_title,
        *record.capabilities,
        *record.roles,
        *record.systems,
        *record.controls,
        *record.dependencies,
        *record.business_rules,
        *(rule.rule for rule in record.rules),
        *(rule.topic for rule in record.rules),
        *(rule.role for rule in record.rules),
    ]
    return " ".join(value for value in values if value).lower()


def _lifecycle_stages(record: ProcessRecord) -> list[str]:
    text = _record_text(record)
    stage_terms = {
        stage.label: [keyword.lower() for keyword in stage.keywords]
        for stage in TaxonomyConfig.load().lifecycle_stages
    }
    return [stage for stage, terms in stage_terms.items() if any(term in text for term in terms)]


def _coverage_status(matches: list[ProcessRecord], score: int, missing: list[str]) -> str:
    if not matches:
        return "uncovered"
    if score >= 65 and len(missing) <= 1:
        return "covered"
    return "partial"


def _missing_signals(
    matches: list[ProcessRecord],
    roles: list[str],
    systems: list[str],
    controls: list[str],
    lifecycle_stages: list[str],
) -> list[str]:
    if not matches:
        return ["No approved process source matched this operating-model domain."]
    missing = []
    if not roles:
        missing.append("Role/owner evidence missing")
    if not systems:
        missing.append("System evidence missing")
    if not controls:
        missing.append("Control evidence missing")
    if len(lifecycle_stages) < 3:
        missing.append("Value-chain stage coverage is narrow")
    return missing or ["No major evidence signal missing from current registry fields"]


def _shared(left: list[str], right: list[str]) -> list[str]:
    left_map = {item.strip().lower(): item.strip() for item in left if item and item.strip()}
    right_keys = {item.strip().lower() for item in right if item and item.strip()}
    return sorted((left_map[key] for key in left_map.keys() & right_keys), key=str.lower)


def _finding_id(prefix: str, parts: list[str]) -> str:
    slug = "-".join(_slug(part) for part in parts if part)
    return f"{prefix}-{slug[:96]}"


def _slug(value: str) -> str:
    cleaned = "".join(char.lower() if char.isalnum() else "-" for char in value)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "unknown"


def _severity_rank(severity: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(severity, 3)


def _type_rank(finding_type: str) -> int:
    return {"clash": 0, "gap": 1, "overlap": 2}.get(finding_type, 3)


def _unique(values) -> list[str]:  # type: ignore[no-untyped-def]
    cleaned = {value.strip() for value in values if value and value.strip()}
    return sorted(cleaned, key=str.lower)
