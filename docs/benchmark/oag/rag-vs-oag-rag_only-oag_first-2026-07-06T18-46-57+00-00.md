# RAG vs OAG Benchmark - DIAGNOSTIC RUN

Generated: 2026-07-06T18:46:57+00:00
Dataset: rag-vs-oag-v2 (69 questions)
Verdict status: diagnostic only
Metric leader: rag_only
Split filter: holdout
Category filter: aggregate, out_of_scope, structured_entity
ID filter: all
Split counts: holdout=24, tuning=45
Runs: 1
Fake generator: False
Model: ollama · qwen2.5:7b-instruct · nomic-embed-text
Code state: main@66a4b0b9 (dirty, 20 changed paths)
Total runtime: 75.2s
Diagnostic reasons: runs fewer than 3; split filter is holdout; category filter applied; not all default configs evaluated

## Overall By Configuration

| Config | Passed | Accuracy | Path hit | Stable | Mean latency | P95 latency |
|---|---:|---:|---:|---:|---:|---:|
| rag_only | 9/12 | 75% | 33% | 12/12 | 3.46s | 5.74s |
| oag_first | 8/12 | 67% | 33% | 12/12 | 2.80s | 5.21s |

## Accuracy By Split

| Config | Split | Passed | Accuracy | Path hit | Stable |
|---|---|---:|---:|---:|---:|
| rag_only | holdout | 9/12 | 75% | 33% | 12/12 |
| oag_first | holdout | 8/12 | 67% | 33% | 12/12 |

## Per-Category Accuracy

| Config | Category | Passed | Accuracy | Path hit |
|---|---|---:|---:|---:|
| rag_only | aggregate | 1/4 | 25% | 0% |
| rag_only | out_of_scope | 4/4 | 100% | 100% |
| rag_only | structured_entity | 4/4 | 100% | 0% |
| oag_first | aggregate | 1/4 | 25% | 0% |
| oag_first | out_of_scope | 4/4 | 100% | 100% |
| oag_first | structured_entity | 3/4 | 75% | 0% |

## Path Usage Matrix

| Config | oag | rag | rag+ontology | Other |
|---|---:|---:|---:|---:|
| rag_only | 0 | 12 | 0 | 0 |
| oag_first | 0 | 4 | 8 | 0 |

## Citation Types

| Config | document | ontology_object | process_registry | none |
|---|---:|---:|---:|---:|
| rag_only | 17 | 0 | 0 | 4 |
| oag_first | 9 | 17 | 0 | 4 |

## Interpretation Targets

- Structured relationship lift: +0%
- Aggregate lift: +0%
- Narrative loss versus RAG-only: +0%
- Out-of-scope preserved by OAG-first: 100%

## Failed Rows

| Config | Run | ID | Category | Path | Missed facts |
|---|---:|---|---|---|---|
| rag_only | 1 | aggregate-holdout-001 | aggregate | rag | mapping controls |
| rag_only | 1 | aggregate-holdout-002 | aggregate | rag | pricing setup; assortment setup |
| rag_only | 1 | aggregate-holdout-004 | aggregate | rag | operational packaging movement |
| oag_first | 1 | structured-entity-holdout-004 | structured_entity | rag+ontology | point-of-sale or consumer-system owner validates downstream article and tax behaviour |
| oag_first | 1 | aggregate-holdout-001 | aggregate | rag+ontology | mapping controls |
| oag_first | 1 | aggregate-holdout-002 | aggregate | rag+ontology | pricing setup |
| oag_first | 1 | aggregate-holdout-004 | aggregate | rag+ontology | operational packaging movement; packaging-waste reporting |

## Reviewer Notes

- Fake-generator runs validate benchmark arithmetic only and are not model-quality evidence.
- Real runs should use `--runs 3` so stability can be inspected before architectural decisions are made.
- Treat holdout split metrics as decision-grade for new OAG routing changes; tuning split metrics are regression/training evidence.
- OAG-only is intentionally expected to degrade on narrative questions; it is a boundary probe, not the target user mode.