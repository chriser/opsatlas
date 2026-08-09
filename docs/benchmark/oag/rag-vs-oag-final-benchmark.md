# Final RAG/OAG Benchmark Snapshot

- Generated: `2026-08-05T16:10:27+00:00`
- Dataset: `rag-vs-oag-v2`
- Questions: 69 (45 tuning, 24 holdout)
- Configurations: `rag_only`, `oag_first`, `oag_only`
- Runs: 3
- Executions: 621
- Runtime: Ollama with `qwen2.5:7b-instruct` and `nomic-embed-text`
- Result status: decision-grade proof-of-concept evidence

## Holdout result

| Configuration | Passed | Accuracy | Route accuracy | Stable questions | Mean latency |
| --- | ---: | ---: | ---: | ---: | ---: |
| RAG-only | 53/72 | 73.61% | 50.00% | 22/24 | 3.84s |
| OAG-first | 68/72 | 94.44% | 100.00% | 23/24 | 1.32s |
| OAG-only | 48/72 | 66.67% | 83.33% | 24/24 | 0.03s |

## Overall result

| Configuration | Passed | Accuracy | Route accuracy | Stable questions | Mean latency |
| --- | ---: | ---: | ---: | ---: | ---: |
| RAG-only | 149/207 | 71.98% | 46.38% | 64/69 | 4.12s |
| OAG-first | 165/207 | 79.71% | 94.20% | 66/69 | 1.70s |
| OAG-only | 102/207 | 49.28% | 79.71% | 69/69 | 0.09s |

## OAG-first holdout by category

| Category | Passed | Accuracy |
| --- | ---: | ---: |
| Structured entity | 12/12 | 100.0% |
| Structured relationship | 12/12 | 100.0% |
| Aggregate | 12/12 | 100.0% |
| Narrative | 11/12 | 91.7% |
| Mixed | 9/12 | 75.0% |
| Out of scope | 12/12 | 100.0% |

## Interpretation

OAG-first is the preferred hybrid route in this proof of concept. It improves
structured and aggregate answers while retaining document RAG for narrative,
mixed and fallback cases. OAG-only is not suitable as a universal answer mode.

See [`README.md`](README.md) for method, decision rationale and limitations, and
[`rag-vs-oag-final-benchmark.json`](rag-vs-oag-final-benchmark.json) for the complete
machine-readable result.
