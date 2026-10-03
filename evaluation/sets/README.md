# Evaluation Datasets

## Hallucination Probes

`hallucination_probes.json` is a regression dataset for unsupported-response testing.

Each row contains:

- `question`: the probe to ask.
- `expected`: rubric class used by the evaluation runner (`answer`, `refuse`, `decline`, `guardrail`).
- `expected_behavior`: the expected refusal, decline or evidence-qualified correction.
- `hallucination_risk`: what unsafe unsupported behaviour the probe is designed to catch.
- `source_expectation`: whether retrieved evidence should exist.

Contradictory-premise probes may expect `answer` because the correct behaviour is to correct the premise using grounded evidence, not to refuse.

## RAG vs OAG Questions

`rag_vs_oag_questions.json` is the pre-registered comparison set for the RAG-only, OAG-first and OAG-only benchmark.

Each row contains:

- `id`: stable label identifier.
- `category`: one of `structured_entity`, `structured_relationship`, `aggregate`, `narrative`, `out_of_scope` or `mixed`.
- `question`: the user question to run through each configuration.
- `expected_path`: the expected natural home for the question, `oag`, `rag` or `either`.
- `expected_answer_facts`: atomic facts the answer must contain. Each fact has canonical `text` and optional `aliases`.
- `notes`: pack/source rationale for the label.

The scoring rule is deterministic: normalise answer text and fact aliases to lowercase alphanumeric tokens, then mark a fact as hit when either the canonical text or one alias appears. A row passes only when every expected fact is hit. Out-of-scope rows pass when the answer clearly refuses or qualifies that the requested evidence is absent from the approved corpus.

The category quotas are part of the design: structured entity, structured relationship and aggregate questions should favour OAG; narrative questions should favour RAG; mixed questions should require both structured facts and explanatory context. Labels are written before running either pipeline so benchmark changes do not fit to observed outputs.

## Sales Playbook Sets

Three labelled sets for the `sales-playbook` knowledge space (17 approved sources), written on 2026-10-03 before any run. In all three, an id whose number is a multiple of three is `holdout`; the rest are `tuning`.

- `sales_playbook_retrieval.json` (REF S21): 40 questions. 34 are answerable (13 `fact`, 11 `explanation`, 6 `figure`, 4 `comparison`) and cover all 17 sources; 6 are `out_of_scope`. It measures required-evidence recall at k and source selection. Split: 27 tuning, 13 holdout.
- `sales_playbook_multipart.json` (REF H4): 18 questions. 12 are `multi_part`, each with one required section per part (2–3 different sections) and at least one fact per part; 6 are `single_part` controls. Split: 12 tuning, 6 holdout (4 multi-part, 2 single-part).
- `sales_playbook_scope.json` (REF H3): 5 planted documents with scope metadata and 16 questions (5 `current`, 3 `future`, 5 `site`, 3 `site_missing`). Each row lists `must_use`, `must_not_use` and `forbidden_facts`. The `site_missing` rows expect `ask_or_label_both`. Split: 11 tuning, 5 holdout.

Each row in the first two sets has `required_evidence` items made of a `filename` and the exact text of the nearest Markdown heading above the passage. Headings that are PDF-extraction artefacts are kept as they are (for example `1. Input guardrails check the question for manipulation, unsafe content and`). Every `expected_answer_facts` text appears verbatim in its required section, and scoring uses the token rule described above.

The planted documents in the scope set are fictional: three versions of an OpsAtlas demonstration-environment policy (2025, 2026, 2027) and onboarding guides for two pilot sites (Leeds, Bristol). The runner uploads them only into a disposable copy of the space with `today` fixed at 2026-10-03. They must never be uploaded to the live playbook.
