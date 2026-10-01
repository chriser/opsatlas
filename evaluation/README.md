# Evaluation

One folder for evaluation (AUDIT F14): the sets the harnesses read, the results they write, and the raw evidence that
dated pages cite. Code reads and writes here. The write-ups stay in `docs/`: one dated record per hypothesis or check in
`docs/benchmark/`, and Tibi's pages in `docs/initiatives/sme-interviewer/`.

| Folder | What it holds |
|---|---|
| `sets/` | Labelled inputs: question sets, probes and scenarios. A set changes by a new version, named in the set and in the record that introduces it |
| `results/` | What the harnesses wrote: scorecards, replays and judge results, one file per run, not edited afterwards |
| `evidence/` | Archived raw run dumps: Tibi's development runs of 19–25 September 2026 (`tibi/`) and the probes of the 27 September audit (`audits/`). No code reads them; dated pages cite them |

## Harnesses

| What it measures | Command | Reads | Writes | Write-up |
|---|---|---|---|---|
| Product Guide answers (Sales) | `scripts/evaluate_rag_vs_oag.py --dataset evaluation/sets/sales_product_questions.json --no-write` | `sets/sales_product_questions.json` | the console | `docs/benchmark/sales/` |
| RAG against OAG (the DT603 decision) | `scripts/evaluate_rag_vs_oag.py` | `sets/rag_vs_oag_questions.json` | `results/oag/`, unless `--no-write` | `docs/benchmark/oag/README.md` |
| Unsupported answers | `scripts/evaluate_grounding.py` | `sets/hallucination_probes.json` | the console | `docs/validation/answer-grounding-validation.md` |
| Governance judges | `scripts/evaluate_governance_pairs.py`, `scripts/governance_statement_index.py` | `sets/governance_pair_benchmark.json` | `results/governance/` | `docs/benchmark/governance/README.md` |
| EAM classification | `scripts/evaluate_eam_distribution.py` | a core's `ontology.db` | `results/eam/` | `docs/architecture/enterprise-activity-model.md` |
| Tibi's engine | `services/sme_interviewer/evaluate_engine.py` | `sets/tibi/scenarios.json` | `results/tibi/` | `docs/initiatives/sme-interviewer/` |
| Tibi's latency gate | `services/sme_interviewer/replay_latency.py --out evaluation/results/tibi/<file>.json` | `config/tibi/latency-budget.json` | the `--out` file | the version's entry in `config/tibi/engine-versions.json` |
| Tibi's parity and wake name | `services/sme_interviewer/evaluate_parity.py`, `evaluate_wake.py` | their own probes | `results/tibi/` | `docs/initiatives/sme-interviewer/` |
| Tibi's sentence gate | `tests/test_sme_sentence_gate.py` (part of the test suite) | `sets/tibi/sentence-gate-heldout.json`, `sentence-gate-adversarial.json` | nothing | |
| Supplier-setup regression (OpsAtlas Classic) | `automation/evaluate.py` | `sets/supplier-setup-pack.md`, `sets/supplier-setup-questions.json` (described in `sets/supplier-setup-questions.md`) | the console, or `--out` | |

The Analytics page's RAG vs OAG tab shows every `rag-vs-oag-*.json` scorecard in `results/oag/`, so a run of
`scripts/evaluate_rag_vs_oag.py` without `--no-write` appears there. `sets/simulator-scenarios.json` belongs to the
simulator, which runs only in OpsAtlas Classic.

## Where these were before 1 October 2026

- `sets/` was `tests/evaluation/`, Tibi's `docs/initiatives/sme-interviewer/evaluation/`, and four files in
  `docs/benchmark/`: `questions.json` (now `supplier-setup-questions.json`), `question-set.md` (now
  `supplier-setup-questions.md`), `supplier-setup-pack.md` and `simulator-scenarios.json`.
- `results/` was `docs/benchmark/oag/` (the final benchmark), the JSON files of `docs/benchmark/governance/`,
  `docs/benchmark/eam/`, one probe file of `docs/benchmark/sales/`, and Tibi's
  `docs/initiatives/sme-interviewer/evaluations/`.
- `evidence/` was Tibi's `docs/initiatives/sme-interviewer/evidence/` and `docs/audits/evidence/`.

Results and evidence keep the paths of their day inside them; links in the pages that cite them were updated.
