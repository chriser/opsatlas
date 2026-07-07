# KSB Traceability Matrix

This matrix is a project evidence map for the AI Knowledge and Analytics Assistant. It uses
project KSB-style identifiers until the final official assessment KSB labels are supplied.

The live matrix is exposed in the platform at `/api/analytics/validation-evidence` and on
the Analytics page. Each row now carries:

- Project evidence identifiers used during delivery.
- Provisional official-reference mapping slots for the final assessor-supplied KSB IDs.
- Dated evidence-history events showing when the claim was implemented, expanded or validated.

## Evidence rows

| KSB | Category | Evidence focus | Primary artefacts |
|---|---|---|---|
| KSB-P1 | Knowledge | Knowledge governance and approved-source control | Source lifecycle, governance tests, Build Governance |
| KSB-P2 | Skill | Analytics dashboarding and evidence-led insight | Analytics aggregation tests, value hypothesis, Analytics page |
| KSB-P3 | Skill | AI/RAG evaluation and hallucination control | Grounded evidence, hallucination probes, audit traces |
| KSB-P4 | Knowledge | External context and regulatory triage | GOV.UK snapshots, regulatory candidates, impact simulation |
| KSB-P5 | Skill | Business value modelling and assumptions governance | Value assumptions ledger, value analytics tests |
| KSB-P6 | Behaviour | Ethical handling of anonymised/synthetic evidence | Synthetic data rules, anonymisation rules, simulator replay metadata |

## Analytics DT603 matrix

The analytics-specific DT603 mapping and screenshot checklist is maintained in
`docs/evidence/analytics-dt603-traceability-matrix.md`. Use it alongside this
KSB matrix when preparing final screenshots and explaining how the analytics
layer supports MLO1/MLO2/MLO3, S52/S53 and informed decision-making evidence.

## Official reference mapping rule

Use the `official_references` array in the API as the single place to map project KSB rows
to official assessment references. Until the final official reference list is supplied, rows
must remain `mapped_provisional` and the rationale must explain the evidence area being
matched. When final IDs are confirmed, update the reference ID and status without changing
the underlying project evidence row.

## Evidence history rule

Use `evidence_history` to record meaningful maturity changes only: implementation,
expansion, UAT evidence, validation reruns or replacement of provisional references. Do not
add routine commits unless they change the evidence claim, the mapping or the validation
status.

## Boundary

The matrix links delivered product evidence to assessment-style claims. It does not claim
that the provisional wording is the final official KSB taxonomy. Replace the provisional
official-reference IDs with official assessment IDs when that mapping is confirmed.
