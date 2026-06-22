"""KSB-style traceability and validation protocol evidence."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    path: str
    kind: str


class KsbTraceabilityRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ksb_id: str
    category: str
    capability: str
    evidence_claim: str
    delivered_features: list[str]
    evidence_refs: list[EvidenceReference]
    validation_status: str
    next_evidence: str


class ValidationProtocolRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_id: str
    component: str
    validation_method: str
    metric: str
    acceptance_rule: str
    current_evidence: list[EvidenceReference]
    status: str
    cadence: str
    boundary: str


class ValidationEvidenceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generated_at: str
    ksb_rows: list[KsbTraceabilityRow]
    validation_protocols: list[ValidationProtocolRow]
    summary: dict
    caveats: list[str]


def build_validation_evidence_report() -> ValidationEvidenceReport:
    ksb_rows = _ksb_rows()
    protocols = _validation_protocols()
    return ValidationEvidenceReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        ksb_rows=ksb_rows,
        validation_protocols=protocols,
        summary=_summary(ksb_rows, protocols),
        caveats=[
            "Rows are project evidence mappings; replace labels with official assessment KSB IDs when the final mapping is supplied.",
            "Validation protocols evidence disciplined analytics behaviour, not legal, financial or operational certainty.",
            "Live enterprise telemetry is still required before ROI, regulatory or process-risk claims can be treated as verified.",
        ],
    )


def _ksb_rows() -> list[KsbTraceabilityRow]:
    return [
        KsbTraceabilityRow(
            ksb_id="KSB-P1",
            category="Knowledge",
            capability="Knowledge governance and approved-source control",
            evidence_claim="The platform controls what knowledge can be used before answers or analytics rely on it.",
            delivered_features=["Source register", "Ingestion state", "Governance review", "Approved-source-only answering"],
            evidence_refs=[
                EvidenceReference(label="Governance tests", path="tests/test_governance.py", kind="test"),
                EvidenceReference(label="Build governance", path="docs/ways-of-working/Build-Governance.md", kind="doc"),
            ],
            validation_status="implemented",
            next_evidence="Add screenshots from Sprint 2 UAT showing failed/not-ingested and approved source states.",
        ),
        KsbTraceabilityRow(
            ksb_id="KSB-P2",
            category="Skill",
            capability="Analytics dashboarding and evidence-led insight",
            evidence_claim="The platform turns answer, governance, simulator and process events into explainable analytics.",
            delivered_features=["Analytics scorecard", "Knowledge gaps", "Governance history", "Process complexity", "Value dashboard"],
            evidence_refs=[
                EvidenceReference(label="Analytics tests", path="tests/test_analytics_aggregation.py", kind="test"),
                EvidenceReference(label="Value hypothesis", path="docs/evidence/value-hypothesis.md", kind="doc"),
            ],
            validation_status="implemented",
            next_evidence="Add UAT screenshots for Analytics page value and validation sections.",
        ),
        KsbTraceabilityRow(
            ksb_id="KSB-P3",
            category="Skill",
            capability="AI/RAG evaluation and hallucination control",
            evidence_claim="Answers are evaluated with expected behaviour classes, grounding metadata and benchmark probes.",
            delivered_features=["Grounding validation", "Hallucination probes", "Cited answers", "Audit traces"],
            evidence_refs=[
                EvidenceReference(label="Grounding evidence", path="docs/evidence/grounded-evidence.md", kind="doc"),
                EvidenceReference(label="Grounding tests", path="tests/test_grounding_eval.py", kind="test"),
            ],
            validation_status="implemented",
            next_evidence="Run the grounding evaluation after the full 52-pack corpus is ingested.",
        ),
        KsbTraceabilityRow(
            ksb_id="KSB-P4",
            category="Knowledge",
            capability="External context and regulatory triage",
            evidence_claim="Public snapshots and candidate review provide dated context without bypassing internal approval.",
            delivered_features=["GOV.UK snapshots", "Regulatory candidates", "Impact simulation"],
            evidence_refs=[
                EvidenceReference(label="Regulatory tests", path="tests/test_regulatory_candidates.py", kind="test"),
                EvidenceReference(label="Regulatory docs", path="docs/data-and-governance/regulatory-candidate-discovery.md", kind="doc"),
            ],
            validation_status="implemented",
            next_evidence="Manually review at least one candidate against a real GOV.UK snapshot during UAT.",
        ),
        KsbTraceabilityRow(
            ksb_id="KSB-P5",
            category="Skill",
            capability="Business value modelling and assumptions governance",
            evidence_claim="The value case is represented as inspectable assumptions plus separate observed value events.",
            delivered_features=["Value assumptions ledger", "Scenario metrics", "Value event capture"],
            evidence_refs=[
                EvidenceReference(label="Value tests", path="tests/test_value_analytics.py", kind="test"),
                EvidenceReference(label="Value ledger", path="src/assistant/value/default_assumptions.json", kind="data"),
            ],
            validation_status="implemented",
            next_evidence="Replace illustrative assumptions with sponsor-approved values when available.",
        ),
        KsbTraceabilityRow(
            ksb_id="KSB-P6",
            category="Behaviour",
            capability="Ethical handling of anonymised/synthetic evidence",
            evidence_claim="The project separates anonymised learning material, synthetic simulation data and aggregate telemetry.",
            delivered_features=["Synthetic data rules", "Anonymisation rules", "Simulator synthetic-only QA metadata"],
            evidence_refs=[
                EvidenceReference(label="Synthetic rules", path="docs/data-and-governance/synthetic-data-rules.md", kind="doc"),
                EvidenceReference(label="Simulator tests", path="tests/test_simulator_runner.py", kind="test"),
            ],
            validation_status="implemented",
            next_evidence="Confirm the full 52-pack ingestion batch follows the same source-register fields.",
        ),
    ]


def _validation_protocols() -> list[ValidationProtocolRow]:
    return [
        ValidationProtocolRow(
            protocol_id="VAL-RAG-001",
            component="Grounded answer generation",
            validation_method="Benchmark questions, expected behaviour classes and grounding metadata.",
            metric="Answer class accuracy, grounding score, citation count and faithfulness status.",
            acceptance_rule="In-scope answers should be grounded and cited; missing evidence must refuse rather than invent.",
            current_evidence=[
                EvidenceReference(label="Evaluation runner", path="src/assistant/eval/runner.py", kind="code"),
                EvidenceReference(label="Grounding evidence", path="docs/evidence/grounded-evidence.md", kind="doc"),
            ],
            status="active",
            cadence="Run after ingestion, retrieval or prompt changes.",
            boundary="Does not prove factual completeness beyond approved source coverage.",
        ),
        ValidationProtocolRow(
            protocol_id="VAL-SIM-001",
            component="Synthetic persona simulator",
            validation_method="Seeded scenario selection, replay fingerprints and expected behaviour matching.",
            metric="Expectation match rate, replay question fingerprint and synthetic-only metadata.",
            acceptance_rule="Replay must preserve config and question set; user traffic must stay separate from persona traffic.",
            current_evidence=[
                EvidenceReference(label="Simulator tests", path="tests/test_simulator_runner.py", kind="test"),
                EvidenceReference(label="Simulator scenarios", path="docs/benchmark/simulator-scenarios.json", kind="data"),
            ],
            status="active",
            cadence="Run before UAT and after scenario catalogue changes.",
            boundary="Synthetic outcomes test behaviour boundaries, not real user adoption.",
        ),
        ValidationProtocolRow(
            protocol_id="VAL-VALUE-001",
            component="Value analytics",
            validation_method="Assumptions ledger validation and observed value-event aggregation.",
            metric="Gross benefit, net benefit, payback, NPV, IRR and observed GBP-equivalent events.",
            acceptance_rule="Assumptions must remain inspectable; observed events must be aggregate and non-negative.",
            current_evidence=[
                EvidenceReference(label="Value tests", path="tests/test_value_analytics.py", kind="test"),
                EvidenceReference(label="Value hypothesis", path="docs/evidence/value-hypothesis.md", kind="doc"),
            ],
            status="active",
            cadence="Review whenever assumptions or value-event taxonomy changes.",
            boundary="Illustrative until validated with live commercial telemetry.",
        ),
        ValidationProtocolRow(
            protocol_id="VAL-REG-001",
            component="Regulatory impact simulation",
            validation_method="Term-based deterministic impact scan over approved sources and dated public snapshots.",
            metric="Impact score, affected source count, affected process areas and external context count.",
            acceptance_rule="Must present triage evidence and next actions without claiming confirmed legal change.",
            current_evidence=[
                EvidenceReference(label="Regulatory tests", path="tests/test_regulatory_candidates.py", kind="test"),
                EvidenceReference(label="Regulatory docs", path="docs/data-and-governance/regulatory-candidate-discovery.md", kind="doc"),
            ],
            status="active",
            cadence="Run when candidate terms, public snapshots or source packs change.",
            boundary="Not legal advice and not proof that an operating procedure changed.",
        ),
        ValidationProtocolRow(
            protocol_id="VAL-PROC-001",
            component="Process analytics",
            validation_method="Deterministic parsing, process registry extraction and complexity rubric tests.",
            metric="Process count, complexity score, key-person-risk score and rubric coverage.",
            acceptance_rule="Scores must expose signals and caveats; capped scores need signal-level review.",
            current_evidence=[
                EvidenceReference(label="Process tests", path="tests/test_process_complexity.py", kind="test"),
                EvidenceReference(label="Process registry tests", path="tests/test_process_registry.py", kind="test"),
            ],
            status="active",
            cadence="Run after pack ingestion or parser/rubric changes.",
            boundary="Diagnostic indicator only, not operational risk proof.",
        ),
    ]


def _summary(ksb_rows: list[KsbTraceabilityRow], protocols: list[ValidationProtocolRow]) -> dict:
    ksb_status = Counter(row.validation_status for row in ksb_rows)
    protocol_status = Counter(row.status for row in protocols)
    return {
        "ksb_count": len(ksb_rows),
        "validation_protocol_count": len(protocols),
        "ksb_by_status": dict(sorted(ksb_status.items())),
        "protocols_by_status": dict(sorted(protocol_status.items())),
        "evidence_reference_count": sum(len(row.evidence_refs) for row in ksb_rows)
        + sum(len(row.current_evidence) for row in protocols),
    }
