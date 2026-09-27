# Tibi: sales rehearsal and name activation

ADO Epic #1837 (TIBI E3), steps 4 and 5 of the plan, 26 September 2026. Engine 1.2.0.

## How to rehearse

1. In **Talk with Tibi**, choose **Sales rehearsal** in the side panel. Optionally, describe the customer, for example
   "regional bank, head of operations".
2. **Start sales rehearsal.** Tibi says it is listening and will help when asked.
3. Deliver the pitch. What you and the customer say is **meeting context**. Tibi hears it and does not answer it.
   The badge on the stage says what Tibi is doing with what it hears.
4. When you want help, press **Ask Tibi** (or **T**), then say what you want:
   - “What have I missed?” names one or two points from the approved records that the meeting has not covered.
   - “Explain that more simply.” restates the last point (Tibi's own, or the last product point made) in plain words.
   - “Help me answer that question.” answers the customer's last question.
   - “Give an example relevant to this customer.” gives an example for the customer's situation.
   - Anything else is answered as a question, with the meeting as context.
5. Tibi answers in one or two short sentences, checked against approved records, without asking anything back. The
   floor returns to you, and the badge says so. Speak at any time to interrupt Tibi. **Esc** cancels a request,
   and **M** mutes at once.

When typing, **Add to meeting** adds a line of the meeting and **Ask Tibi** asks Tibi.

## Listening, and what is kept

| Choice | What it does |
|---|---|
| Listening (always, in a rehearsal) | The meeting is heard to give Tibi context. It is held for the rehearsal only, in memory, and is never a product claim or a proposal. |
| Your requests and Tibi's replies (always) | Kept in the Conversation Log, like any conversation, as the opening says. The customer description is kept with the rehearsal's settings. Without a transcript, a sentence the checks stopped is logged only with why it was stopped, never its wording (it may repeat the meeting). |
| Listen for “Tibi” | Saying “Tibi” or “Tiberius” asks Tibi, as Ask Tibi does. It is off by default and can be switched on or off during the rehearsal. |
| Keep a meeting transcript | Saves the meeting lines with the rehearsal, from the moment it is switched on. Switching it off keeps what was already saved. It is off by default and a separate choice from listening. |
| Mute (M) | Stops listening at once. No microphone audio leaves the page until you unmute. |

The badge on the stage is visible to everyone in the room. It shows one of:
- **Listening to the meeting · not kept**
- **Listening for “Tibi” · not kept**
- **Listening for your request**
- **Tibi is answering**
- **Muted · not listening**
- **Transcript kept**, shown only when the transcript is being kept

Requests to Tibi and its replies are logged like any other turn (conversation log, mode `rehearsal`). The meeting's
words are not, unless the transcript is kept.

## When the name counts

The name counts only when it is addressed to Tibi:
- **At the start** of what someone says: “Tibi, what have I missed?”, “Hey Tiberius, …”, “Tibi what have I missed?”.
- **At the start of a later sentence:** “… forty branches. Tibi, what have I missed?”.
- **After a comma at the end:** “What have I missed, Tibi?”.
- **The name alone** (“Tibi?”) gets “Yes?”, and the next thing said is the request.

It does not count in passing: “I told Tibi about it”, “Tibi is our assistant”, “Tibi's voice”, “TB is a problem”.
“Toby”, “TV”, “the Tiber” and “Tibco” never count.

While Tibi speaks, and for a few seconds after, anything the microphone hears that is mostly Tibi's own words is
treated as its echo. It is ignored: never a request and never meeting context.

## Measured

**Rehearsal scorecard** (`evaluate_engine`, scenarios `rehearsal-bank` and `rehearsal-direct-question`)
- A full pitch to a regional bank with the four requests and a second customer question, plus a direct question.
- Each reply is checked for the right route, being grounded in the records, brevity (at most 300 characters), no
  question back, a new point for “what have I missed?”, and relevance to the customer for the example.
- Also timed to the first spoken words.

**Spoken name test** (`evaluate_wake`)
- 10 system voices (British, Irish, Australian, Indian, South African, American), run through Tibi's own speech
  recognition.
- 8 activations and 10 non-activations per voice.
- 3 two-speaker utterances.
- 3 of Tibi's replies as echo.

The heard spellings were added from this very set, so the second column is not evidence that the rules generalise
(audit F07). A held-out set, written afterwards and never used to change the rules, is reported in guide 53.

| Measure | First run | After fixing the heard spellings |
|---|---|---|
| Activations recognised, with the right request | 87.5% | 100% (80 of 80) |
| Accidental triggers | 0% | 0% (0 of 100) |
| Two speakers in one utterance | 100% | 100% |
| Tibi's own replies recognised as echo | 100% | 100% |

**Scorecard, engine 1.2.0.**
- **Rehearsal requests:** 10 of 12 pass every check, with a median of 794 ms to the first words, about the same as an ordinary product answer.
- **Scenarios shared with 1.1.0:** no regression. Routing is 1.00, appropriateness 1.00 (0.99 before), grounding 0.95 (the same), and the 95th percentile to the first words is 812 ms (1,004 ms before).

**The example request is conservative.** Asked for an example for a regional bank, Tibi's own wording reused the
pitch's words and the customer's ("your teams", "up-to-date answers across your forty branches"). The sentence check
blocked those words because no approved record states them, so Tibi spoke the record's approved first sentence
instead. The check worked as designed here. It is a lexical check, not a guarantee of accuracy: the independent
audit of 27 September 2026 showed wording it lets through, and guide 53 records what was fixed and what remains. The fix is content: approved example or use-case
records for typical customers (a bank, an insurer, a public body), written and approved through content management,
give the example something to stand on.

The recognition heard “OK Tibi” as “OkTibi” or “OKTb”, “Hey Tibi” as “ATB”, and “Tiberius” as “Tibiarius”. These are
now understood. Synthetic voices are a proxy: the Human's test below is the real one.

## The Human's test with the Jabra speakerphone

Run this before relying on name activation in a real meeting:
1. **Set up.** Choose the Jabra as both microphone and speaker in the side panel. Choose Sales rehearsal, turn on
   Listen for “Tibi”, and leave Keep a meeting transcript off.
2. **Missed activations.** Say each of these five times, at normal pace, from where you would sit:
   - “Tibi, what have I missed?”
   - “Hey Tibi, explain that more simply.”
   - “What have I missed, Tibi?”
   - “Tiberius, help me answer that question.”

   Count how often the badge changes to **Tibi is answering**.
3. **Accidental triggers.** Talk for five minutes about the product, naming Tibi in passing (“Tibi told me…”, “Tibi is
   our assistant”). Count any answer Tibi gives.
4. **Several speakers.** With a second person, alternate lines. Have them ask Tibi once by name and once with the
   button.
5. **Tibi hearing itself.** Ask a question whose answer mentions Tibi, and let Tibi answer through the speaker. Then
   interrupt it once. Tibi must never answer its own words, and the activity log (`scripts/opsatlas-activity --grep
   echo`) shows each ignored echo.
6. **Mute.** Press M while speaking, and check that the badge shows **Muted** at once and nothing you say is heard.
7. Mark any odd turn in the **Conversation Log** with a note.

## Latency replay (the voice-path gate)

Engine 1.2.0, 27 September 2026, 40 spoken turns, `evaluations/2026-09-27T0046-latency-replay-engine-1.2.0.json`:

| Measure | 1.2.0 | Budget | 25 September baseline |
|---|---|---|---|
| End of speech to first audio, median | 1,526 ms | 1,950 ms | 1,822 ms |
| End of speech to first audio, 95th percentile | 1,891 ms | 3,100 ms | 2,885 ms |

The run had no errors, and 40 of 40 speculative replies were adopted. The other project's model server was loaded for
the whole run (31 contention samples), so these figures are under load. The replay covers engine 1.1.0's changes too.

What this does and does not show (audit F07):
- The 40 turns are 27 product, 8 conversation, 2 general, 2 about Tibi and 1 clarification: **no rehearsal turns**.
  The replay's rehearsal mode (`--rehearsal`, added for audit F07) times requests made during a rehearsal.
- Two general turns cannot give a route-level 95th percentile.
- Passing the budget is non-regression, not G1.5 acceptance, which still needs a p50 of 1.5 s or less over at least
  100 turns and the Human's ten-minute rating.
