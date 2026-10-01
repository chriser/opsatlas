# Configuration the code reads

The files here decide how OpsAtlas behaves, or whether a release passes its gate. They are inputs, not documentation:
change one only together with the code and tests that read it. Settings that come from the environment are registered
in `src/assistant/settings.py` (and generated into `.env.example`); the Sales workspace's own values are in
`services/opsatlas_sales/profile.json`.

| File | Read by | What it holds | How it changes |
|---|---|---|---|
| `tibi/engine-versions.json` | `services/sme_interviewer/engine.py`, `tests/test_sme_engine.py` | Tibi's engine versions: each version's commit, fingerprint, models and changes, and the current version | A new entry for each change to the engine's files or models, after its latency replay passes |
| `tibi/latency-budget.json` | `services/sme_interviewer/replay_latency.py` and `latency_report.py`, `tests/test_sme_latency_budget.py` | The latency gate: p50 and p95 budgets for the replay and the headset, from the end of the person's speech to Tibi's first audio | Tightening is welcome; loosening is the Human's decision, recorded in the file |

Until 1 October 2026 (AUDIT F14) both files were in `docs/initiatives/sme-interviewer/`, the engine registry as
`tibi-engine-versions.json`.
