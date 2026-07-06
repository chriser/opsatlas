# RAG vs OAG Benchmark - rag_only best config

Generated: 2026-07-06T16:29:44+00:00
Dataset: rag-vs-oag-v2 (69 questions)
Split filter: holdout
Category filter: aggregate, out_of_scope, structured_entity
ID filter: all
Split counts: holdout=24, tuning=45
Runs: 1
Fake generator: False
Model: ollama · qwen2.5:7b-instruct · nomic-embed-text
Code state: main@a4fa2a32 (dirty, 30 changed paths)
Total runtime: 68.3s

## Overall By Configuration

| Config | Passed | Accuracy | Path hit | Stable | Mean latency | P95 latency |
|---|---:|---:|---:|---:|---:|---:|
| rag_only | 8/12 | 67% | 33% | 12/12 | 3.39s | 5.35s |
| oag_first | 7/12 | 58% | 33% | 12/12 | 2.31s | 3.59s |

## Accuracy By Split

| Config | Split | Passed | Accuracy | Path hit | Stable |
|---|---|---:|---:|---:|---:|
| rag_only | holdout | 8/12 | 67% | 33% | 12/12 |
| oag_first | holdout | 7/12 | 58% | 33% | 12/12 |

## Per-Category Accuracy

| Config | Category | Passed | Accuracy | Path hit |
|---|---|---:|---:|---:|
| rag_only | aggregate | 2/4 | 50% | 0% |
| rag_only | out_of_scope | 4/4 | 100% | 100% |
| rag_only | structured_entity | 2/4 | 50% | 0% |
| oag_first | aggregate | 1/4 | 25% | 0% |
| oag_first | out_of_scope | 4/4 | 100% | 100% |
| oag_first | structured_entity | 2/4 | 50% | 0% |

## Path Usage Matrix

| Config | oag | rag | rag+ontology | Other |
|---|---:|---:|---:|---:|
| rag_only | 0 | 12 | 0 | 0 |
| oag_first | 0 | 4 | 8 | 0 |

## Citation Types

| Config | document | ontology_object | process_registry | none |
|---|---:|---:|---:|---:|
| rag_only | 20 | 0 | 0 | 5 |
| oag_first | 15 | 4 | 0 | 4 |

## Interpretation Targets

- Structured relationship lift: +0%
- Aggregate lift: -25%
- Narrative loss versus RAG-only: +0%
- Out-of-scope preserved by OAG-first: 100%

## Failed Rows

| Config | Run | ID | Category | Path | Missed facts |
|---|---:|---|---|---|---|
| rag_only | 1 | structured-entity-holdout-002 | structured_entity | rag | architecture owner decides whether packaging needs separate article records |
| rag_only | 1 | structured-entity-holdout-004 | structured_entity | rag | point-of-sale or consumer-system owner validates downstream article and tax behaviour |
| rag_only | 1 | aggregate-holdout-002 | aggregate | rag | assortment setup |
| rag_only | 1 | aggregate-holdout-004 | aggregate | rag | operational packaging movement; packaging-waste reporting |
| oag_first | 1 | structured-entity-holdout-001 | structured_entity | rag+ontology | data governance owner approves purposeful article attributes |
| oag_first | 1 | structured-entity-holdout-004 | structured_entity | rag+ontology | point-of-sale or consumer-system owner validates downstream article and tax behaviour |
| oag_first | 1 | aggregate-holdout-001 | aggregate | rag+ontology | mapping controls |
| oag_first | 1 | aggregate-holdout-002 | aggregate | rag+ontology | pricing setup; assortment setup |
| oag_first | 1 | aggregate-holdout-004 | aggregate | rag+ontology | shelf-packaging information |

## Reviewer Notes

- Fake-generator runs validate benchmark arithmetic only and are not model-quality evidence.
- Real runs should use `--runs 3` so stability can be inspected before architectural decisions are made.
- Treat holdout split metrics as decision-grade for new OAG routing changes; tuning split metrics are regression/training evidence.
- OAG-only is intentionally expected to degrade on narrative questions; it is a boundary probe, not the target user mode.