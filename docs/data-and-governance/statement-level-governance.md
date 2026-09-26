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

## The same review with Claude Opus 5.5 (26 September 2026)

The Human approved sending the 21 learning packs' candidate pairs to Anthropic, to compare the statement-level review with the 35-hour Full Governance Review. The candidates are the same 1,987, from the same local index; only the judge changes. The run used `--provider anthropic`, with 8 requests at a time.

**What left the machine** (`docs/benchmark/governance/statement-review-2026-09-26-opus.json`, `audit`):
- 2,070 requests, 3.6 MB in all, sent to `api.anthropic.com` only.
- Per request: the pre-registered prompt and two statements (document title, section heading, text).
- The key stayed in `.env` and travelled only in its header.

| The 21 learning packs | Full Governance Review, July | Statement-level, local `qwen2.5:14b` | Local, with reasoning second opinion | Statement-level, **Claude Opus 5.5** |
|---|---|---|---|---|
| Time | 35 h 23 m | 49 m 28 s | about 65 min | **10 m 52 s** (10 m 4 s, then 48 s rerunning 83 replies cut off at 300 tokens) |
| Cost | local | local | local | **about $10** at list price ($9.10 for the kept judgements) |
| Conflicts raised | 0 contradictions, and 32 other findings (all dismissed or accepted) | 9 | 2 | **3** |
| Duplicates raised | none | 38 (24 in the same process family) | 38 | 38 (**31** in the same process family) |

**Opus's 3 conflicts, checked by hand.** They are a different kind from the local model's: who owns a task. None of the local model's 9 conflicts was raised by Opus; it read the Pack 6 tax-rate pair as compatible, which is defensible.

| Conflict | Judged by hand |
|---|---|
| **Pack 9:** step 7 gives "check whether future discount or promotional scenarios need a richer model" to the business or process owner; the roles table gives the same assessment to the finance or commercial owner | **Plausibly real**: one pack, two owners for one task |
| **Packs 1 and 2:** using supplier status to stop incomplete suppliers being used is the operational system owner's job in Pack 1 and the master data owner's in Pack 2 | **Plausibly real**: an ownership ambiguity. The one July finding the Human fixed was also a Pack 1/Pack 2 ownership clarification |
| **Pack 17 and a promotions pack:** "the system creates live promotion records once approved" against "the promotions support owner creates live promotions from templates" | Borderline: may be two stages of the same process |

**Duplicates.**
- Both judges raised 38; 15 are the same pairs.
- Of the 23 only Opus raised, 19 are within the same process family.
- Of the 23 only the local model raised, 12 are within a family; the rest are mostly parallel steps in different processes (article staging against promotion staging), and Opus rejected 22 of those 23.
- Opus's duplicates are therefore the better list of consolidation candidates.

**Read with care:**
- This corpus has no labelled answers. "Plausibly real" is a first reading for the Human to confirm, not a measured precision.
- The benchmark cannot separate Opus from the local pipeline (both score 100%); benchmark v2 is needed (GOV S4).

## Checked

- **Tests.** 11 new tests cover:
  - units and table headers;
  - stable IDs across re-ingestion, and derived sections;
  - incremental extraction;
  - template text and cited evidence kept out;
  - embeddings cached by model;
  - judgements cached per pair, with an edit re-judging only its own pairs;
  - same-document restatement against contradiction;
  - the pre-registered prompt;
  - judge errors recorded and retried;
  - the second-opinion rule;
  - the Claude judge (fixed host, key only in its header, retry, audit, and reading a reply cut off in its reason).
- **Suites.** 991 Python tests pass on 3.11 and 3.12.
