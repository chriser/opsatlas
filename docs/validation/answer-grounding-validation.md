# Answer Grounding Validation

OpsAtlas answers are constrained to approved internal sources and governed
ontology evidence. This note records the controls and repeatable validation
assets used to check citations, grounding and refusal behaviour.

## Implemented controls

- Only approved sources are available to retrieval and answering.
- Document retrieval combines lexical and local embedding evidence.
- Structured questions can use ontology objects and links through OAG-first
  routing.
- Mixed and narrative questions retain document evidence and can include
  ontology context.
- Answers carry citations, confidence and grounding metadata.
- Unsupported or out-of-scope questions are refused rather than completed from
  ungoverned model knowledge.
- The Digital SME receives the same validated answer as Written Query; the
  avatar renderer does not produce an independent organisational answer.

## Validation assets

| Asset | Purpose |
| --- | --- |
| `tests/evaluation/hallucination_probes.json` | Covers missing specifics, disclosure traps, action requests, contradictory premises, currentness, prompt injection and unsupported comparisons |
| `scripts/evaluate_grounding.py` | Runs grounding probes and produces a reviewable report |
| `tests/test_answer.py` | Tests answer construction, citations and refusal paths |
| `tests/test_retrieval.py` | Tests lexical/embedding retrieval and approved-source boundaries |
| `tests/test_validation.py` | Tests answer-to-evidence support checks |
| `docs/benchmark/oag/rag-vs-oag-final-benchmark.json` | Compares RAG and ontology-assisted paths on tuning and holdout questions |

Evidence command:

```bash
PYTHONPATH=src .venv/bin/python scripts/evaluate_grounding.py --format markdown
```

## Focused corpus check

An earlier end-to-end check over nine anonymised learning packs used seven
questions: six in-scope questions were answered with citations and one
out-of-scope question was refused. The sample produced an 85.7% answer and
grounded rate with four citations per answered question on average. This remains
a focused regression example, not the final architecture comparison; the final
RAG/OAG decision is based on the separate 69-question benchmark.

## Boundary

Grounding confirms support from the evidence supplied to the answer path. It
does not prove that the source corpus is complete, current for every use case or
operationally correct. Source approval, governance disposition and process-owner
validation remain human responsibilities.
