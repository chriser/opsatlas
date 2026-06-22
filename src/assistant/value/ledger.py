"""Assumptions-led value analytics for the platform."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ..analytics.events import AnalyticsEvent

DEFAULT_LEDGER_PATH = Path(__file__).with_name("default_assumptions.json")

REQUIRED_METRICS = {
    "annual_workstreams",
    "affected_share",
    "delay_reduction_months",
    "monthly_delay_value_gbp",
    "one_off_capex_gbp",
    "annual_opex_gbp",
    "discount_rate",
    "horizon_years",
}


class ValueScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    label: str
    description: str
    confidence: str


class ValueAssumption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assumption_id: str
    scenario_id: str
    driver: str
    metric: str
    label: str
    value: float
    unit: str
    confidence: str
    rationale: str
    source: str


class ValueLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    scenarios: list[ValueScenario]
    assumptions: list[ValueAssumption]


class ValueScenarioMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    label: str
    confidence: str
    gross_annual_benefit_gbp: float
    annual_opex_gbp: float
    net_annual_benefit_gbp: float
    one_off_capex_gbp: float
    simple_payback_years: float | None
    npv_gbp: float
    irr: float | None
    horizon_years: int
    formula: str


class ValueEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=2, max_length=120)
    value_driver: str = Field(default="time_saved", min_length=2, max_length=80)
    value_estimate: float = Field(ge=0)
    process_area: str = Field(default="", max_length=120)
    scenario_id: str = Field(default="base", min_length=2, max_length=80)
    unit: str = Field(default="GBP", max_length=40)
    confidence: str = Field(default="review", max_length=40)
    evidence_type: str = Field(default="operator_estimate", max_length=80)


class ValueReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    active_scenario_id: str
    scenarios: list[ValueScenario]
    assumptions: list[ValueAssumption]
    metrics: list[ValueScenarioMetric]
    telemetry: dict
    driver_options: list[str]
    rubric: dict[str, str]


def load_value_ledger(path: str | Path | None = None) -> ValueLedger:
    ledger_path = Path(path) if path is not None else DEFAULT_LEDGER_PATH
    ledger = ValueLedger.model_validate(json.loads(ledger_path.read_text(encoding="utf-8")))
    _validate_required_metrics(ledger)
    return ledger


def build_value_report(events: list[AnalyticsEvent], ledger: ValueLedger | None = None) -> ValueReport:
    value_ledger = ledger or load_value_ledger()
    value_events = [event for event in events if event.event_type == "value_event_recorded"]
    assumption_drivers = {assumption.driver for assumption in value_ledger.assumptions}
    event_drivers = {event.value_driver or "" for event in value_events}
    driver_options = sorted((assumption_drivers | event_drivers) - {""})
    return ValueReport(
        schema_version=value_ledger.schema_version,
        active_scenario_id="base",
        scenarios=value_ledger.scenarios,
        assumptions=value_ledger.assumptions,
        metrics=[_scenario_metric(scenario, value_ledger.assumptions) for scenario in value_ledger.scenarios],
        telemetry=_telemetry(value_events),
        driver_options=driver_options,
        rubric={
            "boundary": "Assumptions-led and illustrative until validated with live enterprise telemetry.",
            "gross_formula": "workstreams x affected share x delay months saved x monthly value of avoided delay.",
            "net_formula": "gross annual benefit minus annual opex; capex is used for payback, NPV and IRR.",
            "event_rule": "Value events capture operator-estimated GBP-equivalent benefits without raw prompts, answers or source text.",
        },
    )


def _validate_required_metrics(ledger: ValueLedger) -> None:
    scenario_ids = {scenario.scenario_id for scenario in ledger.scenarios}
    missing_scenarios = {assumption.scenario_id for assumption in ledger.assumptions} - scenario_ids
    if missing_scenarios:
        raise ValueError(f"Value assumptions reference unknown scenarios: {sorted(missing_scenarios)}")
    for scenario_id in sorted(scenario_ids):
        metrics = {assumption.metric for assumption in ledger.assumptions if assumption.scenario_id == scenario_id}
        missing = sorted(REQUIRED_METRICS - metrics)
        if missing:
            raise ValueError(f"Value scenario {scenario_id} is missing required assumptions: {missing}")


def _scenario_metric(scenario: ValueScenario, assumptions: list[ValueAssumption]) -> ValueScenarioMetric:
    values = {assumption.metric: assumption.value for assumption in assumptions if assumption.scenario_id == scenario.scenario_id}
    gross = (
        values["annual_workstreams"]
        * values["affected_share"]
        * values["delay_reduction_months"]
        * values["monthly_delay_value_gbp"]
    )
    opex = values["annual_opex_gbp"]
    capex = values["one_off_capex_gbp"]
    horizon_years = int(values["horizon_years"])
    net = gross - opex
    payback = capex / net if net > 0 else None
    npv = _npv(capex=capex, annual_net=net, discount_rate=values["discount_rate"], horizon_years=horizon_years)
    return ValueScenarioMetric(
        scenario_id=scenario.scenario_id,
        label=scenario.label,
        confidence=scenario.confidence,
        gross_annual_benefit_gbp=round(gross, 2),
        annual_opex_gbp=round(opex, 2),
        net_annual_benefit_gbp=round(net, 2),
        one_off_capex_gbp=round(capex, 2),
        simple_payback_years=round(payback, 2) if payback is not None else None,
        npv_gbp=round(npv, 2),
        irr=_irr(capex=capex, annual_net=net, horizon_years=horizon_years),
        horizon_years=horizon_years,
        formula="annual_workstreams * affected_share * delay_reduction_months * monthly_delay_value_gbp",
    )


def _telemetry(events: list[AnalyticsEvent]) -> dict:
    by_driver_count: Counter = Counter()
    by_driver_value: dict[str, float] = defaultdict(float)
    rows = []
    for event in sorted(events, key=lambda item: item.timestamp, reverse=True):
        driver = event.value_driver or "unclassified"
        estimate = float(event.value_estimate or 0)
        by_driver_count[driver] += 1
        by_driver_value[driver] += estimate
        rows.append({
            "event_id": event.event_id,
            "timestamp": event.timestamp,
            "label": str(event.metadata.get("label") or "Value event"),
            "value_driver": driver,
            "process_area": event.process_area or "",
            "scenario_id": str(event.metadata.get("scenario_id") or ""),
            "unit": str(event.metadata.get("unit") or "GBP"),
            "confidence": str(event.metadata.get("confidence") or "review"),
            "value_estimate": round(estimate, 2),
        })
    return {
        "event_count": len(events),
        "observed_total_gbp": round(sum(float(event.value_estimate or 0) for event in events), 2),
        "by_driver": [
            {"value_driver": driver, "count": by_driver_count[driver], "value_estimate": round(by_driver_value[driver], 2)}
            for driver in sorted(by_driver_count, key=lambda item: (-by_driver_value[item], item))
        ],
        "recent_events": rows[:20],
    }


def _npv(*, capex: float, annual_net: float, discount_rate: float, horizon_years: int) -> float:
    return -capex + sum(annual_net / ((1 + discount_rate) ** year) for year in range(1, horizon_years + 1))


def _irr(*, capex: float, annual_net: float, horizon_years: int) -> float | None:
    if capex <= 0 or annual_net <= 0 or horizon_years <= 0:
        return None

    cashflows = [-capex, *([annual_net] * horizon_years)]

    def value(rate: float) -> float:
        return sum(cashflow / ((1 + rate) ** index) for index, cashflow in enumerate(cashflows))

    low, high = -0.99, 10.0
    if value(low) * value(high) > 0:
        return None
    for _ in range(80):
        midpoint = (low + high) / 2
        if value(low) * value(midpoint) <= 0:
            high = midpoint
        else:
            low = midpoint
    return round((low + high) / 2, 4)
