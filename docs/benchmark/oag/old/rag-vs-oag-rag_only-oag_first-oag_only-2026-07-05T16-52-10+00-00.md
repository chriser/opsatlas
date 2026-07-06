# RAG vs OAG Benchmark - oag_first best config

Generated: 2026-07-05T16:52:10+00:00
Dataset: rag-vs-oag-v1 (45 questions)
Runs: 3
Fake generator: False
Model: ollama · qwen2.5:7b-instruct · nomic-embed-text
Total runtime: 804.7s

## Overall By Configuration

| Config | Passed | Accuracy | Path hit | Stable | Mean latency | P95 latency |
|---|---:|---:|---:|---:|---:|---:|
| rag_only | 30/135 | 22% | 44% | 43/45 | 3.26s | 5.94s |
| oag_first | 32/135 | 24% | 58% | 42/45 | 2.56s | 4.72s |
| oag_only | 15/135 | 11% | 78% | 45/45 | 0.14s | 1.08s |

## Per-Category Accuracy

| Config | Category | Passed | Accuracy | Path hit |
|---|---|---:|---:|---:|
| rag_only | aggregate | 4/15 | 27% | 0% |
| rag_only | mixed | 0/15 | 0% | 100% |
| rag_only | narrative | 3/30 | 10% | 100% |
| rag_only | out_of_scope | 15/15 | 100% | 100% |
| rag_only | structured_entity | 6/30 | 20% | 0% |
| rag_only | structured_relationship | 2/30 | 7% | 0% |
| oag_first | aggregate | 6/15 | 40% | 0% |
| oag_first | mixed | 0/15 | 0% | 100% |
| oag_first | narrative | 3/30 | 10% | 100% |
| oag_first | out_of_scope | 15/15 | 100% | 100% |
| oag_first | structured_entity | 4/30 | 13% | 40% |
| oag_first | structured_relationship | 4/30 | 13% | 20% |
| oag_only | aggregate | 0/15 | 0% | 100% |
| oag_only | mixed | 0/15 | 0% | 100% |
| oag_only | narrative | 0/30 | 0% | 0% |
| oag_only | out_of_scope | 15/15 | 100% | 100% |
| oag_only | structured_entity | 0/30 | 0% | 100% |
| oag_only | structured_relationship | 0/30 | 0% | 100% |

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

- Structured relationship lift: +7%
- Aggregate lift: +13%
- Narrative loss versus RAG-only: +0%
- Out-of-scope preserved by OAG-first: 100%

## Failed Rows

| Config | Run | ID | Category | Path | Missed facts |
|---|---:|---|---|---|---|
| rag_only | 1 | structured-entity-001 | structured_entity | rag | trading support assistant or master data operator creates the supplier record |
| rag_only | 1 | structured-entity-002 | structured_entity | rag | logistics-side owner defines service rules |
| rag_only | 1 | structured-entity-003 | structured_entity | rag | ranging or assortment owner controls launch timing and site-level sellability |
| rag_only | 1 | structured-entity-004 | structured_entity | rag | profile or access owner controls restricted lists |
| rag_only | 1 | structured-entity-005 | structured_entity | rag | regulatory or reporting owner owns packaging-waste reporting requirements |
| rag_only | 1 | structured-entity-008 | structured_entity | rag | testing and governance owners validate error handling and file-format rules |
| rag_only | 1 | structured-entity-009 | structured_entity | rag | data governance owner ensures attributes have accountable ownership and purposeful use |
| rag_only | 1 | structured-entity-010 | structured_entity | rag | point-of-sale or consumer-system owner ensures downstream consumers understand article and tax data |
| rag_only | 1 | structured-relationship-001 | structured_relationship | rag | due diligence and credit checks are gating controls |
| rag_only | 1 | structured-relationship-002 | structured_relationship | rag | commercial contract, service contract and payment contract are all required |
| rag_only | 1 | structured-relationship-003 | structured_relationship | rag | downstream price and assortment modules consume supplier and contract structure |
| rag_only | 1 | structured-relationship-004 | structured_relationship | rag | schedule generation should reflect supplier-side service rules and site-side calendar rules |
| rag_only | 1 | structured-relationship-005 | structured_relationship | rag | mandatory-field checks and referential checks reject incomplete or invalid data |
| rag_only | 1 | structured-relationship-006 | structured_relationship | rag | the article structure must be complete enough before supplier relationships, pricing and assortments can be built |
| rag_only | 1 | structured-relationship-007 | structured_relationship | rag | site sellability depends on later price and assortment associations |
| rag_only | 1 | structured-relationship-008 | structured_relationship | rag | automatic list criteria can include manufacturer, attributes, hierarchy nodes and other supported fields |
| rag_only | 1 | structured-relationship-009 | structured_relationship | rag | planning or layout consumer receives shelf-packaging information |
| rag_only | 1 | structured-relationship-010 | structured_relationship | rag | downstream mapping must remain accurate for special item handling |
| rag_only | 1 | aggregate-002 | aggregate | rag | operational packaging movement; descriptive shelf-packaging information |
| rag_only | 1 | aggregate-003 | aggregate | rag | mandatory-field checks; format checks; referential checks |
| rag_only | 1 | aggregate-004 | aggregate | rag | targeted maintenance |
| rag_only | 1 | narrative-001 | narrative | rag | checks must be completed before the supplier can move forward |
| rag_only | 1 | narrative-003 | narrative | rag | source-of-truth positions and master-and-consumer model must be agreed |
| rag_only | 1 | narrative-004 | narrative | rag | staging validation catches mandatory-field, format and referential errors before live processing |
| rag_only | 1 | narrative-005 | narrative | rag | attributes without a clear owner and use case risk becoming unmanaged or unused |
| rag_only | 1 | narrative-006 | narrative | rag | site sellability depends on pricing and assortment-related setup |
| rag_only | 1 | narrative-007 | narrative | rag | flexible list creation can lead to duplication, confusion or unused lists without an owner |
| rag_only | 1 | narrative-008 | narrative | rag | dedicated packaging-item model should only be introduced where movement tracking or returns are needed |
| rag_only | 1 | narrative-009 | narrative | rag | service items are non-stock or non-logistics items and do not need normal logistics-unit setup |
| rag_only | 1 | narrative-010 | narrative | rag | testing validates publication timing, tax updates, product-change behaviour, article-list logic and consumer-system responses end to end |
| ... | ... | ... | ... | ... | 298 more failed rows omitted. |

## Reviewer Notes

- Fake-generator runs validate benchmark arithmetic only and are not model-quality evidence.
- Real runs should use `--runs 3` so stability can be inspected before architectural decisions are made.
- OAG-only is intentionally expected to degrade on narrative questions; it is a boundary probe, not the target user mode.