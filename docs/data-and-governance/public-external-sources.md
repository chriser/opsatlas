# Public External Source Registry

Sprint 2 introduces controlled public-source snapshots for GOV.UK guidance/content pages.

## Scope

- Source provider: GOV.UK Content API.
- Permitted inputs: selected public `https://www.gov.uk/...` URLs or GOV.UK content paths.
- Stored attribution: source URL, title, public body, content ID, document type, update date, retrieval date, snapshot version and content hash.
- Licence note: GOV.UK content is recorded as `Open Government Licence v3.0` unless a source-specific review changes the record.
- Update cadence: `manual` by default; later regulatory-currentness work can propose refresh cadence by topic.

## Governance Rules

- Do not send internal process text, user questions, source-register content or confidential context to GOV.UK.
- A snapshot request sends only the selected public GOV.UK URL/path.
- Failed fetches and rate limits are recorded as safe failure states; prior good snapshots are retained.
- External snapshots are context/evidence candidates for human review. They are not legal advice and do not replace internal approval.
