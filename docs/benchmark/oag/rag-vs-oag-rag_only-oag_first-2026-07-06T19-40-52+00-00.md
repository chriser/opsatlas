# RAG vs OAG Benchmark - DIAGNOSTIC RUN

Generated: 2026-07-06T19:40:52+00:00
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
Code state: main@43f4b240 (dirty, 30 changed paths)
Total runtime: 287.9s
Diagnostic reasons: split filter is holdout; not all default configs evaluated

## Overall By Configuration

| Config | Passed | Accuracy | Path hit | Stable | Mean latency | P95 latency |
|---|---:|---:|---:|---:|---:|---:|
| rag_only | 48/72 | 67% | 50% | 21/24 | 2.64s | 5.54s |
| oag_first | 57/72 | 79% | 100% | 24/24 | 1.36s | 4.23s |

## Accuracy By Split

| Config | Split | Passed | Accuracy | Path hit | Stable |
|---|---|---:|---:|---:|---:|
| rag_only | holdout | 48/72 | 67% | 50% | 21/24 |
| oag_first | holdout | 57/72 | 79% | 100% | 24/24 |

## Per-Category Accuracy

| Config | Category | Passed | Accuracy | Path hit |
|---|---|---:|---:|---:|
| rag_only | aggregate | 3/12 | 25% | 0% |
| rag_only | mixed | 9/12 | 75% | 100% |
| rag_only | narrative | 11/12 | 92% | 100% |
| rag_only | out_of_scope | 12/12 | 100% | 100% |
| rag_only | structured_entity | 7/12 | 58% | 0% |
| rag_only | structured_relationship | 6/12 | 50% | 0% |
| oag_first | aggregate | 12/12 | 100% | 100% |
| oag_first | mixed | 9/12 | 75% | 100% |
| oag_first | narrative | 9/12 | 75% | 100% |
| oag_first | out_of_scope | 12/12 | 100% | 100% |
| oag_first | structured_entity | 12/12 | 100% | 100% |
| oag_first | structured_relationship | 3/12 | 25% | 100% |

## Path Usage Matrix

| Config | oag | rag | rag+ontology | Other |
|---|---:|---:|---:|---:|
| rag_only | 0 | 72 | 0 | 0 |
| oag_first | 36 | 12 | 24 | 0 |

## Citation Types

| Config | document | ontology_object | process_registry | none |
|---|---:|---:|---:|---:|
| rag_only | 134 | 0 | 0 | 12 |
| oag_first | 56 | 190 | 0 | 12 |

## Interpretation Targets

- Structured relationship lift: -25%
- Aggregate lift: +75%
- Narrative loss versus RAG-only: -17%
- Out-of-scope preserved by OAG-first: 100%

## Failed Rows

| Config | Run | ID | Category | Path | Missed facts |
|---|---:|---|---|---|---|
| rag_only | 1 | structured-entity-holdout-004 | structured_entity | rag | point-of-sale or consumer-system owner validates downstream article and tax behaviour |
| rag_only | 1 | structured-relationship-holdout-002 | structured_relationship | rag | site sellability depends on pricing and assortment associations |
| rag_only | 1 | structured-relationship-holdout-004 | structured_relationship | rag | downstream code-based logic still needs accurate special item mapping |
| rag_only | 1 | aggregate-holdout-001 | aggregate | rag | mapping controls |
| rag_only | 1 | aggregate-holdout-002 | aggregate | rag | pricing setup; assortment setup |
| rag_only | 1 | aggregate-holdout-004 | aggregate | rag | operational packaging movement; packaging-waste reporting |
| rag_only | 1 | mixed-holdout-002 | mixed | rag | unmanaged list creation can cause duplication confusion or unused lists |
| oag_first | 1 | structured-relationship-holdout-001 | structured_relationship | oag | contracts mapping and readiness controls must be complete |
| oag_first | 1 | structured-relationship-holdout-002 | structured_relationship | oag | site sellability depends on pricing and assortment associations |
| oag_first | 1 | structured-relationship-holdout-003 | structured_relationship | oag | format mandatory-field and referential checks run before processing |
| oag_first | 1 | narrative-holdout-001 | narrative | rag+ontology | unclear attributes can become unmanaged data graveyard content |
| oag_first | 1 | mixed-holdout-002 | mixed | rag+ontology | unmanaged list creation can cause duplication confusion or unused lists |
| rag_only | 2 | structured-entity-holdout-001 | structured_entity | rag | data governance owner approves purposeful article attributes |
| rag_only | 2 | structured-entity-holdout-004 | structured_entity | rag | point-of-sale or consumer-system owner validates downstream article and tax behaviour |
| rag_only | 2 | structured-relationship-holdout-002 | structured_relationship | rag | site sellability depends on pricing and assortment associations |
| rag_only | 2 | structured-relationship-holdout-004 | structured_relationship | rag | downstream code-based logic still needs accurate special item mapping |
| rag_only | 2 | aggregate-holdout-001 | aggregate | rag | mapping controls |
| rag_only | 2 | aggregate-holdout-002 | aggregate | rag | pricing setup; assortment setup |
| rag_only | 2 | aggregate-holdout-004 | aggregate | rag | operational packaging movement |
| rag_only | 2 | narrative-holdout-002 | narrative | rag | a supplier can be active while contracts mapping or controls remain incomplete |
| rag_only | 2 | mixed-holdout-002 | mixed | rag | unmanaged list creation can cause duplication confusion or unused lists |
| oag_first | 2 | structured-relationship-holdout-001 | structured_relationship | oag | contracts mapping and readiness controls must be complete |
| oag_first | 2 | structured-relationship-holdout-002 | structured_relationship | oag | site sellability depends on pricing and assortment associations |
| oag_first | 2 | structured-relationship-holdout-003 | structured_relationship | oag | format mandatory-field and referential checks run before processing |
| oag_first | 2 | narrative-holdout-001 | narrative | rag+ontology | unclear attributes can become unmanaged data graveyard content |
| oag_first | 2 | mixed-holdout-002 | mixed | rag+ontology | unmanaged list creation can cause duplication confusion or unused lists |
| rag_only | 3 | structured-entity-holdout-001 | structured_entity | rag | data governance owner approves purposeful article attributes |
| rag_only | 3 | structured-entity-holdout-004 | structured_entity | rag | point-of-sale or consumer-system owner validates downstream article and tax behaviour |
| rag_only | 3 | structured-relationship-holdout-002 | structured_relationship | rag | site sellability depends on pricing and assortment associations |
| rag_only | 3 | structured-relationship-holdout-004 | structured_relationship | rag | downstream code-based logic still needs accurate special item mapping |
| ... | ... | ... | ... | ... | 9 more failed rows omitted. |

## Reviewer Notes

- Fake-generator runs validate benchmark arithmetic only and are not model-quality evidence.
- Real runs should use `--runs 3` so stability can be inspected before architectural decisions are made.
- Treat holdout split metrics as decision-grade for new OAG routing changes; tuning split metrics are regression/training evidence.
- OAG-only is intentionally expected to degrade on narrative questions; it is a boundary probe, not the target user mode.