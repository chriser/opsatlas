# OAG Ontology Coverage Diagnostic

Generated: 2026-07-06T18:07:43+00:00
Benchmark generated: 2026-07-06T16:29:44+00:00
Dataset: rag-vs-oag-v2
Config filter: oag_first
Split filter: holdout
Only failed rows: True
Analysed facts: 6
Coverage counts: partial=2, present=4
Ontology candidates inspected: 834

## Coverage Table

| ID | Category | Status | Coverage | Missing Tokens | Best Ontology Candidate | Expected Fact |
|---|---|---|---:|---|---|---|
| structured-entity-holdout-001 | structured_entity | partial | 71% | governanc, purposeful | source/Pack 5: Article Master Data Attributes and Logistic Structure process_derived_from Article Master Data, Attributes and Logistic Structure | data governance owner approves purposeful article attributes |
| structured-entity-holdout-004 | structured_entity | partial | 80% | owner, validat | system/Point-of-sale consumer – anonymised process_uses_system Article Integration, Tax Handling, Product Change and Article Lists | point-of-sale or consumer-system owner validates downstream article and tax behaviour |
| aggregate-holdout-001 | aggregate | present | 100% | n/a | compliance_finding/finding-db88baabc9d0402741 finding_affects_process Schedule, Integration and End-State Architecture Dependencies | mapping controls |
| aggregate-holdout-002 | aggregate | present | 100% | n/a | source/Pack 6: Article Integration Tax Handling Product Change and Article Lists process_derived_from Article Integration, Tax Handling, Product Change and Article Lists | pricing setup |
| aggregate-holdout-002 | aggregate | present | 100% | n/a | source/Pack 5: Article Master Data Attributes and Logistic Structure process_derived_from Article Master Data, Attributes and Logistic Structure | assortment setup |
| aggregate-holdout-004 | aggregate | present | 100% | n/a | control/scope-pragmatism process_enforced_by Packaging, Shelf Packaging and Packaging-Waste Reporting | shelf-packaging information |

## How To Read This

- `present` means the expected fact text or an alias was found directly in ontology object/link text.
- `partial` means related ontology text exists, but key tokens are missing; this usually points to a content enrichment gap.
- `absent` means the diagnostic could not find enough ontology content to support the expected fact.
- If most misses are `partial` or `absent`, prioritise ontology sync/schema enrichment before routing changes.