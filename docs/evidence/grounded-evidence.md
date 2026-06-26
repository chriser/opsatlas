# Grounded answer evidence — real anonymised corpus

Captured against the live PoC (local Ollama: `qwen2.5:7b-instruct` + `nomic-embed-text`)
over **9 anonymised learning packs** (105 sections, all approved). All figures below were
produced end-to-end through the control-panel API; the UI renders the same state.

## Knowledge base
- 9 packs ingested and approved (governance gate), 105 sections, embedded (768-dim).
- Retrieval mode (corpus > full-context limit); hybrid BM25Plus + semantic with RRF fusion,
  query rewrite, relevance threshold **0.55** (calibrated), LLM rerank, groundedness validation.

## Grounded, cited answer (sample)
**Q:** "How is tax handling configured for articles?"

> Tax handling for articles is configured through both parameter-level definitions and
> item-level or price-level updates. Broad VAT or tax-rate changes are handled by closing
> the old rate and opening a new, dated parameter-level rate definition **[3]**. For selective
> tax treatment affecting only a subset of items, mass maintenance or pricing-related updates
> are required **[1][2]**. …

| Marker | Source | Section |
|---|---|---|
| [1] | Pack 6: Article Integration Tax Handling Product Change and Article Lists | 8. JSON-style learning records |
| [2] | Pack 6: Article Integration Tax Handling Product Change and Article Lists | 4. Key business rules |
| [3] | Pack 6: Article Integration Tax Handling Product Change and Article Lists | 7. Realistic Q&A pairs |

Confidence: **grounded** · Groundedness validation: **supported**.

## Hallucination probe groundedness scoring

Sprint 2 adds an explicit hallucination-risk probe set and scoring route:

- Dataset: `tests/evaluation/hallucination_probes.json` (18 probes).
- Expected behaviours: grounded correction, refusal, action decline or guardrail.
- Runtime fields: `grounding`, `grounding_score` and `faithfulness` are written to answer responses and audit traces.
- Evidence command: `PYTHONPATH=src .venv/bin/python scripts/evaluate_grounding.py --format markdown`.

The dataset covers missing specifics, disclosure traps, action requests, contradictory premises,
out-of-scope prompts, currentness/legal-currentness prompts, prompt injection and unsupported
comparisons. Contradictory-premise probes intentionally expect a grounded correction rather than
a refusal when the approved evidence directly refutes the premise.

## Scorecard (7-question sample run)
| Metric | Value |
|---|---|
| Total queries | 7 |
| Answered | 6 |
| Refused | 1 (out-of-scope: "capital of France") |
| Answer rate | 85.7% |
| Grounded rate | 85.7% |
| Avg citations / answer | 4.0 |
| Knowledge gaps | 1 — the out-of-scope question, correctly captured |

All six in-scope questions returned **grounded** answers with citations (groundedness
*supported* on five, *partial* on one); the out-of-scope question was **refused**.

## Governance — Knowledge Intelligence scan (9 packs)
| Check | Result |
|---|---|
| Conflicts (LLM contradiction check) | **0** |
| Outdated | **0** |
| Metadata / compliance | **0** (after readable titles applied) |
| Near-duplicate sections | 23 — shared-template overlap across packs (expected; surfaced as signal) |

## Retrieval calibration (real corpus)
| | Cosine range |
|---|---|
| In-scope questions | 0.66 – 0.78 |
| Out-of-scope | 0.41 – 0.48 |

Threshold set to **0.55** (gap midpoint, ~0.1 margin each side): out-of-scope queries now
return zero passages and are cleanly refused.

## Screenshot checklist (operator-captured for the Evidence Index)
Run the control panel (`scripts/dev.sh`), sign in, then capture:
1. **Written Query** — the tax-handling question above showing the grounded answer with `[n]` citations
   to the named packs → Evidence Index "first grounded cited response" (#680/#681).
2. **Dashboard** — the scorecard panel (answer rate, grounded rate, avg citations, knowledge
   gaps) → analytics evidence (#637).
3. **Governance** — the Knowledge Intelligence result (0 conflicts; duplicate/template signal).
4. **System** — the audit-trace table (mode, confidence, grounding, latency, evidence) (#67).
