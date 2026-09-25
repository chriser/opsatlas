# Governance pair benchmark: results

The review that uses these results is [governance-reasoning-engine-review-2026-09-25.md](../../data-and-governance/governance-reasoning-engine-review-2026-09-25.md).

**Dataset:** `tests/evaluation/governance_pair_benchmark.json`, 91 cases.

**Files in this folder:**

| File | What it holds |
|---|---|
| `result-<system>.json` | Per-case answers and timings for one system |
| `scorecard.json` | Scores for every result file (`python scripts/evaluate_governance_pairs.py score`) |
| `statement-index.json` | Candidate generation: document pairs against the statement index (`python scripts/governance_statement_index.py`) |
| `pipeline-trial-<model>.json` | The whole proposed pipeline run on the real 21-document corpus, with every conflict and duplicate it raised (`python scripts/governance_statement_index.py --trial <model>`) |

All runs of 25 September 2026 shared the GPU with another workload. Timings compare the systems with each other; they are not absolute.
