# RAG vs OAG Benchmark - oag_first best config

Generated: 2026-07-05T18:07:41+00:00
Dataset: rag-vs-oag-v1 (45 questions)
Runs: 3
Fake generator: False
Model: ollama · qwen2.5:7b-instruct · nomic-embed-text
Total runtime: 804.7s

## Overall By Configuration

| Config | Passed | Accuracy | Path hit | Stable | Mean latency | P95 latency |
|---|---:|---:|---:|---:|---:|---:|
| rag_only | 87/135 | 64% | 44% | 35/45 | 3.26s | 5.94s |
| oag_first | 94/135 | 70% | 58% | 40/45 | 2.56s | 4.72s |
| oag_only | 24/135 | 18% | 78% | 45/45 | 0.14s | 1.08s |

## Per-Category Accuracy

| Config | Category | Passed | Accuracy | Path hit |
|---|---|---:|---:|---:|
| rag_only | aggregate | 4/15 | 27% | 0% |
| rag_only | mixed | 3/15 | 20% | 100% |
| rag_only | narrative | 19/30 | 63% | 100% |
| rag_only | out_of_scope | 15/15 | 100% | 100% |
| rag_only | structured_entity | 22/30 | 73% | 0% |
| rag_only | structured_relationship | 24/30 | 80% | 0% |
| oag_first | aggregate | 9/15 | 60% | 0% |
| oag_first | mixed | 1/15 | 7% | 100% |
| oag_first | narrative | 21/30 | 70% | 100% |
| oag_first | out_of_scope | 15/15 | 100% | 100% |
| oag_first | structured_entity | 21/30 | 70% | 40% |
| oag_first | structured_relationship | 27/30 | 90% | 20% |
| oag_only | aggregate | 0/15 | 0% | 100% |
| oag_only | mixed | 0/15 | 0% | 100% |
| oag_only | narrative | 0/30 | 0% | 0% |
| oag_only | out_of_scope | 15/15 | 100% | 100% |
| oag_only | structured_entity | 3/30 | 10% | 100% |
| oag_only | structured_relationship | 6/30 | 20% | 100% |

## Path Usage Matrix

| Config | oag | rag | rag+ontology | Other |
|---|---:|---:|---:|---:|
| rag_only | 0 | 135 | 0 | 0 |
| oag_first | 18 | 0 | 117 | 0 |
| oag_only | 135 | 0 | 0 | 0 |

## Citation Types

| Config | document | ontology_object | process_registry | none |
|---|---:|---:|---:|---:|
| rag_only | 269 | 0 | 0 | 15 |
| oag_first | 241 | 44 | 0 | 21 |
| oag_only | 0 | 26 | 0 | 123 |

## Interpretation Targets

- Structured relationship lift: +10%
- Aggregate lift: +33%
- Narrative loss versus RAG-only: +7%
- Out-of-scope preserved by OAG-first: 100%

## Failed Rows

| Config | Run | ID | Category | Path | Missed facts |
|---|---:|---|---|---|---|
| rag_only | 1 | structured-entity-005 | structured_entity | rag | regulatory or reporting owner owns packaging-waste reporting requirements |
| rag_only | 1 | structured-entity-009 | structured_entity | rag | data governance owner ensures attributes have accountable ownership and purposeful use |
| rag_only | 1 | structured-relationship-003 | structured_relationship | rag | downstream price and assortment modules consume supplier and contract structure |
| rag_only | 1 | structured-relationship-010 | structured_relationship | rag | downstream mapping must remain accurate for special item handling |
| rag_only | 1 | aggregate-002 | aggregate | rag | descriptive shelf-packaging information |
| rag_only | 1 | aggregate-003 | aggregate | rag | mandatory-field checks; format checks; referential checks |
| rag_only | 1 | aggregate-004 | aggregate | rag | targeted maintenance |
| rag_only | 1 | narrative-003 | narrative | rag | source-of-truth positions and master-and-consumer model must be agreed |
| rag_only | 1 | narrative-006 | narrative | rag | site sellability depends on pricing and assortment-related setup |
| rag_only | 1 | narrative-009 | narrative | rag | service items are non-stock or non-logistics items and do not need normal logistics-unit setup |
| rag_only | 1 | mixed-001 | mixed | rag | trading support or master data owner completes readiness controls |
| rag_only | 1 | mixed-003 | mixed | rag | replenishment, warehouse, finance or store processes may need schedule outputs; source-of-truth and ownership decisions prevent duplicate or unstable maintenance |
| rag_only | 1 | mixed-004 | mixed | rag | article lists group items manually or automatically for reporting, maintenance or downstream usage |
| rag_only | 1 | mixed-005 | mixed | rag | connected systems still rely on code-based logic even without full stock process |
| oag_first | 1 | structured-entity-002 | structured_entity | oag | logistics-side owner defines service rules |
| oag_first | 1 | structured-entity-004 | structured_entity | oag | profile or access owner controls restricted lists |
| oag_first | 1 | structured-entity-009 | structured_entity | oag | data governance owner ensures attributes have accountable ownership and purposeful use |
| oag_first | 1 | structured-relationship-010 | structured_relationship | rag+ontology | downstream mapping must remain accurate for special item handling |
| oag_first | 1 | aggregate-003 | aggregate | rag+ontology | mandatory-field checks; format checks; referential checks |
| oag_first | 1 | aggregate-004 | aggregate | rag+ontology | reporting; promotions; assortments; targeted maintenance |
| oag_first | 1 | narrative-003 | narrative | rag+ontology | source-of-truth positions and master-and-consumer model must be agreed |
| oag_first | 1 | narrative-006 | narrative | rag+ontology | site sellability depends on pricing and assortment-related setup |
| oag_first | 1 | narrative-009 | narrative | rag+ontology | service items are non-stock or non-logistics items and do not need normal logistics-unit setup |
| oag_first | 1 | mixed-001 | mixed | rag+ontology | trading support or master data owner completes readiness controls |
| oag_first | 1 | mixed-003 | mixed | rag+ontology | replenishment, warehouse, finance or store processes may need schedule outputs; source-of-truth and ownership decisions prevent duplicate or unstable maintenance |
| oag_first | 1 | mixed-004 | mixed | rag+ontology | article lists group items manually or automatically for reporting, maintenance or downstream usage |
| oag_first | 1 | mixed-005 | mixed | rag+ontology | connected systems still rely on code-based logic even without full stock process |
| oag_only | 1 | structured-entity-001 | structured_entity | oag | trading support assistant or master data operator creates the supplier record |
| oag_only | 1 | structured-entity-002 | structured_entity | oag | logistics-side owner defines service rules |
| oag_only | 1 | structured-entity-003 | structured_entity | oag | ranging or assortment owner controls launch timing and site-level sellability |
| ... | ... | ... | ... | ... | 170 more failed rows omitted. |

## Reviewer Notes

- Fake-generator runs validate benchmark arithmetic only and are not model-quality evidence.
- Real runs should use `--runs 3` so stability can be inspected before architectural decisions are made.
- OAG-only is intentionally expected to degrade on narrative questions; it is a boundary probe, not the target user mode.