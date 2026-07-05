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

The remaining evidence step for story `#1152` is one real three-run scorecard using the local production stack.
