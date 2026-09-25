# Statement-level governance

**25 September 2026 · Built by Claude · Epic #1744 (GOV E1) · Feature #1745 (GOV F2), Stories #1749 (S5), #1750 (S6), #1751 (S7) · Status: steps 1–3 of the approved plan, delivered for the Human's evaluation on branch `claude/tiberius-speed-safety`.**

## Why

The Human approved the plan in the [governance engine review](governance-reasoning-engine-review-2026-09-25.md) on 25 September 2026. The document-pair Full Governance Review is being replaced by governance that works on statements.

The reasons, from the review:
- **Speed.** 210 document pairs took 35 h 23 m.
- **No real findings.** All 32 findings were dismissed or accepted by a person.
- **Blind spots.** The engine only ever saw sentences containing "must" or "should".

This document covers steps 1–3: the statement store, the candidate index and the judge. Steps 4, 5 and 7 (scope and dates, findings keyed by statements, and retiring the old path) come next, as #1752–#1754.

## How it works

| Step | Module | What it does |
|---|---|---|
| 1. Statements | `src/assistant/governance/statements.py` | Every bullet, table row and sentence of an approved source becomes a statement. Its ID is a hash of the source, the section heading and the normalised text, so it survives re-ingestion and sections moving. It also records its section, offset, kind and source version. Sections that restate the document are marked as derived and kept for reference only: Q&A pairs, JSON-style records, open questions, the tagging structure, and the preamble before numbered sections. A source is re-extracted only when its content or version changes. |
| 2. Candidates | `src/assistant/governance/statement_index.py` | Each governed statement is embedded once; the cache is keyed by model and text. Candidates are its 3 nearest statements in other documents, plus its nearest in another section of the same document, at cosine 0.70 or above. Two kinds of statement are never candidates: template text (a line repeated verbatim in 3 or more documents) and sources the caller names as cited evidence. |
| 3. Judgement | `src/assistant/governance/statement_judge.py` | Each candidate gets one call with the pre-registered benchmark prompt and no domain guards. Judgements are cached per prompt version, model and statement pair, in either order, so an unchanged pair is never judged twice. |
| Review | `src/assistant/governance/statement_review.py` | Findings quote both statements with their sources. A conflict is raised across documents or between sections of one document. A duplicate is raised only across documents: a document restating itself is recorded but not raised. An optional second opinion from a reasoning model re-checks each conflict. |

Run it with:

```
python scripts/governance_statement_review.py [--judge-model qwen2.5:14b-instruct] [--workers 4] [--second-opinion qwen3.5:35b-a3b]
```

Statements, embeddings, judgements and the latest result are kept under `data/governance/`, which is git-ignored runtime data.

## Rules fixed before measuring

These rules were decided before the runs that measure them:
- **Same-document duplicates.** A document restating itself (an overview repeating its rules) is not a duplicate; a document contradicting itself is a conflict.
- **Table headers.** A table's header row is the line directly above its `|---|` separator.
- **Second opinion.** A conflict stands only if the reasoning judge agrees; if the reasoning judge gives no answer, the first verdict stands.

## Measured

All runs used the real 21-document corpus, the one in which a person found no material contradiction after the 35-hour Full Governance Review. They used `qwen2.5:14b-instruct` on a Mac Studio M4 Max, sharing the GPU with another workload throughout. Results are in `docs/benchmark/governance/`.

| Run | Time | What happened |
|---|---|---|
| First run | **49 m 28 s** (index 6.7 s) | 1,627 statements (849 governed; 13 template lines) and 1,987 candidates (571 of them in the same document), all judged. Raised 9 conflicts and 38 duplicates; recorded 98 same-document restatements without raising them. |
| Rerun, corpus unchanged | **0.4 s** | All 1,987 judgements came from the cache, and the findings were identical. |
| One sentence edited, in a copy of the data | **10 s** | Only Pack 6 was re-extracted: 1 statement embedded, 6 pairs judged, 1,981 from the cache. The edit aligned the tax-rate step with its rule, and that conflict disappeared. |
| Second opinion on the 9 conflicts (`qwen3.5:35b-a3b`, thinking) | **15 m 7 s**, over two attempts | Of the 9 conflicts, **2 stand** and 7 are dismissed. The first attempt (7 m 30 s) allowed 4,096 thinking tokens, and 5 conflicts got no answer. A second attempt (7 m 37 s) retried only those 5 with room to finish (16,384 tokens), and all were answered. |

**The 38 duplicates:**
- 24 lie within the same process family. These are consolidation candidates, the same guidance kept twice: for example the article-list rules in Packs 6 and 7, the pack-size rule in Packs 5 and 6, and price-coverage monitoring in Packs 14 and 16.
- 14 cross families, mostly parallel role or step rows.

This reproduces the trial, which found 37 duplicates split 24 and 13.

**The 9 conflicts, and what the second opinion did with them.** All were checked by hand.

| Conflict | Judged by hand | Second opinion |
|---|---|---|
| 4 across documents: supplier request against buyer role, header record against readiness, operator against owner, day-one mass maintenance against planning feed | False: the same 4 the trial left | All dismissed |
| Pack 6: "update the parameter-level tax definition with dated validity" (step 4) against "close the old tax definition and open a new one" (key rule) | **Plausibly real**: the same document prescribes two methods | **Kept** |
| Pack 4: "legacy one-line forms are expected to be retired" against "Supplier new-line form … expected to become the standard intake" | **Plausibly real**, if "one-line" and "new-line" are the same form mis-transcribed | Dismissed as compatible. This is defensible if they are different forms; it is for the Human to decide |
| Pack 13: step 5 "Use day-one manual upload route …" against the role "Uses the mass-maintenance route …" | False: the step's own text says mass maintenance | Kept (a false alarm both judges made) |
| Pack 8 reporting extraction; Pack 5 sales against logistics units | False | Dismissed |

**Second opinion on the benchmark** (`scripts/evaluate_governance_pairs.py second-opinion`, the rule fixed before the run):
- Every case `qwen2.5:14b` called a conflict went to the reasoning judge.
- It kept all **25 of 25** true conflicts and dismissed both false ones (the travel-site price-list override and the planogram pair).
- That takes the benchmark to **100%**, at a median of 2.2 s per case, because only conflict calls pay for the slow check.

**Compared with the document-pair Full Governance Review** of the same corpus:

| | Full Governance Review | Statement-level review |
|---|---|---|
| Time for a full review | 35 h 23 m | about 65 minutes (49½ minutes, plus 15 minutes of second opinion) |
| Time for a changed document | re-judges all its pairs | seconds |
| Findings a person reviews | 32 findings, all dismissed or accepted | 2 conflicts (1 plausibly real, 1 false) and 38 duplicates (24 consolidation candidates) |

**What this does not show yet:**
- Recall on conflicts written independently rather than edited (GOV S4).
- How a frontier model compares (GOV S3).
- Scope and dates as data rather than text (GOV S8).

## Checked

- **Tests.** 9 new tests cover:
  - units and table headers;
  - stable IDs across re-ingestion, and derived sections;
  - incremental extraction;
  - template text and cited evidence kept out;
  - embeddings cached by model;
  - judgements cached per pair, with an edit re-judging only its own pairs;
  - same-document restatement against contradiction;
  - the pre-registered prompt;
  - judge errors recorded and retried;
  - the second-opinion rule.
- **Suites.** 991 Python tests pass on 3.11 and 3.12.
