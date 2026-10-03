# REF E1 phase 2: the hypotheses H1, H3 and H4, and the retrieval baseline

**3 October 2026.** The pass marks below were proposed by Claude and approved by the Human before any run, and are
registered on each item in Azure DevOps with how each number is counted. Every candidate is a setting that is off by
default (`assistant/settings.py`), so nothing changed in production while it was measured. A candidate that misses any
part of its mark is recorded as rejected.

Runner: `scripts/evaluate_evidence.py` (commit 2dddac6), on a disposable copy of the sales workspace; OpsAtlas Classic's
corpus copied for the RAG/OAG set (Classic itself only read). Baseline and candidate in one session, the answer model
`qwen3.5:4b` for the Sales cores, `qwen2.5:7b-instruct` for the Classic corpus, and an independent judge
(`qwen2.5:14b-instruct`, temperature 0) for H1. Results: `evaluation/results/evidence/2026-10-03-*.json`.

## Verdicts

| Item | Pass mark | Baseline | Candidate | Verdict |
|---|---|---|---|---|
| REF H1 #2055, withhold an answer the check marks unsupported | unsupported shown halved; correct held back +2 points at most; median +300 ms at most | 20 unsupported shown (Sales 5, RAG/OAG holdout 15) | 15 (2 and 13): a 25 % fall; 2 correct answers of 60 held back (3.3 points); median faster | **Rejected** |
| REF H3 #2057, scope decides which source may answer | violations 5 % of scope questions at most; correct in-scope answers −2 points at most | 5 of 16 violate (31 %); 40 % correct in scope | 2 of 16 (12.5 %); 80 % correct in scope | **Rejected** (violations) |
| REF H4 #2058, evidence for each part of a multi-part question | coverage +15 points at least; single-part within 2 points; median +1 s at most | coverage 76.9 %; single-part 83.3 % | coverage 84.6 % (+7.7); single-part 83.3 %; median 0.5 s faster | **Rejected** (coverage) |

## What the numbers say

**H1.** The grounding check rarely says "unsupported" (2 of 30 Sales answers, none of 20 on the RAG/OAG holdout), so
withholding acts on few answers, and the two it withheld on the Sales set were correct. The fall in "unsupported shown"
is not the candidate's doing: the three Sales answers that disappeared from the count were simply answered differently
on the second run (the answer model is not deterministic). The independent judge is also strict: on the RAG/OAG
holdout it called 15 of 20 delivered answers unsupported although every one held all its expected facts. Withholding on
this check's label does not reduce unsupported answers; a better check (task #1877, or a judge of the kind used here
behind a review queue) would have to come first.

**H3.** With scope on, a source answers only when it is in force on the date asked about, is not replaced, and is for the
site named. Violations fell from 5 to 2 and correct in-scope answers doubled, but both remaining violations are real:
the 2025 policy's "Synthetic Pack A" and the Bristol guide's "3 onboarding days" still reached answers, because scope
filters the retrieved passages and not the facts map or the process registry, which are built from every approved
document. A second version that also filters those paths is the next step; it needs a new holdout, as this one has now
been looked at. Separately, the runner's "label both sites" check looked for the wrong word, so three answers that did
name both sites were scored wrong; that check is not part of the mark.

**H4.** Splitting a multi-part question and retrieving for each part raised coverage by 7.7 points and doubled the
multi-part answers that held every expected fact (25 % to 50 %), at no cost to single-part questions or speed; but the
mark asked for 15 points. On the six holdout questions accuracy fell (50 % to 33 %): the sample is small, and the
candidate is not adopted.

## The retrieval baseline (REF S21 #2053)

First measure of retrieval quality, on the Sales Playbook (65 KB, so retrieval mode), `sales_playbook_retrieval.json`:

| Measure | Value |
|---|---|
| Required-evidence recall at 1 / 3 / 5 | 55.9 % / 70.6 % / 85.3 % |
| Source selection (top passage from a required source) | 55.9 % |
| Answers holding every expected fact (34 answerable) | 73.5 % |
| Out-of-scope questions refused | 3 of 6 |
| Median answer time | 1.9 s |

Half the out-of-scope questions were answered rather than refused: retrieval returns the nearest passages above the
0.55 threshold, and the model answers from them. That is the written path's version of what H2 tests on Tibi's.

## REF H2 #2056 and the two answer paths end to end (REF S19 #2051)

`scripts/evaluate_evidence.py channels` (commit 03f8024 and later, run at bc20e81): the 36-question Sales set through
the written path, and through Tibi's text channel (what the Digital SME uses) with this phase's core, on one copy.

| Measure | Written | Tibi (1.8.9) |
|---|---|---|
| Holds every expected fact (out of scope: declines) | 88.9 % | 47.2 % |
| Refusal agrees with the other path | 30 of 36 | |
| In-scope questions answered | | 100 % |
| Answered when no record passed the threshold | | 0 |
| Median reply time | | 1.1 s |

**H2: rejected, no effect.** With the candidate on (`SME_DECLINE_BELOW_THRESHOLD=1`), nothing changed: no question in the
set fell below the threshold, so the fallback to the two nearest records never ran. The workspace marked 8 to 13
records as relevant even for the out-of-scope questions (price, certifications, customers, release dates). The
problem H2 aimed at is real, but its cause is a relevance threshold that passes nearly everything for short records,
not the fallback; that is where a next hypothesis belongs.

**What the comparison shows.** Tibi's lower score is mostly its form: replies under 300 characters miss expected facts
the written answer, given the whole guide, includes; and the guide's note on a retired service (a written-path fixed
sentence) does not travel to Tibi. On the six out-of-scope questions the written path said the guide's refusal five
times; Tibi declined in its own words in five ("not established in the available records"), each ending with the
guide's referral (new in 1.8.9), which the scorer's refusal pattern does not recognise, and in two added a negative
claim the records do not make ("does not hold any certifications", "not used in production by any customers"). The
contract tests hold the paths to the same permission, scope, citation and refusal decision at the evidence boundary;
the wording on Tibi's side is where they still differ.

## Tibi's answer scorecard per engine (REF S21)

`evaluate_engine --runs 2 --judge --core <copy>` on one copy, 1.8.8 against 1.8.9:

| Measure | 1.8.8 | 1.8.9 (prompt reworded, rejected) | 1.8.9 (as recorded) |
|---|---|---|---|
| Routing accuracy | 1.000 | 1.000 | 1.000 |
| Appropriateness | 0.985 | 0.969 | 0.969 |
| Citation coverage | 0.974 | 0.949 | 0.949 |
| Fallback rate | 0.154 | 0.231 (degraded) | 0.154 |
| Judged support (of 5) | 5.00 | 4.69 (degraded) | 4.88 |
| First segment p50 / p95 | 606 / 1,407 ms | 601 / 1,290 ms | 606 / 1,285 ms |

The engine gate now carries this scorecard beside the latency replay: a measure that moves beyond its tolerance blocks
the version, as the reworded prompt did here.
