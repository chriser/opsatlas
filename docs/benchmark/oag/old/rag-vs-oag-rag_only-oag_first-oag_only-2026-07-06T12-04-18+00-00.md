# RAG vs OAG Benchmark - rag_only best config

Generated: 2026-07-06T12:04:18+00:00
Dataset: rag-vs-oag-v2 (69 questions)
Split filter: all
Split counts: holdout=24, tuning=45
Runs: 3
Fake generator: False
Model: ollama · qwen2.5:7b-instruct · nomic-embed-text
Total runtime: 2908.6s

## Overall By Configuration

| Config | Passed | Accuracy | Path hit | Stable | Mean latency | P95 latency |
|---|---:|---:|---:|---:|---:|---:|
| rag_only | 139/207 | 67% | 46% | 52/69 | 7.11s | 10.05s |
| oag_first | 129/207 | 62% | 65% | 59/69 | 6.59s | 10.57s |
| oag_only | 45/207 | 22% | 80% | 69/69 | 0.35s | 2.32s |

## Accuracy By Split

| Config | Split | Passed | Accuracy | Path hit | Stable |
|---|---|---:|---:|---:|---:|
| rag_only | holdout | 46/72 | 64% | 50% | 17/24 |
| rag_only | tuning | 93/135 | 69% | 44% | 35/45 |
| oag_first | holdout | 39/72 | 54% | 58% | 20/24 |
| oag_first | tuning | 90/135 | 67% | 69% | 39/45 |
| oag_only | holdout | 12/72 | 17% | 83% | 24/24 |
| oag_only | tuning | 33/135 | 24% | 78% | 45/45 |

## Per-Category Accuracy

| Config | Category | Passed | Accuracy | Path hit |
|---|---|---:|---:|---:|
| rag_only | aggregate | 7/27 | 26% | 0% |
| rag_only | mixed | 10/27 | 37% | 100% |
| rag_only | narrative | 32/42 | 76% | 100% |
| rag_only | out_of_scope | 24/27 | 89% | 100% |
| rag_only | structured_entity | 32/42 | 76% | 0% |
| rag_only | structured_relationship | 34/42 | 81% | 0% |
| oag_first | aggregate | 12/27 | 44% | 0% |
| oag_first | mixed | 12/27 | 44% | 100% |
| oag_first | narrative | 29/42 | 69% | 100% |
| oag_first | out_of_scope | 24/27 | 89% | 100% |
| oag_first | structured_entity | 18/42 | 43% | 79% |
| oag_first | structured_relationship | 34/42 | 81% | 14% |
| oag_only | aggregate | 0/27 | 0% | 100% |
| oag_only | mixed | 0/27 | 0% | 100% |
| oag_only | narrative | 0/42 | 0% | 0% |
| oag_only | out_of_scope | 27/27 | 100% | 100% |
| oag_only | structured_entity | 12/42 | 29% | 100% |
| oag_only | structured_relationship | 6/42 | 14% | 100% |

## Path Usage Matrix

| Config | oag | rag | rag+ontology | Other |
|---|---:|---:|---:|---:|
| rag_only | 0 | 207 | 0 | 0 |
| oag_first | 39 | 0 | 168 | 0 |
| oag_only | 207 | 0 | 0 | 0 |

## Citation Types

| Config | document | ontology_object | process_registry | none |
|---|---:|---:|---:|---:|
| rag_only | 421 | 0 | 0 | 24 |
| oag_first | 328 | 77 | 0 | 47 |
| oag_only | 0 | 39 | 0 | 189 |

## Interpretation Targets

- Structured relationship lift: +0%
- Aggregate lift: +19%
- Narrative loss versus RAG-only: -7%
- Out-of-scope preserved by OAG-first: 89%

## Failed Rows

| Config | Run | ID | Category | Path | Missed facts |
|---|---:|---|---|---|---|
| rag_only | 1 | structured-entity-005 | structured_entity | rag | regulatory or reporting owner owns packaging-waste reporting requirements |
| rag_only | 1 | structured-entity-009 | structured_entity | rag | data governance owner ensures attributes have accountable ownership and purposeful use |
| rag_only | 1 | aggregate-002 | aggregate | rag | operational packaging movement; descriptive shelf-packaging information |
| rag_only | 1 | aggregate-003 | aggregate | rag | mandatory-field checks; format checks; referential checks |
| rag_only | 1 | aggregate-004 | aggregate | rag | targeted maintenance |
| rag_only | 1 | aggregate-005 | aggregate | rag | lotto |
| rag_only | 1 | narrative-003 | narrative | rag | source-of-truth positions and master-and-consumer model must be agreed |
| rag_only | 1 | narrative-008 | narrative | rag | dedicated packaging-item model should only be introduced where movement tracking or returns are needed |
| rag_only | 1 | mixed-001 | mixed | rag | trading support or master data owner completes readiness controls |
| rag_only | 1 | mixed-003 | mixed | rag | replenishment, warehouse, finance or store processes may need schedule outputs; source-of-truth and ownership decisions prevent duplicate or unstable maintenance |
| rag_only | 1 | mixed-004 | mixed | rag | article lists group items manually or automatically for reporting, maintenance or downstream usage |
| rag_only | 1 | mixed-005 | mixed | rag | connected systems still rely on code-based logic even without full stock process |
| rag_only | 1 | structured-relationship-holdout-002 | structured_relationship | rag | site sellability depends on pricing and assortment associations |
| rag_only | 1 | structured-relationship-holdout-004 | structured_relationship | rag | downstream code-based logic still needs accurate special item mapping |
| rag_only | 1 | aggregate-holdout-001 | aggregate | rag | mapping controls |
| rag_only | 1 | aggregate-holdout-002 | aggregate | rag | pricing setup; assortment setup |
| rag_only | 1 | aggregate-holdout-004 | aggregate | rag | operational packaging movement; packaging-waste reporting |
| rag_only | 1 | narrative-holdout-002 | narrative | rag | a supplier can be active while contracts mapping or controls remain incomplete |
| rag_only | 1 | out-of-scope-holdout-002 | out_of_scope | rag | refuse because named employee ownership is not available |
| rag_only | 1 | mixed-holdout-002 | mixed | rag | unmanaged list creation can cause duplication confusion or unused lists |
| rag_only | 1 | mixed-holdout-004 | mixed | rag | packaging use cases are separated to avoid overengineering |
| oag_first | 1 | structured-entity-001 | structured_entity | oag | trading support assistant or master data operator creates the supplier record |
| oag_first | 1 | structured-entity-002 | structured_entity | oag | logistics-side owner defines service rules |
| oag_first | 1 | structured-entity-006 | structured_entity | oag | master data operator creates service items |
| oag_first | 1 | structured-entity-008 | structured_entity | oag | testing and governance owners validate error handling and file-format rules |
| oag_first | 1 | structured-entity-009 | structured_entity | oag | data governance owner ensures attributes have accountable ownership and purposeful use |
| oag_first | 1 | structured-relationship-010 | structured_relationship | rag+ontology | downstream mapping must remain accurate for special item handling |
| oag_first | 1 | aggregate-003 | aggregate | rag+ontology | mandatory-field checks; format checks; referential checks |
| oag_first | 1 | aggregate-004 | aggregate | rag+ontology | reporting; promotions; assortments; targeted maintenance |
| oag_first | 1 | narrative-003 | narrative | rag+ontology | source-of-truth positions and master-and-consumer model must be agreed |
| ... | ... | ... | ... | ... | 278 more failed rows omitted. |

## Reviewer Notes

- Fake-generator runs validate benchmark arithmetic only and are not model-quality evidence.
- Real runs should use `--runs 3` so stability can be inspected before architectural decisions are made.
- Treat holdout split metrics as decision-grade for new OAG routing changes; tuning split metrics are regression/training evidence.
- OAG-only is intentionally expected to degrade on narrative questions; it is a boundary probe, not the target user mode.