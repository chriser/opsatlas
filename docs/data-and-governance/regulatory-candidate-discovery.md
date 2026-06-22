# Regulatory Candidate Discovery

Sprint 2 regulatory discovery scans approved, ingested knowledge sections for transparent keyword themes.

## Theme Taxonomy

- Food safety and hygiene.
- Fuel, EV charging and environmental operations.
- Employment, staffing and training.
- Health, safety and incident controls.
- Data protection and privacy.
- Financial, fiscal and tax references.
- Product compliance and standards.
- Site operations, licences and inspections.

## Review Semantics

The detector produces review candidates only. A candidate means approved internal knowledge contains wording that may require compliance or external-currentness review.

Review states:

- `relevant`: human agrees this candidate should be considered in compliance/currentness review.
- `irrelevant`: human reviewed and considers it not relevant.
- `needs_research`: human wants external guidance or subject-matter follow-up.

The output must include supporting source passages, matched terms, confidence and reason. It must not make definitive legal claims.
