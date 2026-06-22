"""Deterministic process stress-test simulation over registry records."""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, ConfigDict

from .models import ProcessRecord

RISK_TERMS = ("exception", "manual", "unclear", "requires validation", "open decision", "fail", "reject", "missing")


class StressScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    label: str
    demand_multiplier: float
    exception_rate: float
    staffing_factor: float


class ProcessStressRuleSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    process_id: str
    process_name: str
    source_title: str
    role_count: int
    system_count: int
    dependency_count: int
    control_count: int
    rule_count: int
    handoff_count: int
    exception_term_count: int
    validation_gate_count: int
    dominant_role: str
    stress_factors: list[str]


class ProcessStressScenarioResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    process_id: str
    process_name: str
    scenario_id: str
    scenario_label: str
    cycle_time_index: float
    queue_pressure_score: int
    rework_risk_score: int
    bottleneck_role: str
    bottleneck_reason: str
    optimisation_actions: list[str]


class ProcessStressReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    process_count: int
    scenario_count: int
    rules: list[ProcessStressRuleSet]
    scenarios: list[StressScenario]
    results: list[ProcessStressScenarioResult]
    highest_risk: ProcessStressScenarioResult | None
    rubric: dict[str, str]


SCENARIOS = [
    StressScenario(scenario_id="baseline", label="Baseline", demand_multiplier=1.0, exception_rate=0.08, staffing_factor=1.0),
    StressScenario(scenario_id="volume_spike", label="Volume spike", demand_multiplier=1.6, exception_rate=0.1, staffing_factor=1.0),
    StressScenario(scenario_id="exception_spike", label="Exception spike", demand_multiplier=1.1, exception_rate=0.25, staffing_factor=1.0),
    StressScenario(
        scenario_id="staff_constraint",
        label="Staff constraint",
        demand_multiplier=1.2,
        exception_rate=0.12,
        staffing_factor=0.7,
    ),
]


def build_process_stress_report(records: list[ProcessRecord]) -> ProcessStressReport:
    rules = [_rule_set(record) for record in records]
    results = [
        _simulate(rule_set, scenario)
        for rule_set in rules
        for scenario in SCENARIOS
    ]
    highest = max(results, key=lambda row: (row.queue_pressure_score + row.rework_risk_score, row.cycle_time_index), default=None)
    return ProcessStressReport(
        process_count=len(records),
        scenario_count=len(SCENARIOS),
        rules=sorted(rules, key=lambda row: (-row.exception_term_count, -row.handoff_count, row.process_name)),
        scenarios=SCENARIOS,
        results=sorted(results, key=lambda row: (-row.queue_pressure_score, -row.rework_risk_score, row.process_name)),
        highest_risk=highest,
        rubric={
            "cycle_time_index": "Relative index from roles, systems, dependencies, hand-offs, demand and staffing pressure.",
            "queue_pressure_score": "0-100 indicator for queueing pressure under a scenario; higher needs review.",
            "rework_risk_score": "0-100 indicator from exception wording, validation gates, dependencies and staffing stress.",
            "boundary": "Scenario-planning indicator only; not a production forecast or capacity model.",
        },
    )


def _rule_set(record: ProcessRecord) -> ProcessStressRuleSet:
    rule_roles = [rule.role.strip().lower() for rule in record.rules if rule.role.strip()]
    role_counts = Counter(rule_roles)
    dominant_role = role_counts.most_common(1)[0][0] if role_counts else (record.roles[0] if record.roles else "")
    text = " ".join(record.business_rules + [rule.rule for rule in record.rules]).lower()
    exception_terms = sum(text.count(term) for term in RISK_TERMS)
    validation_gates = sum(1 for rule in record.rules if _mentions_validation(rule.rule)) + sum(
        1 for rule in record.business_rules if _mentions_validation(rule)
    )
    handoffs = max(0, len({role.lower() for role in record.roles}) - 1)
    stress_factors = _stress_factors(record, handoffs, exception_terms, validation_gates)
    return ProcessStressRuleSet(
        process_id=record.id,
        process_name=record.name,
        source_title=record.source_title,
        role_count=len(record.roles),
        system_count=len(record.systems),
        dependency_count=len(record.dependencies),
        control_count=len(record.controls),
        rule_count=len(record.rules),
        handoff_count=handoffs,
        exception_term_count=exception_terms,
        validation_gate_count=validation_gates,
        dominant_role=dominant_role.replace("_", " "),
        stress_factors=stress_factors,
    )


def _simulate(rule_set: ProcessStressRuleSet, scenario: StressScenario) -> ProcessStressScenarioResult:
    base_complexity = (
        10
        + rule_set.role_count * 4
        + rule_set.system_count * 5
        + rule_set.dependency_count * 6
        + rule_set.handoff_count * 5
        + rule_set.validation_gate_count * 4
        + rule_set.rule_count * 1.5
    )
    cycle_time = base_complexity * scenario.demand_multiplier * (1 + scenario.exception_rate) / max(0.2, scenario.staffing_factor)
    queue_pressure = min(100, round(cycle_time * 0.75 + rule_set.dependency_count * 5 + rule_set.handoff_count * 4))
    rework_risk = min(
        100,
        round(
            rule_set.exception_term_count * 10
            + rule_set.validation_gate_count * 7
            + rule_set.dependency_count * 5
            + max(0, 1 - scenario.staffing_factor) * 35
            + scenario.exception_rate * 45
        ),
    )
    return ProcessStressScenarioResult(
        process_id=rule_set.process_id,
        process_name=rule_set.process_name,
        scenario_id=scenario.scenario_id,
        scenario_label=scenario.label,
        cycle_time_index=round(cycle_time, 1),
        queue_pressure_score=queue_pressure,
        rework_risk_score=rework_risk,
        bottleneck_role=rule_set.dominant_role or "unassigned",
        bottleneck_reason=_bottleneck_reason(rule_set, scenario),
        optimisation_actions=_optimisation_actions(rule_set, queue_pressure, rework_risk),
    )


def _mentions_validation(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in ("validation", "validate", "gate", "approval", "check", "requires validation"))


def _stress_factors(record: ProcessRecord, handoffs: int, exception_terms: int, validation_gates: int) -> list[str]:
    factors = []
    if handoffs >= 3:
        factors.append("Multiple role hand-offs")
    if len(record.systems) >= 3:
        factors.append("Multiple systems")
    if len(record.dependencies) >= 2:
        factors.append("Several dependencies")
    if exception_terms:
        factors.append("Exception/manual wording")
    if validation_gates >= 2:
        factors.append("Multiple validation gates")
    if not record.roles and record.rules:
        factors.append("Rules without clear owner")
    return factors or ["No elevated stress factor from registry fields"]


def _bottleneck_reason(rule_set: ProcessStressRuleSet, scenario: StressScenario) -> str:
    if scenario.staffing_factor < 1:
        return "Staffing constraint magnifies the dominant role and hand-off load."
    if rule_set.dependency_count >= 2:
        return "Dependencies create queueing risk when scenario demand increases."
    if rule_set.validation_gate_count >= 2:
        return "Validation gates are likely to concentrate work under stress."
    return "Dominant role owns the largest share of structured process rules."


def _optimisation_actions(rule_set: ProcessStressRuleSet, queue_pressure: int, rework_risk: int) -> list[str]:
    actions = []
    if queue_pressure >= 70:
        actions.append("Review hand-offs and dependency sequencing before increasing volume.")
    if rework_risk >= 70:
        actions.append("Clarify exception handling and validation ownership before go-live.")
    if rule_set.system_count >= 3:
        actions.append("Check whether system touchpoints can be consolidated or automated.")
    if rule_set.validation_gate_count:
        actions.append("Define explicit validation entry/exit criteria and evidence retention.")
    return actions or ["Monitor during pilot; no elevated optimisation action from current registry signals."]
