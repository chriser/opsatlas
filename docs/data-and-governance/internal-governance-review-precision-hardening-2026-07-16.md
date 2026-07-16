# Internal Governance Review Precision Hardening

Date: 2026-07-16  
ADO: Bug #1285; Stage 4C Task #1284; final-corpus Story #1271

## Trigger

The first T1 Full Governance Review completed all 36 document pairs in 11h 19m but exported exactly 100 findings. Runtime inspection showed that this was a capped subset of 212 pair-level findings, not 100 unique governance defects.

The run contained three material precision failures:

- 24 of 25 returned contradictions were deterministic conflict-guard promotions rather than model contradiction decisions.
- 100 of the 212 pair findings involved either a bare `Requires validation` table cell or repeated source-basis boilerplate.
- Bidirectional comparisons and pair-only consolidation returned mirrored and repeated manifestations of the same root concern.

The four deterministic Quick Scan acronym findings were separately verified against the current source content and remain valid. Quick Scan is an independent document-hygiene layer; Full Governance Review does not replace it.

## Remediation

The internal reasoning payload now excludes sections that are not governed assertions:

- open questions and design decisions;
- JSON-style learning records;
- suggested tagging structure;
- repeated source-basis and anonymisation boilerplate.

Markdown tables are parsed as complete rows. Header, separator and status-only rows are ignored, so `| Requires validation |` cannot become a standalone obligation. Fenced machine-readable blocks are ignored by claim extraction.

Internal review now uses an internal-only contradiction safety path. External regulatory conflict guards no longer override internal model decisions. A model contradiction is retained only with strong same-statement evidence or an explicit polarity conflict; differing lifecycle stages are routed to human scope review.

Findings are consolidated globally before the result limit is applied:

- directional mirrors collapse into one root finding;
- repeated missing-detail and too-vague manifestations share one root;
- the retained finding records the related-comparison and affected-source counts.

Review status and Markdown exports now distinguish:

- pair findings generated;
- root findings after consolidation;
- findings returned;
- findings omitted by the configured limit.

The agent prompt is version `governance-review-agent-v8.7` and the pair cache schema is `pair-cache-v2`, invalidating results produced by the earlier decision boundary.

## Static T1 Validation

The revised non-mutating payload check against the nine approved T1 packs produced:

- 9 documents and 36 unique document pairs;
- 65 governed sections;
- 230 substantive claims, down from 386 in the previous run;
- 0 bare `Requires validation` claims;
- 0 JSON learning-record claims.

Applying the new global consolidation logic to the previous 212 cached findings reduced them to 114 root findings before the extraction and contradiction-guard corrections were considered.

## Human Validation Run

Use **Force rerun** for the first post-fix Full Governance Review. Cache versioning should already prevent reuse, but Force rerun provides an explicit audit trail and should show all 36 pairs as forced/bypassed.

Acceptance checks:

1. Prompt version is `governance-review-agent-v8.7`.
2. All 36 pairs complete and the cache summary records 36 forced pairs.
3. Generated, consolidated, returned and truncated counts are visible in the UI and export.
4. No evidence block is a bare validation-status cell, provenance paragraph, tagging block or JSON record set.
5. Unrelated supplier/article-list JSON blocks, contract-versus-formal-request wording and pack-change-versus-supplier-readiness wording are not contradictions.
6. Supplier-shell saving versus later readiness completion is no stronger than human scope review unless the model demonstrates the same lifecycle stage.
7. Findings read as unique root concerns; one source correction is not represented by several mirrored findings.

Do not approve Tranche 2 until the Human has reviewed and accepted the post-fix export under Stage 4C.

## Verification

- Focused compliance service and application bridge tests passed.
- Full Python regression suite passed.
- `ruff check .` passed.
- Frontend TypeScript and production build passed.

The real Qwen review remains the semantic acceptance test. Static and automated tests prove the evidence boundary, safety behaviour, accounting and consolidation contracts; they do not substitute for Human review of the new findings.
