# RAG vs OAG Benchmark - DIAGNOSTIC RUN

Generated: 2026-07-06T19:35:47+00:00
Dataset: rag-vs-oag-v2 (69 questions)
Verdict status: diagnostic only
Metric leader: oag_first
Split filter: holdout
Category filter: aggregate, out_of_scope, structured_entity
ID filter: all
Split counts: holdout=24, tuning=45
Runs: 1
Fake generator: False
Model: ollama · qwen2.5:7b-instruct · nomic-embed-text
Code state: main@43f4b240 (dirty, 28 changed paths)
Total runtime: 41.8s
Diagnostic reasons: runs fewer than 3; split filter is holdout; category filter applied; not all default configs evaluated

## Overall By Configuration

| Config | Passed | Accuracy | Path hit | Stable | Mean latency | P95 latency |
|---|---:|---:|---:|---:|---:|---:|
| rag_only | 7/12 | 58% | 33% | 12/12 | 3.44s | 6.18s |
| oag_first | 12/12 | 100% | 100% | 12/12 | 0.05s | 0.06s |

## Accuracy By Split

| Config | Split | Passed | Accuracy | Path hit | Stable |
|---|---|---:|---:|---:|---:|
| rag_only | holdout | 7/12 | 58% | 33% | 12/12 |
| oag_first | holdout | 12/12 | 100% | 100% | 12/12 |

## Per-Category Accuracy

| Config | Category | Passed | Accuracy | Path hit |
|---|---|---:|---:|---:|
| rag_only | aggregate | 1/4 | 25% | 0% |
| rag_only | out_of_scope | 4/4 | 100% | 100% |
| rag_only | structured_entity | 2/4 | 50% | 0% |
| oag_first | aggregate | 4/4 | 100% | 100% |
| oag_first | out_of_scope | 4/4 | 100% | 100% |
| oag_first | structured_entity | 4/4 | 100% | 100% |

## Path Usage Matrix

| Config | oag | rag | rag+ontology | Other |
|---|---:|---:|---:|---:|
| rag_only | 0 | 12 | 0 | 0 |
| oag_first | 8 | 4 | 0 | 0 |

## Citation Types

| Config | document | ontology_object | process_registry | none |
|---|---:|---:|---:|---:|
| rag_only | 17 | 0 | 0 | 4 |
| oag_first | 0 | 15 | 0 | 4 |

## Interpretation Targets

- Structured relationship lift: +0%
- Aggregate lift: +75%
- Narrative loss versus RAG-only: +0%
- Out-of-scope preserved by OAG-first: 100%

## Failed Rows

| Config | Run | ID | Category | Path | Missed facts |
|---|---:|---|---|---|---|
| rag_only | 1 | structured-entity-holdout-001 | structured_entity | rag | data governance owner approves purposeful article attributes |
| rag_only | 1 | structured-entity-holdout-004 | structured_entity | rag | point-of-sale or consumer-system owner validates downstream article and tax behaviour |
| rag_only | 1 | aggregate-holdout-001 | aggregate | rag | mapping controls |
| rag_only | 1 | aggregate-holdout-002 | aggregate | rag | pricing setup; assortment setup |
| rag_only | 1 | aggregate-holdout-004 | aggregate | rag | operational packaging movement |

## Reviewer Notes

- Fake-generator runs validate benchmark arithmetic only and are not model-quality evidence.
- Real runs should use `--runs 3` so stability can be inspected before architectural decisions are made.
- Treat holdout split metrics as decision-grade for new OAG routing changes; tuning split metrics are regression/training evidence.
- OAG-only is intentionally expected to degrade on narrative questions; it is a boundary probe, not the target user mode.