# Evaluation 5: chat quirks and what governance reviews

**25 September 2026 · Built by Claude · Story #1743 (S160) under F17 and Story #1742 (S161) under F19 · Status: delivered for the Human's evaluation on branch `claude/tiberius-speed-safety`; nothing is merged to `main` until the Human accepts it.**

## Why

The Human's fifth session was the first on the native Talk with Tibi page. The chat went well, with some quirks, and the interview worked better than before. Then the governance interview read out issues that were true but useless: records flagged as duplicates of the DT603 sections they were written from.

## Chat quirks (S160)

| What happened | Cause | Now |
|---|---|---|
| "How's your weekend going?" on a Friday | The conversation model was never told the day or time. | The model is given the local day, date and part of the day, for example "Friday afternoon, 25 September 2026". |
| "DT603 is a reference to a specific development or issue in the project" | "What's dt603?" was treated as a general definition, and the model guessed. | A question about a code or acronym that the enabled records use goes to the evidence layer. That layer says what the records say ("added after the DT603 submission") and what they do not establish. The follow-up "I wonder what that is" stays with the same records. |
| "What are you most looking forward to today?", asked a second time | The model repeated a question it had already asked. | A question Tibi has already asked in the conversation is not asked again. It is still spoken if it would otherwise leave Tibi with nothing to say. |
| "I don't think that question is relevant to what I said" was not taken as a correction | Repairs covered only "you're not answering". | Saying Tibi's last question or answer was irrelevant is a repair. Calling a topic irrelevant ("security isn't relevant for us yet") is not. |
| "The records don't mention the price of milk" | "Price" counted as OpsAtlas pricing. | Everyday prices are small talk. The price of OpsAtlas, a licence or a pilot remains a product question. |
| "Tibi's just happy to chat" | The conversation guidance is written about "Tibi", and the model copied the third person. | The prompt says to speak in the first person, and "Tibi's"/"Tibi is" as a subject is spoken as "I'm". |

The approved conversation-style records were not changed. They are governed data, and each is bound to its hash.

## What governance reviews (S161)

The Human preferred that records be produced from DT603 but no longer compared with it. This was measured on a copy of the live workspace before changing anything:

| Sales governance agenda | Items |
|---|---|
| Before | 22 |
| Duplicates of a record against the very DT603 section it cites | 5 of 5 |
| Issues only inside cited evidence ("BY", "CC" and "NC" from a licence line, long sentences in the paper, a README link) | 10 |
| After the change | **7**, all about the records Tibi speaks from |

The change is `GovernedSources` in `services/opsatlas_sales/governance.py`:
- The scan no longer sees the sources a record cites as evidence, or a record's earlier versions.
- Records are compared with records, and any document no record cites is still governed.
- Definitions and passages are still looked up in every source.

The wider governance engine review, and the benchmark behind it, is `docs/data-and-governance/governance-reasoning-engine-review-2026-09-25.md`.

## Checked

- **Tests:** 983 Python tests pass on 3.11 and 3.12, with new tests for each chat quirk and each phrase rule, including the cases that must not trigger. A further test checks that governance skips cited evidence but keeps other sources.
- **Latency:** a before/after replay (40 turns each, run back to back) is within budget: p50 1,904 ms against 1,872 ms before, and p95 2,134 ms against 2,179 ms. The budget is 1,950 ms / 3,100 ms. The chat model's first token moved from 238 to 274 ms. Another workload used the GPU throughout both runs. An earlier single run at 2.7 s had run under heavier contention: the model stage was unchanged but the voice stage doubled.
