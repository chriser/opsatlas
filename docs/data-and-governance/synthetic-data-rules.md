# Synthetic Data Rules

Ticket: #40

These rules define how learning data can be created for the AI Knowledge and Analytics Assistant without exposing confidential organisational information. They apply to markdown packs, benchmark packs, source-register entries, metadata sidecars, screenshots, exported evidence and any future sample datasets used by the assistant.

## Allowed source basis

Learning content may be based on:

- Anonymised workshop notes where names, organisation identifiers, system names, locations, commercial values and other confidential details have already been removed or generalised.
- Synthetic process scenarios invented for the proof of concept.
- Publicly safe process patterns, such as generic onboarding, master-data maintenance, governance checks and hand-off controls.
- Operator-approved summaries that have been checked against the anonymisation rules.

Learning content must not be based on:

- Raw confidential transcripts.
- Real supplier, customer, employee, contractor or partner names.
- Real internal system names, code names, hostnames, URLs, credentials or environment identifiers.
- Commercially sensitive trading, payment, contract, pricing, performance or volume information.
- Documents that have not been approved for PoC use.

## Synthetic substitution rules

Use realistic but generic language:

| Real-world category | Synthetic replacement style | Example |
|---|---|---|
| Organisation | Generic business label | `the business`, `the retailer`, `the organisation` |
| Department | Functional role | `commercial requester`, `support team`, `finance master data role` |
| Person | Role-based actor | `buyer`, `process support lead`, `requester` |
| System | Capability label | `operational master data tool`, `finance master data environment` |
| Supplier/customer | Generic party | `supplier`, `new supplier`, `external party` |
| Money/volume | Qualitative description | `material value`, `high-volume process`, `payment readiness` |
| Dates | Relative process timing | `before activation`, `during review`, `after approval` |
| Locations | Business-neutral scope | `store`, `warehouse`, `support function` |

## Realism requirements

Synthetic data should still be useful for retrieval and analytics. Every pack should include:

- Process overview in plain language.
- Step-by-step flow with trigger, roles, actions, outputs and controls.
- Role and responsibility records.
- Business rules and stop-gates.
- System and data dependencies using generic capability names.
- Exceptions, unresolved decisions and validation flags.
- Realistic Q&A pairs that exercise grounded answering and refusal behaviour.
- Structured records with stable IDs for analytics, governance checks and future dashboards.

## Evidence boundaries

The assistant may store and analyse:

- Source title, source ID, file name, sensitivity flag and approval state.
- Section headings, record IDs, role labels, process areas and validation status.
- Aggregated analytics facts, such as event type, count, outcome, latency, confidence and citation count.

The assistant must not store in analytics events:

- Raw source text.
- Raw prompts or full user questions.
- Generated answers.
- Issue details that could reproduce confidential content.
- Personal or commercial details.

## Pack author checklist

Before a synthetic learning pack is accepted:

1. All actors are roles, not people.
2. All systems are capability labels, not real products or internal names.
3. Financial, contractual and volume information is qualitative only.
4. Any uncertain source interpretation is marked `requires_validation`.
5. Every structured record has a stable `record_id`.
6. The pack has metadata tags for process area, role, system, sensitivity and source basis.
7. The pack can be ingested without manual cleanup.
8. The pack has been reviewed against the anonymisation rules.

## Governance decision

For Sprint 2, the project standard is:

- Use `synthetic` when the content is invented or materially rewritten from generic process patterns.
- Use `anonymised` when the content is derived from approved DT602 learning material and has been scrubbed.
- Use `requires_validation` on any fact where the source material was ambiguous or the future-state design was not final.

If in doubt, mark the content as `requires_validation` and keep it out of any evidence claim that implies operational certainty.
