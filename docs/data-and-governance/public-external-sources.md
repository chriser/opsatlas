# Public External Source Registry

Sprint 2 introduces controlled public-source snapshots for selected public UK government guidance and legislation pages.

## Scope

- Source providers: GOV.UK Content API for `www.gov.uk` guidance/content pages, and the `legislation.gov.uk` XML data service for legislation pages, with public HTML fallback for page URLs.
- Permitted inputs: selected public `https://www.gov.uk/...` URLs, GOV.UK content paths, or selected `https://www.legislation.gov.uk/...` page/XML URLs.
- Stored attribution: source URL, title, public body, content ID, document type, update date, retrieval date, snapshot version and content hash.
- Licence note: public source content is recorded as `Open Government Licence v3.0` unless a source-specific review changes the record.
- Update cadence: `manual` by default; later regulatory-currentness work can propose refresh cadence by topic.

## Governance Rules

- Do not send internal process text, user questions, source-register content or confidential context to public source providers.
- A snapshot request sends only the selected public URL/path.
- Failed fetches and rate limits are recorded as safe failure states; prior good snapshots are retained.
- Failed or obsolete source rows can be refreshed or removed from the External Sources registry.
- External snapshots are context/evidence candidates for human review. They are not legal advice and do not replace internal approval.
