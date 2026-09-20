# Low-latency local conversation architecture — v6

20 September 2026 · #1524 · Release candidate for another synthetic Human trial; held-out G2 acceptance remains open.

The v5 trial improved question relevance, but the Human correctly identified that canned thinking phrases were masking a slow architecture. The v5 critical path made three sequential general-model calls: coverage extraction, question writing and semantic review. Warm seeded turns took 7.693–8.912 seconds. Adding more evidence to that sequence would increase delay and would make the spoken filler feel more repetitive.

## Decision

The v6 critical path is now:

1. Read the current immutable ledger prefix and typed question state from SQLite.
2. Apply narrow deterministic facts for explicitly completed outcomes, actors, warnings, check results, requested inputs and stated “because” reasons.
3. Ask resident `qwen3.5:35b-a3b` for one grounded question with exact source IDs.
4. Run deterministic structure, correction, provenance and premise checks.
5. Use resident `qwen2.5:7b-instruct` for the focused independent question review. Repair once only after a real rejection.
6. Persist and speak only the checked question.

Both Ollama calls use the same 8,192-token context and a 30-minute keep-alive. Earlier testing accidentally changed context size between calls and forced Ollama to reload the 23 GB writer; the fixed runtime avoids that runner churn. Explicit unknowns and one checked hold-resolution form remain deterministic, so they do not wait for a fallible general-model review.

Coverage no longer requires a general extraction call before every question. A confirmed response inherits the detail identity of the question it answered, while the first free account uses only narrow explicit recognisers. The writer still receives the bounded confirmed account and prior questions, so it can follow the narrative. This is a deliberate latency/recall trade-off: the sidebar can under-report a detail from the initial free narrative, but the live question path does not wait for a second broad semantic analysis.

## Measured result

The final warm seeded run produced four reviewed questions in 1.622–1.738 seconds, plus the explicit-unknown guide without inference. The explicit activation remained understood, the held supplier question explored resolution, the released exception asked about additional checks and the hypothetical remained conditional. All four ordinary turns passed on their first attempt. See [architecture measurements](evidence/2026-09-20/conversation-v6-architecture.json), [verification](evidence/2026-09-20/conversation-v6-verification.json) and the [isolated browser journey](evidence/2026-09-20/conversation-v6-browser.json).

The interface now starts with a quiet visual status. After 0.9 seconds it may show one brief phrase; Voice B speaks a prepared cue only if planning is still running after 2.2 seconds. A normal measured turn therefore moves directly into the next question. The cue remains cancellable and never becomes evidence or part of the transcript.

## Database and retrieval choice

A “neural database” is not a single production storage class that would solve the present delay. The published NeuralDB work describes database support for natural-language inference over text; it does not replace the need for an authoritative, revisioned ledger or make local generation free. Vector similarity also cannot decide whether an approval happened or whether a claim is valid.

The current Atlas retrieval profile covered 246 sections: the first hybrid query took 0.666 seconds while the embedding model warmed, and subsequent queries took 0.098 and 0.110 seconds. The current eight-second problem was therefore generation orchestration, not retrieval. The existing Python BM25 rebuild and full vector scan will not scale indefinitely, so v6 defines this storage split:

- SQLite remains authoritative for interview events, corrections, question identity, review state and typed facts.
- Atlas ontology/OAG lookup remains first choice for structured organisational facts.
- A rebuildable hybrid lexical/vector index becomes a derived evidence accelerator when the real evidence adapter is introduced. It can be queried in parallel with direct state lookup.
- LanceDB is the first embedded spike candidate because it supports local vector, full-text and hybrid search without a new service. Qdrant remains the server option for later multi-user scale. Neither is promoted into this release.

This follows the capabilities documented by [SQLite FTS5](https://www.sqlite.org/fts5.html), [LanceDB hybrid search](https://docs.lancedb.com/search/hybrid-search), [Qdrant deployment guidance](https://qdrant.tech/documentation/guides/) and the [NeuralDB research paper](https://www.vldb.org/pvldb/vol14/p1033-thorne.pdf). Ollama’s [chat API](https://docs.ollama.com/api/chat), [structured outputs](https://docs.ollama.com/capabilities/structured-outputs) and [model residency controls](https://docs.ollama.com/faq) support the local runtime choices.

## Remaining gates

This is a synthetic release candidate, not evidence that the interviewer now sounds fully human. The next acceptance work is a longer multi-turn Human conversation and p50/p95 measurement with speech, retrieval and both dialogue models resident concurrently. The derived hybrid index should be benchmarked with a realistically enlarged, approved corpus before selecting LanceDB or Qdrant. Real Atlas evidence, participant identity/RBAC, owner adjudication and publication remain disabled.
