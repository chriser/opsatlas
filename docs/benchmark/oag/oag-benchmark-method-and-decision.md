# OAG Benchmark Method and Decision

Date: 2026-07-06

Status: Current decision note for the OAG-6 structured holdout slice.

## Purpose

The RAG-vs-OAG benchmark measures whether ontology-assisted generation improves
OpsAtlas answers where process facts are structured enough to be represented as
objects, links and fact atoms.

The benchmark does not claim that ontology-only answering should replace
documents. It tests whether the production `oag_first` route improves structured
questions while preserving narrative and out-of-scope behaviour.

## Configurations

| Config | Meaning |
|---|---|
| `rag_only` | Standard approved-source retrieval and answer generation. |
| `oag_first` | Production route. Structured questions use ontology answer plans first; narrative and mixed questions use document RAG with optional ontology evidence. |
| `oag_only` | Boundary probe used in earlier runs. It is not a target user mode because narrative questions need document evidence. |

## Dataset

Current dataset: `tests/evaluation/rag_vs_oag_questions.json`

The current dataset contains tuning and holdout splits. The holdout split is the
decision signal for new OAG routing changes. Tuning rows are retained as
regression evidence and should not be treated as clean generalisation evidence
after they have informed routing or ontology-content changes.

Categories include:

- narrative
- structured entity
- structured relationship
- aggregate/list
- mixed ontology plus document questions
- out-of-scope refusal

## Harness

Runner: `scripts/evaluate_rag_vs_oag.py`

The harness records:

- accuracy by configuration, split and category;
- answer path usage (`rag`, `rag+ontology`, `oag`);
- citation type mix;
- stability across repeated runs;
- latency;
- failed row details and missed facts;
- code-state metadata.

Filtered single-run outputs are diagnostic only. Decision-grade OAG runs should
use repeated runs and the holdout split.

## Current Decision Evidence

Latest accepted OAG-6 holdout scorecard:

`docs/benchmark/oag/rag-vs-oag-rag_only-oag_first-2026-07-06T19-47-56+00-00.md`

Summary:

| Config | Passed | Accuracy | Path hit | Stability |
|---|---:|---:|---:|---:|
| `rag_only` | 47/72 | 65% | 50% | 20/24 |
| `oag_first` | 67/72 | 93% | 100% | 23/24 |

Per-category `oag_first` result:

| Category | Result |
|---|---:|
| Structured entity | 12/12 |
| Structured relationship | 12/12 |
| Aggregate/list | 12/12 |
| Out-of-scope | 12/12 |
| Narrative | 10/12 |
| Mixed | 9/12 |

Interpretation:

- OAG-first is validated as the default route for structured process facts.
- Deterministic ontology answers closed the structured entity, structured
  relationship and aggregate/list gaps.
- Remaining misses are narrative/mixed wording rows, not structured OAG object
  failures.
- RAG remains the right baseline for broad explanatory answers.

## Current Decision

Keep `oag_first` as the production Ask route.

Do not expose OAG-only as a user mode. Keep it as a benchmark boundary probe if
needed.

Do not chase perfect scorecard saturation by tuning against the current holdout.
Future OAG changes should either:

- add fresh holdout labels before tuning; or
- be scoped as regression maintenance rather than generalisation evidence.

## Known Limitations

- The July 6 scorecard is holdout decision evidence for the OAG-6 slice, not a
  universal proof that all questions should use ontology first.
- Narrative and mixed questions still rely on document RAG for context and
  explanation.
- Ontology quality depends on approved-source extraction and schema coverage.
- The benchmark uses synthetic/anonymised learning-pack content, not live
  enterprise telemetry.
