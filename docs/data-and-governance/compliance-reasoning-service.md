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
- `missing_detail`
- `too_vague`
- `outdated`
- `unsupported_claim`
- `not_related`
- `needs_human_review`

Broad `missing_obligation` coverage-gap findings are opt-in. The Governance
control panel keeps them suppressed by default so the review view focuses on
actual aligned comparisons rather than every external obligation that the
deterministic fallback could not match internally.

## Governance Review Agent

The local development workflow now enables a bounded Governance Review Agent by
default. It is not an autonomous agent framework. It is a narrow adjudicator
inside the standalone service:

- deterministic extraction first identifies external obligations and internal
  governed claims
- lexical alignment proposes a small number of candidate obligation/claim pairs
- a local Ollama model reviews each candidate pair and first answers the
  threshold question: are these passages about the same obligation?
- the service only returns `contradiction` when the model says the passages are
  about the same obligation and the internal wording conflicts with the external
  requirement
- if the local model is unavailable, candidate pairs are demoted to
  `needs_human_review` instead of being treated as confirmed contradictions

This design keeps the slow-but-accurate queued workflow the user requested: each
external source is compared with each approved internal source one pair at a
time, and the Governance page polls progress while work is running.

Agent mode is controlled by environment variables:

- `KP_COMPLIANCE_AGENT_ENABLED=1` enables the Governance Review Agent
- `KP_OLLAMA_URL` points to the local Ollama endpoint
- `KP_COMPLIANCE_LLM_MODEL` selects the compliance adjudication model and falls
  back to `KP_LLM_MODEL`
- `KP_COMPLIANCE_LLM_NUM_CTX` controls the context window and falls back to
  `KP_LLM_NUM_CTX`
- `KP_COMPLIANCE_LLM_TIMEOUT` controls the per-candidate model timeout

For a local DeepSeek-R1 adjudicator:

```bash
ollama pull deepseek-r1:14b
KP_COMPLIANCE_LLM_MODEL=deepseek-r1:14b ./scripts/dev.sh
```

The review audit will show the active model as
`local-llm-adjudicator:<model-name>`. Reasoning-model responses may include
private thinking blocks before the final answer, so the service strips
`<think>...</think>` blocks and fenced JSON wrappers before parsing the required
JSON decision.

The agent still has deterministic safety rails. A model cannot return a
`contradiction` solely because it reasons broadly over weakly related wording:
contradiction findings below the `min_contradiction_alignment_score` review
option, default `0.30`, are suppressed unless the two passages share enough
concrete obligation terms. This is intended to prevent low-alignment examples
such as VAT supply flexibility being matched to article-list permissions.

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
  modal/helper or discourse words such as `may`, `must`, `needed`, `but` and
  `still` are ignored so they cannot create false contradictions by themselves
- opt-in coverage-gap reporting for unmatched external obligations
- conservative finding classification

When agent mode is off, this baseline remains available as the deterministic
fallback. It is intentionally conservative and should be used as transparent
triage, not as a final compliance conclusion.

## Future Model-backed Pipeline

The next intelligence slices can add replaceable model adapters while keeping
the same queued pairwise workflow:

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
PYTHONPATH=. KP_COMPLIANCE_AGENT_ENABLED=1 \
  .venv/bin/python -m uvicorn services.compliance_reasoning.app:app --host 127.0.0.1 --port 5310
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
