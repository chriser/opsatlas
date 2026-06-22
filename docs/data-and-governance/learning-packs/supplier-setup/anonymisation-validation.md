# Supplier Setup Anonymisation Validation

Ticket: #667

Validation date: 2026-06-22

Scope:

- `process-overview-record.md`
- `role-responsibility-records.md`
- `process-step-records.md`
- `structured-knowledge-records.json`
- `metadata-register.json`

## Validation outcome

Status: `validated`

The supplier setup learning-pack evidence is suitable for Sprint 2 use as anonymised learning data. It uses generic roles, generic system capability labels and synthetic record IDs. It does not include real names, real organisations, real systems, URLs, email addresses, credentials, commercial values or long operational identifiers.

## Checks performed

| Check | Command or review method | Result |
|---|---|---|
| Email, URL, currency, long number and secret scan | `rg -n '@|https?://|www\\.|\\.com|\\.co\\.|£|\\$|€|[0-9]{6,}|Pochopien|Yahoo|chriser|password|secret|token|api[_-]?key' docs/data-and-governance/learning-packs/supplier-setup` | No matches |
| Potential person-name scan | `rg -n '\\b[A-Z][a-z]+\\s+[A-Z][a-z]+\\b' docs/data-and-governance/learning-packs/supplier-setup` | Only document headings matched |
| JSON validity | `python -m json.tool` against structured records and metadata register | Passed |
| Metadata completeness | Structured record IDs compared to metadata register IDs | 19 records, 19 tags, no missing or extra tags |
| Manual red-line review | Compared against `docs/data-and-governance/anonymisation-rules.md` | Passed |

## Generic vocabulary observed

Roles:

- `commercial requester`
- `buyer`
- `support team`
- `process support lead`
- `master data operator`
- `accounts payable role`
- `finance master data role`
- `operational system owner`
- `requesting business team`

Systems and dependencies:

- `operational master data tool`
- `finance master data environment`
- `document repository`
- `none`

These are generic labels and do not identify real people, organisations or internal systems.

## Remaining non-anonymisation caveats

The following items remain marked `requires_validation` because the source material did not fully settle the process design:

- Ownership of each due diligence pack field.
- Exact sequence between operational setup, finance setup and contract completion.
- Final evidence repository for submitted forms and supporting documents.
- Handling and retention of failed-check evidence.
- Final readiness sign-off where operational and finance setup complete at different times.

These caveats do not block anonymised learning-data use. They should be treated as process-design open questions, not confidentiality issues.

## Approval recommendation

The supplier setup evidence can be used for:

- Local retrieval and grounded Q&A testing.
- Governance-intelligence checks.
- Analytics and event-ledger examples.
- Sprint 2 UAT evidence.

The evidence must not be used for:

- Real supplier onboarding.
- Operational decisioning.
- Reconstructing raw workshop material.
- Inferring confidential organisation-specific process details.
