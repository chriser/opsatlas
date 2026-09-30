# Response to the external architecture review of 27 September 2026

An external reviewer read `main` at 6d2195d (20 September 2026) and produced an architecture review with ten problems,
a fix list, an attribution analysis, and design advice on scaling and pilot costs. This is the project's response,
written on 30 September against the code that is live today. The review itself is not kept in the repository.

Rule applied throughout: every claim was checked against the code, and every proposed change is either small enough
to just do, or a hypothesis to measure with the existing benchmarks before it is adopted.

## What the reviewer could not see

- `main` has not moved since 6d2195d. The live deployment runs `claude/tiberius-speed-safety` (pull request 2, open),
  121 commits ahead. That branch holds the Tibi engines 1.0–1.7.1, knowledge spaces, process interviews and the
  process map notation. None of it is in the review.
- The live product is OpsAtlas Sales (`services/opsatlas_sales`, port 8780). It is built on the core application the
  reviewer read, with the same file stores under `.runtime/opsatlas-sales/core`, so most core findings carry over.
  But it also changes some of what the review describes:
  - the compliance-reasoning sidecar is switched off (`KP_COMPLIANCE_REASONING_URL=''`), and governance runs through
    the statement-level engine (GOV E1), which has one worker thread and a queued follow-up review;
  - the operator password is the workspace's own random key (`local-access.key`), not the default;
  - the question rewrite is off (`KP_QUERY_REWRITE=0`), and answers use `qwen3.5:4b`;
  - the Tibi voice service needs its own token, issued only behind the core sign-in, and the process diagram service
    listens on 127.0.0.1 only.
- The counts have moved on: 143 core modules (26,205 lines), 142 endpoints in 17 route files, 15 screens, 133 Python
  test files and 8 browser test files, 1,189 passing tests at the live commit.

## The ten problems, checked

| # | Finding | Checked today | Live impact | Already planned | Verdict |
|---|---|---|---|---|---|
| 1 | Files rewritten in place, no temp-and-rename; locks per process; some readers unlocked | **True.** No atomic-write helper in the core; 37 modules rewrite JSON whole. SQLite only for the ontology, content and spaces. One `os.replace` exists (the conversation log) | One process, one operator: the risk is a crash mid-write leaving a half-written store | KS F5 (backup and tested restore) | **Do now, small.** One atomic-write helper (temp file, `os.replace`) used by every JSON store. Moving stores into SQLite: later |
| 2 | Facts map cleared then refilled in separate steps; not rebuilt on delete; OAG answers always "grounded", never fall back | **True on all three.** `rebuild_ontology` calls `store.clear()` (its own transaction) then refills; `remove_source` records an event and returns; `_answer_from_ontology` skips the validator, sets `confidence="grounded"`, and a refusal is returned rather than falling through to retrieval | An answer asked mid-rebuild can see an empty map; a deleted source's facts stay until the next rebuild | None | **Two bug fixes now** (rebuild on delete; rebuild into a fresh table or one transaction). **Two hypotheses to benchmark** (run the grounding check on OAG answers; fall back to retrieval on an OAG refusal) with the existing RAG-vs-OAG harness, since OAG-first was chosen by that benchmark |
| 3 | Rules tuned to one document set: router phrases, VAT and packaging rules, "Anonymised Learning Pack" headings, guardrail keywords | **True.** 280 quoted literals in the router; VAT and packaging regexes in the compliance agent; the parser matches "Anonymised Learning Pack N"; the off-topic guard blocks "forecast" (with weather) and "medical" | The compliance rules are off in Sales. The router and guardrails apply to every space, including organisations' data | Knowledge spaces partition data by organisation (KS F2–F3), not the rules | **Benchmark first.** Move the router phrases and guard lists to per-space configuration, then re-run the RAG/OAG benchmark on the Sales product guide as the second document set. The "forecast" guard is a one-line fix worth making now |
| 4 | Thin security: default password, tokens never expire, no attempt limit, token in browser storage, helper services open, approval flag never enforced, direct action endpoint | **Mostly true.** Default `knowledge-demo` in the core (the Sales app overrides it with a random key); tokens live in memory with no expiry; no attempt limit; `localStorage`; `requires_human_approval` is only printed into the agent's prompt; `POST /actions/{api_name}` executes for any signed-in operator. The Tibi service has a token; the diagram service has none but is local-only | Acceptable for one operator on one machine, which is the current scope | KS F4 (accounts, roles, server-side checks, access audit), KS F5 (hardening before real data), SME F30 (participant identity) | **Light now, the rest as planned.** Now: no default password (require or generate one), token expiry with an attempt limit, enforce the approval flag in the actions engine and keep the direct endpoint for non-approval actions. Later, in KS F4: accounts and roles; single sign-on only if a pilot needs it |
| 5 | Heavy work inside requests: four model calls, 120 s timeouts, all-pairs governance, a thread per review, no retries, no logging | **True for the core.** `review_jobs` starts a daemon thread per review with no cap; `intelligence.py` compares every section with every other; the provider has no retries; the retrieval fallback to lexical search is a silent `except`. **Not true for the live governance path**, which has one worker and a queue | The core review path still exists behind the Sales app; the silent fallbacks hide degraded answers | TIBI E2 gave the Tibi side an activity log; the core's fallbacks are not in it | **Do now, small:** log the fallbacks (hybrid→lexical, rerank failed, OAG refused) to the activity log; cap the core review threads. **Later:** a job queue and workers, when there is more than one user |
| 6 | Search will not scale: no vector store, keyword index rebuilt per search | **True as described, and measured** (below). BM25 is built inside `search()`; the embeddings cache re-parses its JSON file on every call; the cosine sums are pure Python; the cache is never pruned (177 of the 196 cached vectors are stale) | The live core has 19 sections, 10,561 characters: under the 24,000-character limit, so every answer takes the whole approved text as evidence and no search runs at all | None | **Not a vector database: an index in memory, when the corpus grows.** Keep a normalised numpy matrix and the BM25 index in memory, rebuilt when a source's version or section count changes; prune the cache. Same scores, no new dependency. A vector store only when several processes must share the index or the corpus passes tens of thousands of sections |
| 7 | Hot spots: huge files, rules in route code, ~15 store classes, no page addresses, no frontend tests, no timeouts, leaking polls | **Partly out of date.** `agent.py` 3,203 lines (off in Sales), `api.ts` 3,128, `AnalyticsPage` 2,474; `GovernancePage` is now 690 (split since). Views have hash addresses and deep links (`#tibi`, `#process-review:id`), but `replaceState` means no back button. 65 browser tests exist, all for the Tibi voice client; none for the React pages. Three requests use `AbortController`. Page timers are one-shot; the one interval is cleaned up | Maintainability, not correctness | None | **Opportunistic.** Split `api.ts` by area and `AnalyticsPage` when next touched; `pushState` for the back button is small. No big refactor |
| 8 | Pipeline: GitHub mirror runs even when tests fail and force-pushes; branch names shortened; no Python lock file; Anam SDK from esm.sh unpinned; no coverage or dependency scan | **True on every point.** `condition: always()`, `--force-with-lease`, `$(Build.SourceBranchName)` (last segment only); `requirements.txt` is 8 minimum versions (the frontend does have `package-lock.json`); `https://esm.sh/@anam-ai/js-sdk` has no version | Broken code can reach the GitHub mirror; a dependency update can change behaviour silently | None | **Do now, small.** Mirror only on success with the full branch name; a pinned `requirements.lock`; a pinned Anam SDK version; a `pip-audit` step. Coverage: optional |
| 9 | Small bugs: "false" parsed as true; process facts from raw bytes (PDF and Word yield nothing); simulated questions in real usage statistics | **True on all three.** `bool(payload.get("same_obligation"))`; `read_content(...).decode("utf-8", "replace")` in the registry and the sync (the ingestion service already has extractors to reuse); the simulator calls the real `AnswerService.answer`, which logs to the usage log and audit trace with no simulated flag | The first is off in Sales; the other two affect the process registry and the analytics | None | **Do now, small** |
| 10 | Documentation drift: "resumable" reviews, "Anam is the only managed runtime component", avatar page and `/api/ask` | **True for `ARCHITECTURE_STATUS.md`** (dated 19 September, 121 commits stale; it also predates knowledge spaces, Tibi and process interviews). The avatar page calls `/api/avatar/answer`; the `/api/ask` wording was not found in the page | Readers and agents get the wrong picture | None | **Do now, small:** refresh `ARCHITECTURE_STATUS.md` |

## Measured: how search scales today

The exact steps of `search()` were timed on the live core (read-only) and on synthetic corpora of 768-dimension
vectors and 120-word sections, against the cheap alternative of a normalised numpy matrix held in memory
(`numpy` is already a dependency).

| Sections | `embeddings.json` | Parse the file | Build BM25 | Cosine, pure Python | Total per search | Python lists in memory | numpy dot product |
|---|---|---|---|---|---|---|---|
| 19 (live, 196 cached vectors) | 3 MB | 23 ms | 0.4 ms | 10 ms | ~35 ms | small | — |
| 1,000 | 14 MB | 111 ms | 21 ms | 49 ms | ~0.2 s | 25 MB | 0.2 ms |
| 5,000 | 74 MB | 558 ms | 120 ms | 240 ms | ~0.9 s | 123 MB | 0.9 ms |
| 20,000 | ~290 MB (estimated) | ~2.2 s (extrapolated) | 596 ms | 961 ms | ~4 s | 492 MB | 0.9 ms |

The query's own embedding, one Ollama call, took 13 ms; the answer generation takes seconds. So:
- Today the reviewer is right that it is fine, and more than that: the live corpus is small enough that the answer
  path does not search at all.
- Today's code does slow down with thousands of sections, as the review says: about a second per search at 5,000,
  several at 20,000, and hundreds of megabytes parsed per search. The cache file is also rewritten whole whenever a
  new section is embedded.
- The remedy at that scale is an index in memory, not a database: the semantic scoring is under a millisecond at
  20,000 sections once the vectors are a matrix, and the BM25 index is built once per corpus change instead of once
  per search. Knowledge spaces already keep each organisation's corpus in its own core, so each index stays small.
- A vector store (locally `sqlite-vec`, which fits the existing SQLite use; `pgvector` only with a PostgreSQL move)
  becomes worth it when more than one process must share the index, or a corpus passes tens of thousands of
  sections, or filtering by metadata at scale is needed. None of those is in view.

Any index change must return the same results as today's code on the RAG/OAG benchmark before it replaces it.

## Attribution (the review's section 10)

- The `main` counts match git exactly: 62 commits with "Claude Opus 4.8", 17 with a Codex line, 1 with "Claude Opus 5"
  (ebbe010). The 19 commits of 9–11 August carry no line, as the review says.
- The open question, "the model behind the newest Claude branch": Claude Opus 5.5, named on 95 of the branch's 121
  commits. The other 26 are 25 one-line Codex commits of 20–24 September that carry no trailer at all (so on that
  branch the review's rule "all commits carry lines" does not hold for Codex) and one Antigravity design commit
  (52bc6c5, 26 September). From 30 September the Claude commits are attributed to Claude Fable 5.1.
- "SME Interviewer … not connected to the core yet" is no longer true: Tibi runs as a Sales service behind the core's
  gateway, and process interviews save into organisation spaces.

## Scaling and costs (the review's sections 12–13)

Design advice, not findings, and not verified here: the prices and capacity figures are the reviewer's. As a map of
what a multi-user deployment would need, it is sensible and it matches the project's own production note
(`ARCHITECTURE_STATUS.md`, "Production considerations") and the planned KS F4–F5 and SME E3 work. Two points:
- The cloud and pay-per-use options conflict with the local-first rule; the onsite figures are the relevant ones if
  the rule stands. That is a decision for when a pilot is on the table.
- "Make each question cheaper" is four testable hypotheses: skipping the rewrite (already off in Sales), a small
  reranker instead of the model, the grounding check after the answer is shown, and a cached answer. The latency
  replay and the RAG/OAG benchmark measure them; none should be adopted on the estimate.

## What is reasonable to plan

Three tiers, sized against the project's habit of small, gated deliveries.

**Tier 1 — small fixes, agreed by the Human on 30 September** (ADO epic ARCH E1; each item is hours, not days)
1. Atomic writes for the JSON stores.
2. Facts map: rebuild on source deletion; rebuild into fresh tables and swap.
3. Pipeline: mirror only on success, full branch name, pinned Python dependencies, pinned Anam SDK, `pip-audit`.
4. The three small bugs.
5. Fallbacks logged to the activity log; a cap on core review threads.
6. The "forecast" guard, and a refreshed `ARCHITECTURE_STATUS.md`.
7. An in-memory search index (numpy matrix and BM25 built once per corpus change) and a pruned embeddings cache,
   proven identical to today's results on the RAG/OAG benchmark. Not urgent while the corpus is small, but small to do.

**Identity and access — scoped separately.** The Human decided on 30 September not to patch security piecemeal
(default password, token expiry, attempt limits, the approval flag). A proper identity and access management scope
is being prepared by Codex; the review's security findings are input to it, together with KS F4 (accounts and
roles) and KS F5 (hardening before real data). Until then the deployment stays as it is: one operator, one machine,
a random per-workspace password.

**Tier 2 — hypotheses, measured before adoption** (each needs a pre-registered pass mark and a holdout)
1. Grounding check on OAG answers; fallback to retrieval on an OAG refusal (RAG/OAG benchmark).
2. Router phrases and guard lists as per-space configuration, proven on the Sales product guide as a second corpus.
3. The cheaper question path (reranker, deferred grounding check, answer cache), on the latency replay.

**Tier 3 — later, with a pilot decision** (already largely in ADO)
- Accounts, roles and access (KS F4); hardening, backup and restore, proven deletion (KS F5); participant identity and
  operational assurance (SME F30–F31).
- A job queue with workers; a vector store (only on the conditions measured above); page history; the big-file splits.
- Single sign-on, per-document permissions, hosting and cost decisions.

Nothing in the review needs a rewrite, and nothing in tier 1 changes Tibi's engine, so none of it needs the latency
gate. Tier 1 is built on the branch `claude/architecture-review`, from the live commit, and goes live by the usual
fast-forward and restart.

## As built (30 September 2026)

Tier 1 items 1–6 are in: atomic writes (`assistant.storage`, fed9ef5), the transactional facts-map rebuild also on
deletion and transfer (af01018), the pipeline changes with `requirements.lock`, `pip-audit` and the pinned, bundled
Anam SDK, the three bugs (5b56699), fallbacks recorded with the answer and one internal review at a time (8c6abd0),
the forecast guard and this file's companion `ARCHITECTURE_STATUS.md` refreshed (with the IAM guide, 104b8e4).
Item 7, the in-memory search index, is still open (ADO ARCH F7 #1941). The light-security item was not done as
such: identity and access were built from the separate specification instead (`docs/iam/README.md`, IAM E1 #1951),
which covers the default password, token expiry and approval-flag points of problem 4 in full.
