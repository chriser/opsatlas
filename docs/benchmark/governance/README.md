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
| `result-<model>_+_scope.json` | GOV S8: the model behind the final scope rules, with pairs set aside by dates or phase marked `set_aside` (`python scripts/evaluate_governance_pairs.py scope <model>`) |
| `result-<model>_+_scope_v1_*.json` | GOV S8's first rule (any mention of a phase or date was scope), with and without telling the judge what each statement applies to. Superseded; kept as measured. See [statement-level-governance.md](../../data-and-governance/statement-level-governance.md#scope-and-dates-26-september-2026-gov-s8-1752) |

All runs of 25 September 2026 shared the GPU with another workload. Timings compare the systems with each other; they are not absolute.
