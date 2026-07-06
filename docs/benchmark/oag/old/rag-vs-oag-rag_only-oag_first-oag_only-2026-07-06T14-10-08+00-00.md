# RAG vs OAG Benchmark - oag_first best config

Generated: 2026-07-06T14:10:08+00:00
Dataset: rag-vs-oag-v2 (69 questions)
Split filter: all
Split counts: holdout=24, tuning=45
Runs: 3
Fake generator: False
Model: ollama · qwen2.5:7b-instruct · nomic-embed-text
Code state: main@92164aa2 (dirty, 30 changed paths)
Total runtime: 1977.0s

## Overall By Configuration

| Config | Passed | Accuracy | Path hit | Stable | Mean latency | P95 latency |
|---|---:|---:|---:|---:|---:|---:|
| rag_only | 134/207 | 65% | 46% | 50/69 | 4.70s | 6.18s |
| oag_first | 146/207 | 71% | 57% | 60/69 | 4.71s | 6.74s |
| oag_only | 36/207 | 17% | 80% | 69/69 | 0.14s | 1.09s |

## Accuracy By Split

| Config | Split | Passed | Accuracy | Path hit | Stable |
|---|---|---:|---:|---:|---:|
| rag_only | holdout | 45/72 | 62% | 50% | 18/24 |
| rag_only | tuning | 89/135 | 66% | 44% | 32/45 |
| oag_first | holdout | 44/72 | 61% | 54% | 21/24 |
| oag_first | tuning | 102/135 | 76% | 58% | 39/45 |
| oag_only | holdout | 12/72 | 17% | 83% | 24/24 |
| oag_only | tuning | 24/135 | 18% | 78% | 45/45 |

## Per-Category Accuracy

| Config | Category | Passed | Accuracy | Path hit |
|---|---|---:|---:|---:|
| rag_only | aggregate | 9/27 | 33% | 0% |
| rag_only | mixed | 9/27 | 33% | 100% |
| rag_only | narrative | 31/42 | 74% | 100% |
| rag_only | out_of_scope | 24/27 | 89% | 100% |
| rag_only | structured_entity | 31/42 | 74% | 0% |
| rag_only | structured_relationship | 30/42 | 71% | 0% |
| oag_first | aggregate | 13/27 | 48% | 0% |
| oag_first | mixed | 13/27 | 48% | 100% |
| oag_first | narrative | 34/42 | 81% | 100% |
| oag_first | out_of_scope | 24/27 | 89% | 100% |
| oag_first | structured_entity | 26/42 | 62% | 36% |
| oag_first | structured_relationship | 36/42 | 86% | 14% |
| oag_only | aggregate | 0/27 | 0% | 100% |
| oag_only | mixed | 0/27 | 0% | 100% |
| oag_only | narrative | 0/42 | 0% | 0% |
| oag_only | out_of_scope | 27/27 | 100% | 100% |
| oag_only | structured_entity | 3/42 | 7% | 100% |
| oag_only | structured_relationship | 6/42 | 14% | 100% |

## Path Usage Matrix

| Config | oag | rag | rag+ontology | Other |
|---|---:|---:|---:|---:|
| rag_only | 0 | 207 | 0 | 0 |
| oag_first | 21 | 0 | 186 | 0 |
| oag_only | 207 | 0 | 0 | 0 |

## Citation Types

| Config | document | ontology_object | process_registry | none |
|---|---:|---:|---:|---:|
| rag_only | 420 | 0 | 0 | 24 |
| oag_first | 370 | 68 | 0 | 33 |
| oag_only | 0 | 34 | 0 | 195 |

## Interpretation Targets

- Structured relationship lift: +14%
- Aggregate lift: +15%
- Narrative loss versus RAG-only: +7%
- Out-of-scope preserved by OAG-first: 89%

## Failed Rows

| Config | Run | ID | Category | Path | Missed facts |
|---|---:|---|---|---|---|
| rag_only | 1 | structured-entity-005 | structured_entity | rag | regulatory or reporting owner owns packaging-waste reporting requirements |
| rag_only | 1 | structured-entity-009 | structured_entity | rag | data governance owner ensures attributes have accountable ownership and purposeful use |
| rag_only | 1 | structured-relationship-007 | structured_relationship | rag | site sellability depends on later price and assortment associations |
| rag_only | 1 | structured-relationship-010 | structured_relationship | rag | downstream mapping must remain accurate for special item handling |
| rag_only | 1 | aggregate-002 | aggregate | rag | operational packaging movement; descriptive shelf-packaging information |
| rag_only | 1 | aggregate-003 | aggregate | rag | mandatory-field checks; format checks; referential checks |
| rag_only | 1 | aggregate-004 | aggregate | rag | targeted maintenance |
| rag_only | 1 | narrative-003 | narrative | rag | source-of-truth positions and master-and-consumer model must be agreed |
| rag_only | 1 | narrative-005 | narrative | rag | attributes without a clear owner and use case risk becoming unmanaged or unused |
| rag_only | 1 | mixed-001 | mixed | rag | trading support or master data owner completes readiness controls |
| rag_only | 1 | mixed-002 | mixed | rag | shelf packaging can be a descriptive attribute or listing field |
| rag_only | 1 | mixed-003 | mixed | rag | replenishment, warehouse, finance or store processes may need schedule outputs; source-of-truth and ownership decisions prevent duplicate or unstable maintenance |
| rag_only | 1 | mixed-004 | mixed | rag | article lists group items manually or automatically for reporting, maintenance or downstream usage |
| rag_only | 1 | mixed-005 | mixed | rag | connected systems still rely on code-based logic even without full stock process |
| rag_only | 1 | structured-entity-holdout-001 | structured_entity | rag | data governance owner approves purposeful article attributes |
| rag_only | 1 | structured-entity-holdout-004 | structured_entity | rag | point-of-sale or consumer-system owner validates downstream article and tax behaviour |
| rag_only | 1 | structured-relationship-holdout-002 | structured_relationship | rag | site sellability depends on pricing and assortment associations |
| rag_only | 1 | structured-relationship-holdout-004 | structured_relationship | rag | downstream code-based logic still needs accurate special item mapping |
| rag_only | 1 | aggregate-holdout-002 | aggregate | rag | assortment setup |
| rag_only | 1 | aggregate-holdout-004 | aggregate | rag | operational packaging movement |
| rag_only | 1 | out-of-scope-holdout-002 | out_of_scope | rag | refuse because named employee ownership is not available |
| rag_only | 1 | mixed-holdout-002 | mixed | rag | unmanaged list creation can cause duplication confusion or unused lists |
| rag_only | 1 | mixed-holdout-004 | mixed | rag | packaging use cases are separated to avoid overengineering |
| oag_first | 1 | structured-entity-002 | structured_entity | oag | logistics-side owner defines service rules |
| oag_first | 1 | structured-entity-004 | structured_entity | oag | profile or access owner controls restricted lists |
| oag_first | 1 | structured-entity-009 | structured_entity | oag | data governance owner ensures attributes have accountable ownership and purposeful use |
| oag_first | 1 | aggregate-002 | aggregate | rag+ontology | packaging-waste reporting |
| oag_first | 1 | aggregate-003 | aggregate | rag+ontology | mandatory-field checks; format checks; referential checks |
| oag_first | 1 | aggregate-004 | aggregate | rag+ontology | reporting; targeted maintenance |
| oag_first | 1 | narrative-003 | narrative | rag+ontology | source-of-truth positions and master-and-consumer model must be agreed |
| ... | ... | ... | ... | ... | 275 more failed rows omitted. |

## Reviewer Notes

- Fake-generator runs validate benchmark arithmetic only and are not model-quality evidence.
- Real runs should use `--runs 3` so stability can be inspected before architectural decisions are made.
- Treat holdout split metrics as decision-grade for new OAG routing changes; tuning split metrics are regression/training evidence.
- OAG-only is intentionally expected to degrade on narrative questions; it is a boundary probe, not the target user mode.