# Compliance Reasoning Engine Benchmarking and Tuning

Date: 2026-07-05

Status: Accepted decision record and handover note

Related work items: #1114, #1117, #1118, #1121-#1135, #1154-#1156

Primary decision: use `qwen2.5:14b-instruct` as the default Deep Audit model, with `deepseek-r1:8b` retained as the Balanced same-obligation screen.

## Executive Summary

The compliance reasoning engine started as a useful but noisy regulatory matching workflow. Early findings were mostly keyword and modality matches rather than genuine reasoning. For example, a VAT rule about input-tax evidence could be matched to an unrelated internal passage about supplier contracts because they shared weak words such as "needed" or "still". That was not good enough for governance use.

The work therefore shifted from "make the model bigger" to "make the review pipeline measurable and honest". We built a benchmark harness, labelled evidence pairs, added diagnostic scorecards, separated model-only behaviour from deterministic guard overrides, rotated contaminated holdout labels into training/regression, and only then compared models.

The most important outcome is not just the final model choice. The important engineering evidence is that the team detected benchmark leakage, stopped tuning against contaminated holdouts, added clean holdout domains, and used ablation to understand whether the LLM or the guard layer was carrying the score.

Final decision:

- `qwen2.5:14b-instruct` is the default Deep Audit adjudication model.
- `deepseek-r1:8b` remains the Balanced same-obligation screening model.
- DeepSeek-R1 14B remains useful as a comparison baseline, but is no longer the default.
- DeepSeek-R1 32B is not justified for routine local use because it is much slower and did not improve the trusted clean-holdout result.
- Further quality work should focus on guard behaviour and expanding clean holdout coverage, not broad model shopping.

## What We Were Trying To Build

The Governance page needed to compare external regulatory or public-source obligations with internal learning/process documents. The aim was to highlight:

- direct contradictions, where internal content says or allows something the external source prohibits or constrains
- missing obligations, where an external duty has no internal coverage
- missing detail, where the internal content covers the topic but omits a material qualifier, scope, deadline or exception
- too-vague coverage, where internal wording is too broad to prove the specific obligation is handled
- supported coverage, where internal wording aligns with the external source
- not-related pairs, where similar words do not mean the same obligation is being discussed

The desired output was not a legal decision. It was a review queue for human governance review, with evidence, rationale, suggested action and enough traceability to explain why an item was raised.

## Important Scope Note

This work did not fine-tune model weights. No local model was trained or updated at the parameter level.

The "tuning" was applied to the reasoning engine around the model:

- prompt and rubric wording
- candidate selection
- same-obligation screening
- fallback classification
- deterministic safety gates
- benchmark labels and holdout discipline
- observability and scorecard reporting

That distinction matters. The evidence supports an engineered evaluation and orchestration layer around local open-source models, not a custom-trained compliance LLM.

## Initial Problem: Fast But Poor Intelligence

The first regulatory-candidate approach worked mainly by extracting terms from external sources and looking for internal matches. This produced many false positives. A typical failure looked like:

- External: "You must keep certain records to be able to reclaim input tax."
- Internal: "Where a supplier has materially different fulfilment or operational rules, multiple commercial or service contracts may be needed."
- Reported signal: shared word "needed" plus external obligation/internal permission.

The system could see modality, but it could not reliably understand whether the two passages were about the same governed obligation. That created low-trust findings and the risk of reviewer fatigue.

The key conclusion was that the engine needed a pairwise reasoning workflow:

1. Pick candidate external/internal evidence pairs.
2. Decide whether they are about the same obligation.
3. Classify the relationship.
4. Keep diagnostics showing whether the LLM was actually called.
5. Report model-only and guard-adjusted decisions separately.

## Architecture Direction

The compliance reasoning engine was built as a standalone local microservice. This was deliberate because the reasoning workflow is expensive, experimental and likely to evolve independently from the main app.

Core design choices:

- FastAPI microservice for reasoning review jobs.
- Queue-style review execution because pairwise checks can be slow.
- API bridge from the main Control Panel.
- Exportable markdown findings for benchmark review.
- Local Ollama model backends for DeepSeek and Qwen models.
- `nomic-embed-text` embedding support for semantic candidate rescue.
- Separate review modes for external-vs-internal and internal-vs-internal checks.
- Progress, cancellation and rerun controls for long-running reviews.

The service kept the main application protected from direct model coupling while allowing the reasoning pipeline to change quickly.

## Benchmark Harness

The benchmark harness became the backbone of the work.

The labelled corpus lives at:

`tests/evaluation/compliance_reasoning_labels.json`

The scorecards are stored under:

`docs/benchmark/compliance/`

Each benchmark run records:

- overall accuracy
- split accuracy for training versus holdout labels
- per-class precision, recall and F1
- contradiction precision, recall and false-positive rate
- confusion matrix
- mean and p95 latency
- model-only accuracy versus guarded accuracy
- guard-helped and guard-hurt counts
- candidate source counts: lexical, anchor and semantic
- same-obligation screen calls, passes, rejects and errors
- adjudicator coverage and never-adjudicated rows
- no-candidate fallback reasons
- gate-demotion reasons
- prompt context estimates
- classification stability across repeated runs

The normal benchmark command is:

```bash
.venv/bin/python scripts/evaluate_compliance_reasoning.py --depth deep --model qwen2.5:14b-instruct --runs 3
```

The fake-generator mode is CI plumbing only. It proves the harness can run without Ollama, but it is not model-quality evidence.

## Label Classes

The final labelled benchmark used these classification classes:

| Class | Meaning |
|---|---|
| `contradiction` | Internal content conflicts with the external obligation or reverses its meaning. |
| `supported` | Internal content covers the external obligation well enough to be assurance evidence. |
| `too_vague` | Internal content is broadly related but too generic to prove the requirement is handled. |
| `missing_obligation` | The internal source family is relevant, but the specific obligation is absent. |
| `missing_detail` | The internal content is on-topic but omits a material scope, qualifier, deadline, exception or detail. |
| `not_related` | The passages are not about the same governed obligation. |

The labels include true positives and false-positive traps. Examples include VAT evidence retention, VAT rate-change timing, packaging waste reporting, anti-bribery controls, data-protection duties, accessibility obligations and consumer-rights obligations.

## Training Versus Holdout Discipline

One of the most important lessons was that holdout labels can become contaminated.

When a benchmark failure directly informs a prompt, guard, anchor or rubric change, that label can no longer be treated as clean generalisation evidence. It becomes training/regression evidence.

This led to an explicit rotation policy:

- VAT and packaging labels became training/regression because they were used during early tuning.
- Bribery holdout became training after its failures informed fixes.
- Data-protection holdout became training after it exposed polarity and safety-gate defects.
- Accessibility holdout became training after it exposed guard overreach.
- Consumer-rights holdout became the clean final model-comparison holdout.

This is why later scorecards prioritised clean-holdout and model-only metrics over the headline overall score.

## Iteration Timeline

The table below summarises the key benchmark progression. The totals changed as the labelled set grew, so the percentages are not all directly comparable. The pattern is still useful: the project moved from hidden pipeline failure, to observable failure, to overfitting detection, to clean model comparison.

| Stage | Date / scorecard | Main model profile | Result | What it taught us |
|---|---|---|---|---|
| Baseline | 2026-07-03 11:57 | DeepSeek-R1 14B | 33/114, 28.9% | The engine collapsed many classes into `missing_obligation`; candidate starvation was hidden. |
| Observability rerun | 2026-07-03 13:06 | DeepSeek-R1 14B | 33/114, 28.9% | 57/114 rows never reached useful adjudication; prompt context was not the problem. |
| v6 candidate alignment | 2026-07-03 15:30 | DeepSeek-R1 14B | 84/114, 73.7% | Lexical plus anchor candidate rescue helped materially, but some gains came from hand-written anchors. |
| v7 generalisation slice | 2026-07-03 17:54 | DeepSeek-R1 14B | 87/150, 58.0%; holdout 41.7% | Fresh bribery holdout exposed overfitting; semantic threshold alone could not separate related from unrelated pairs. |
| v8 screen and fallback | 2026-07-03 22:53 | DeepSeek-R1 14B | 99/150, 66.0%; holdout 50.0% | Same-obligation screening was promising but still had failure modes and too many conservative misses. |
| v8.1 | 2026-07-04 07:04 | Balanced DeepSeek 8B + DeepSeek 14B | 120/150, 80.0%; holdout 83.3% | Screen errors were fixed; screen rejects still needed better resolution. |
| v8.2 | 2026-07-04 09:47 | Balanced DeepSeek 8B + DeepSeek 14B | 135/150, 90.0%; holdout 83.3% | Generic polarity and class-boundary fixes improved the result, but saturation risk increased. |
| v8.3 | 2026-07-04 12:36 | Balanced DeepSeek 8B + DeepSeek 14B | 144/150, 96.0% | Benchmark saturation detected. Too much of the score came from deterministic guard rewrites. |
| v8.4 reset | 2026-07-04 14:41 | Balanced DeepSeek 8B + DeepSeek 14B | 171/186, 91.9%; clean holdout 75.0% | Data-protection holdout showed guards helped training but hurt fresh generalisation. |
| v8.5 guard repair | 2026-07-04 17:49 | Balanced DeepSeek 8B + DeepSeek 14B | 201/222, 90.5%; accessibility holdout 83.3% | Model-only holdout was 100%, but guards reduced it to 83.3%. The model was often right and guards were overcorrecting. |
| Final DeepSeek baseline | 2026-07-04 22:12 | Balanced DeepSeek 8B + DeepSeek 14B | 234/258, 90.7%; consumer-rights holdout 75.0% | DeepSeek 14B remained strong on training/regression, but weaker on the clean consumer-rights holdout. |
| Final Qwen comparison | 2026-07-05 00:29 | Balanced DeepSeek 8B + Qwen 14B | 219/258, 84.9%; consumer-rights holdout 91.7%; model-only holdout 100% | Qwen 14B generalised best on the clean holdout and was much faster. |

## Key Engineering Changes

### 1. Candidate Starvation Became Visible

Early scorecards could not tell whether the model was wrong or whether the evidence pair never reached the model. We added diagnostics such as:

- `llm_called`
- `candidate_count`
- `adjudication_count`
- `never_adjudicated_rows`
- `missing_obligation_fallback_count`
- `gate_demotion_reasons`

This changed the debugging conversation. Instead of saying "DeepSeek missed it", we could say "the adjudicator never saw the pair" or "the safety gate demoted the model result".

### 2. Candidate Selection Improved

Candidate selection started with lexical overlap, then added governed anchors and optional embeddings.

Useful governed anchors included concepts such as:

- VAT invoice records
- input-tax evidence
- business/private-use proportion
- packaging threshold
- packaging evidence retention
- anti-bribery payment/training controls

This improved recall, but it also created a risk: too many hand-written anchors can memorise the benchmark. That is why clean holdout rotation became necessary.

### 3. Semantic Embedding Rescue Had A Negative Result

`nomic-embed-text` was tested as a semantic rescue path. The diagnostics showed an important negative result:

- related cross-register pairs often scored around 0.49 to 0.70
- unrelated pairs could still score around 0.34 to 0.55
- the ranges overlapped too much for a simple threshold to solve the problem

The conclusion was not "embeddings are useless". The conclusion was narrower: embeddings alone could not safely decide same-obligation alignment for legislation-versus-policy pairs. This was useful evidence because it stopped us from endlessly tuning a threshold that could not separate the classes.

### 4. Same-Obligation Screening Was Added

The next step was to use a bounded local LLM screen for candidate pairs that lexical and semantic selection struggled with.

The Balanced screen asks a narrower question:

"Are these passages about the same governed obligation?"

This helped separate:

- same topic, same obligation
- same topic, different obligation
- similar wording, unrelated obligation

The Balanced screen is intentionally cheaper than the Deep adjudicator. It remains `deepseek-r1:8b`.

### 5. No-Candidate Handling Was Separated

A major early defect was that no-candidate situations often fell into `missing_obligation`. That could create false assurance in the wrong direction: every unmatched external obligation became an apparent internal compliance gap.

The engine now separates:

- genuine `missing_obligation`
- deterministic `not_related`
- screen-rejected not-related
- screen-rejected in-scope missing obligation
- screen error requiring human review

This is safer and easier to explain.

### 6. Deterministic Guards Were Added, Then Audited

Guards were added to catch patterns the model missed, such as:

- obligation versus denial
- prohibition versus permission
- broad internal wording omitting an exception
- goods/services scope mismatch
- business/private-use scope mismatch
- weak supported coverage

These guards improved saturated training scores, but later holdout tests proved that guards could also damage generalisation. The v8.4 and v8.5 scorecards showed the key problem:

- training labels improved after guards
- clean holdout labels sometimes got worse after guards
- model-only results were often better than guarded results on fresh domains

That is why guard ablation became mandatory.

### 7. Guard Ablation Became A Decision Metric

Every serious scorecard now reports:

- model-only accuracy
- with-guards accuracy
- guard changed count
- guard helped count
- guard hurt count
- guard impact by split

This avoided a misleading headline score. If guards carry the result on the training set but hurt clean holdout, that is not a stable reasoning engine.

## Important Lessons

### Larger Model Does Not Automatically Mean Better Reasoning

The project started with the assumption that DeepSeek-R1 reasoning models might be the best fit. The benchmark showed something more nuanced.

DeepSeek-R1 14B performed well on training/regression labels, but Qwen 2.5 14B Instruct performed better on the clean consumer-rights holdout and was much faster.

### Instruct Models Can Beat Reasoning Models For Closed Adjudication

The final comparison showed that an instruction-tuned model can outperform an R1-style reasoning model for this task. The task is not open-ended creative reasoning. It is bounded classification against two evidence passages and a fixed rubric.

For this closed adjudication workflow, extra "thinking token" latency did not translate into better trusted results.

### Overall Accuracy Was Not The Best Metric

DeepSeek-R1 14B had the highest final overall guarded accuracy: 90.7%.

But that overall number included a large training/regression set that had already influenced prompt and guard tuning. Qwen 14B had lower overall accuracy at 84.9%, but it won the clean holdout and model-only tracks.

That is why the final ranking prioritised:

1. clean-holdout model-only accuracy
2. clean-holdout guarded accuracy
3. contradiction precision
4. contradiction recall
5. lower p95 latency

### Benchmark Saturation Was A Real Risk

The v8.3 scorecard reached 96% overall accuracy. On the surface that looked like a breakthrough. In reality it was a warning.

The high score was partly caused by deterministic guard rewrites that had been iterated against known failures. Once that was identified, the old benchmark was treated as training/regression evidence rather than proof of generalisation.

That decision made the final model comparison much more trustworthy.

## Final Model Comparison

The final comparison used five local Ollama model profiles:

- `deepseek-r1:8b`
- `deepseek-r1:14b`
- `deepseek-r1:32b`
- `qwen2.5:7b-instruct`
- `qwen2.5:14b-instruct`

All were compared with the same benchmark harness and three-run stability check. The Balanced screen remained `deepseek-r1:8b`.

| Rank | Model | Overall | Clean holdout | Holdout model-only | Contradiction P/R/F1 | P95 latency | Guard hurt |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | `qwen2.5:14b-instruct` | 84.9% | 91.7% | 100.0% | 100.0% / 83.3% / 90.9% | 7.3s | 6 |
| 2 | `deepseek-r1:32b` | 80.2% | 75.0% | 83.3% | 100.0% / 79.2% / 88.4% | 38.9s | 6 |
| 3 | `deepseek-r1:14b` | 90.7% | 75.0% | 83.3% | 100.0% / 70.8% / 82.9% | 18.3s | 6 |
| 4 | `deepseek-r1:8b` | 72.1% | 66.7% | 66.7% | 100.0% / 66.7% / 80.0% | 33.4s | 3 |
| 5 | `qwen2.5:7b-instruct` | 69.8% | 58.3% | 66.7% | 100.0% / 41.7% / 58.8% | 5.7s | 6 |

Source comparison:

`docs/benchmark/compliance/model-comparison-2026-07-05T00-29-37+00-00.md`

## Final Decision

Use:

```bash
KP_COMPLIANCE_DEEP_LLM_MODEL=qwen2.5:14b-instruct
```

Keep:

```bash
KP_COMPLIANCE_BALANCED_LLM_MODEL=deepseek-r1:8b
```

Rationale:

- Qwen 14B had the best clean consumer-rights holdout score.
- Qwen 14B had 100% model-only clean holdout accuracy.
- Qwen 14B had the best contradiction recall while preserving 100% contradiction precision.
- Qwen 14B was materially faster than DeepSeek 14B and DeepSeek 32B.
- DeepSeek 14B's stronger overall result was discounted because it was driven by the saturated training/regression set.
- DeepSeek 32B was slower and did not beat Qwen 14B on the trusted clean-holdout metrics.
- Qwen 7B was fast but missed too many contradictions.

## Small-Holdout Caveat

The final clean holdout was still small: 12 consumer-rights labels, scored across three runs as 36 rows.

That means Qwen 14B's 91.7% versus DeepSeek 14B's 75.0% guarded holdout difference is a two-label margin per run. The decision is still accepted because every trusted signal pointed the same way:

- model-only holdout
- guarded holdout
- contradiction recall
- latency
- stability
- zero contradiction false positives

Future regression runs should keep expanding clean holdout domains so that the final choice remains evidence-backed as the corpus grows.

## Latest Guard Follow-Up

The model comparison revealed that for Qwen 14B, the guard layer reduced clean holdout accuracy:

- model-only clean holdout: 36/36, 100%
- guarded clean holdout: 33/36, 91.7%

The repeated miss was a true contradiction demoted by the contradiction safety gate because lexical/concrete overlap was sparse. A follow-up v8.6 change refined the guard so confident same-obligation contradictions near the threshold are preserved when they share concrete terms. The change was intentionally narrow: it avoids broad false-positive rescues such as unrelated VAT rate-parameter wording.

Validation for the v8.6 guard change:

- `ruff check .` passed
- full pytest passed: 333 tests
- Azure build `20260705.4` / `#365` succeeded
- commit: `11380c6 Refine compliance contradiction guard`

## Current Operating Recommendation

For routine local governance review:

1. Use Fast only for cheap triage where false negatives are acceptable.
2. Use Balanced for quicker review where the same-obligation screen is enough.
3. Use Deep Audit with Qwen 14B for serious compliance review and benchmark runs.
4. Keep exports enabled so findings can be reviewed outside the UI.
5. Treat findings as review candidates, not legal determinations.
6. Preserve clean holdout discipline before changing prompts, anchors or guards.

## How To Reproduce The Final Benchmark

Pull the models:

```bash
ollama pull deepseek-r1:8b
ollama pull qwen2.5:14b-instruct
```

Run the benchmark:

```bash
KP_COMPLIANCE_BALANCED_LLM_MODEL=deepseek-r1:8b \
KP_COMPLIANCE_DEEP_LLM_MODEL=qwen2.5:14b-instruct \
.venv/bin/python scripts/evaluate_compliance_reasoning.py --depth deep --model qwen2.5:14b-instruct --runs 3
```

Compare multiple models:

```bash
.venv/bin/python scripts/compare_compliance_models.py \
  --scorecard docs/benchmark/compliance/deep-balanced-ollama-deepseek-r1-8b-deep-ollama-deepseek-r1-8b-2026-07-04t21-21-39-00-00.json \
  --scorecard docs/benchmark/compliance/deep-balanced-ollama-deepseek-r1-8b-deep-ollama-deepseek-r1-14b-2026-07-04t22-12-05-00-00.json \
  --scorecard docs/benchmark/compliance/deep-balanced-ollama-deepseek-r1-8b-deep-ollama-deepseek-r1-32b-2026-07-04t23-52-07-00-00.json \
  --scorecard docs/benchmark/compliance/deep-balanced-ollama-deepseek-r1-8b-deep-ollama-qwen2.5-7b-instruct-2026-07-05t00-06-13-00-00.json \
  --scorecard docs/benchmark/compliance/deep-balanced-ollama-deepseek-r1-8b-deep-ollama-qwen2.5-14b-instruct-2026-07-05t00-29-37-00-00.json
```

## Evidence Files

Primary files:

- `docs/benchmark/compliance/model-comparison-2026-07-05T00-29-37+00-00.md`
- `docs/benchmark/compliance/model-comparison-2026-07-05T00-29-37+00-00.json`
- `docs/benchmark/compliance/deep-balanced-ollama-deepseek-r1-8b-deep-ollama-qwen2.5-14b-instruct-2026-07-05t00-29-37-00-00.md`
- `docs/benchmark/compliance/deep-balanced-ollama-deepseek-r1-8b-deep-ollama-qwen2.5-14b-instruct-2026-07-05t00-29-37-00-00.json`
- `tests/evaluation/compliance_reasoning_labels.json`
- `docs/data-and-governance/compliance-reasoning-service.md`

Archived development scorecards:

- `docs/benchmark/compliance/Old/`

Key implementation files:

- `services/compliance_reasoning/agent.py`
- `services/compliance_reasoning/app.py`
- `scripts/evaluate_compliance_reasoning.py`
- `scripts/compare_compliance_models.py`
- `tests/test_compliance_reasoning_service.py`
- `tests/test_compliance_eval_harness.py`

## Remaining Risks And Next Work

The engine is now much more trustworthy than the first regulatory-candidate workflow, but it is not finished.

Known limitations:

- The final clean holdout is small and should keep growing.
- Guard logic can still hurt fresh domains if it is too aggressive.
- Synthetic labels are useful for evaluation discipline but should be complemented with reviewed real-domain examples.
- The engine can identify likely conflicts and gaps, but human review remains mandatory.
- Latency is acceptable for local queued review, not instant interactive chat.

Recommended next work:

1. Keep Qwen 14B as the Deep Audit default.
2. Add more clean holdout domains before any broad prompt or guard tuning.
3. Continue reporting model-only versus guarded accuracy.
4. Track contradiction recall on novel domains as the main quality risk.
5. Preserve all scorecards as S52/S53/S14 evaluation evidence.
6. Connect findings into the upcoming ontology layer so obligations, claims, controls and affected processes become queryable graph objects.

## Final Rationale In Plain English

We did not simply find a model that "looked good". We built enough measurement to know when we were fooling ourselves.

The reasoning engine improved because the benchmark process became stricter:

- failures were labelled
- hidden non-adjudication was surfaced
- false positives were preserved as test traps
- contaminated holdouts were retired
- clean holdouts were rotated in
- guards were ablated
- latency was measured
- model-only judgement was separated from deterministic overrides

That is why the final Qwen 14B decision is defensible. It is not based on a single anecdotal review. It is based on the cleanest available evidence after the pipeline defects and benchmark leakage risks were made visible.
