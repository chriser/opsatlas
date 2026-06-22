# Anonymisation Rules

Ticket: #41

These rules are the mandatory validation standard for any learning pack marked `anonymised`. They are stricter than general synthetic-data guidance because anonymised material may have been derived from real workshop or project context before being rewritten.

## Red lines

Do not commit, upload, index or use a source if it contains any of the following:

- Real person names, initials used as identifiers, email addresses, phone numbers or account IDs.
- Real organisation, supplier, partner, customer, brand, subsidiary or project names.
- Real internal application names, acronyms, hostnames, database names, environment names, URLs or file paths.
- Real contract references, supplier numbers, customer IDs, product IDs, order IDs, invoice IDs or ticket IDs.
- Real commercial terms, prices, volumes, margins, payment terms, forecast figures, performance metrics or risk ratings.
- Raw meeting transcript fragments that preserve speaking style, attribution or sequence in a way that could identify participants.
- Credentials, tokens, secrets, API keys, screenshots of admin tools, or operational configuration details.

## Replacement rules

| Sensitive item | Required replacement |
|---|---|
| Named individual | Role label, for example `commercial requester` |
| Named team | Generic function, for example `support team` |
| Named system | Capability label, for example `operational master data tool` |
| Named supplier/customer | Generic party, for example `supplier` |
| Internal acronym | Plain-language capability unless the acronym is public and generic |
| Quantified value | Qualitative risk/scale statement |
| Exact date | Relative process timing |
| Exact location | Functional location such as `store`, `warehouse`, `support function` |
| Document title with identifiers | Neutral learning-pack title |

## Minimum safe record metadata

Every anonymised structured record should carry:

- `record_id`: stable synthetic ID.
- `source_pack`: learning pack name or ID.
- `process_area`: process taxonomy label.
- `role`: generic role owner.
- `system`: generic capability label or `none`.
- `sensitivity`: `anonymised`.
- `source_basis`: approved anonymised source or synthetic derivation.
- `validation_status`: `validated` or `requires_validation`.

## Anonymisation validation process

1. Read the source end to end before upload or commit.
2. Search for obvious identifiers: names, emails, URLs, numbers, currencies, product codes, system codes and initials.
3. Replace sensitive terms using the replacement rules.
4. Convert transcript wording into process-neutral prose; do not preserve speaker identity or exact back-and-forth phrasing.
5. Mark uncertain interpretation as `requires_validation`.
6. Run a second-pass review against the red-line list.
7. Record the review outcome in a validation note or metadata register.
8. Only then upload, ingest or approve the pack.

## Search checklist

Before acceptance, reviewers should scan for:

- `@`, `http`, `.com`, `.co.`, `.local`, `.internal`
- Currency symbols and values.
- Long numeric strings that may be IDs.
- Capitalised names that are not section headings or generic roles.
- Product, supplier, store, warehouse or contract labels.
- Specific system terms not present in the approved generic vocabulary.
- Pasted meeting language such as speaker names, timestamps or action-owner initials.

## Approved generic vocabulary

Use these terms unless a future governance decision extends the vocabulary:

- `commercial requester`
- `buyer`
- `support team`
- `process support lead`
- `master data operator`
- `finance master data role`
- `accounts payable role`
- `operational system owner`
- `operational master data tool`
- `finance master data environment`
- `document repository`
- `downstream consumer`
- `planning or layout consumer`
- `integration owner`
- `reporting owner`

## Acceptance standard

A pack can be marked `anonymised` only when:

- It contains no red-line content.
- Its actors, systems and parties use approved generic labels.
- All records include minimum safe metadata.
- The validation status is recorded.
- Any open interpretation is explicitly marked `requires_validation`.

If any red-line item remains, the pack must stay out of the source register and ADO evidence until corrected.
