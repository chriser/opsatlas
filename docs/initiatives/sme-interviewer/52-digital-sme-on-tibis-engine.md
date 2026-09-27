# The Digital SME answers with Tibi's engine

ADO Epic #1851 (TIBI E4), Feature DSME F1 #1852, 27 September 2026. Engine 1.3.0.

The Human asked for the Digital SME avatar to answer the same questions as Tibi, with the same answers, spoken
through the Anam avatar. Before this, **Ask Digital SME** used the Written Query pipeline (`/api/avatar/answer`):
general retrieval over the approved sources, which is a different flow from Tibi's. It now asks Tibi's own engine.

## How it works

```
Ask Digital SME page ──► OpsAtlas gateway /services/tibi (operator sign-in)
                          └─► Tibi service: text channel (services/sme_interviewer/text_channel.py)
                                └─► Tibi's engine (tibi.py): routing, enabled records, spoken answers, sentence checks
                    ◄── reply text, route, records, timings, engine version
Ask Digital SME page ──► Anam avatar: talk(reply)   (renders only; its microphone stays off)
```

- **One engine.** The text channel builds Tibi exactly as the voice does, with the same companion factory, and runs
  its turns the same way, without audio. There is no speech recognition, no Higgs voice and no speculation. Every
  answer carries the engine version, as a voice turn does.
- **One conversation per page.** Follow-ups ("Why is that?", "The first one") are answered in context. **New
  conversation** starts afresh. A conversation is held in memory only: closed when you leave the page, forgotten
  after 30 minutes idle, and gone when the Tibi service restarts. If it has gone, the page says so and starts a new
  one. It never shares history with a Talk with Tibi conversation, and at most 8 are open at once.
- **Warm start.** Opening the page starts the conversation, and its model begins loading. If the first answer
  still takes more than 4 seconds, the status says **Loading Tibi's model**.
- **What Anam receives.** Only the reply text, as before. Anam's input audio stays disabled.
- **Logs.**
  - Each turn goes to the **Conversation Log** with mode `digital_sme` (the session is labelled Digital SME) and can
    be marked like any other.
  - The activity log records each turn's route and timing (`scripts/opsatlas-activity --grep text`), never its
    wording.
- **What the page shows.** Each reply, then **How Tibi answered**:
  - the route (for example Product answer, Conversation, Clarifying question);
  - the grounding (for example Checked against enabled records, Approved spoken wording);
  - why that route;
  - the records used, each linking to its row in Tibi Knowledge;
  - the time to the first sentence and to the whole reply.

The Natural or Formal style switch and the process-map walkthrough came from the Written Query pipeline. They are
not part of Tibi's answers, so they are no longer on this page. Written Query and Citation Check are unchanged.

## Same answers, measured

`evaluate_parity` asks the latency replay's 20 questions, as one conversation each time, three ways:
- twice through Tibi's engine as the voice runs it, which gives the model's own run-to-run variation;
- once through the text channel, as the page does.

It was run on a disposable copy of the live workspace.

| Measure | Digital SME against the voice | The voice against itself |
|---|---|---|
| Same route | 20 of 20 | 20 of 20 |
| Same records | 16 of 20 | 14 of 20 |
| Same grounding | 18 of 20 | 17 of 20 |
| Word-for-word identical | 6 of 20 | 3 of 20 |
| Wording similarity (0 to 1) | 0.64 | 0.55 |

The Digital SME agrees with the voice at least as closely as the voice agrees with itself. Where records differ,
they differ in the voice's own reruns too: the records cited follow the wording, and the model samples its
wording. An earlier run, before the tag fixes below, gave the same picture: routes 20 of 20 both ways, and records
15 of 20 both ways. Evidence: `evaluations/2026-09-27T1809-digital-sme-parity.json` and `.md`.

## A fix found on the way (engine 1.3.0)

The first Digital SME turn, on a model still loading, replied "An ordinary reply follows. Hello, how are you
today?". The small conversation model had copied the protocol's description of its "OK" tag into the reply. The
same could happen in the voice. The engine now drops that description whenever it follows the tag
(`TAG_DESCRIPTION` in `tibi.py`, tested in `test_the_tags_own_description_is_never_spoken`). No other behaviour
changes.

### Scorecard

The saved 1.3.0 card (`evaluations/2026-09-27T1803-engine-1.3.0.*`) compares with yesterday's 1.2.0 card. The
models sample their wording, so a fair comparison needs 1.2.0 scored again on the same day and with the same
knowledge (digest `5c1c4ccb…`, 56 turns, 2 runs each; `evaluations/2026-09-27T1805-baseline-engine-1.2.0.*`):

| Measure | 1.3.0 | 1.2.0 today | 1.2.0 yesterday |
|---|---|---|---|
| Routing accuracy | 1.00 | 1.00 | 1.00 |
| Appropriateness | 0.988 | 0.983 | 0.988 |
| Grounding precision | 0.827 | 0.846 | 0.885 |
| First sentence, median | 464 ms | 468 ms | 532 ms |
| First sentence, 95th percentile | 1,130 ms | 1,099 ms | 1,174 ms |

- **Appropriateness.** 1.2.0 today failed "How's your day going?" with "An ordinary reply follows…", the bug that
  1.3.0 fixes. 1.3.0 did not fail it.
- **Grounding precision.** It moves between runs of the same engine (0.885 yesterday, 0.846 today). The turns that
  differ are rehearsal answers from the evidence path, which 1.3.0 does not change: in each, a second sentence
  cites no record.
- **Still failing, as in 1.2.0.** "Give an example relevant to this customer" does not mention the customer's
  situation. This is the content gap noted in guide 51: there are no approved use-case records to stand on.

### Latency replay

The voice's latency gate for 1.3.0 was run on a disposable copy of the live workspace: 40 spoken turns, with the
other project's model server idle throughout.

| From the end of speech | Median | 95th percentile | Budget |
|---|---|---|---|
| First audio (1.3.0) | 1,501 ms | 1,723 ms | 1,950 / 3,100 ms |
| First audio (1.2.0, under load) | 1,526 ms | 1,891 ms | |

There were no errors, and the result is within budget. Evidence:
`evaluations/2026-09-27T1919-latency-replay-engine-1.3.0.json`.

## Where

| Part | File |
|---|---|
| Text channel | `services/sme_interviewer/text_channel.py`; routes in `sales_preview.py`: `POST /api/text/sessions`, `/api/text/sessions/{id}/turns`, `/api/text/sessions/{id}/close` |
| Page | `frontend/src/AvatarLabPage.tsx`; client calls `openTibiText`, `askTibiText`, `closeTibiText` in `api.ts` |
| Parity check | `services/sme_interviewer/evaluate_parity.py`; results in `evaluations/*-digital-sme-parity.*` |
| Tests | `tests/test_sme_text_channel.py`, and the tag test in `tests/test_sme_tibi.py` |

## For the Human to test

1. Open **Ask Assistant › Ask Digital SME**. The line under the avatar should say **Tibi engine 1.3.0**.
2. Without starting the avatar, ask what you would ask Tibi, for example:
   - "What is OpsAtlas?"
   - "Can it run offline?", then "Why is that?"
   - "Is the platform secure enough for a bank?", then "The first one"
   - "How are you today?"

   Compare with Talk with Tibi.
3. **Start Avatar**, and ask again. The avatar speaks the same reply that appears in the conversation.
4. In the **Conversation Log**, the session is labelled Digital SME. Mark any odd turn.
