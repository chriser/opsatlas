# Evaluation Datasets

## Hallucination Probes

`hallucination_probes.json` is a Sprint 2 dataset for unsupported-response testing.

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
