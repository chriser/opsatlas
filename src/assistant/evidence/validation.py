"""KSB-style traceability and validation protocol evidence."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    path: str
    kind: str


class OfficialKsbReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_id: str
    category: str
    framework_area: str
    mapping_status: str
    rationale: str


class EvidenceHistoryEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_date: str
    event_type: str
    summary: str
    evidence_refs: list[EvidenceReference] = Field(default_factory=list)


class KsbTraceabilityRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ksb_id: str
    category: str
    capability: str
    evidence_claim: str
    delivered_features: list[str]
    evidence_refs: list[EvidenceReference]
    official_references: list[OfficialKsbReference] = Field(default_factory=list)
    evidence_history: list[EvidenceHistoryEntry] = Field(default_factory=list)
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
            official_references=[
                _official(
                    "OFFICIAL-KNOWLEDGE-GOVERNANCE",
                    "Knowledge",
                    "Data governance, quality controls and approved-use boundaries",
                    "mapped_provisional",
                    "Maps the project governance controls to the official knowledge evidence area once final IDs are supplied.",
                )
            ],
            evidence_history=[
                _history(
                    "2026-06-20",
                    "implemented",
                    "Source lifecycle and governance review controls were added to keep unapproved material out of answers.",
                    [EvidenceReference(label="Governance tests", path="tests/test_governance.py", kind="test")],
                ),
                _history(
                    "2026-06-22",
                    "uat_evidence",
                    "Sprint 2 UAT confirmed duplicate/not-ingested remediation behaviour before ticket closure.",
                    [EvidenceReference(label="Agent handover", path="docs/ways-of-working/Agent-Handover-Log.md", kind="doc")],
                ),
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
            official_references=[
                _official(
                    "OFFICIAL-SKILL-ANALYTICS",
                    "Skill",
                    "Analytics dashboarding, insight generation and evidence-led reporting",
                    "mapped_provisional",
                    "Links the analytics dashboard/reporting evidence to the official skill evidence area.",
                )
            ],
            evidence_history=[
                _history(
                    "2026-06-21",
                    "implemented",
                    "Analytics scorecard, governance history and process-complexity indicators were exposed in the UI.",
                    [EvidenceReference(label="Analytics aggregation tests", path="tests/test_analytics_aggregation.py", kind="test")],
                ),
                _history(
                    "2026-06-23",
                    "expanded",
                    "Value assumptions, exportable reports and process stress analytics strengthened the evidence spine.",
                    [EvidenceReference(label="Analytics report tests", path="tests/test_analytics_report.py", kind="test")],
                ),
            ],
            validation_status="implemented",
            next_evidence="Add UAT screenshots for Analytics page value and validation sections.",
        ),
        KsbTraceabilityRow(
            ksb_id="KSB-P3",
            category="Skill",
            capability="AI/RAG/OAG evaluation and hallucination control",
            evidence_claim=(
                "Answers are evaluated with expected behaviour classes, grounding metadata, benchmark probes and "
                "comparative architecture evidence."
            ),
            delivered_features=[
                "Grounding validation",
                "Hallucination probes",
                "Cited answers",
                "Audit traces",
                "RAG-vs-OAG comparative benchmark",
            ],
            evidence_refs=[
                EvidenceReference(label="Grounding evidence", path="docs/evidence/grounded-evidence.md", kind="doc"),
                EvidenceReference(label="Grounding tests", path="tests/test_grounding_eval.py", kind="test"),
                EvidenceReference(
                    label="RAG-vs-OAG method",
                    path="docs/benchmark/oag/oag-benchmark-method-and-decision.md",
                    kind="doc",
                ),
                EvidenceReference(
                    label="OAG-6 holdout scorecard",
                    path="docs/benchmark/oag/rag-vs-oag-rag_only-oag_first-2026-07-06T19-47-56+00-00.md",
                    kind="data",
                ),
            ],
            official_references=[
                _official(
                    "OFFICIAL-SKILL-AI-VALIDATION",
                    "Skill",
                    "AI evaluation, retrieval validation and hallucination-risk controls",
                    "mapped_provisional",
                    "Connects RAG evaluation and refusal behaviour to the official AI validation evidence area.",
                )
            ],
            evidence_history=[
                _history(
                    "2026-06-20",
                    "implemented",
                    "Benchmark probes and grounding validation were added to test answer/refusal expectations.",
                    [EvidenceReference(label="Grounding tests", path="tests/test_grounding_eval.py", kind="test")],
                ),
                _history(
                    "2026-06-22",
                    "uat_evidence",
                    "Sprint 2 UAT confirmed improved answer grounding for the tax-handling control question.",
                    [EvidenceReference(label="Grounding evidence", path="docs/evidence/grounded-evidence.md", kind="doc")],
                ),
                _history(
                    "2026-07-06",
                    "comparative_evaluation",
                    "OAG-first and RAG-only were benchmarked over the clean holdout split after OAG-6 structured routing improvements.",
                    [
                        EvidenceReference(
                            label="OAG-6 holdout scorecard",
                            path="docs/benchmark/oag/rag-vs-oag-rag_only-oag_first-2026-07-06T19-47-56+00-00.md",
                            kind="data",
                        )
                    ],
                ),
            ],
            validation_status="implemented",
            next_evidence="Keep adding fresh holdout rows before future OAG routing or ontology-content tuning.",
        ),
        KsbTraceabilityRow(
            ksb_id="KSB-P4",
            category="Knowledge",
            capability="External context and regulatory triage",
            evidence_claim="Public snapshots and candidate review provide dated context without bypassing internal approval.",
            delivered_features=["Public external-source snapshots", "Regulatory candidates", "Impact simulation"],
            evidence_refs=[
                EvidenceReference(label="Regulatory tests", path="tests/test_regulatory_candidates.py", kind="test"),
                EvidenceReference(label="Regulatory docs", path="docs/data-and-governance/regulatory-candidate-discovery.md", kind="doc"),
            ],
            official_references=[
                _official(
                    "OFFICIAL-KNOWLEDGE-EXTERNAL-CONTEXT",
                    "Knowledge",
                    "External context, regulatory scanning and change-impact triage",
                    "mapped_provisional",
                    "Maps public-source snapshots and impact simulation to the official context-analysis evidence area.",
                )
            ],
            evidence_history=[
                _history(
                    "2026-06-21",
                    "implemented",
                    "Public external-source snapshot registration and regulatory-candidate discovery were added with review status.",
                    [EvidenceReference(label="Regulatory tests", path="tests/test_regulatory_candidates.py", kind="test")],
                ),
                _history(
                    "2026-06-22",
                    "expanded",
                    "Impact simulation was added so candidate changes can be triaged against approved internal sources.",
                    [
                        EvidenceReference(
                            label="Regulatory docs",
                            path="docs/data-and-governance/regulatory-candidate-discovery.md",
                            kind="doc",
                        )
                    ],
                ),
            ],
            validation_status="implemented",
            next_evidence="Manually review at least one candidate against a real public external-source snapshot during UAT.",
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
            official_references=[
                _official(
                    "OFFICIAL-SKILL-VALUE-MODELLING",
                    "Skill",
                    "Commercial value modelling, assumptions management and benefits evidence",
                    "mapped_provisional",
                    "Links the assumptions ledger and value-event telemetry to the official value-analysis evidence area.",
                )
            ],
            evidence_history=[
                _history(
                    "2026-06-22",
                    "implemented",
                    "Assumption-led value scenarios and observed value-event aggregation were added.",
                    [EvidenceReference(label="Value tests", path="tests/test_value_analytics.py", kind="test")],
                ),
                _history(
                    "2026-06-23",
                    "expanded",
                    "Exportable analytics report now carries the value scenario into downloadable evidence.",
                    [EvidenceReference(label="Analytics report tests", path="tests/test_analytics_report.py", kind="test")],
                ),
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
            official_references=[
                _official(
                    "OFFICIAL-BEHAVIOUR-ETHICS",
                    "Behaviour",
                    "Ethical evidence handling, anonymisation and safe AI-assisted delivery",
                    "mapped_provisional",
                    "Maps anonymised/synthetic data separation and safe-use boundaries to the official behaviour evidence area.",
                )
            ],
            evidence_history=[
                _history(
                    "2026-06-20",
                    "implemented",
                    "Synthetic data rules and anonymisation boundaries were documented for safe testing.",
                    [EvidenceReference(label="Synthetic rules", path="docs/data-and-governance/synthetic-data-rules.md", kind="doc")],
                ),
                _history(
                    "2026-06-22",
                    "expanded",
                    "Synthetic pilot replay metadata was separated from real operator telemetry for analytics reporting.",
                    [EvidenceReference(label="Simulator tests", path="tests/test_simulator_runner.py", kind="test")],
                ),
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
            protocol_id="VAL-OAG-001",
            component="Ontology-assisted generation routing",
            validation_method=(
                "Comparative architecture evaluation over the same approved corpus using RAG-only "
                "and OAG-first routing across repeated holdout runs."
            ),
            metric=(
                "Per-category accuracy, answer-path usage, citation-type mix, latency and stability "
                "from tests/evaluation/rag_vs_oag_questions.json."
            ),
            acceptance_rule=(
                "OAG-first should improve structured entity, structured relationship and aggregate "
                "questions, preserve out-of-scope refusal and avoid material narrative degradation."
            ),
            current_evidence=[
                EvidenceReference(label="RAG-vs-OAG labels", path="tests/evaluation/rag_vs_oag_questions.json", kind="data"),
                EvidenceReference(label="RAG-vs-OAG harness", path="scripts/evaluate_rag_vs_oag.py", kind="code"),
                EvidenceReference(
                    label="RAG-vs-OAG method",
                    path="docs/benchmark/oag/oag-benchmark-method-and-decision.md",
                    kind="doc",
                ),
                EvidenceReference(
                    label="OAG-6 holdout scorecard",
                    path="docs/benchmark/oag/rag-vs-oag-rag_only-oag_first-2026-07-06T19-47-56+00-00.md",
                    kind="data",
                ),
            ],
            status="active",
            cadence="Run after ontology schema, routing, prompt or ingestion changes.",
            boundary=(
                "This isolates routing as the variable for S14/S52/S53 evidence; it does not prove "
                "complete process knowledge or legal correctness."
            ),
        ),
        ValidationProtocolRow(
            protocol_id="VAL-EAM-001",
            component="Enterprise Activity Model projection",
            validation_method=(
                "Deterministic model projection over the governed ontology, plus synthetic scale fixture and SVG render checks."
            ),
            metric=(
                "Coverage score, domain/stage coverage, gap/overlap/clash counts, evidence-confidence distribution, "
                "source provenance and render performance over a 60-process fixture."
            ),
            acceptance_rule=(
                "EAM must rebuild from current ontology state, keep finding output bounded/ranked, render all four views, "
                "show source provenance and stay within the scale-test performance budget."
            ),
            current_evidence=[
                EvidenceReference(label="EAM projection tests", path="tests/test_eam_model.py", kind="test"),
                EvidenceReference(label="EAM API tests", path="tests/test_eam_api.py", kind="test"),
                EvidenceReference(label="EAM scale tests", path="tests/test_eam_scale.py", kind="test"),
                EvidenceReference(label="EAM dynamic update tests", path="tests/test_eam_dynamic_update.py", kind="test"),
                EvidenceReference(label="EAM architecture note", path="docs/architecture/enterprise-activity-model.md", kind="doc"),
            ],
            status="active",
            cadence="Run after ontology schema, projection, renderer, source-ingestion or EAM UI changes.",
            boundary=(
                "This validates deterministic visual analytics over approved ontology evidence; it does not prove live "
                "operating-model completeness or operational risk."
            ),
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



def _official(reference_id: str, category: str, framework_area: str, mapping_status: str, rationale: str) -> OfficialKsbReference:
    return OfficialKsbReference(
        reference_id=reference_id,
        category=category,
        framework_area=framework_area,
        mapping_status=mapping_status,
        rationale=rationale,
    )


def _history(
    event_date: str,
    event_type: str,
    summary: str,
    evidence_refs: list[EvidenceReference],
) -> EvidenceHistoryEntry:
    return EvidenceHistoryEntry(
        event_date=event_date,
        event_type=event_type,
        summary=summary,
        evidence_refs=evidence_refs,
    )


def _summary(ksb_rows: list[KsbTraceabilityRow], protocols: list[ValidationProtocolRow]) -> dict:
    ksb_status = Counter(row.validation_status for row in ksb_rows)
    protocol_status = Counter(row.status for row in protocols)
    official_status = Counter(ref.mapping_status for row in ksb_rows for ref in row.official_references)
    return {
        "ksb_count": len(ksb_rows),
        "validation_protocol_count": len(protocols),
        "ksb_by_status": dict(sorted(ksb_status.items())),
        "protocols_by_status": dict(sorted(protocol_status.items())),
        "official_reference_count": sum(len(row.official_references) for row in ksb_rows),
        "official_references_by_status": dict(sorted(official_status.items())),
        "evidence_history_event_count": sum(len(row.evidence_history) for row in ksb_rows),
        "evidence_reference_count": sum(len(row.evidence_refs) for row in ksb_rows)
        + sum(len(row.current_evidence) for row in protocols)
        + sum(len(entry.evidence_refs) for row in ksb_rows for entry in row.evidence_history),
    }
