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
