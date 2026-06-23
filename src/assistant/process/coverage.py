"""End-to-end retail operating-model coverage map over process records."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

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


STAGE_TERMS = {
    "intake/request": ["request", "trigger", "need", "submit", "form"],
    "validation/control": ["validate", "validation", "check", "approval", "gate", "review"],
    "create/setup": ["create", "setup", "set up", "record", "attribute", "assign"],
    "integrate/map": ["map", "mapping", "system", "integration", "interface", "downstream"],
    "activate/release": ["activate", "release", "ready", "go-live", "available for use"],
    "maintain/change": ["change", "update", "maintenance", "annual", "future", "exception"],
}


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
                "0-100 indicator from matched processes, lifecycle stages, roles, systems, controls and dependencies."
            ),
            "coverage_score": "Weighted percentage: covered domains count as 100 and partial domains count as 50.",
            "boundary": "Coverage shows approved-source evidence breadth, not proof that the live operating model is complete.",
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
        evidence_notes=notes or ["Record carries domain, lifecycle and ownership evidence."],
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
    return [stage for stage, terms in STAGE_TERMS.items() if any(term in text for term in terms)]


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
        missing.append("Lifecycle coverage is narrow")
    return missing or ["No major evidence signal missing from current registry fields"]


def _unique(values) -> list[str]:  # type: ignore[no-untyped-def]
    cleaned = {value.strip() for value in values if value and value.strip()}
    return sorted(cleaned, key=str.lower)
