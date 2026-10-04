# ARCH H3a — thinking off and a bounded output for the core's model call

**Hypothesis (ADO ARCH H3 #1944); marks registered 30 September 2026 before the run.** Sending `think: false` and a
`num_predict` bound of 1,536 tokens from the core generator makes Product Guide answers fast without costing accuracy.

**Why.** The core sent only `num_ctx` and `temperature`, so `qwen3.5:4b`, a reasoning model, thought before every
answer. On one real guide prompt it wrote 1,366–2,623 tokens of hidden reasoning (13–28 s) before a one-sentence
answer. With thinking off it wrote 15 tokens in 0.2 s, and the answer was the same. Tibi already calls the same model
with thinking off.

**Built (`claude/arch-h3`, ddb4324).**
- `OllamaGenerator` sends `"think": false` and `num_predict`.
- `KP_LLM_THINK` (0, 1 or auto) and `KP_LLM_NUM_PREDICT` configure them.
- The core's governance generator keeps its own behaviour.
- Models that cannot think accept `false`: `qwen2.5:7b-instruct` rejects only `true`.

**Runs.**
- **Sales:** set sales-product-v1, 36 questions, oag_first, three runs, Product Guide configuration, qwen3.5:4b, on the
  same guide copy as H2.
- **Classic holdout:** oag_first, three runs, qwen2.5:7b-instruct.
- **Baselines** (declared before the run): today's H2 runs of the code now live.

## Marks and results

| Mark | Baseline | H3a | Verdict |
|---|---|---|---|
| Sales mean latency ≤ 10 s | 57.3 s | **2.1 s** | Met |
| Sales p95 latency ≤ 20 s | 112.5 s | **4.1 s** (maximum 16.7 s, against 163.9) | Met |
| Sales tuning within ±2 | 62/72 | **64/72** (stable 23/24, from 18/24) | Met |
| Sales holdout within ±2 | 30/36 | **33/36** (stable 12/12, from 8/12) | Met |
| No more wrong refusals than 13 | 13 | **3** (all `sales-narrative-004`) | Met |
| Graceful redirect on ≥ 90 % of out-of-scope answers | 17/18 | **15/18 (83 %)** | **Missed** |
| Classic holdout within ±2 of 71/72 | 71/72 | **72/72** (route 100 %, stable 24/24, 1.46 s) | Met |

## Reading the miss

The three missing redirects are one question, `sales-out-of-scope-holdout-002`: "Does OpsAtlas integrate directly
with SAP?", on all three runs. With thinking off, the model answers it truthfully from the guide:

> No, OpsAtlas does not integrate directly with SAP. The evidence states that the proof of concept does not provide
> direct integration with live organisational systems [16].

The answer is grounded and correct. What it lacks is the pointer to the sales team that the Human asked for on topics
the guide does not establish (integrations, pricing, customers, certifications, release plans). With thinking on, the
model used to decline this question instead, and the decline carried the redirect.

The other changes are label strictness, noted for the set's next version rather than applied to this result:
- `sales-mixed-001` answers what the benchmark compared (the three approaches) and omits "69 questions".
- `sales-narrative-004` asks about the "Precision view", a Sales Playbook term that the guide does not use, so a
  refusal is right.

## Decision trail

- **Recommendation: adopt.** Answers are 27 times faster, with a tighter spread. Accuracy and stability are up, wrong
  refusals are down from 13 to 3, and Classic is unchanged at 72/72.
- **The redirect miss becomes its own follow-up, H2b.** The Product Guide's configuration names commercial and
  integration topics, and answers on them end with the sales-team pointer, whether or not the guide answers them.
  Mark: redirect on 6/6 out-of-scope questions × 3 runs, with no other change.
- **Adopted by the Human on 30 September 2026**, with H2b as the follow-up. Replayed onto the live line after
  AUDIT F1 (`claude/arch-h3-live`: 566e6a0 the change, 01fbd42 this record).
