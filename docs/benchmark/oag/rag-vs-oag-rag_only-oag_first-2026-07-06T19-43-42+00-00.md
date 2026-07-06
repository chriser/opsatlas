# RAG vs OAG Benchmark - DIAGNOSTIC RUN

Generated: 2026-07-06T19:43:42+00:00
Dataset: rag-vs-oag-v2 (69 questions)
Verdict status: diagnostic only
Metric leader: oag_first
Split filter: holdout
Category filter: structured_relationship
ID filter: all
Split counts: holdout=24, tuning=45
Runs: 1
Fake generator: False
Model: ollama · qwen2.5:7b-instruct · nomic-embed-text
Code state: main@43f4b240 (dirty, 32 changed paths)
Total runtime: 9.4s
Diagnostic reasons: runs fewer than 3; split filter is holdout; category filter applied; not all default configs evaluated

## Overall By Configuration

| Config | Passed | Accuracy | Path hit | Stable | Mean latency | P95 latency |
|---|---:|---:|---:|---:|---:|---:|
| rag_only | 2/4 | 50% | 0% | 4/4 | 2.29s | 4.20s |
| oag_first | 4/4 | 100% | 100% | 4/4 | 0.05s | 0.06s |

## Accuracy By Split

| Config | Split | Passed | Accuracy | Path hit | Stable |
|---|---|---:|---:|---:|---:|
| rag_only | holdout | 2/4 | 50% | 0% | 4/4 |
| oag_first | holdout | 4/4 | 100% | 100% | 4/4 |

## Per-Category Accuracy

| Config | Category | Passed | Accuracy | Path hit |
|---|---|---:|---:|---:|
| rag_only | structured_relationship | 2/4 | 50% | 0% |
| oag_first | structured_relationship | 4/4 | 100% | 100% |

## Path Usage Matrix

| Config | oag | rag | rag+ontology | Other |
|---|---:|---:|---:|---:|
| rag_only | 0 | 4 | 0 | 0 |
| oag_first | 4 | 0 | 0 | 0 |

## Citation Types

| Config | document | ontology_object | process_registry | none |
|---|---:|---:|---:|---:|
| rag_only | 9 | 0 | 0 | 0 |
| oag_first | 0 | 17 | 0 | 0 |

## Interpretation Targets

- Structured relationship lift: +50%
- Aggregate lift: +0%
- Narrative loss versus RAG-only: +0%
- Out-of-scope preserved by OAG-first: 0%

## Failed Rows

| Config | Run | ID | Category | Path | Missed facts |
|---|---:|---|---|---|---|
| rag_only | 1 | structured-relationship-holdout-002 | structured_relationship | rag | site sellability depends on pricing and assortment associations |
| rag_only | 1 | structured-relationship-holdout-004 | structured_relationship | rag | downstream code-based logic still needs accurate special item mapping |

## Reviewer Notes

- Fake-generator runs validate benchmark arithmetic only and are not model-quality evidence.
- Real runs should use `--runs 3` so stability can be inspected before architectural decisions are made.
- Treat holdout split metrics as decision-grade for new OAG routing changes; tuning split metrics are regression/training evidence.
- OAG-only is intentionally expected to degrade on narrative questions; it is a boundary probe, not the target user mode.