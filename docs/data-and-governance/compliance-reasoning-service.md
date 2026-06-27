# Standalone Compliance Reasoning Service

The compliance reasoning engine is intentionally separated from the main
Knowledge Platform API. The main app remains the workflow owner: it supplies
approved internal evidence and selected public snapshots, stores or displays the
returned findings, and controls human review decisions.

The service does not approve, reject, edit or mutate knowledge sources.

## Purpose

The existing Regulatory candidate review is transparent keyword triage. It is
useful for surfacing topics, but it cannot reason over what legislation says
against what internal documents say.

The standalone service is the foundation for a stronger workflow:

- extract external obligations, prohibitions and permissions
- extract comparable internal claims
- align likely related statements
- classify supported wording, contradictions, missing obligations and vague
  wording
- preserve evidence, source hashes and model/run metadata for review

## API Contract

Current baseline endpoints:

- `GET /health`
- `GET /v1/capabilities`
- `POST /v1/reviews`
- `GET /v1/reviews/{job_id}`
- `GET /v1/reviews/{job_id}/findings`

`POST /v1/reviews` accepts external evidence documents and internal evidence
documents. Each document contains source metadata plus section-level text and
citations. Reviews run as queued pairwise jobs: the service checks external
document 1 against internal document 1, then external document 1 against
internal document 2, and so on until every approved internal source has been
checked against every selected external source.

The initial response includes a `queued`, `running` or already `completed`
status. Call `GET /v1/reviews/{job_id}` to poll progress and
`GET /v1/reviews/{job_id}/findings` to load findings when the job completes.

The review payload includes:

- review status and audit metadata
- pair totals, completed pair count and current pair progress
- extracted external obligations
- extracted internal claims
- evidence-backed findings

Finding classifications:

- `supported`
- `contradiction`
- `missing_obligation`
- `too_vague`
- `outdated`
- `unsupported_claim`
- `not_related`
- `needs_human_review`

Broad `missing_obligation` coverage-gap findings are opt-in. The Governance
control panel keeps them suppressed by default so the review view focuses on
actual aligned comparisons rather than every external obligation that the
deterministic fallback could not match internally.

## Baseline Engine

The first implementation uses a deterministic baseline inside the queued
workflow:

- sentence-level modal extraction for `must`, `shall`, `required`, `must not`,
  `may`, `optional` and related wording
- simple actor/action/condition extraction
- pair-level relevance gating so unrelated documents are suppressed before
  obligation comparison
- term-overlap alignment between external obligations and internal claims within
  a related pair
- statement alignment requires at least two meaningful shared terms; generic
  modal/helper words such as `may`, `must` and `needed` are ignored so they
  cannot create false contradictions by themselves
- opt-in coverage-gap reporting for unmatched external obligations
- conservative finding classification

This is not the target intelligence layer. It exists so the API contract,
service boundary, queued orchestration, progress UI and integration shape can be
built before adding model dependencies.

## Planned Model-backed Pipeline

The next intelligence slice should add replaceable model adapters while keeping
the queued pairwise workflow:

- structured obligation extraction using a local LLM with strict JSON output
- semantic retrieval with a local embedding model such as BGE-M3
- reranking of obligation/claim pairs
- NLI contradiction scoring
- long-context LLM adjudication for rationale and final review classification
  inside each external/internal pair

The service should keep the same public API while these internals change.

## Local Run

From the repository root:

```bash
PYTHONPATH=. .venv/bin/uvicorn services.compliance_reasoning.app:app --port 5310
```

OpenAPI docs will be available at:

```text
http://127.0.0.1:5310/docs
```

## Main App Integration Rule

The main app should call this service through a feature-flagged client. When the
flag is disabled, Governance should behave exactly as it does today. When the
service is unreachable, Governance should show a clear status message and keep
the existing keyword Regulatory candidate review available.

Current backend bridge:

- `GET /api/compliance-reasoning/status`
- `GET /api/compliance-reasoning/capabilities`
- `POST /api/compliance-reasoning/reviews`
- `GET /api/compliance-reasoning/reviews/{job_id}`
- `GET /api/compliance-reasoning/reviews/{job_id}/findings`

The bridge is enabled only when `KP_COMPLIANCE_REASONING_URL` is configured, for
example:

```bash
KP_COMPLIANCE_REASONING_URL=http://127.0.0.1:5310
```

The main app builds the review payload from approved internal sources and stored
external snapshots. Pending or rejected internal sources are excluded.

## Control Panel Surface

The Governance page now includes a `Compliance reasoning review` panel. It shows
the standalone service status, starts the queued review, polls the review status,
shows a pairwise progress bar, and displays findings with external evidence and
internal evidence side by side.

The previous keyword-based review remains available as `Regulatory signals` so
operators can distinguish lightweight topic triage from evidence-backed
compliance comparison.
