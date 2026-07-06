# RAG vs OAG Benchmark

## Purpose

This benchmark measures whether ontology-assisted generation improves Ask answers where the question needs structured process facts, while preserving normal RAG performance for narrative explanation and refusal behaviour for out-of-scope questions.

The benchmark compares three answer-routing configurations:

- `rag_only`: ontology routing disabled. This is the baseline document-RAG path.
- `oag_first`: production routing. Structured questions try ontology facts first, and narrative questions can still use document evidence plus compact ontology process evidence.
- `oag_only`: ontology-only boundary probe. This should perform well on structured facts and degrade on narrative questions.

## Label Set

Labels live in `tests/evaluation/rag_vs_oag_questions.json`.

The current registered set is `rag-vs-oag-v2` and contains 69 questions split into two evidence groups:

- `tuning`: 45 original questions used as the regression/training set for OAG Phase A.
- `holdout`: 24 fresh questions used as decision-grade evidence for routing changes.

The full set contains:

- 14 structured entity questions
- 14 structured relationship questions
- 9 aggregate/list questions
- 14 narrative questions
- 9 out-of-scope questions
- 9 mixed structured-plus-explanatory questions

The holdout split adds four questions in each category. These should not be tuned against directly; they exist to catch overfitting before routing changes are accepted.

Each label records the question, expected answer path, and atomic expected facts. The scoring rule is deterministic: answer text and expected fact aliases are normalised to lowercase alphanumeric tokens, and a fact is counted as hit when either the canonical fact text or one alias appears in the answer.

Because real model answers often paraphrase the registered facts, the scorer also has a generic fallback: if no exact phrase matches, it compares content-bearing tokens after simple plural and verb-ending normalisation. A fact can pass when content-token coverage is at least `0.72` with no more than two missing content tokens. This is deliberately generic and applies to every label; it is not tuned to a specific answer.

Out-of-scope labels pass when the answer refuses or clearly states that the requested evidence is absent from the approved corpus.

## Harness

The harness entry point is:

```bash
.venv/bin/python scripts/evaluate_rag_vs_oag.py --runs 3
```

Outputs are written to `docs/benchmark/oag/` as timestamped `.md` and `.json` scorecards.

Long real-model runs now print row-level progress to stderr:

- row number and total row count
- run/config/question id/split/category
- row pass/fail, answer path and row latency
- elapsed time and rough ETA

Use `--no-progress` only when running from automation that captures structured output separately.

To run one evidence split only:

```bash
.venv/bin/python scripts/evaluate_rag_vs_oag.py --split holdout --runs 3
.venv/bin/python scripts/evaluate_rag_vs_oag.py --split tuning --runs 3
```

For CI and arithmetic-only validation, use fake mode:

```bash
.venv/bin/python scripts/evaluate_rag_vs_oag.py --fake-generator --runs 2 --output-dir /tmp/kp-oag-benchmark
```

Fake mode is not model-quality evidence. It only proves that scoring, path matrices, citation counts and stability calculations work.

To rescore a previously captured real run after scorer fixes:

```bash
.venv/bin/python scripts/evaluate_rag_vs_oag.py \
  --rescore-existing docs/benchmark/oag/<existing-scorecard>.json
```

This reuses the captured answers, paths, citations and latency, and only reapplies the current deterministic fact scorer.

## Scorecard Contents

Each real scorecard records:

- question, category, config and run number
- answer text
- expected facts hit and missed
- pass/fail
- answer path taken: `oag`, `rag`, `rag+ontology` or other
- benchmark split: `tuning` or `holdout`
- citation types used: document, ontology object, process registry or none
- latency
- per-config and per-category accuracy
- per-config and per-split accuracy
- path usage matrix
- citation type matrix
- stability across runs
- code state: git branch, commit, dirty flag, dirty path count and a small dirty-path sample

## Interpretation Gates

The benchmark is useful only when interpreted by category.

The expected decision pattern is:

- `oag_first` should beat `rag_only` on `structured_relationship` and `aggregate`.
- `oag_first` should not lose materially against `rag_only` on `narrative`.
- `out_of_scope` refusal should be preserved.
- `oag_only` is expected to degrade on narrative questions; that confirms it is a boundary probe rather than the target user mode.
- Holdout split results should drive new routing decisions. Tuning split results should be treated as regression evidence.

If `oag_first` improves structured categories but damages narrative or refusal behaviour, routing should be adjusted before expanding ontology use.

## Current Implementation Notes

`AnswerService.answer()` now accepts a `routing_mode` argument while preserving the default production behaviour:

- `oag_first` is the default used by the Ask API.
- `rag_only` skips ontology-first routing and skips ontology fallback evidence.
- `oag_only` returns only ontology-backed structured answers and otherwise refuses.

This keeps the benchmark faithful to production code without monkey-patching internals.

OAG-6.2 adds a more explicit routing boundary:

- Questions can now classify as `mixed` when they contain both structured and narrative intent.
- Pure structured questions can use direct OAG role lookup for explicit "who owns", "who is responsible" and roles-list patterns.
- Action-specific role questions such as "who creates", "who controls" or "who validates" remain RAG-led with ontology process evidence until the ontology records action-specific role semantics.
- Mixed questions remain RAG-led, but the RAG prompt is augmented with both the structured ontology evidence and the compact process evidence.
- Unsupported lookup patterns such as named employees, future facts and supplier-selection advice are excluded from direct OAG lookup so refusal behaviour is preserved.

The intended effect is composition rather than model substitution: OAG-first should answer mixed questions with document explanation plus ontology facts, while OAG-only remains a boundary probe.

## Validation Status

Hermetic validation has passed for:

```bash
.venv/bin/python -m pytest tests/test_answer.py tests/test_rag_vs_oag_eval.py tests/test_rag_vs_oag_labels.py
RUFF_CACHE_DIR=/tmp/kp-ruff-cache .venv/bin/ruff check src/assistant/answer/service.py src/assistant/eval/rag_vs_oag.py scripts/evaluate_rag_vs_oag.py tests/test_answer.py tests/test_rag_vs_oag_eval.py tests/test_rag_vs_oag_labels.py
```

## First Real Run

The first real three-run scorecard was captured on 2026-07-05 using:

- LLM: `qwen2.5:7b-instruct`
- Embeddings: `nomic-embed-text`
- Runs: `3`
- Dataset: `rag-vs-oag-v1`

The original run exposed a scorer defect: many correct paraphrased answers were marked as failures because the first scorer required exact phrase matching. The captured answers were preserved and rescored with the generic content-token fallback described above.

Corrected scorecard:

- Raw captured run: `docs/benchmark/oag/rag-vs-oag-rag_only-oag_first-oag_only-2026-07-05T16-52-10+00-00.json`
- Corrected scorecard: `docs/benchmark/oag/rag-vs-oag-rag_only-oag_first-oag_only-2026-07-05T18-07-41+00-00.json`

Headline corrected result:

| Config | Accuracy | Stable | Mean latency | P95 latency |
|---|---:|---:|---:|---:|
| `rag_only` | 64% | 35/45 | 3.26s | 5.94s |
| `oag_first` | 70% | 40/45 | 2.56s | 4.72s |
| `oag_only` | 18% | 45/45 | 0.14s | 1.08s |

Interpretation targets:

- Structured relationship lift: `+10%`
- Aggregate lift: `+33%`
- Narrative loss: `+7%` (gain, not loss)
- Out-of-scope preserved: `100%`

Decision: `#1152` is satisfied as a benchmark harness and first evidence baseline. The benchmark shows OAG-first is currently the best routing mode, but it also exposes follow-up work: mixed questions are weak, structured entity ownership questions sometimes fall back to RAG+ontology instead of clean ontology objects, and OAG-only is useful as a boundary probe rather than a target user mode.

## Repeat Confirmation Run

A second real three-run benchmark was run on 2026-07-05 after the scorer fix using the same dataset and model profile:

- LLM: `qwen2.5:7b-instruct`
- Embeddings: `nomic-embed-text`
- Runs: `3`
- Dataset: `rag-vs-oag-v1`
- Scorecard: `docs/benchmark/oag/rag-vs-oag-rag_only-oag_first-oag_only-2026-07-05T18-42-05+00-00.json`

This was a fresh model run, not a rescore. It has no `rescored_from` field, and row-level answers differ from the corrected baseline because the local LLM is not fully deterministic in practice.

Headline repeat result:

| Config | Accuracy | Stable | Mean latency | P95 latency |
|---|---:|---:|---:|---:|
| `rag_only` | 67% | 33/45 | 3.39s | 5.79s |
| `oag_first` | 70% | 39/45 | 2.57s | 4.67s |
| `oag_only` | 18% | 45/45 | 0.17s | 1.14s |

Repeat-run interpretation targets:

- Structured relationship lift: `+3%`
- Aggregate lift: `+27%`
- Narrative result: `+3%` (gain, not loss)
- Out-of-scope preserved: `100%`

Interpretation: the repeat run confirms the same architectural decision even though the lift is narrower. OAG-first remains the best routing mode, OAG-only remains a boundary probe, and refusal behaviour remains intact. The narrowed structured-relationship lift suggests the next useful work is not another model comparison; it is targeted OAG routing/composition quality improvement.

## OAG-6.1 Dataset Split

OAG-6.1 expands the benchmark to `rag-vs-oag-v2`.

The original 45-label `rag-vs-oag-v1` dataset is preserved as the `tuning` split so previous evidence remains comparable and useful as regression coverage. The new 24-label `holdout` split adds four labels per category, covering:

- fresh structured ownership questions
- fresh structured dependency questions
- fresh aggregate/list questions
- fresh narrative explanation questions
- fresh refusal/out-of-scope questions
- fresh mixed structured-plus-narrative questions

The harness now reports:

- `summary.split_filter`
- `summary.split_counts`
- `summary.evaluated_question_count`
- `by_split`
- `by_split_category`
- row-level `split`

This mirrors the compliance-reasoning lesson: once a benchmark starts influencing implementation, routing changes need a clean holdout slice and an explicit tuning/holdout split before the score is used as evidence.

## OAG-6.3 First v2 Evidence Run

A full three-run benchmark was captured on 2026-07-06 after the first OAG-6.2 routing change:

- Scorecard: `docs/benchmark/oag/old/rag-vs-oag-rag_only-oag_first-oag_only-2026-07-06T12-04-18+00-00.json`
- LLM: `qwen2.5:7b-instruct`
- Embeddings: `nomic-embed-text`
- Dataset: `rag-vs-oag-v2`
- Runtime: 2908.6 seconds

Headline result:

| Config | Accuracy | Holdout accuracy | Stable | Mean latency | P95 latency |
|---|---:|---:|---:|---:|---:|
| `rag_only` | 67% | 64% | 52/69 | 7.11s | 10.05s |
| `oag_first` | 62% | 54% | 59/69 | 6.59s | 10.57s |
| `oag_only` | 22% | 17% | 69/69 | 0.35s | 2.32s |

Interpretation: this is a useful negative result, not acceptance evidence. The first OAG-6.2 change over-routed action-specific role questions into direct OAG, but the current ontology stores process roles rather than precise action-role semantics. That made `oag_first` weaker than `rag_only`, especially on structured entity questions. The corrective decision is to keep only explicit owner/responsibility/roles-list questions on direct OAG and route action-specific role questions through RAG+ontology until the ontology data model can represent action ownership more precisely.

## OAG-6.3 Post-Correction v2 Evidence Run

A second full three-run benchmark was captured on 2026-07-06 after the routing correction and benchmark observability fix:

- Scorecard: `docs/benchmark/oag/old/rag-vs-oag-rag_only-oag_first-oag_only-2026-07-06T14-10-08+00-00.json`
- LLM: `qwen2.5:7b-instruct`
- Embeddings: `nomic-embed-text`
- Dataset: `rag-vs-oag-v2`
- Code state: `main@92164aa2`, dirty due to unrelated compliance benchmark archive moves
- Runtime: 1977.0 seconds

Headline result:

| Config | Accuracy | Holdout accuracy | Stable | Mean latency | P95 latency |
|---|---:|---:|---:|---:|---:|
| `rag_only` | 65% | 62% | 50/69 | 4.70s | 6.18s |
| `oag_first` | 71% | 61% | 60/69 | 4.71s | 6.74s |
| `oag_only` | 17% | 17% | 69/69 | 0.14s | 1.09s |

Interpretation: the correction recovered OAG-first overall, moving from 62% to 71% and making it the best overall configuration again. It also improved holdout performance from 54% to 61%. However, OAG-first is still slightly behind RAG-only on holdout (61% versus 62%), so this is not final acceptance evidence for #1170. The result supports the routing boundary decision but does not yet prove clean-holdout superiority. The next improvement should focus on ontology data coverage and action-specific role semantics rather than broadening direct OAG routing.

## OAG-6.4 Action-Role Routing and Targeted Slices

OAG-6.4 is a narrow implementation slice created as ADO #1175 after reviewing the post-correction v2 scorecard. It deliberately avoids broad schema expansion and focuses on three practical fixes:

- Pure OAG role answers are kept for process-level ownership questions, such as "Who owns Supplier Setup?", where the ontology has a process-to-role relationship.
- Action-specific role questions, such as "Who owns supplier-side ordering days?", now fall through to RAG+ontology unless the question names the process itself. This prevents direct OAG from refusing when the original document wording is needed to map the action to the right role.
- Unsupported named-employee, Companies House, future-rate and supplier-recommendation lookups now refuse before generation, so the platform does not answer beyond approved evidence.
- Aggregate/list prompts can receive a small packet of up to three matching process summaries, improving the evidence available for list-style OAG-first answers.
- The benchmark harness now supports targeted slices with `--category` and `--ids`, alongside the existing `--split` filter.

Validation completed before the next real-model run:

- `tests/test_answer.py` and `tests/test_rag_vs_oag_eval.py` passed.
- Focused `ruff` passed with cache redirected to `/tmp`.
- Fake benchmark probe passed for `--split holdout --category aggregate`, proving the new filter path and scorecard labelling.

This is implementation evidence, not final acceptance evidence. The next real validation should start with targeted holdout slices before running the full benchmark:

```bash
PYTHONPATH=src .venv/bin/python scripts/evaluate_rag_vs_oag.py \
  --split holdout \
  --category structured_entity \
  --category aggregate \
  --category out_of_scope \
  --configs rag_only,oag_first \
  --runs 1
```

If the targeted slice improves or at least preserves holdout quality, follow with the full three-run benchmark before closing OAG-6.

## OAG-6.5 Coverage Diagnostic Plan

The OAG-6.4 targeted real-model run was captured on 2026-07-06:

- Scorecard: `docs/benchmark/oag/rag-vs-oag-rag_only-oag_first-2026-07-06T16-29-44+00-00.json`
- Coverage diagnostic: `docs/benchmark/oag/oag-coverage-diagnostic-2026-07-06T18-07-43+00-00.json`
- Scope: `--split holdout --category structured_entity --category aggregate --category out_of_scope --configs rag_only,oag_first --runs 1`
- Code state: `main@a4fa2a32`

Result:

| Config | Passed | Accuracy | Notes |
|---|---:|---:|---|
| `rag_only` | 8/12 | 67% | Best on this diagnostic slice. |
| `oag_first` | 7/12 | 58% | Faster, but weaker on aggregate/list questions. |

This run is diagnostic only. It is filtered, single-run, and does not include all categories or all routing modes. It should not be used to crown a permanent winner.

Coverage diagnostic finding:

| Coverage status | Count | Interpretation |
|---|---:|---|
| `present` | 4 | The missed fact exists somewhere in ontology object/link text but was not used strongly enough in the Ask evidence packet. |
| `partial` | 2 | Related ontology content exists, but exact owner/action semantics are missing. |
| `absent` | 0 | None of the analysed missed facts were completely absent from ontology text. |

Interpretation: Claude's content-vs-routing caution is correct, with nuance. This is not primarily a router problem. The next useful slice is ontology content/evidence-packet enrichment, captured as ADO #1177:

- add a coverage diagnostic step before further tuning;
- improve evidence packet selection so facts already present in ontology are included in the Ask prompt when relevant;
- enrich process/action semantics for owner/action facts that are only partially represented;
- avoid broad process-summary injection when it adds context but not the requested granular fact.

The benchmark harness now labels filtered/single-run reports as `DIAGNOSTIC RUN`. Only full, unfiltered, default-config, `--runs 3` reports can show a decision-grade winner.

Next test sequence:

```bash
PYTHONPATH=src .venv/bin/python scripts/diagnose_oag_coverage.py \
  docs/benchmark/oag/rag-vs-oag-rag_only-oag_first-2026-07-06T16-29-44+00-00.json
```

Then, after the next enrichment slice:

```bash
PYTHONPATH=src .venv/bin/python scripts/evaluate_rag_vs_oag.py \
  --split holdout \
  --category structured_entity \
  --category aggregate \
  --category out_of_scope \
  --configs rag_only,oag_first \
  --runs 1
```

Only if that diagnostic slice is at least parity with RAG-only should the full holdout/full benchmark run proceed.

## OAG-6.6 Ontology Evidence Enrichment

ADO #1177 implements the first content/evidence-packet enrichment slice after the 18:07 coverage diagnostic.

Change summary:

- Process ontology objects now include `key_facts`: compact, source-derived fact atoms extracted from approved pack structure.
- `key_facts` are generated during ontology rebuild from:
  - roles-and-responsibilities table rows;
  - systems-and-data-dependencies table rows;
  - structured process steps;
  - realistic Q&A rows;
  - business rules;
  - JSON-style learning records.
- OAG fallback evidence now ranks granular ontology facts before broad process summaries.
- Owner/action questions prefer role-responsibility facts, so questions such as "who approves..." or "who validates..." receive the relevant owner/action evidence rather than a broad process packet.
- Aggregate/list questions receive light domain query expansion for adjacent business concepts, such as downstream article publication linking to pricing, assortment, mapping, sellability and consumer-system facts.

Local validation:

```bash
KP_DATA_DIR=/tmp/opsatlas-test-data PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  .venv/bin/python -m pytest -p no:cacheprovider \
  tests/test_answer.py \
  tests/test_ontology_sync.py \
  tests/test_ontology_schema.py \
  tests/test_rag_vs_oag_eval.py \
  tests/test_oag_coverage.py

RUFF_CACHE_DIR=/tmp/opsatlas-ruff-cache PYTHONPATH=src .venv/bin/python -m ruff check \
  src/assistant/ontology/router.py \
  src/assistant/ontology/sync.py \
  tests/test_answer.py \
  tests/test_ontology_sync.py \
  tests/test_ontology_schema.py
```

Smoke validation rebuilt the ontology into `/tmp` and confirmed the enriched packet now surfaces:

- Data governance owner responsibility for article attributes and purposeful use.
- Point-of-sale / consumer-system owner responsibility for downstream article and tax data.
- Article integration process evidence containing pricing, assortment, mapping, sellability and consumer-system dependencies.
- Packaging evidence separating shelf-packaging, planning/layout consumption, reporting and logistics packaging concepts.

Next real-model test:

```bash
PYTHONPATH=src .venv/bin/python scripts/evaluate_rag_vs_oag.py \
  --split holdout \
  --category structured_entity \
  --category aggregate \
  --category out_of_scope \
  --configs rag_only,oag_first \
  --runs 1
```

If `oag_first` is at least parity with `rag_only` on this diagnostic slice, proceed to the full holdout three-run benchmark.

## Recommended Next Steps

1. Keep `18-07-41` as the official corrected v1 baseline because it is the committed, documented rescore of the original captured run and is already referenced in ADO/Wiki.
2. Treat `18-42-05` as supporting repeat-run evidence that validates the same v1 decision under a fresh model pass.
3. Use `rag-vs-oag-v2` for OAG-6 routing work, with holdout metrics as the primary acceptance signal.
4. Run the OAG-6.6 targeted real-model diagnostic before more routing work.
5. Keep filtered and single-run benchmarks labelled as diagnostics; use full unfiltered three-run scorecards for decisions.
6. Do not start Phase B/C roadmap items (#1157/#1158) without an explicit human decision.
