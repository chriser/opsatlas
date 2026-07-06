# Compliance Reasoning v6 Benchmark Review

Date: 2026-07-03

Reviewer: Codex

Purpose: document the latest `governance-review-agent-v6` benchmark result for Claude review before more engineering work is approved.

## Evidence Reviewed

Latest v6 benchmark:

- `docs/benchmark/compliance/deep-deep-ollama-deepseek-r1-14b-2026-07-03t15-30-39-00-00.json`
- `docs/benchmark/compliance/deep-deep-ollama-deepseek-r1-14b-2026-07-03t15-30-39-00-00.md`

Relevant prior comparison points:

- `deep-deep-ollama-deepseek-r1-14b-2026-07-03t13-06-48-00-00`
- `deep-deep-ollama-deepseek-r1-14b-2026-07-03t14-17-21-00-00`
- `deep-deep-ollama-deepseek-r1-14b-2026-07-03t14-32-42-00-00`

The latest run used:

- depth: `deep`
- model: `deepseek-r1:14b`
- runs: `3`
- fake generator: `false`
- safety gates disabled: `false`

## Result Summary

| Run | Passed | Accuracy | LLM rows | Coverage | Fallback missing-obligation count | Gate demotions |
|---|---:|---:|---:|---:|---:|---:|
| 13:06 pre-v5 baseline | 33/114 | 28.9% | 57 | 50.0% | 96 | 15 |
| 14:17 v5 gates on | 33/114 | 28.9% | 63 | 55.3% | 51 | 24 |
| 14:32 v5 gates off | 51/114 | 44.7% | 63 | 55.3% | 51 | 0 |
| 15:30 v6 latest | 84/114 | 73.7% | 90 | 78.9% | 24 | 0 |

The v6 result is a material improvement. The important change is not only the accuracy jump, but the healthier pipeline shape:

- More labelled pairs reach LLM adjudication.
- `too_vague`, `missing_detail`, `supported` and `contradiction` are now reachable in real 14B runs.
- Safety gates are no longer over-demoting valid findings in this benchmark.
- The run is stable across repeats: 0 classification flips.

## Latest Per-Class Result

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| contradiction | 1.000 | 0.875 | 0.933 | 24 |
| supported | 0.857 | 1.000 | 0.923 | 18 |
| too_vague | 1.000 | 0.833 | 0.909 | 18 |
| missing_detail | 0.667 | 0.667 | 0.667 | 18 |
| missing_obligation | 0.500 | 0.667 | 0.571 | 18 |
| not_related | 0.400 | 0.333 | 0.364 | 18 |

## Interpretation

The v6 candidate-alignment work appears successful.

Before v6, the dominant failure was candidate starvation: many pairs never reached the model and fell into `missing_obligation`. After v6, candidate coverage improved to 90/114 rows. The remaining weaknesses are narrower and easier to reason about.

The 14B model now appears capable enough for this workflow once candidate selection is working. The current evidence does not support spending time on larger model comparison before pipeline-specific fixes are reviewed.

## Remaining Failure Clusters

The latest run has 10 unique failed labels, repeated across three runs.

### 1. No-candidate not-related rows become fallback missing obligations

These rows never reached LLM adjudication:

- `not-related-vat-supply-flexibility-lists-001`
- `not-related-packaging-supplier-contract-004`
- `not-related-packaging-age-restricted-005`
- `not-related-packaging-scheduling-006`

Observed behaviour:

- expected: `not_related`
- actual: `missing_obligation`
- `llm_called`: false
- `candidate_count`: 0
- `no_alignment_reason`: `no_candidate_above_alignment_threshold`

Interpretation:

This is not a model-quality problem. It is a fallback classification issue. The engine currently treats no aligned internal candidate as a potential missing obligation when missing-obligation reporting is enabled. That is reasonable for genuine coverage gaps, but it is wrong for clearly unrelated internal passages.

Claude review question:

- Should the next slice introduce a separate no-candidate classifier that can return `not_related` versus fallback `missing_obligation`?
- If yes, should this be deterministic, LLM-backed, or hybrid?

### 2. Packaging contradiction misread as supported

Failed label:

- `packaging-contradiction-third-party-shipping-006`

Evidence:

- External: `A producer must assess whether packaging handled through third-party fulfilment still counts toward its packaging reporting threshold.`
- Internal: `Organisations can ignore packaging reporting when a third-party logistics provider ships goods on their behalf.`
- Expected: `contradiction`
- Actual: `supported`

Interpretation:

The candidate reaches the model, but the model misses that "must assess whether it still counts" conflicts with "can ignore". This is a judgement/prompt problem, not candidate starvation.

Claude review question:

- Should packaging-specific contradiction examples be added to the prompt, or should a deterministic post-check catch direct "must assess/include/retain" versus "ignore/does not apply/delete" packaging conflicts?

### 3. Packaging detail boundaries need refinement

Failed labels:

- `too-vague-packaging-threshold-005`
- `missing-detail-packaging-material-categories-004`
- `missing-detail-packaging-reusable-006`
- `missing-obligation-packaging-deadline-005`

Observed behaviour:

- Some same-topic packaging rows are now reaching LLM adjudication, which is good.
- The model still struggles to choose between `too_vague`, `missing_detail`, `missing_obligation` and `not_related` for packaging examples.

Interpretation:

This is the new main quality frontier. The model is seeing the relevant evidence but needs better classification boundaries.

Claude review question:

- Should we refine the classification rubric with concrete examples for packaging:
  - generic coverage but weak precision => `too_vague`
  - same topic but missing categories/scope/evidence rules => `missing_detail`
  - related document but no attempt to cover the obligation => `missing_obligation`
  - packaging word overlap only, different obligation => `not_related`

### 4. Semantic embedding rescue did not activate

Observed diagnostics:

- `semantic_candidate_count_total`: 0
- `embedding_error_count_total`: 0
- `anchor_candidate_count_total`: 84

Interpretation:

Embeddings did not fail, but they also did not rescue any candidate. The v6 improvement came from governed anchors, not semantic embedding rescue. This may be fine, but current diagnostics only count successful semantic rescues, not attempted semantic comparisons or max semantic score.

Claude review question:

- Should the harness add semantic-attempt and max-semantic-score diagnostics before we tune embedding thresholds?

## Proposed Next Options For Claude Review

Option A: No-candidate classifier first.

Rationale: this targets the worst remaining class (`not_related`) without disturbing the good contradiction/supported/too-vague gains.

Potential implementation:

- When no candidate passes alignment:
  - preserve fallback `missing_obligation` for plausible same-governance gaps
  - return `not_related` for clearly unrelated pairs when `include_not_related_pairs=true`
  - record `no_candidate_resolution=not_related|fallback_missing_obligation`

Risk:

- A too-aggressive no-candidate classifier could hide true missing obligations.

Option B: Packaging prompt/rule refinement first.

Rationale: six failures are candidate-present LLM judgement errors, mostly packaging.

Potential implementation:

- Add prompt examples for packaging contradictions and missing detail boundaries.
- Add narrow deterministic post-checks only for direct packaging conflicts, not broad packaging overlap.

Risk:

- Too many deterministic special cases may overfit the labelled dataset.

Option C: Diagnostic-only slice before more tuning.

Rationale: semantic embeddings did not visibly contribute. More diagnostics would prevent blind threshold tuning.

Potential implementation:

- Add `semantic_attempt_count`.
- Add `max_semantic_score`.
- Add per-row candidate-source breakdown in Markdown.

Risk:

- Does not directly improve user-facing quality, but may prevent a bad next fix.

## Codex Recommendation

Do not compare more models yet. The latest run shows 14B can produce useful results once the pipeline is shaped correctly.

Recommended order:

1. Add no-candidate resolution so unrelated no-candidate rows do not become fallback `missing_obligation`.
2. Add limited packaging rubric refinement for the specific classification boundaries now exposed.
3. Add semantic-attempt diagnostics before changing embedding thresholds.
4. Rerun the same 14B benchmark and compare against the 15:30 v6 result.

Success target for next run:

- overall accuracy above 80%
- `not_related` recall above 70%
- maintain contradiction precision at or near 100%
- preserve supported recall at or near 100%
- no significant increase in gate demotions

## Decision Needed

Claude should review whether the next approved implementation slice should be:

1. no-candidate classifier,
2. packaging rubric refinement,
3. diagnostics-first,
4. or a combined but still narrow slice.

