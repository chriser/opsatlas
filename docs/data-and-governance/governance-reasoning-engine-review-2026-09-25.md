# Governance reasoning engine: review and benchmark

**25 September 2026 · Claude, for the Human · Status: for decision. Nothing in this review changes the main platform's governance engine; the one change already made is to the sales workspace (section 6).**

## Why

The Human reported that the governance review has been "largely incorrect with lots of false positives" and "incredibly slow". In the latest governance interview, records were flagged as duplicates of the DT603 sections they were written from: true, but useless. The Human asked for a major review with five questions:
1. Is comparing document with document the right approach?
2. Are we storing knowledge the right way?
3. What role should the ontology play?
4. Is the model right?
5. Should this be done differently, or through a frontier model's API?

Dan's note on an SME knowledge architecture was also considered. The Human asked that every claim in it be tested and benchmarked before anything is built from it (section 7).

## The answers in brief

1. **Document against document? No. It is the main cause of both problems.** Comparing each statement only with its nearest statements in other documents needs **2,528 judgements instead of about 25,000–45,000 model calls**. It sees **35 of 37** planted conflicts and duplicates, against 17, and puts forward only **6 of the 31** findings the Human dismissed.
2. **Storage? Not for governance.** Knowledge is kept as positional 1,200-character sections, with no statements, scope, effective dates or version history. The sales records are hash-bound to their evidence, but governance ignored that link.
3. **Ontology? Subject, scope and provenance, not the verdict.** Today no governance check reads it.
4. **The model? It is fine; the pipeline around it is not.** The same `qwen2.5:14b`, asked one plain question about the right pair:
   - scores **98%** on the benchmark, against 64% inside the engine;
   - finds **25 of 25** planted conflicts and **12 of 12** duplicates;
   - flags **0 of 31** real dismissed findings;
   - is about ten times faster per case.

   `qwen3.5:35b-a3b` is almost as accurate and faster. A 4B model is not good enough.
5. **Different approach, or a frontier model? Change the approach first; speed no longer needs a frontier model.** The proposed pipeline reviewed the whole real corpus in **1 h 6 m** against 35 h 23 m (section 3.3). All remaining errors are about scope and dates. Whether a frontier model or effective-date metadata fixes them is measurable, once the Human decides to run it (section 9).

## Since the Human's approval (25 September, evening)

Steps 1–3 of the plan are built: the statement store, the candidate index and the cached judge, with an optional reasoning second opinion. Details are in [statement-level-governance.md](statement-level-governance.md).

On the real corpus:

| | Full Governance Review | Statement-level review |
|---|---|---|
| Full review | 35 h 23 m | about 65 minutes (49½ minutes, plus 15 minutes of second opinion) |
| Unchanged corpus | — | 0.4 s |
| One sentence edited | all pairs of that document re-judged | 10 s |
| For a person to review | 32 findings, all dismissed or accepted | 2 conflicts and 38 duplicates |

- **The 2 conflicts** are both inside Pack 6 and Pack 13. The Pack 6 tax-rate conflict is plausibly real: one step says to update the tax definition, while the key rule says to close the old one and open a new one. The Pack 13 conflict is a false alarm.
- **The 38 duplicates** include 24 consolidation candidates within a process family.
- **On the benchmark,** the second opinion kept 25 of 25 true conflicts and dismissed both false ones, for 100%.

## 1. What the engine does today

The Full Governance Review compares **every pair of documents**:
- For each pair, it extracts statements with modal-verb patterns.
- It scores each statement against every statement in the other document by shared words, with an embedding rescue.
- It then asks a local model about each candidate, up to three per statement, in both directions, one call at a time behind a single lock.
- Deterministic "guards" can overrule the model afterwards.

The deep adjudicator is `qwen2.5:14b-instruct`; the screen is `deepseek-r1:8b`.

The Quick Scan compares every section with every other section by embedding. Anything at a cosine of 0.92 or above is a duplicate.

Neither stage consults the ontology, the process registry or any link between a document and its source.

## 2. What the record shows

| Evidence | Source |
|---|---|
| 21 documents, 210 pairs: **35 h 23 m**. 37 findings, consolidated to 32; a person dismissed or accepted all 32, and "no material internal contradiction was evidenced". | Tranche 2 closure note and review export (git history, `cd8e5a1`) |
| 9 documents, 36 pairs: **11 h 19 m**. 24 of 25 contradictions were guard promotions, not model decisions; 69–71 "duplicates" were template text. | `internal-governance-review-precision-hardening-2026-07-16.md`, pair cache |
| External review, 42 pairs: **19 h 19 m**, 1,052 findings. All 40 model-path contradictions were guard promotions. | Handover log, pair cache |
| The pair cache holds **88.6 hours** of recorded model time across 522 pair reviews. | `data/compliance_reasoning_pair_cache.json` |
| The corpus was **capped at 21 documents** because "workload grows quadratically"; tranches 3–5 were deferred. | Tranche 2 closure note |
| The last benchmark scorecard is from 5 July, and its 86 labels are all sentence against sentence and external against internal, with **no duplicate class**. Guards carried the older domains; the regexes written against holdout labels are still in the code. | Benchmark write-up, #1114–#1135 |

**The cause is the design, not the tuning.** The engine asks "do these two documents disagree?" about every pair of documents. Most pairs describe different processes: finding 11 of the real run compared a fuel service-item step (Pack 9) with a delisting step (Pack 13) because both said "retest if the future scope changes". Every such pair costs about 120–216 model calls and invites a "missing detail" or "needs human review" finding that a person then dismisses.

## 3. The benchmark

A new benchmark, `tests/evaluation/governance_pair_benchmark.json`, tests the task that matters: given two statements from different governed documents, say **conflict**, **duplicate** or **neither**.
- All labels were written before any model ran.
- The prompt was fixed in advance and not tuned afterwards.
- Families are split between dev (supplier, article, assortment) and holdout (pricing, promotions, ingredients, age restriction).

| Kind | Cases | Label |
|---|---|---|
| Real findings from the 35-hour run, all reviewed by a person | 31 (one "fixed" finding excluded) | neither |
| Planted conflicts: sequence, owner, requirement, negation, method, number and priority, written from the packs' own wording | 25 | conflict |
| Duplicates, 2 of them already in the corpus (article lists, Packs 6 and 7) | 12 | duplicate |
| Scoped variants: same subject, different phase, site, date or item type | 12 | neither |
| Complementary statements about the same area | 10 | neither |

Run it with `scripts/evaluate_governance_pairs.py`. Results are in `docs/benchmark/governance/`.

### 3.1 Finding the candidates: document pairs against a statement index

`scripts/governance_statement_index.py` treats every bullet, table row and sentence as a statement: 1,330 across the 21 documents. It embeds each statement once and takes each statement's nearest statements in other documents as its candidates.

| Design | Pairs to judge | Planted conflicts and duplicates it can see | Real dismissed findings it still puts forward |
|---|---|---|---|
| Current: every document pair, modal-verb statements | 210 document pairs, about 25,000–45,000 model calls | **17 of 37**: the extractor drops statements without "must/should" | 31 of 31 (this is where they came from) |
| Statement index, 3 nearest | 3,381 | 35 of 37 | 7 of 31 |
| Statement index, 3 nearest, cosine ≥ 0.70 | **2,528** | **35 of 37** | **6 of 31** |
| Statement index, 3 nearest, cosine ≥ 0.75 | 1,353 | 32 of 37 | 3 of 31 |

- Embedding all 1,330 statements took 20 seconds.
- The two misses are an inconsistency inside one document (Pack 10). Neither design compares a document with itself; the index can do so cheaply.
- **Caveat:** the planted conflicts are edits of real sentences, so they sit close to their originals. Conflicts between independently written documents may be worded further apart. This recall is a best case until independently written conflicts are added (section 8).

### 3.2 Judging a candidate: the current engine against single calls to local models

Every system sees the same 91 cases; 90 are scored (one "fixed" finding is excluded).
- **Current engine:** the Full Governance Review pair path at deep depth with its guards, with each case wrapped as two one-section documents.
- **Models:** each was given the pre-registered prompt once, with temperature 0, JSON output and no guards.

| System | Accuracy (dev / holdout) | Conflicts found | Conflict precision | Duplicates found | Real dismissed findings flagged again | Non-issues flagged | Median s per case |
|---|---|---|---|---|---|---|---|
| **Current engine** (qwen2.5:14b + deepseek-r1:8b + guards) | 64% (47% / 44%) | 6 / 25 | 86% | 0 / 12 | **17 / 31** | 19 / 53 | 18.3 |
| **qwen2.5:14b**, one question | **98%** (97% / 96%) | **25 / 25** | 93% | **12 / 12** | **0 / 31** | 2 / 53 | 1.9 |
| qwen3.5:35b-a3b, one question | 97% (100% / 96%) | 25 / 25 | 89% | 12 / 12 | 2 / 31 | 3 / 53 | 0.84 |
| qwen2.5:7b, one question | 96% (97% / 89%) | 25 / 25 | 86% | 12 / 12 | 0 / 31 | 4 / 53 | 0.74 |
| qwen3.5:4b, one question | 80% (94% / 85%) | 25 / 25 | 96% | 12 / 12 (precision 41%) | 12 / 31 | 18 / 53 | 1.13 |

- **Where the current engine loses cases:**
  - It keeps only statements with "must" or "should", so many planted cases never reach the model.
  - Its duplicate check needs 8 shared key terms per section, so it finds no statement-level duplicates.
  - It raises "missing detail" and "needs human review" on 17 of the 31 real findings even when they are shown in isolation.
- **Where the models go wrong:** every mistake by the 14B, 35B and 7B models was about scope or dates:
  - the national price list against a travel-site override;
  - day one against the end state;
  - "from 1 April 2027" against "until 31 March 2027";
  - an exception that goes through formal governance.
- **Fairness:** the new question asks only conflict, duplicate or neither. "Missing detail" between documents about different processes caused most of the noise, so it is deliberately not asked. Section 8 moves it to a completeness check in the ontology.
- **Timing:** another workload used the GPU during every run. The times compare the systems with each other; they are not absolute.
- **Reasoning models:** see section 3.3. A first run used too small an output limit and returned no answers; it was rerun on the scope-sensitive cases.

### 3.3 The whole pipeline on the real corpus

`scripts/governance_statement_index.py --trial qwen2.5:14b-instruct` runs the proposed pipeline over the real 21-document corpus, with no planted cases:
- index the 1,330 statements;
- take each statement's 3 nearest statements in other documents, keeping pairs at cosine 0.70 or above;
- judge each of the resulting 2,345 candidates once, four requests at a time.

This is the corpus in which a person found no material contradiction after the 35-hour review. Every conflict raised is therefore either a miss by that review or a false alarm, and each one was checked.

| | Full Governance Review, 18 July | Proposed pipeline, 25 September |
|---|---|---|
| Time for the whole corpus | 35 h 23 m | **1 h 6 m** (index 20 s; judging 3,938 s, GPU shared with another workload) |
| Conflicts raised | 0 contradictions, and 32 other findings (all dismissed or accepted by a person) | 12 before filtering; **4** after |
| Duplicates raised | none reported | 232 before filtering; **37** after |

**The 12 conflicts are all false alarms.** Checked one by one:
- **Different forms in different processes** (the supplier setup form against the article new-line form): three cases.
- **Manual and automatic lists**, which both exist: two cases.
- **Consistent statements read as opposed:** four cases.
- **Roles described in different processes:** two cases.
- **Day one against the general design:** one case.

Six of the 12 involve a pack's "Realistic Q&A pairs" section, which restates the pack.

**The 232 duplicates were mostly template text.** 145 are word-for-word repeats of just 11 lines: a table header, "Content has been anonymised for internal learning use" (16 packs), the "Requires validation" note, and the "Source basis" lines. Most of the rest pair a Q&A answer with the rule it restates.

**Two generic filters** were therefore added after this trial, and are reported as such:
1. Statements in derived sections (a pack's Q&A pairs and its preamble) are skipped.
2. A statement repeated word for word in three or more documents is template text.

Both mirror rules the platform already has: the Quick Scan's structural suppression, and the review payload's exclusion of derived sections. Neither removes any planted benchmark case (`--filter`, `pipeline-trial-qwen2.5_14b-instruct-filtered.json`). They still need confirming on a corpus not yet seen.

**After the filters:**
- **4 conflicts,** all false. They are subject and scope confusions, the same kind of error as in section 3.2.
- **37 duplicates:**
  - 24 sit in the same process family. These are consolidation candidates: the same guidance kept twice, for example the article-list rules in Packs 6 and 7, the pack-size rule in Packs 5 and 6, and price-coverage monitoring in Packs 14 and 16.
  - 13 cross families, and 8 of those are parallel role or step rows ("Master data operator loads the file into staging" in the article, price and promotion packs).

  A subject key from the ontology would separate these two groups (plan step 4).

**Cost of a frontier model for this step:**
- A judgement averages 331 input tokens and 43 output tokens, which is about 0.8 million input and 0.1 million output tokens per full review of this corpus.
- At typical frontier list prices this is in the order of a few dollars per full review, and cents per changed document (to be confirmed against the chosen provider's prices).
- Speed no longer requires one: a changed document adds about 200 candidates, a few minutes locally.

**Reasoning models:** `qwen3.5:35b-a3b` with thinking was run on the 22 scope-sensitive cases (scoped and complementary):
- It answered **20 correctly and none wrongly**. That includes the national price list against a travel-site override, and "from 1 April 2027" against "until 31 March 2027", which the faster models got wrong.
- Two cases ran out of output (4,096 tokens) before answering.
- It took a median 37 s per case, against 0.84 s without thinking. That is about 20 hours for 2,345 candidates, so it cannot be the bulk judge.

It is a candidate for a **second opinion on the few conflicts the fast judge raises**: 12 in this trial, about 10 minutes. Whether it dismisses those false alarms while still confirming true conflicts is the next test.

### 3.4 A specialist contradiction model (decision 3, approved 25 September)

`MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` (MIT licence, 363 MB) is a natural-language-inference model that scores contradiction and entailment between two sentences. It runs in the project's own environment from the optional `requirements-nli.txt`, on the Mac's GPU.

The decision rule was fixed before the first run (`scripts/evaluate_governance_pairs.py nli`):
- **conflict** if contradiction is at least 0.5 in either direction;
- **duplicate** if entailment is at least 0.5 in both directions;
- **neither** otherwise.

| System | Accuracy | Conflicts found | Conflict precision | Duplicates (P / R) | Real dismissed findings flagged again | Median s per case |
|---|---|---|---|---|---|---|
| NLI model | 77% | 23 / 25 | 57% | 100% / 83% | 9 / 31 | **0.02** |
| qwen2.5:14b, one question | 98% | 25 / 25 | 93% | 100% / 100% | 0 / 31 | 1.93 |

On its own, the NLI model is far faster but too noisy.

**As a first pass in front of the 14B judge** (exploratory; this rule was not fixed in advance):
- It scored all 2,345 real-corpus candidates in **19 s**.
- With both thresholds at 0.5, only 775 candidates (33%) would reach the 14B judge. That would cut judging from 66 minutes to about 22.
- It does not remove false alarms. All 4 filtered false conflicts pass the NLI model too.
- It loses duplicates: 37 fall to 9, and on the benchmark one conflict and two duplicates are missed.

**Verdict:** a speed option for very large corpora, not a precision fix. It is not the default. The precision idea to test next remains a reasoning model's second opinion on the few conflicts raised.

### 3.5 Frontier models (decision 2, approved 26 September)

Claude Opus 5.5, Sonnet 5 and Haiku 4.5 ran through Anthropic's API (`scripts/evaluate_governance_pairs.py frontier`), with the same pre-registered prompt.

**What left the machine** (recorded in each result file's `audit`):
- The 91 benchmark pairs and the prompt, about 150 KB per model, sent to `api.anthropic.com` only.
- The key was read from `.env` and travelled only in its header; it appeared in no request body.
- A first attempt was rejected before any model ran: Sonnet 5 no longer accepts a temperature setting, and Opus 5.5 does not allow a forced tool call.
- The scored runs therefore use one method for all three models: the prompt's own "Return JSON" instruction, with the answer parsed from the reply.

| System | Accuracy (dev / holdout planted) | Conflicts found | Conflict precision | Duplicates (P / R) | Real dismissed findings re-flagged | Median s per case | Full review of the real corpus (1,987 candidates), list price |
|---|---|---|---|---|---|---|---|
| **Claude Opus 5.5** | **100%** (32/32 · 27/27) | 25 / 25 | 100% | 100% / 100% | 0 / 31 | 1.96 | $8.02 (batch $4.01) |
| Claude Sonnet 5 | 99% (31/32 · 27/27) | 25 / 25 | 100% | 92% / 100% | 0 / 31 | 1.68 | $3.20 (batch $1.60) |
| Claude Haiku 4.5 | 99% (32/32 · 27/27) | 25 / 25 | 96% | 100% / 100% | 1 / 31 | 1.25 | $1.37 (batch $0.69) |
| qwen2.5:14b, local | 98% | 25 / 25 | 93% | 100% / 100% | 0 / 31 | 1.93 | $0; about 50 minutes on the Mac |
| qwen2.5:14b + local reasoning second opinion | 100% | 25 / 25 | 100% | 100% / 100% | 0 / 31 | 2.20 | $0; about 65 minutes |

Prices are the list prices on 26 September 2026: Opus 5.5 $4 / $20, Sonnet 5 $2 / $10 and Haiku 4.5 $1 / $5 per million input / output tokens, with Batch at half price. They are applied to the tokens each model used per case.

This test cost under $1 in total.

**What this shows:**
- **The frontier models make the scope-and-date calls the fast local models miss.** All three were right on the travel-site price-list override and the effective-date ranges.
- **Opus 5.5 is the only single model with no mistake.** Sonnet 5 called one complementary pair a duplicate. Haiku 4.5 re-flagged one dismissed finding.
- **The local pipeline with its reasoning second opinion also reaches 100%**, at no cost and with no data leaving the machine.
- **A frontier model as the second opinion only** is the lowest-exposure frontier option, computed from these runs with no extra calls:
  - The local 14B judge flags conflicts; a Claude model checks only those.
  - This reaches **100% with any of the three Claude models**.
  - It sends only the conflicts raised, 9 pairs for a full review of the real corpus.
- **Speed does not require a frontier model.** A Claude judge with concurrent requests could review the whole corpus in minutes rather than the local 50, if data policy allows the statements to leave the machine.
- **This benchmark is now saturated**: several setups reach 100%. Telling them apart needs the harder benchmark v2 with independently written conflicts (GOV S4, decision 4).

**Not sent:** statements from the real corpus. Using a frontier model on the real corpus, even for the 9 conflicts, is a separate decision.

## 4. Are we storing knowledge the right way?

Not for governance.

**Main platform:**
- Knowledge is stored as whole documents cut into sections of up to 1,200 characters. A section's ID is its position, so any edit that shifts the order changes the IDs.
- There is no statement-level store.
- There is no scope (process, site, phase), effective date, `supersedes` or review date.
- An edit overwrites the previous version.
- Embeddings are keyed by text alone, not by text and model.
- A resolved issue is keyed by its free-text detail, so rewording it makes it reappear.

**Sales workspace:** it already does better. Records are hash-bound to the evidence they cite, carry a status, and keep earlier versions. Governance ignored all of that; see section 6.

**What a governance-ready store needs:**
- statements with a stable ID (hash of normalised text + source + section);
- their span and section in the source;
- the document version;
- an embedding keyed by model;
- scope and effective dates where known;
- a link to the evidence they were derived from.

## 5. What role should the ontology play?

Today it plays none in governance: no check reads the ontology, the process registry or the schema.

The benchmark suggests it should provide what document pairing cannot:
- **the subject:** which process, role, system or control a statement is about;
- **the scope:** phase, site, item type or date;
- **provenance:** which evidence a record came from.

It should not replace the judgement. Most planted conflicts (sequence, method, negation) need reading, not a lookup; only the numeric and owner changes are open to a typed comparison. The ontology narrows and labels the candidates; a model or a person decides.

## 6. Already changed: governance reviews knowledge, not the evidence behind it

The Human preferred that records be written from DT603 but no longer compared with it. That was measured first, on a copy of the sales workspace:

| Sales governance agenda | Items |
|---|---|
| Before | 22 |
| Duplicates of a record against the very section it cites | 5 of 5 |
| Issues only inside the cited DT603 sections or repository files (acronyms such as "BY", "CC" and "NC" from a licence line, long sentences in the paper, a README link) | 10 |
| Issues in the records Tibi speaks from | 7 |
| **After the change** | **7**, all about the records |

**The change** (`services/opsatlas_sales/governance.py`, `GovernedSources`):
- The scan no longer sees sources that a record cites as evidence, or a record's earlier versions.
- Records are compared with records.
- Any document no record cites stays governed.
- Definitions and passages are still looked up in every source, so an acronym defined in the paper can still be explained.

It is covered by a test.

## 7. Dan's note: each claim as a hypothesis

The note proposes a ChatGPT-based SME architecture. Only the parts that bear on governance were tested; none is adopted because the note says so.

| Claim in the note | How it was tested | Result | Status |
|---|---|---|---|
| Keep raw evidence and curated knowledge as two separate assets | The sales agenda, by source type (section 6) | 5 of 5 duplicates and 10 of 22 items were evidence. The agenda went from 22 items to 7. | **Supported; applied** to the sales workspace |
| Promote durable statements into their own records | Statement index against document pairs (section 3.1) | 35 of 37 planted issues seen, against 17. 6 of 31 false alarms put forward, against 31. 2,528 judgements, against 25,000 or more. | **Supported**, with the edited-sentence caveat |
| Lifecycle metadata (effective dates, supersedes, versions, review dates) | Cases whose scope or dates are written in the text | Every remaining model error was a scope or date mistake. Metadata would settle these deterministically, but it is not built yet. | **Promising; test next** (plan step 4) |
| Rank sources by authority, prefer newer when authority is equal, never reconcile silently, cite both | Not testable: every learning pack has the same authority | Needs labelled cases of mixed authority, for example an SME interview against a pack. "Cite both" already happens: Tibi's governance interview reads both passages. | **Untested** |
| Keep originals as provenance, with hash, version and supersedes | Design check | The sales workspace does this. The main platform does not: an edit overwrites the document, and no history is kept. | **Gap confirmed** |
| "Instructions are not a security boundary" | Applies to a frontier judge | The judge needs only two statements per call. What leaves the machine must be audited before any use. | **Test if a frontier model is approved** |
| ChatGPT workspace agents, MCP connectors, internal and external agents | Not tested | These concern how answers are served, not governance. | **Out of scope** |

## 8. Recommendation and plan

The plan is governance at the statement level. Each step is checked against this benchmark, and the whole pipeline against the real corpus, before the old path is retired.

1. **Statement store.** Every bullet, table row and sentence becomes a statement. It carries a stable ID, its place in the source, the document version, and an embedding keyed by model. The store is built when a document is loaded, so a new or changed document adds only its own statements.
2. **Candidate index.** Each statement is compared with its nearest statements in other documents, and in other sections of the same document; the latter closes the Pack 10 gap. Evidence that a record cites stays out, as it already does on the sales workspace.
3. **One judgement per candidate.** Candidates get the benchmark's question, sent to `qwen2.5:14b` by default, with no domain-specific guards. Each result is cached per statement pair, so an edit re-checks only what changed. A reasoning model gives a second opinion on each conflict raised, if the test in section 3.3 shows that it removes false alarms without losing true conflicts.
4. **Scope and dates.** Sources and statements record effective dates, phase, site or network, and what they supersede, and the engine uses these directly. The scope cases are then re-scored.
5. **Findings and decisions keyed by statements.** Both statements are quoted, and a decision still applies after the text is reworded.
6. **Benchmark v2.** It adds conflicts written independently by the Human and Dan, cases inside one document, and a larger holdout. It also compares a frontier model and a specialist model, if approved.
7. **Retire the document-pair Full Governance Review** once steps 1–5 pass. The Quick Scan hygiene checks stay. "Missing detail" becomes an ontology completeness check, for example a process step without an owner.

## 9. Decisions for the Human

1. **The direction.** *Approved on 25 September.* The epic, feature and stories are in ADO, and steps 1–3 have started.
2. **A frontier model on the same benchmark.** *Approved and done on 26 September* (section 3.5). Opus 5.5 scored 100%, Sonnet 5 and Haiku 4.5 99%. A full review of the real corpus would cost $1.37–$8.02 at list price. The local pipeline with its second opinion also scores 100%, at no cost.
3. **A specialist contradiction model.** *Approved and done on 25 September* (section 3.4): fast, but not accurate enough to replace the 14B judge.
4. **Independently written conflicts.** The Human and Dan would each write about ten conflicting statement pairs about the packs, without seeing the benchmark. This tests recall on real wording rather than on edits.
