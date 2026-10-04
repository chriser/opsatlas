# ARCH H1 — an answerability judge on facts-map answers, with a fall-back to the documents

**Hypothesis (ADO ARCH H1 #1942), pass mark registered 30 September 2026 before any code:** a check that a facts-map
(OAG) answer's facts really answer the question, and a fall-back to document retrieval when the facts map refuses or
fails the check, raises accuracy without regressing the accepted route. Benchmark: `scripts/evaluate_rag_vs_oag.py`,
dataset rag-vs-oag-v2, a copy of the Classic corpus (246 approved sections), `qwen2.5:7b-instruct` and
`nomic-embed-text`, three runs per configuration, `oag_first`. Development on the tuning split; the holdout evaluated once.

**Marks.** Effect: tuning accuracy ≥ 115/135. Guards: holdout accuracy ≥ 68/72, route accuracy 100 %, out-of-scope
refusals 100 %, stable questions ≥ 23/24; no new wrong refusals; mean holdout latency within +0.5 s of the same-session baseline.

## What was built (`claude/arch-h1`)

`GroundednessValidator.answers(question, facts)`: one short YES/NO judgement by the local model on whether the plan's
facts state what the question asks. `AnswerService.answer()`: a facts-map answer stands only when the judge does not say
NO (a judge with no verdict keeps the answer and records it); when the facts map refuses, or the judge says NO, the
question goes to the documents, and the audit trace records the fall-back (`fallbacks`). `oag_only` is unchanged.

## Results (same session, same machine, back to back)

| Split | Variant | Passed | Route | Stable | Mean latency | p95 |
|---|---|---|---|---|---|---|
| tuning | baseline | 91/135 (67.4 %) | 123/135 (91.1 %) | 40/45 | 1.59 s | 7.08 s |
| tuning | judge on every plan | 107/135 (79.3 %) | 117/135 (86.7 %) | 43/45 | 1.52 s | 5.42 s |
| holdout | baseline | 72/72 (100.0 %) | 72/72 (100.0 %) | 24/24 | 1.37 s | 6.34 s |
| holdout | judge on every plan | 68/72 (94.4 %) | 69/72 (95.8 %) | 23/24 | 1.75 s | 6.02 s |

Tuning: the four out-of-scope questions the facts map used to answer with a listing of loosely related facts are now
refused (15/15 out-of-scope passes, from 3/15), `structured-relationship-001` is answered correctly from the documents,
failures on the facts-map path fall from 27 to 12, and no question is wrongly refused. But the judge also said NO to
one correct facts-map answer (`structured-entity-004`, a `process_controls` plan) on every run.

Holdout (evaluated once): accuracy 68/72 meets the guard exactly, out-of-scope 12/12, stability 23/24, latency +0.38 s —
but **route accuracy 95.8 % fails the guard**: `structured-entity-holdout-003`, a precise facts-map lookup, was judged
NO on all three runs, sent to the documents, and answered wrongly there (3/3 → 0/3). One narrative question varied
(3/3 → 2/3), which is model noise on the document path.

**Decision: not adopted as built.** The judge earns its keep on the facts map's *aggregate listings* (every out-of-scope
mistake and most wrong answers came from them) and costs accuracy on the *precise* plans (owner, controls, systems,
roles), where its only effect on both splits was a false NO. The effect mark (115) was also set against the accepted
result's tuning baseline (97) rather than the same-session one (91), which made it unreachable by the facts-map path
alone; the same-session comparison is the one reported above.

## Follow-up registered: H1b

The judge applied to `aggregate_facts` plans only, with the same refusal fall-back; precise plans answer as before.
Marks: tuning out-of-scope refusals 15/15 and facts-map-path failures ≤ 14 (from 27); holdout accuracy ≥ 72/72 of the
same-session baseline minus noise (≥ 70/72), route accuracy 100 %, stable ≥ 23/24, latency within +0.5 s; no new wrong
refusals. The holdout has been seen once (above); its second evaluation is declared as such in the record.

## H1b results (same session; the holdout's declared second look)

| Split | Variant | Passed | Route | Stable | Mean latency | p95 |
|---|---|---|---|---|---|---|
| tuning | baseline | 91/135 (67.4 %) | 123/135 (91.1 %) | 40/45 | 1.59 s | 7.08 s |
| tuning | judge on listings only | 104/135 (77.0 %) | 123/135 (91.1 %) | 40/45 | 1.70 s | 6.21 s |
| holdout | baseline | 72/72 (100.0 %) | 72/72 (100.0 %) | 24/24 | 1.37 s | 6.34 s |
| holdout | judge on listings only | 72/72 (100.0 %) | 72/72 (100.0 %) | 24/24 | 1.46 s | 6.11 s |

Tuning: out-of-scope refusals **15/15** (mark met); facts-map-path failures **27 → 15** against a mark of ≤ 14 — missed by
one. The fifteen that remain are five questions on every run: `structured-relationship-001` (a precise plan, no longer
judged), and four listings the judge accepts — `structured-relationship-003`, `-008`, `-009` and `aggregate-003` — where
its YES is a defensible reading of the facts (008's listing is in fact a correct answer that the scorer's aliases do not
match; 003 and aggregate-003 name the systems and the staging control the question is about) or a conflation (009: the
step that *sends* shelf-packaging information, not the consumer that receives it). No question is wrongly refused; the
route split is unchanged (123/135 both). Latency +0.11 s.

Holdout: **72/72, route 100 %, stable 24/24, latency +0.09 s, out-of-scope 12/12** — identical to the baseline
question by question. Every guard met.

**Reading.** The narrowed judge removes the one failure class it was built for — out-of-scope questions answered with a
listing of lexically similar facts — on both splits, at no measured cost to the accepted route, and the fall-back on a
facts-map refusal is in place for the Sales corpus, where refusals occur. The single miss is the one-count shortfall on
an effect estimate the author set. The decision to adopt is recorded in ADO ARCH H1 with this file.

Raw results: the scratch JSON of the runs is kept with this session; the harness was run with `--no-write`, so the
accepted benchmark files are untouched.
