# Claude Handover - Ontology and RAG-vs-OAG Benchmark Review

## Review Request

Please review the latest implementation of the ontology-assisted generation layer and the RAG-vs-OAG benchmark evidence.

The main question for review is: does Phase A provide enough evidence that OAG-first routing is a useful production default, and what should the next approved slice be?

## Current Phase A Status

Phase A is complete through OAG-5:

| Area | ADO | Status |
|---|---:|---|
| Ontology foundation | #1137 | Resolved |
| OAG-first answer path | #1141 | Resolved |
| Governed actions engine | #1144 | Resolved |
| Ontology agent and HITL proposals | #1147 | Resolved |
| RAG-vs-OAG benchmark and DT603 evidence | #1150 | Resolved |

Epic #1136 remains Active because Phase B/C are still roadmap items.

Do not start:

- #1157 - Phase B commercial-model adapter
- #1158 - Phase C instance-level digital twin

Both are explicitly marked as later-phase / do-not-start items.

## Implementation Pointers

Key files:

- `src/assistant/ontology/store.py` - SQLite object/link store.
- `src/assistant/ontology/query.py` - read-only query service.
- `src/assistant/ontology/router.py` - deterministic OAG answer planning and RAG+ontology fallback evidence.
- `src/assistant/answer/service.py` - `routing_mode` support: `rag_only`, `oag_first`, `oag_only`.
- `src/assistant/ontology/actions.py` - declared, validated, audited actions.
- `src/assistant/ontology/agent.py` - bounded ontology agent tool loop.
- `src/assistant/ontology/proposals.py` - pending action proposal store.
- `scripts/evaluate_rag_vs_oag.py` - benchmark CLI and rescore path.
- `src/assistant/eval/rag_vs_oag.py` - scoring, scorecard and report logic.
- `tests/evaluation/rag_vs_oag_questions.json` - 45-question registered dataset.
- `src/assistant/evidence/validation.py` - `VAL-OAG-001` and KSB-P3 evidence.
- `frontend/src/AnalyticsPage.tsx` - answer-path split and ontology stats tiles.

Architecture/Wiki mirrors:

- `docs/architecture/05-RAG-Framework.md`
- `docs/architecture/07-Core-Modules.md`
- `docs/benchmark/oag/RAG-vs-OAG-Benchmark.md`

## Benchmark Files

Official corrected baseline:

- `docs/benchmark/oag/rag-vs-oag-rag_only-oag_first-oag_only-2026-07-05T18-07-41+00-00.json`
- `docs/benchmark/oag/rag-vs-oag-rag_only-oag_first-oag_only-2026-07-05T18-07-41+00-00.md`

This file is the corrected rescore of the first captured run. It includes:

- `rescored_from: 2026-07-05T16:52:10+00:00`
- `rescore_method: exact-or-content-token-coverage-0.72-max2`

Fresh confirmation run:

- `docs/benchmark/oag/rag-vs-oag-rag_only-oag_first-oag_only-2026-07-05T18-42-05+00-00.json`
- `docs/benchmark/oag/rag-vs-oag-rag_only-oag_first-oag_only-2026-07-05T18-42-05+00-00.md`

This is a new model run, not a rescore. It has no `rescored_from` field and differs in row-level answers because the local LLM is not fully deterministic.

## Results Summary

Corrected baseline:

| Config | Accuracy | Structured relationship lift | Aggregate lift | Narrative | Out-of-scope |
|---|---:|---:|---:|---:|---:|
| RAG-only | 64% | baseline | baseline | 63% | 100% |
| OAG-first | 70% | +10% | +33% | 70% | 100% |
| OAG-only | 18% | boundary probe | boundary probe | 0% | 100% |

Fresh confirmation run:

| Config | Accuracy | Structured relationship lift | Aggregate lift | Narrative | Out-of-scope |
|---|---:|---:|---:|---:|---:|
| RAG-only | 67% | baseline | baseline | 63% | 100% |
| OAG-first | 70% | +3% | +27% | 67% | 100% |
| OAG-only | 18% | boundary probe | boundary probe | 0% | 100% |

Interpretation:

- OAG-first wins both real runs.
- The repeat run narrows the margin, especially for structured relationships.
- Aggregate/list questions remain the clearest OAG gain.
- Narrative questions are not materially harmed.
- Out-of-scope refusal is preserved at 100%.
- OAG-only is not a user-facing default; it is a boundary probe.

## Important Scoring Note

The first raw scorecard under-counted correct answers because exact phrase matching treated faithful paraphrases as misses. The scorer now uses:

- exact canonical/alias phrase match first;
- generic content-token coverage fallback;
- threshold `0.72`;
- max missing content tokens `2`.

This is generic and not label-specific. It was added after examples showed answers such as "Trading support assistant / master data operator" being marked wrong against "trading support assistant or master data operator creates the supplier record".

## Known Limitations

1. Mixed questions are weak in both RAG-only and OAG-first.
2. Structured entity questions sometimes route through `rag+ontology` rather than clean object-only OAG.
3. OAG-first path usage is still mostly `rag+ontology` rather than pure `oag` for many structured labels.
4. The local LLM shows row-level variance between three-run scorecards.
5. The dataset is useful but still small; more labels should be added before claiming broad enterprise generalisation.

## Recommended Next Slice

Recommended Phase A follow-up, if approved:

1. Improve mixed-question composition so structured facts and explanatory context are both represented.
2. Improve structured entity routing, especially role/owner questions.
3. Add benchmark observability for why a question used `oag`, `rag`, or `rag+ontology`.
4. Add more registered labels before any larger architectural claim.

Do not spend the next slice on model shopping. Both real runs suggest the bottleneck is routing/composition quality, not model choice.

Do not start Phase B/C until the human explicitly unlocks it.

## Suggested Review Questions

1. Is the current OAG-first default justified by the evidence?
2. Should the next story be OAG-6 mixed-question and structured-entity routing hardening?
3. Are the scorer thresholds acceptable, or should the benchmark move to an LLM-as-judge secondary audit for borderline cases?
4. Should the benchmark dataset expand before or after routing improvements?
5. Should the fresh confirmation run be added to ADO as supporting evidence, or kept as local benchmark history only?

## Latest Pipeline / Commit Context

Latest pushed OAG evidence commit before this handover:

- `0158a29 Add #1153 OAG validation evidence analytics`
- Azure build #377 succeeded.

This handover adds the fresh confirmation run and a recommendation note for review.
