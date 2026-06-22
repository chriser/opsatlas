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

## Change-Impact Simulation

The candidate review workflow now supports deterministic impact simulation through
`/api/regulatory/candidates/{candidate_id}/impact-simulation`.

The simulation:

- Reuses the regulatory candidate and its matched terms.
- Rescans approved, ingested internal sources for the same terms.
- Links affected sources to process areas, supporting passages and recommended next actions.
- Includes GOV.UK snapshot matches where available.
- Records an aggregate `regulatory_impact_simulated` analytics event.

This is a triage workflow only. It identifies likely affected knowledge/process areas and
the evidence to review; it does not confirm that a law, policy or operating process has
changed.
