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
- `KP_COMPLIANCE_BALANCED_LLM_MODEL` selects the lighter Balanced adjudication
  model and defaults to `deepseek-r1:8b`; set it to `qwen2.5:7b-instruct` if you
  want to compare against the pre-DeepSeek local profile
- `KP_COMPLIANCE_DEEP_LLM_MODEL` selects the Deep audit adjudication model and
  defaults to `KP_COMPLIANCE_LLM_MODEL` or `deepseek-r1:14b`. Local benchmark
  runs on 2026-07-01 showed 14B was the best practical baseline: materially
  cleaner than 7B and faster than 32B, while 32B showed diminishing returns and
  missed one of the clearest VAT record-retention conflicts from the synthetic
  test pack.
- `KP_COMPLIANCE_BALANCED_LLM_NUM_CTX` controls the Balanced context window and
  defaults to `4096`
- `KP_COMPLIANCE_DEEP_LLM_NUM_CTX` controls the Deep context window and falls
  back to `KP_COMPLIANCE_LLM_NUM_CTX` or `KP_LLM_NUM_CTX`
- The Control Panel `Throttle Deep` toggle uses the
  `KP_COMPLIANCE_DEEP_THROTTLED_LLM_*` Ollama profile. By default it sets
  `num_gpu=0`, `num_batch=16`, `num_thread=4`, `num_ctx=4096` and a
  three-second cooldown between local LLM calls. This is intentionally much
  slower, but it avoids normal Deep Audit GPU offload.
- `KP_COMPLIANCE_DEEP_THROTTLE=1` applies the same throttling behaviour to Deep
  Audit globally. Ollama does not expose a precise 60-70% GPU cap; partial GPU
  use can be tested by raising `KP_COMPLIANCE_DEEP_THROTTLED_LLM_NUM_GPU`, but
  `0` is the safest workstation-protection default.
- `KP_COMPLIANCE_LLM_TIMEOUT` controls the per-candidate model timeout
- `KP_COMPLIANCE_PAIR_CACHE_PATH` controls the durable pair-result cache path
  and defaults to `data/compliance_reasoning_pair_cache.json`
- `KP_GOVERNANCE_LLM_ENABLED=1` opts the main Governance page into legacy
  model-backed internal contradiction checks; the default is deterministic so
  opening Governance does not load the GPU model
- `KP_GOVERNANCE_LLM_MODEL` selects the optional model for those legacy page-load
  contradiction checks without changing the Ask answer model

For the default local depth profiles:

```bash
ollama pull deepseek-r1:8b
ollama pull deepseek-r1:14b
./scripts/dev.sh
```

The review audit shows the active depth profile, for example
`balanced=ollama:deepseek-r1:8b` or `deep=ollama:deepseek-r1:14b`. Reasoning-model
responses may include private thinking blocks before the final answer, so the
service strips `<think>...</think>` blocks and fenced JSON wrappers before
parsing the required JSON decision.

To run an explicit benchmark above the default, override the model at startup:

```bash
KP_COMPLIANCE_DEEP_LLM_MODEL=deepseek-r1:32b ./scripts/dev.sh
```

The agent still has deterministic safety rails. A model cannot return a
`contradiction` solely because it reasons broadly over weakly related wording:
contradiction findings below the `min_contradiction_alignment_score` review
option, default `0.30`, are suppressed unless the two passages share enough
concrete obligation terms. This is intended to prevent low-alignment examples
such as VAT supply flexibility being matched to article-list permissions.
The current safety rails also down-rank candidate pairs with conflicting
rate-change timing contexts, for example supplies before a change date versus
supplies after a change date, and reclassify broad internal wording that omits
an external `unless`/`except` qualifier as `missing_detail` rather than direct
`contradiction`.

Supported coverage has a stricter standard than exploratory matching. A model
can only return a `supported` finding when the passages share a concrete governed
anchor, such as VAT invoice records, business-use proportion, input-tax evidence
or VAT rate-change invoicing, or when lexical alignment is very strong and there
are enough concrete shared terms. Broad terms such as VAT, tax, work, rate or
calculation are not enough by themselves. Weak supported pairs are suppressed as
not-related so the coverage list does not overstate assurance.
Contradiction findings use the same governed anchors differently: a low lexical
alignment contradiction can still be retained when both passages share a concrete
anchor, for example invoice evidence and VAT invoice-record deletion.

A deliberately incorrect upload fixture is available at
`docs/data-and-governance/test-fixtures/synthetic-vat-conflict-learning-pack.md`.
Upload, ingest and approve it in a local test environment, then run the
Governance compliance review against VAT guide Notice 700 to validate that
obvious conflicts are detected.

## Pair Cache and Reruns

Long local reviews should not be repeated when nothing has changed. The service
caches each external/internal pair result using a fingerprint made from:

- external snapshot id, version and content hash
- internal source id and content hash
- engine version, model profile and prompt version
- material review options

The default Governance action reuses cached pair results and marks them as
`cache_status=hit` in the job status. The Control Panel `Force rerun` action
sets `force_rerun=true`, bypasses cache for that job and records
`cache_status=bypassed` on each reviewed pair.

Review status includes elapsed seconds, current-pair elapsed seconds, cache
hit/miss/bypass counts and per-pair durations. The Control Panel deliberately
avoids a precise ETA when a reasoning model is working through uneven document
pairs. It now shows cautious timing labels such as early estimate, approximate
range or long-running pair; timing uncertain. This is important because a large
pair, for example a full VAT guide against a synthetic VAT pack, can dominate
the whole run even when earlier pairs were quick.

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
- `GET /api/compliance-reasoning/resolutions`
- `POST /api/compliance-reasoning/resolutions`
- `POST /api/compliance-reasoning/findings/reconcile`

The bridge is enabled only when `KP_COMPLIANCE_REASONING_URL` is configured, for
example:

```bash
KP_COMPLIANCE_REASONING_URL=http://127.0.0.1:5310
```

The main app builds the review payload from approved internal sources and stored
external snapshots. Pending or rejected internal sources are excluded.

## Control Panel Surface

The Governance page is organised around:

- `Internal Source Review` for internal source quality, consistency and
  correctness checks
- `External Source Review` for DeepSeek-backed comparison of external
  obligations and approved internal wording
- `Source approval` for approval state plus internal/external review outcomes

The Internal Source Review surface now has its own queued run control, force
rerun action, progress bar, elapsed time and cache state. It still uses the
existing internal knowledge-intelligence checks, with the configured governance
model available for bounded internal contradiction checks.

The External Source Review surface shows elapsed time, current-pair elapsed
time, cautious timing labels, cache reuse, finding definitions, clickable
classification filters, advisor-style explanations and a resolution workbench.
The workbench shows read-only external evidence beside the editable internal
source, prints the original internal wording next to the suggested wording,
shows whether that original wording is still present in the current source,
saves the source through the existing edit/re-ingest path and records a human
resolution such as fixed, acknowledged, accepted risk, dismissed, SME review or
superseded by source edit.

After a source edit, the bridge can reconcile the latest findings against the
current source text. Open findings whose original internal wording no longer
exists are recorded as `superseded_by_source_edit`, hidden from the default open
queue and retained in the audit trail. Findings that share the same original
wording are grouped so one source edit can clear related stale findings.

The previous keyword-based review remains available as `Regulatory signals` so
operators can distinguish lightweight topic triage from evidence-backed
compliance comparison. It is collapsed and positioned at the bottom of the
Governance page.
