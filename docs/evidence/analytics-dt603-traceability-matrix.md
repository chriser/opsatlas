# Analytics DT603 Traceability Matrix

Last updated: 2026-07-07

This matrix links the advanced analytics layer to the DT603 evidence story. It is intentionally practical: each row names the live artefact, the assessment-style outcome it supports, and the screenshot or export evidence to capture during final UAT.

## Matrix

| Analytic / surface | Live artefact | MLO / skill evidence | S52/S53 / evaluation evidence | Business decision evidence | Ethics / professionalism evidence |
|---|---|---|---|---|---|
| Raw analytics export and reproducibility pack | `/api/analytics/export`, `/api/analytics/export/reproducibility-pack`, Analytics Raw Data Export panel | MLO2 Digital Proficiency; MLO3 extract/explore/analyse | Reproducible datasets, field dictionary, methodology catalogue | Lets the assessor recompute headline numbers | GDPR/data minimisation note; raw prompts, answers and source text excluded |
| Methods and Models catalogue | `/api/analytics/methods`, `/api/analytics/explain`, Analytics Methods panel | MLO2 Creative Problem Solving; MLO3 Discipline Skills | Formula and substituted-value traces for each metric | Makes analytics decisions inspectable rather than black-box | Shows assumptions and boundaries for each metric |
| Forecasting and advanced statistics | `/api/analytics/forecast/{series_id}`, Forecast section | MLO3 analysis and interpretation | `VAL-ANL-FORECAST-001`; rolling-origin backtest MAE/MAPE/RMSE | Highlights likely future demand/refusal/quality pressure | Forecast boundary prevents operational certainty claims |
| Precision metrics | `/api/analytics/recurring-questions`, `/api/analytics/retrieval-health`, Analytics Precision section | MLO3 identify patterns and improvement opportunities | Deterministic grouping tests; retrieval-health failure-rate tests | Prioritises content repair based on repeated demand and failed retrievals | Bias limitation: lexical grouping can over/under group and requires human review |
| Improvement loop | `/api/analytics/improvements`, `/api/analytics/improvements/metrics`, Analytics Improvement Loop section | MLO2 iterative delivery and control; MLO1 professional ownership | Governed action log plus lifecycle metrics | Converts findings into owned source-improvement work | Closure requires linked source evidence or explicit decision |
| Validation / KSB evidence | `/api/analytics/validation-evidence`, Analytics Validation/KSB section | MLO1 Professionalism; MLO2 Digital Proficiency; MLO3 Discipline Skills | Protocol catalogue, ethics notes and KSB evidence history | Shows which platform claims are validated and where limits remain | GDPR, bias and sustainability notes are surfaced in the live report |
| RAG-vs-OAG benchmark | `docs/benchmark/oag/*`, planned `/api/analytics/oag-benchmark` | MLO2 architecture choice; MLO3 comparative evaluation | S52/S53 holdout scorecards, path/citation/latency/stability metrics | Justifies OAG-first for structured process questions | Diagnostic badges and holdout split avoid benchmark overclaiming |
| Live OAG operations | Planned Analytics OAG Operations section | MLO3 monitoring and operational insight | Answer-path telemetry, path x grounding matrix, latency by path | Shows whether OAG is helping real usage or creating coverage gaps | RAG fallback as coverage gap routes to governed improvement actions |

## Screenshot Checklist

Capture these final UAT screenshots after the remaining Analytics work is complete:

| Screenshot | Required view | Evidence purpose |
|---|---|---|
| Analytics Summary | Summary tab with headline metrics visible | Overall demand, quality, governance and value overview |
| Raw Data Export | Export panel with ethics boundary and reproducibility controls | Reproducibility and data-minimisation evidence |
| Methods and Models | Methods tab showing at least one expanded method/trace | Glass-box analytics and explainability |
| Forecast | Forecast tab with selected model and validation scorecard | Backtest-based forecasting validation |
| Precision | Precision tab with recurring questions or failed retrieval patterns | Content-improvement prioritisation |
| Improvement Loop | Improvement Loop tab with metrics and status board | Closed-loop governance from insight to action |
| Validation/KSB | Validation tab showing ethics notes and protocol metrics | KSB/DT603 traceability and ethical controls |
| RAG vs OAG | RAG-vs-OAG benchmark section once ANL-7 is delivered | Architecture comparison and S52/S53 evidence |
| OAG Operations | OAG Operations section once ANL-7 is delivered | Live answer-path monitoring and ontology coverage gaps |

## Boundaries

- These mappings are project evidence mappings until official KSB labels are supplied.
- Analytics outputs are decision-support evidence, not legal, operational or financial determinations.
- Synthetic replay, benchmark and real operator telemetry must stay visually and analytically separate.
- The current evidence index remains the top-level citation list for the final submission.
