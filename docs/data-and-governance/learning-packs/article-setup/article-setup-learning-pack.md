# Anonymised Learning Pack 2 - Article Setup and Tax Handling Process

## 1. Knowledge source card

| Field | Value |
|---|---|
| pack_id | `ARTICLE_SETUP_PACK_002` |
| process_area | `article-master-data` |
| process | `article-setup-tax-handling` |
| sensitivity | `anonymised` |
| source_basis | synthetic/anonymised learning material |
| permitted_use | Retrieval, grounded Q&A, process analytics, regulatory candidate testing |
| prohibited_use | Real article creation, real tax advice, production approval, source reconstruction |

## 2. Plain-English process narrative

Article setup is the controlled process for creating or changing an item record so it can be ordered, priced, taxed and handled through downstream operational processes.

The process starts when a commercial or category role identifies a new article, service item or product change. A request pack is prepared with the article description, hierarchy, supplier relationship, logistics-unit structure, tax treatment, pricing context and any controlled-list requirements.

A data steward reviews the pack for completeness before the article can move into staging. The article is validated against mandatory fields, hierarchy rules, logistics structure, duplicate checks, pricing dependencies and tax configuration. Broad tax-rate changes are handled through dated parameter-level tax records, while selective article-specific tax handling requires a documented exception and approval route.

The article is not ready when the header exists in staging. Readiness depends on validation passing, downstream mapping being complete, required access controls being applied and the activation decision being recorded. Product changes must protect historical records and avoid corrupting reporting, tax and stock logic.

## 3. Roles and responsibilities

| Role | Responsibility |
|---|---|
| Commercial requester | Initiates the article setup or change request and provides business context. |
| Category manager | Confirms hierarchy, assortment and controlled-list rationale. |
| Data steward | Reviews completeness, prepares the staging record and coordinates validation issues. |
| Pricing analyst | Confirms price-related dependencies and effective dates. |
| Tax configuration owner | Maintains tax parameter records and reviews article-specific tax exceptions. |
| Supply chain analyst | Confirms logistics-unit structure, pack coefficients and receiving dependencies. |
| Governance reviewer | Checks exception evidence, access restrictions and activation readiness. |

## 4. Key business rules

- A new article cannot be activated until mandatory fields, hierarchy, logistics structure, pricing dependencies and tax handling have passed validation.
- Broad VAT or tax-rate changes should be represented by dated parameter-level tax records rather than manual changes to every article.
- Article-specific tax exceptions require a documented reason, effective date and review by the tax configuration owner.
- Product changes must preserve historical article records where reporting, stock or tax treatment would otherwise be corrupted.
- Controlled article lists require a business owner, a documented use case and appropriate access profile.
- Service items and fuel lines may need different logistics and tax handling from stock articles.

## 5. Systems and data dependencies

| System / dependency | Purpose | Key data | Notes |
|---|---|---|---|
| Article master data workspace | Stages and validates article records. | Article header, hierarchy, status. | Generic system label only. |
| Pricing configuration environment | Holds price and effective-date dependencies. | Price condition, date range. | No real price values included. |
| Tax parameter register | Maintains dated tax treatment rules. | Tax code, effective date. | Supports broad changes and exceptions. |
| Logistics validation dashboard | Checks pack, layer and pallet structure. | Coefficients, dimensions. | Synthetic operational label. |
| Access profile register | Controls sensitive controlled lists. | User group, list owner. | No real users included. |

## 6. Process steps

1. Trigger article setup or change - Commercial requester - article need identified.
2. Prepare setup request pack - Commercial requester - request pack created with known article facts.
3. Confirm hierarchy and list rationale - Category manager - hierarchy node and controlled-list need confirmed.
4. Review request completeness - Data steward - incomplete records returned for correction.
5. Build staging article record - Data steward - article header and mandatory attributes entered.
6. Validate logistics-unit structure - Supply chain analyst - pack, layer and pallet data checked.
7. Confirm pricing dependencies - Pricing analyst - price-related prerequisites and dates checked.
8. Confirm tax treatment - Tax configuration owner - parameter or exception route selected.
9. Resolve validation exceptions - Data steward with owning role - failed checks corrected or escalated.
10. Apply access profile where needed - Governance reviewer - controlled-list access applied.
11. Activate article - Governance reviewer - activation recorded after validation passes.
12. Confirm downstream readiness - Data steward - requesting team receives completion confirmation.

## 7. Realistic Q&A pairs

**Q: Is the article ready once the staging header exists?**  
A: No. The staging header is only one part of setup. Logistics structure, pricing dependencies, tax treatment, validation checks and any access controls must also be complete before activation.

**Q: How should a broad VAT-rate change be handled?**  
A: A broad VAT-rate change should be handled through dated parameter-level tax records so the effective period is controlled and auditable, rather than by manually editing every article.

**Q: When is an article-specific tax exception acceptable?**  
A: An exception needs a documented reason, effective date and review by the tax configuration owner. It should not be treated as a silent data-steward override.

**Q: Why are controlled article lists governed?**  
A: Controlled lists can affect reporting, promotions, store communication or restricted item access, so they need a business owner, a documented use case and an access profile.

**Q: Can product changes overwrite old article structures?**  
A: Not by default. Product changes should protect historical records where overwriting would corrupt reporting, stock or tax treatment.

## 8. JSON-style learning records

```json
{"record_id":"ART_PROC_001","topic":"trigger","role":"commercial_requester","rule":"article setup starts with a commercial or category request","confidence":"high"}
{"record_id":"ART_PROC_002","topic":"readiness","role":"data_steward","rule":"a staging article header alone does not make an article ready for activation","confidence":"high"}
{"record_id":"ART_PROC_003","topic":"validation","role":"data_steward","rule":"mandatory fields, hierarchy, logistics, pricing and tax checks must pass before activation","confidence":"high"}
{"record_id":"ART_PROC_004","topic":"tax","role":"tax_configuration_owner","rule":"broad VAT or tax-rate changes should use dated parameter-level tax records","confidence":"high"}
{"record_id":"ART_PROC_005","topic":"exception","role":"tax_configuration_owner","rule":"article-specific tax exceptions require documented reason, effective date and owner review","confidence":"medium"}
{"record_id":"ART_PROC_006","topic":"product_change","role":"supply_chain_analyst","rule":"product changes must preserve historical records where reporting or stock logic would be corrupted","confidence":"medium"}
{"record_id":"ART_PROC_007","topic":"controlled_list","role":"governance_reviewer","rule":"controlled article lists require a business owner, use case and access profile","confidence":"medium"}
```

## 9. Suggested tagging structure

- `domain: article-master-data`
- `process: article-setup-tax-handling`
- `capability: master-data`
- `capability: tax-configuration`
- `capability: logistics-validation`
- `dependency: tax-parameter-register`
- `dependency: pricing-effective-dates`
- `dependency: logistics-unit-structure`
- `control: activation-gating`
- `control: exception-review`
- `control: access-profile`

## 10. Open validation points

- Which role has final accountability for selective tax exceptions.
- Which article attributes are mastered centrally versus by downstream operational tools.
- Whether service items and fuel lines follow one shared exception route or separate routes.
- How long rejected article setup evidence should be retained.
- Which controlled-list use cases require periodic recertification.
