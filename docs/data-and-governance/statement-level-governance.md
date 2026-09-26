# Statement-level governance

**25 September 2026 · Built by Claude · Epic #1744 (GOV E1) · Feature #1745 (GOV F2), Stories #1749 (S5), #1750 (S6), #1751 (S7) · Status: steps 1–3 of the approved plan, delivered for the Human's evaluation on branch `claude/tiberius-speed-safety`.**

## Why

The Human approved the plan in the [governance engine review](governance-reasoning-engine-review-2026-09-25.md) on 25 September 2026. The document-pair Full Governance Review is being replaced by governance that works on statements.

The reasons, from the review:
- **Speed.** 210 document pairs took 35 h 23 m.
- **No real findings.** All 32 findings were dismissed or accepted by a person.
- **Blind spots.** The engine only ever saw sentences containing "must" or "should".

This document covers steps 1–3 (the statement store, the candidate index and the judge), the move onto the OpsAtlas Sales data (GOV S9, #1753) and step 4, scope and dates (GOV S8, #1752). Retiring the old path (#1754) waits for the Human's approval.

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
- Scope and dates as data rather than text: done since, in [Scope and dates](#scope-and-dates-26-september-2026-gov-s8-1752).

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

## On the OpsAtlas Sales data (26 September 2026, GOV S9 #1753)

The Human chose **local judging as the default** and moved governance onto the sales data: the records Tibi speaks from, and the claims contributed in interviews. `services/opsatlas_sales/statement_governance.py` runs the review there under four rules, fixed before the first run:

1. **Records, not evidence.** The DT603 sections, repository files and interview accounts a record cites, and a record's earlier versions, are never compared.
2. **Checked before approval.** Pending contributions are governed. Rejected (withdrawn) records are not.
3. **Status is scope.** The judge sees, for example, "Path to production (planned)", so a planned capability is not read as contradicting an available one.
4. **Kinds apart.** Conversation-style records are compared only with each other.

**The judge.** By default the judge is `qwen2.5:14b-instruct`, with `qwen3.5:35b-a3b` thinking as a second opinion on each conflict. A frontier judge is used only when both are set:
- `SALES_GOVERNANCE_JUDGE=anthropic:<model>`;
- `SALES_GOVERNANCE_FRONTIER_APPROVED=yes`, the data owner's approval.

**When it runs:**
- In the background, from the Governance page (**Review records now**).
- Automatically when a claim is proposed. Only the claim's own pairs are judged.

**Settling a finding:**
- **Conflicts** lead the governance agenda, and Tibi's governance interview reads both records with their status and contributor. The decisions are *supersede* (one is right), *distinct scope* (both hold), *dispute* (unsure) or *not an issue*.
- **Duplicates** are settled by *merge* (keep one), *intended* or *not an issue*.
- The Human's approval on the Governance page closes the finding through `accept_issue`. `Knowledge.settle` then applies the decision:
  - the record not kept is withdrawn from answers;
  - a dispute withdraws both until it is resolved;
  - other decisions are noted on both records.
- A withdrawn record can be enabled again from Tibi knowledge.

**Measured, on copies of the live workspace:**
- **As it stands:** 27 records, 92 governed statements and 72 candidates gave no conflicts and no duplicates (111 s). The records were written from DT603 to cover separate topics.
- **With two claims proposed as an SME might phrase them:**
  - Dan's claim, "OpsAtlas runs its language models in a cloud service rather than on the same machine", was found in conflict with the architecture record ("a local-first modular web platform"). The second opinion agreed.
  - Chris's rewording of the security record's model-separation sentence was found as a duplicate.
  - 78 candidates were judged in 210 s.
- **End to end in the browser** (throwaway copy, own key):
  1. The Governance page listed both findings side by side.
  2. A typed governance interview read both records.
  3. The Human's decisions were read back and saved.
  4. On approval, Dan's claim was withdrawn as superseded and Chris's as merged; the kept records stayed approved; no findings remained open.

**Fixed along the way (S162 #1760).** Typing the next answer while Tibi read the following question discarded the whole turn. An answer Tibi had announced as "Saved for your approval" was lost, and the next answer was heard against the previous question.
- A governance turn now commits as soon as the line that moves the interview has been heard: "Saved for your approval.", the question line, or the read-back.
- Fillers never commit a draft that has not been heard.
- A bare "yes" to an either-or question about two records is no longer taken as a decision.
- The latency replay after the change: p50 1,729 ms and p95 1,974 ms, against a budget of 1,950 / 3,100, with another workload using the GPU.

**Still open in GOV S9:** a decision surviving a rewording of the record that keeps its meaning. Today a reworded statement is a new statement, and its pair is judged again.

## Scope and dates (26 September 2026, GOV S8 #1752)

**The claim tested.** Dan's note proposes lifecycle metadata on knowledge: when it is in force, which phase it describes, where it applies, and what it replaces. The claim is that two statements with different scopes should not be raised as a conflict. On the benchmark, every error the fast local judges made was a scope or date case. So S8 was built as rules that settle the plain cases without a model, and then measured.

**What was built:**

| Where | What |
|---|---|
| Sources (`SourceRecord`) | Five optional fields: `effective_from` and `effective_to` (ISO dates), `phases`, `applies_to` (sites, networks), and `supersedes` (source IDs). |
| Statements (`Statement.scope`) | The phase and dates a statement opens with, and the sites or networks it says it applies to. They are kept at extraction; extractor version 3 re-extracted every source once, and every statement ID was unchanged. |
| Rules (`src/assistant/governance/scope.py`) | A pair whose dates cannot overlap is set aside, not judged. So is a pair whose phases exclude each other: day one against the end state, and the proof of concept against a real deployment. "Applies to" never sets a pair aside, because a general rule can genuinely conflict with a site-specific one. A source's fields override what its words say. A source named in a governed source's `supersedes` is not governed; this is the rule the sales workspace already applied to a record's earlier versions. |
| Sales (`services/opsatlas_sales/corpus/record_scope.json`) | A curated record carries a phase only when its title names one. Data, security and limitations are the proof of concept; next steps and real deployment are a real deployment. A contributed claim is scoped only by its own words, never by the topic it was filed under: a claim filed under "real deployment" that states something about the proof of concept must still meet the proof-of-concept records. |
| People | The Governance page shows what each side covers ("Covers the proof of concept") and how many pairs were set aside. Tibi's governance interview says it too: "marked available and covering the proof of concept". |

**Rules fixed before measuring (26 September), and the two revisions measurement forced:**
1. **Dates and exclusive phases set aside; "applies to" told to the judge.** On the benchmark, telling the judge what each statement applies to fixed no case. It also turned one case into a false conflict for `qwen2.5:14b` (scoped-09: stores print labels, against "for the pilot sites only, labels are printed centrally"). **Dropped:** the judge sees only document, section and text, as the benchmark validated, and scope is shown to people instead.
2. **Any mention of a phase or date was the statement's scope.** On the 21 learning packs this set aside 6 pairs of table rows that *discuss* the choice between phases, not rows that are in a phase. One was a duplicate Claude Opus 5.5 had found: "Decides whether the new model is adopted immediately or introduced in a later phase" against "Decides whether ingredient redesign is a day-one change or a later-phase improvement". The local judge had called all 6 "neither", so the default lost nothing, but the rule would hide real findings. **Revised:** a statement's words give it a phase or dates only when it opens with them ("For day one, …", "In the end state, …", "From 1 April 2027, …", "The proof of concept uses …"). The revision was made after seeing the 6 pairs and the benchmark's wording, so the benchmark is not an independent test of it; GOV S4's blind pairs will be.

**Measured on the governance pair benchmark** (91 cases; `docs/benchmark/governance/`):

| Judge | Plain | First rule, annotated | First rule, set aside only | **Final: opening rule, set aside only** |
|---|---|---|---|---|
| `qwen2.5:14b-instruct` (the default's first judge) | 98% | 97% (scoped-09 broken) | 98% | **98%**, no verdict changed |
| `qwen2.5:7b-instruct` | 96% | 98% | 98% | **98%**: scoped-02 (day one against the end state) and scoped-04 (8 weeks from 1 April 2027 against 6 weeks until 31 March 2027) set aside; both were its false conflicts |

- The final rule sets aside exactly 2 of the 91 cases. No planted conflict or duplicate is set aside: conflict-12, day one against day one, is still judged and still found.
- The default, `qwen2.5:14b` with the reasoning second opinion, already scored 100%. It sees the same input, so it is unchanged.
- Timings ran while another workload used the GPU.

**Measured on the 21 learning packs** (a copy of the data, local judge and second opinion):
- The final rule set aside **0** of 1,990 candidates. Only 7 governed statements open with a phase (6 day one, 1 later phase), none opens with a date, and no candidate pair spans two phases.
- The findings are identical: 2 conflicts and 38 duplicates. The run took 5 s, because the judge's input was unchanged and all but 3 judgements came from the cache.

**Measured on the sales data** (throwaway copies of the live workspace; local judge and second opinion; the same review without and with the rules):

| Scenario | Candidates | Set aside by phase | Raised without scope | Raised with scope |
|---|---|---|---|---|
| The 27 records as they stand | 72 | 3: data, limitations and security (the proof of concept) against real deployment and path to production | none | none |
| Dan's cloud claim and Chris's rewording (the S9 scenario) | 78 | the same 3 | 1 conflict, 1 duplicate | the same conflict and duplicate |
| Two claims about phase: Dan, *planned*, "A real deployment would provide enterprise single sign-on …" (topic: limitations); Chris, "The proof of concept connects directly to live organisational systems and the bank's own data" (topic: real deployment) | 76 | 5: the same 3, Dan's claim against the limitations record, and Chris's claim against path to production | 2 conflicts: Chris's claim against the data and security records | the same 2 conflicts, each side shown as covering the proof of concept |

- Every pair set aside had been judged "neither" without the rules. On this data they saved judging and lost nothing.
- Chris's claim was filed under "real deployment" but speaks about the proof of concept. It still met the proof-of-concept records and was raised; scoping a claim by its topic would have hidden it.
- **Fixed during this measurement.** The workspace prefixes a contributed claim with its status ("Currently: …", "Planned, not confirmed available: …"). As first written, the opening rule stopped at the label, so no claim had a scope. The rule now also reads the statement after a short leading label. The benchmark's set-aside cases (scoped-02 and scoped-04) and the 21 packs' result are unchanged by this.

**What this says about the claim:**
- Scope settles pairs only when it is *declared*: by a record's curated metadata, or by a statement that opens with it. Inferred from mentions, it hid a real duplicate.
- It helps a weaker or faster judge (the 7b's two scope errors). It does not change the default judge's accuracy, which already had those cases right. Its other gains are fewer pairs to judge, and findings that show each side's scope to the person deciding.
- The 21 learning packs declare almost no scope, so there it changes nothing. The sales records declare it through `record_scope.json`, and there it matters.

**Tibi's voice path.** Tibi now says what each side of a finding covers, so the latency replay ran before delivery. Time to first audio was p50 1,768 ms and p95 2,032 ms, against a budget of 1,950 / 3,100, over 40 turns with no errors. The other workload held the GPU for the whole run.

**Not done in S8:**
- There is no screen yet for a knowledge owner to set a source's scope fields; today they are set through the register.
- "Applies to" is shown, not used.
- Supersedes is tested in the engine; no workspace sets it yet.

## Checked

- **Tests.** Tests cover the engine (12), scope and dates (8), the sales workspace (7), the interview (3) and the conversation loop (3). The scope tests cover what a statement opens with against what it only mentions, status labels, disjoint dates and exclusive phases, source fields overriding words, supersedes, re-extraction keeping every statement ID, and the judge seeing only the benchmark's payload. The engine tests cover:
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
- **Suites.** 1,015 Python tests pass on 3.11 and 3.12, 58 browser tests pass, and the control panel builds.
