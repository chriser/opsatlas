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
or disbursement evidence, or when lexical alignment is very strong and there are
enough concrete shared terms. VAT rate-change wording is treated as a broad
anchor: it can support coverage only when the aligned passage is still strong,
but it does not rescue low-alignment contradictions. Broad terms such as VAT,
tax, work, rate or calculation are not enough by themselves. Weak supported
pairs are suppressed as not-related so the coverage list does not overstate
assurance.
Contradiction findings use the same governed anchors differently: a low lexical
alignment contradiction can still be retained when both passages share a concrete
anchor, for example invoice evidence and VAT invoice-record deletion.

A deliberately incorrect upload fixture is available at
`docs/data-and-governance/test-fixtures/synthetic-vat-conflict-learning-pack.md`.
Upload, ingest and approve it in a local test environment, then run the
Governance compliance review against VAT guide Notice 700 to validate that
obvious conflicts are detected.

## Evidence-Based Evaluation Harness

The reasoning engine is now benchmarked against a labelled fixture set rather
than judged only from ad hoc exported review files. The fixture corpus lives at
`tests/evaluation/compliance_reasoning_labels.json` and currently contains 74
labelled external/internal evidence pairs:

- VAT, anchored on VAT guide Notice 700 style obligations
- packaging waste, anchored on producer responsibility and evidence-retention
  style obligations
- the former bribery holdout set, now rotated into the training/regression
  corpus after v8.3 tuning touched its failures
- the former data-protection holdout set, now rotated into training after the
  v8.4 review exposed generic contradiction/polarity failures
- a fresh synthetic accessibility holdout set, used as the next clean
  generalisation check with no domain-specific anchors or guards

The labelled classes are:

- `contradiction`
- `supported`
- `too_vague`
- `missing_obligation`
- `missing_detail`
- `not_related`

The labels intentionally include both true positives and false-positive traps,
including the known VAT rate-change timing case, omitted `unless`/`except`
qualifier cases and pairs where similar words do not mean the passages are about
the same obligation.

Labels are now split into `training` and `holdout`. The training split contains
examples that have been used during prompt/gate tuning or failure analysis, so
it proves regression safety rather than generalisation. The holdout split must
stay clean: no prompt, guard or anchor should be written against those labels
before the next real benchmark is reviewed. Model comparison work remains on
hold until the clean holdout and model-only ablation metrics are visible,
because otherwise a larger model can appear better or worse while the candidate
pipeline is still starving or overfitting pairs.

A second deliberately incorrect upload fixture is available at
`docs/data-and-governance/test-fixtures/synthetic-packaging-waste-conflict-learning-pack.md`.
Use it the same way as the VAT fixture: local test environment only, never as
approved production knowledge.

Run the harness with:

```bash
.venv/bin/python scripts/evaluate_compliance_reasoning.py --depth deep --model deepseek-r1:14b --runs 3
```

The harness writes a markdown scorecard and JSON record under
`docs/benchmark/compliance/`. Each scorecard includes:

- overall accuracy
- per-class precision, recall and F1
- confusion matrix
- mean and p95 pair latency
- split latency for LLM-called rows versus deterministic rows
- adjudicator coverage: `llm_called`, `candidate_count`,
  `adjudication_count` and never-adjudicated counts by expected class
- split metrics for training versus holdout labels
- guard ablation: model-only accuracy, with-guards accuracy, guard-changed
  classifications and whether each guard change helped or hurt
- candidate-source counts for lexical, governed-anchor and semantic rescues
- semantic diagnostics: attempted comparisons, max semantic score and semantic
  score distribution
- no-candidate resolution counts, separating fallback missing-obligation from
  deterministic not-related decisions
- gate-demotion reasons such as low concrete overlap, timing mismatch,
  exception qualifier or supported-coverage suppression
- prompt context estimates: observed prompt count, mean/max prompt-token
  estimate and near-context-limit prompt count
- total runtime
- classification stability across repeated runs

The `--fake-generator` option is for CI smoke testing only. It validates that
the harness, schema, report writer and production service path can run without
Ollama. It is not evidence that a model profile is good. Real scorecards from
local Ollama runs remain the quality benchmark.


## v8.1 Repair Plan

The v8 real benchmark from 2026-07-03 22:53 UTC improved total accuracy from
58% to 66%, in-domain accuracy from 63% to 71% and holdout accuracy from 42% to
50%. That is useful progress, but it did not meet the agreed release gate. The
run also exposed a pipeline defect: the new same-obligation screen was invoked
33 times and errored 33 times, with zero recorded passes or rejects. Therefore
v8 did not fairly test the intended generalisation mechanism.

v8.1 addresses the following fixes before any model-comparison work resumes:

- record same-obligation screen error type and message in diagnostics and
  scorecards, so parser/model availability failures are visible rather than
  hidden behind a generic `error` marker
- treat screen failures as `needs_human_review` rather than deterministic
  `missing_obligation`, preventing alignment outages from becoming false
  compliance gaps
- treat clean same-obligation screen rejects as `not_related` rather than
  fallback missing obligations
- include the balanced screen model in the deep benchmark model profile, so a
  scorecard shows both the deep adjudicator and the bounded screen model
- narrow the direct-conflict guard so it restores only high-precision polarity
  conflicts, not every deterministic baseline contradiction
- add generic class-boundary guards for the repeated confusion between
  `too_vague`, `missing_detail` and `not_related`
- relax supported-coverage gating for high-scoring semantic candidates with no
  goods/services, VAT/list-logic or business/private-use mismatch, so holdout
  support evidence is not suppressed just because it lacks VAT/packaging anchors

The next real benchmark gate is: zero same-obligation screen errors, zero
protected v6 baseline flips, no no-LLM `supported` rows, contradiction precision
held, in-domain accuracy at least 80%, and holdout coverage/accuracy materially
better than v8. #1117 model comparison remains blocked until this v8.1 scorecard
is reviewed.

## v8.2 Repair Plan

The v8.1 benchmark from 2026-07-04 reached 80% overall accuracy with zero
same-obligation screen errors and strong holdout not-related precision. The
remaining failures were concentrated in the opposite direction: the screen
rejected too many real obligations as unrelated, especially missing-obligation
and missing-detail cases. Four protected v6 labels were still flipped.

v8.2 keeps the bounded same-obligation screen, but adds a second-stage
resolution policy for screen rejects:

- screen rejects become `not_related` only when the external obligation is
  genuinely outside the internal source family
- screen rejects remain actionable missing obligations when the internal source
  is clearly in the VAT, packaging or anti-bribery source family but omits the
  concrete obligation
- obvious prohibition-versus-permission polarity conflicts can override a
  screen reject and proceed to deep adjudication
- generic anti-bribery and record-retention anchors are available to the same
  candidate-rescue path as VAT and packaging anchors, reducing benchmark-only
  regex coupling
- class-boundary guards now distinguish missing obligations from missing
  details for invoice-correction, packaging deadline, reusable packaging and
  packaging-category gaps
- scorecards expose `same_obligation_screen_override_count` so polarity
  overrides are visible during v8.2 review

The v8.2 benchmark gate remains: no protected v6 baseline flips, contradiction
precision held at 1.0, no no-LLM supported rows, in-domain accuracy at least
80%, holdout accuracy within 15 points of in-domain, and holdout LLM/screen
coverage high enough to show the engine is generalising rather than memorising
the labelled VAT/packaging set.

## v8.3 Repair Plan

The v8.2 benchmark from 2026-07-04 reached 90% overall accuracy, 92%
in-domain accuracy and 83% holdout accuracy with zero same-obligation screen
errors, 100% contradiction precision and no classification instability. The
remaining failures were concentrated in five stable labels, which made the next
slice narrow enough to treat as pipeline repair rather than broad prompt
tuning.

v8.3 addresses three defects:

- the screen-reject source-family resolver now uses only the internal source
  title, heading and text when deciding whether an internal source is in scope.
  It no longer lets the external title, such as "Packaging waste producer
  responsibility guidance", make an unrelated article-list or integration
  scheduling source look like a packaging control.
- the sentence extractor now captures negated "No X is required" internal
  claims. This allows anti-bribery training/evidence denials to reach the
  agent and direct-conflict guard instead of becoming a no-candidate missing
  obligation fallback.
- VAT input-tax evidence gaps are recovered as missing obligations when the
  internal wording is about supplier/payment/approval records but does not
  mention VAT evidence, VAT invoices, reclaim, recovery or input tax. Generic
  VAT paperwork wording remains a partial coverage case and is not promoted to
  missing obligation.

The supported-training holdout label remains a review question rather than a
code fix. The model treated annual high-risk-role training as `missing_detail`
against an external "proportionately to risk" training obligation. That may be
a useful governance challenge rather than a clear engine failure, so it should
be reviewed with the labelled corpus before adding another guard.

## v8.4 Evaluation Reset

The v8.3 benchmark from 2026-07-04 reached 96% overall accuracy and 100%
accuracy on the old in-domain labels. That score is treated as benchmark
saturation, not proof that the reasoning engine is solved. The main evidence is
that a material share of rows only passed after deterministic guards rewrote the
model's own classification, and the former bribery holdout had already been
used to drive post-run fixes. From v8.4 onward:

- the old VAT, packaging and bribery labels are the `training` split
- clean generalisation is measured only against the new
  `data_protection_holdout` labels
- prompt and gate tuning is frozen until the next clean scorecard is reviewed
- each scorecard reports model-only versus with-guards accuracy, so reviewers
  can see whether the model reasoned correctly or whether the deterministic
  guard layer carried the result
- #1117 model comparison remains blocked until a clean holdout scorecard and
  ablation result exist

## v8.4 Clean Scorecard Review

The first v8.4 clean-holdout scorecard
`docs/benchmark/compliance/deep-balanced-ollama-deepseek-r1-8b-deep-ollama-deepseek-r1-14b-2026-07-04t14-41-15-00-00.*`
ran DeepSeek-R1 14B with the Balanced 8B same-obligation screen. It passed
171/186 labelled rows overall, but the useful evidence is the split:

- training: 144/150 passed (96%)
- data-protection holdout: 27/36 passed (75%)
- model-only on the holdout: 30/36 passed (83%)
- with-guards on the holdout: 27/36 passed (75%)
- guard changes helped 36 training rows but hurt 3 holdout rows
- contradiction precision stayed at 100%, but holdout contradiction recall was
  only 25% after guards and 50% model-only
- there were zero same-obligation screen errors, zero embedding errors, zero
  classification flips and no prompt-context pressure

The result confirms that the old training split is saturated and that the guard
layer is carrying old-domain performance while damaging fresh-domain
generalisation. The data-protection labels are therefore no longer clean
holdout labels; they have been rotated into training/regression evidence. The
next implementation slice should be generic, not data-protection-specific:

- repair the contradiction safety gate so it does not demote a model-classified
  contradiction to `not_related` solely because concrete term overlap is low
  when obligation-vs-permission polarity is present (#1154)
- improve polarity/candidate alignment for generic pairs such as deadline
  obligation versus allowed delay, erase/delete versus retain indefinitely, and
  allow/withdraw versus cannot/remove (#1155)
- use the new accessibility holdout as the clean post-fix generalisation gate
  (#1156)

First real baseline, generated on 2026-07-03 with
`deepseek-r1:14b --depth deep --runs 3`, is stored under
`docs/benchmark/compliance/deep-deep-ollama-deepseek-r1-14b-2026-07-03t11-57-06-00-00.*`.
It passed 33/114 labelled run rows (29%) with no classification flips. The
important diagnostic is that 96/114 rows were classified as
`missing_obligation`, including all `too_vague` and `not_related` labels. This
means the next quality slice should improve candidate selection and relevance
gating before running broad model comparisons: too many labelled pairs never
reach useful same-obligation adjudication.

Scorecards generated after #1123 include explicit observability fields so this
failure mode no longer has to be inferred from `0.0s` latency. The harness now
separates three cases:

- no candidate alignment, where the adjudicator is never called
- an LLM adjudication that returns or is demoted to not-related
- an LLM adjudication that is changed by a named safety gate

The 2026-07-03 13:06 rerun
`deep-deep-ollama-deepseek-r1-14b-2026-07-03t13-06-48-00-00.*` kept the same
33/114 result but proved the failure shape: 57/114 rows called the LLM, 57/114
never reached adjudication, prompt context was not under pressure, and the
largest failure bucket was still fallback into `missing_obligation`. This
confirmed that the next work should improve candidate routing and fallback
classification before comparing larger models.

After #1121/#1124 diagnostics, scorecards also include:

- `disable_safety_gates`, so the same benchmark can be run gates-on and
  gates-off for A/B analysis
- model, final, accepted and rejected decision-class counts
- rejected candidate findings retained when `include_not_related_pairs=true`

Run the gates-off comparison with:

```bash
.venv/bin/python scripts/evaluate_compliance_reasoning.py --depth deep --model deepseek-r1:14b --runs 3 --disable-safety-gates
```

Prompt-context estimates use a simple `len(prompt) / 4` token heuristic. A prompt
is flagged as near the context limit when the estimate reaches 80% of the
configured `num_ctx`. This is not tokenizer-perfect, but it is sufficient to
show whether quality problems correlate with context pressure.

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

Agent gate changes must bump the agent prompt/cache version, because the pair
cache key includes the prompt version. `governance-review-agent-v3` introduced
the narrower anchor rescue policy above so older broad VAT rate-change decisions
are not reused by new runs. `governance-review-agent-v4` added result
consolidation and supported-coverage discipline: repeated action findings
against the same internal wording are collapsed into one representative finding,
supported coverage is only kept when no edit/review action is proposed, and
goods-only guidance is not treated as support for services-only wording.
`governance-review-agent-v5` added benchmark-oriented A/B diagnostics, allowed
the external adjudicator to deliberately return `missing_obligation`, and keeps
rejected not-related candidate decisions visible when the review explicitly
requests not-related findings.
`governance-review-agent-v6` added embedding-assisted candidate alignment
using the local Ollama embedding model configured by
`KP_COMPLIANCE_EMBED_MODEL` (default `nomic-embed-text`). The embedding path is
only a candidate rescue layer; if embeddings are unavailable, the agent falls
back to lexical and governed-anchor matching. v6 also added governed VAT and
packaging anchors, made `too_vague` and `missing_detail` prompt guidance more
explicit, preserved true invoice-rate and packaging-scope contradictions through
the safety gate, and marks no-candidate `missing_obligation` findings as
fallbacks so they are not confused with model-adjudicated missing obligations.
When semantic alignment is enabled, the prompt/cache version includes the
embedding model and semantic threshold so cached lexical-only results are not
reused for embedding-assisted runs.
`governance-review-agent-v7` added the next benchmark-quality slice approved
after Claude's v6 review. It lowers the default semantic candidate threshold to
`0.58`, records semantic attempts and maximum scores even when no semantic
candidate is rescued, adds a deterministic no-candidate resolver, replaces
domain-specific packaging post-checks with a generic obligation-versus-dismissal
polarity guard, and reports in-domain versus holdout metrics separately. The
no-candidate resolver is deliberately cautious: it only returns `not_related`
after semantic comparison has actually run and the best measured alignment stays
below the low-similarity threshold. If embeddings are unavailable, no-candidate
obligations remain fallback `missing_obligation` findings rather than being
guessed away. The payload builder also excludes `Expected Governance Review
Outcome` sections from synthetic test fixtures so benchmark answers are never
fed into the review evidence.

`governance-review-agent-v8` responds to the 2026-07-03 v7 scorecard review.
The v7 holdout split proved the VAT/packaging anchor path did not generalise:
holdout accuracy was 42%, holdout LLM coverage was 17%, and the measured
semantic-score bands overlapped too heavily for threshold tuning to solve the
problem. v8 therefore adds:

- `tests/evaluation/compliance_regression_baseline.json`, a committed v6
  in-domain all-pass baseline, plus a CI-safe fake-generator regression test
  that fails if protected labels flip
- a hard safety rule that empty comparable-pair results classify as
  `needs_human_review`, never `supported`; no LLM/no finding cannot produce
  assurance
- a generic scope-rule extractor for `associated with`, `applies to`,
  `includes`, `covers`, in-scope and out-of-scope wording so definitional legal
  passages can reach review
- a bounded same-obligation screen for no-candidate pairs. The screen uses the
  Balanced model profile, only runs for semantic near misses, records call,
  pass/reject/error and latency diagnostics, and sends screen-passed pairs to
  normal Deep adjudication
- a direct-conflict guard that restores obvious same-obligation conflicts when
  the model downgrades them to missing detail or human review
- a domain-agnostic supported-coverage fallback for LLM-supported pairs with
  enough concrete shared terms, so supported coverage is not limited to
  VAT/packaging anchors

For a v8 real benchmark, run:

```bash
KP_COMPLIANCE_EMBEDDINGS_ENABLED=1 \
KP_COMPLIANCE_EMBED_MODEL=nomic-embed-text \
KP_COMPLIANCE_SEMANTIC_CANDIDATE_SCORE=0.58 \
KP_COMPLIANCE_BALANCED_LLM_MODEL=deepseek-r1:8b \
KP_COMPLIANCE_DEEP_LLM_MODEL=deepseek-r1:14b \
KP_COMPLIANCE_DEEP_LLM_TIMEOUT=600 \
KP_COMPLIANCE_LLM_NUM_CTX=8192 \
.venv/bin/python scripts/evaluate_compliance_reasoning.py --depth deep --model deepseek-r1:14b --runs 3 --format markdown
```

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
- `GET /api/compliance-reasoning/reviews/latest`
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
When a completed external review is polled through the bridge, the main app
persists the completed status and findings in
`compliance_reasoning_latest_review.json`. The Governance page reloads this
snapshot so the displayed latest review reflects the actual completed model
profile and timestamp rather than stale browser state.
The service also consolidates repeated findings before export: if multiple
external snippets identify the same action against the same internal sentence,
the strongest representative is retained and marked with a
`consolidated_related_findings` signal. Supported coverage is similarly
de-duplicated by internal wording so benchmark exports stay readable.
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
