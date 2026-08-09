# RAG and OAG Benchmark

## Purpose

This benchmark compares document retrieval with ontology-assisted answering for
the process questions represented by the OpsAtlas proof of concept. It tests
whether structured ontology evidence improves answers without removing the
document evidence needed for explanation and narrative context.

The benchmark supports an architecture decision; it is not a claim of universal
or production-enterprise performance.

## Configurations

| Configuration | Behaviour |
| --- | --- |
| `rag_only` | Uses approved document retrieval without ontology assistance. |
| `oag_first` | Prefers ontology evidence for structured questions and retains document RAG for narrative, mixed and fallback paths. |
| `oag_only` | Uses ontology evidence where possible. This is a boundary test, not a general user mode. |

## Evaluation design

- Label set: `tests/evaluation/rag_vs_oag_questions.json`.
- Runner: `scripts/evaluate_rag_vs_oag.py`.
- Questions: 69 across structured entity, structured relationship, aggregate,
  narrative, mixed and out-of-scope categories.
- Split: 45 tuning questions and 24 held-out questions.
- Repetition: three runs per configuration.
- Total executions: 621.
- Local model runtime: `qwen2.5:7b-instruct` with
  `nomic-embed-text` embeddings.

Reproduction command:

```bash
PYTHONPATH=src .venv/bin/python scripts/evaluate_rag_vs_oag.py --runs 3
```

The accepted result was generated on 5 August 2026 and reused for this cleanup;
it was not rerun. The raw result is retained as
[`rag-vs-oag-final-benchmark.json`](rag-vs-oag-final-benchmark.json), with a concise
human-readable snapshot in
[`rag-vs-oag-final-benchmark.md`](rag-vs-oag-final-benchmark.md).

## Final results

### Holdout split

| Configuration | Passed | Accuracy | Route accuracy | Stable questions | Mean latency |
| --- | ---: | ---: | ---: | ---: | ---: |
| RAG-only | 53/72 | 73.61% | 50.00% | 22/24 | 3.84s |
| OAG-first | 68/72 | 94.44% | 100.00% | 23/24 | 1.32s |
| OAG-only | 48/72 | 66.67% | 83.33% | 24/24 | 0.03s |

### All labelled questions

| Configuration | Passed | Accuracy | Route accuracy | Stable questions | Mean latency |
| --- | ---: | ---: | ---: | ---: | ---: |
| RAG-only | 149/207 | 71.98% | 46.38% | 64/69 | 4.12s |
| OAG-first | 165/207 | 79.71% | 94.20% | 66/69 | 1.70s |
| OAG-only | 102/207 | 49.28% | 79.71% | 69/69 | 0.09s |

## Holdout interpretation

OAG-first achieved:

- 100% for structured-entity questions;
- 100% for structured-relationship questions;
- 100% for aggregate questions;
- 91.7% for narrative questions;
- 75% for mixed questions;
- 100% correct out-of-scope refusal.

The holdout result is the primary decision signal because those questions were
kept separate from routing and ontology tuning. Overall results remain useful as
regression evidence but include the tuning split.

## Decision

Retain a hybrid architecture. OAG-first is the preferred route in the proof of
concept for structured organisational facts. Document RAG remains necessary for
explanation, nuance and mixed or narrative questions. The `oag_only`
configuration remains a benchmark boundary test rather than a user-facing mode.

## Limitations

- The questions and corpus are anonymised and bounded to the proof of concept.
- The holdout contains 24 questions; wider domains and larger unseen sets are
  needed before generalising the result.
- Accuracy combines expected facts, behaviour and route checks; it does not prove
  that the underlying organisational knowledge is complete.
- Latency was measured on one local hardware/runtime configuration.
- Ontology quality depends on source coverage, extraction and reconciliation.
- Human governance remains authoritative for source approval and corrections.
