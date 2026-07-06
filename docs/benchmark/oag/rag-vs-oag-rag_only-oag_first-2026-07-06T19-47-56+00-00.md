# RAG vs OAG Benchmark - DIAGNOSTIC RUN

Generated: 2026-07-06T19:47:56+00:00
Dataset: rag-vs-oag-v2 (69 questions)
Verdict status: diagnostic only
Metric leader: oag_first
Split filter: holdout
Category filter: all
ID filter: all
Split counts: holdout=24, tuning=45
Runs: 3
Fake generator: False
Model: ollama · qwen2.5:7b-instruct · nomic-embed-text
Code state: main@43f4b240 (dirty, 34 changed paths)
Total runtime: 239.9s
Diagnostic reasons: split filter is holdout; not all default configs evaluated

## Overall By Configuration

| Config | Passed | Accuracy | Path hit | Stable | Mean latency | P95 latency |
|---|---:|---:|---:|---:|---:|---:|
| rag_only | 47/72 | 65% | 50% | 20/24 | 2.12s | 4.01s |
| oag_first | 67/72 | 93% | 100% | 23/24 | 1.21s | 3.93s |

## Accuracy By Split

| Config | Split | Passed | Accuracy | Path hit | Stable |
|---|---|---:|---:|---:|---:|
| rag_only | holdout | 47/72 | 65% | 50% | 20/24 |
| oag_first | holdout | 67/72 | 93% | 100% | 23/24 |

## Per-Category Accuracy

| Config | Category | Passed | Accuracy | Path hit |
|---|---|---:|---:|---:|
| rag_only | aggregate | 3/12 | 25% | 0% |
| rag_only | mixed | 11/12 | 92% | 100% |
| rag_only | narrative | 9/12 | 75% | 100% |
| rag_only | out_of_scope | 12/12 | 100% | 100% |
| rag_only | structured_entity | 6/12 | 50% | 0% |
| rag_only | structured_relationship | 6/12 | 50% | 0% |
| oag_first | aggregate | 12/12 | 100% | 100% |
| oag_first | mixed | 9/12 | 75% | 100% |
| oag_first | narrative | 10/12 | 83% | 100% |
| oag_first | out_of_scope | 12/12 | 100% | 100% |
| oag_first | structured_entity | 12/12 | 100% | 100% |
| oag_first | structured_relationship | 12/12 | 100% | 100% |

## Path Usage Matrix

| Config | oag | rag | rag+ontology | Other |
|---|---:|---:|---:|---:|
| rag_only | 0 | 72 | 0 | 0 |
| oag_first | 36 | 12 | 24 | 0 |

## Citation Types

| Config | document | ontology_object | process_registry | none |
|---|---:|---:|---:|---:|
| rag_only | 133 | 0 | 0 | 13 |
| oag_first | 49 | 160 | 0 | 12 |

## Interpretation Targets

- Structured relationship lift: +50%
- Aggregate lift: +75%
- Narrative loss versus RAG-only: +8%
- Out-of-scope preserved by OAG-first: 100%

## Failed Rows

| Config | Run | ID | Category | Path | Missed facts |
|---|---:|---|---|---|---|
| rag_only | 1 | structured-entity-holdout-001 | structured_entity | rag | data governance owner approves purposeful article attributes |
| rag_only | 1 | structured-entity-holdout-002 | structured_entity | rag | architecture owner decides whether packaging needs separate article records |
| rag_only | 1 | structured-entity-holdout-004 | structured_entity | rag | point-of-sale or consumer-system owner validates downstream article and tax behaviour |
| rag_only | 1 | structured-relationship-holdout-002 | structured_relationship | rag | site sellability depends on pricing and assortment associations |
| rag_only | 1 | structured-relationship-holdout-004 | structured_relationship | rag | downstream code-based logic still needs accurate special item mapping |
| rag_only | 1 | aggregate-holdout-001 | aggregate | rag | mapping controls |
| rag_only | 1 | aggregate-holdout-002 | aggregate | rag | pricing setup; assortment setup |
| rag_only | 1 | aggregate-holdout-004 | aggregate | rag | operational packaging movement |
| rag_only | 1 | narrative-holdout-002 | narrative | rag | a supplier can be active while contracts mapping or controls remain incomplete |
| oag_first | 1 | narrative-holdout-001 | narrative | rag+ontology | unclear attributes can become unmanaged data graveyard content |
| oag_first | 1 | mixed-holdout-002 | mixed | rag+ontology | unmanaged list creation can cause duplication confusion or unused lists |
| rag_only | 2 | structured-entity-holdout-001 | structured_entity | rag | data governance owner approves purposeful article attributes |
| rag_only | 2 | structured-entity-holdout-004 | structured_entity | rag | point-of-sale or consumer-system owner validates downstream article and tax behaviour |
| rag_only | 2 | structured-relationship-holdout-002 | structured_relationship | rag | site sellability depends on pricing and assortment associations |
| rag_only | 2 | structured-relationship-holdout-004 | structured_relationship | rag | downstream code-based logic still needs accurate special item mapping |
| rag_only | 2 | aggregate-holdout-001 | aggregate | rag | mapping controls |
| rag_only | 2 | aggregate-holdout-002 | aggregate | rag | pricing setup; assortment setup |
| rag_only | 2 | aggregate-holdout-004 | aggregate | rag | operational packaging movement; packaging-waste reporting |
| rag_only | 2 | narrative-holdout-002 | narrative | rag | a supplier can be active while contracts mapping or controls remain incomplete |
| oag_first | 2 | mixed-holdout-002 | mixed | rag+ontology | unmanaged list creation can cause duplication confusion or unused lists |
| rag_only | 3 | structured-entity-holdout-004 | structured_entity | rag | point-of-sale or consumer-system owner validates downstream article and tax behaviour |
| rag_only | 3 | structured-relationship-holdout-002 | structured_relationship | rag | site sellability depends on pricing and assortment associations |
| rag_only | 3 | structured-relationship-holdout-004 | structured_relationship | rag | downstream code-based logic still needs accurate special item mapping |
| rag_only | 3 | aggregate-holdout-001 | aggregate | rag | mapping controls |
| rag_only | 3 | aggregate-holdout-002 | aggregate | rag | pricing setup; assortment setup |
| rag_only | 3 | aggregate-holdout-004 | aggregate | rag | operational packaging movement; packaging-waste reporting |
| rag_only | 3 | narrative-holdout-002 | narrative | rag | a supplier can be active while contracts mapping or controls remain incomplete |
| rag_only | 3 | mixed-holdout-002 | mixed | rag | unmanaged list creation can cause duplication confusion or unused lists |
| oag_first | 3 | narrative-holdout-001 | narrative | rag+ontology | unclear attributes can become unmanaged data graveyard content |
| oag_first | 3 | mixed-holdout-002 | mixed | rag+ontology | unmanaged list creation can cause duplication confusion or unused lists |

## Reviewer Notes

- Fake-generator runs validate benchmark arithmetic only and are not model-quality evidence.
- Real runs should use `--runs 3` so stability can be inspected before architectural decisions are made.
- Treat holdout split metrics as decision-grade for new OAG routing changes; tuning split metrics are regression/training evidence.
- OAG-only is intentionally expected to degrade on narrative questions; it is a boundary probe, not the target user mode.