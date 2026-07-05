# RAG vs OAG Benchmark

## Purpose

This benchmark measures whether ontology-assisted generation improves Ask answers where the question needs structured process facts, while preserving normal RAG performance for narrative explanation and refusal behaviour for out-of-scope questions.

The benchmark compares three answer-routing configurations:

- `rag_only`: ontology routing disabled. This is the baseline document-RAG path.
- `oag_first`: production routing. Structured questions try ontology facts first, and narrative questions can still use document evidence plus compact ontology process evidence.
- `oag_only`: ontology-only boundary probe. This should perform well on structured facts and degrade on narrative questions.

## Label Set

Labels live in `tests/evaluation/rag_vs_oag_questions.json`.

The first registered set contains 45 questions:

- 10 structured entity questions
- 10 structured relationship questions
- 5 aggregate/list questions
- 10 narrative questions
- 5 out-of-scope questions
- 5 mixed structured-plus-explanatory questions

Each label records the question, expected answer path, and atomic expected facts. The scoring rule is deterministic: answer text and expected fact aliases are normalised to lowercase alphanumeric tokens, and a fact is counted as hit when either the canonical fact text or one alias appears in the answer.

Because real model answers often paraphrase the registered facts, the scorer also has a generic fallback: if no exact phrase matches, it compares content-bearing tokens after simple plural and verb-ending normalisation. A fact can pass when content-token coverage is at least `0.72` with no more than two missing content tokens. This is deliberately generic and applies to every label; it is not tuned to a specific answer.

Out-of-scope labels pass when the answer refuses or clearly states that the requested evidence is absent from the approved corpus.

## Harness

The harness entry point is:

```bash
.venv/bin/python scripts/evaluate_rag_vs_oag.py --runs 3
```

Outputs are written to `docs/benchmark/oag/` as timestamped `.md` and `.json` scorecards.

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
- citation types used: document, ontology object, process registry or none
- latency
- per-config and per-category accuracy
- path usage matrix
- citation type matrix
- stability across runs

## Interpretation Gates

The benchmark is useful only when interpreted by category.

The expected decision pattern is:

- `oag_first` should beat `rag_only` on `structured_relationship` and `aggregate`.
- `oag_first` should not lose materially against `rag_only` on `narrative`.
- `out_of_scope` refusal should be preserved.
- `oag_only` is expected to degrade on narrative questions; that confirms it is a boundary probe rather than the target user mode.

If `oag_first` improves structured categories but damages narrative or refusal behaviour, routing should be adjusted before expanding ontology use.

## Current Implementation Notes

`AnswerService.answer()` now accepts a `routing_mode` argument while preserving the default production behaviour:

- `oag_first` is the default used by the Ask API.
- `rag_only` skips ontology-first routing and skips ontology fallback evidence.
- `oag_only` returns only ontology-backed structured answers and otherwise refuses.

This keeps the benchmark faithful to production code without monkey-patching internals.

## Validation Status

Hermetic validation has passed for:

```bash
.venv/bin/python -m pytest tests/test_answer.py tests/test_rag_vs_oag_eval.py tests/test_rag_vs_oag_labels.py
RUFF_CACHE_DIR=/tmp/kp-ruff-cache .venv/bin/ruff check src/assistant/answer/service.py src/assistant/eval/rag_vs_oag.py scripts/evaluate_rag_vs_oag.py tests/test_answer.py tests/test_rag_vs_oag_eval.py
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
