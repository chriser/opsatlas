# 55 · The first real process interview: what went wrong, and what changes

TIBI E5 (ADO). On 28 September 2026 the Human ran the first process interview, by voice, about "over the counter
sales" for the made-up organisation BeePee (then called BiPi). The Human's verdict: the design was right, and the
experience was frustrating.
- Tibi misheard words ("till" as "tail").
- It put steps and systems where they should not be.
- Correcting what the Human could see was hard.
- An alternative branch that starts early in the process was not understood.

The interview was reviewed from its saved session, the note-taker's per-turn log and the conversation log. At the
Human's request it was then taken out of the live workspace into
`.runtime/opsatlas-sales-archive/bipi-interview-2026-09-28/`, for the Human to delete.

## What the evidence showed

**1. Most of what was said never reached the conversation.** This was a defect.
- *The numbers:* the interviewer was called 72 times, but only 33 replies were given. All 11 steps in the model came
  from answers that are not in the transcript, and so did the participant's name and role.
- *The cause:* a confident turn-end prediction closed a turn after 0.3 s of silence. A process description is a
  string of complete sentences with pauses, so each sentence became a turn. The interviewer noted it and started a
  reply. When the participant carried on speaking, the reply was discarded as stale. But the note-taker had already
  applied that fragment to the model.
- *The gap in the code:* chat joins an interrupted answer to the next one (`continuation`). The interview path passed
  only the latest fragment (`recognised`), and it never recorded the unanswered text for joining.
- *The effect:* the description was noted as disconnected fragments, each with the wrong question as its context.
  This produced "Ask for product" by the customer "in point of sale", and "the cashier customer asks". The three
  choices became one tangled decision. The reply to the heart of the description was never given ("Did you get all of
  that?").

**2. Mishearing.** The speech recogniser (Whisper small.en) uses a word list for OpsAtlas terms, with nothing for the
organisation. It heard:

| Said | Heard |
|---|---|
| till | "tail", "TIL" |
| tobacco | "Tabaku" |
| site worker | "side stuff", "side worker" |
| the organisation's name | "Bipy" |
| (something) | "Add the pipeline" |

A correction ("It's till, T-I-L-L") was applied to one step only.

**3. Corrections that change the shape of the process were not possible.**
- The note-taker could add and change things, but not remove or move them. "Remove it completely" did nothing.
- "That step happens after the tobacco is handed over" was appended to the step's name.
- Tibi did not say what it understood before changing anything.
- Three final "Can I check one thing?" questions were rewordings treated as contradictions.
- The click-a-step comment was not used: it works only while the conversation is live, and it was not obvious.

**4. An alternative branch that starts early.**
- Nothing let the note-taker say "this path splits off after step 2" and move existing steps into one branch.
- Three choices at one point were not modelled as one decision with three branches.
- Tibi never asked where a path splits off or rejoins.

**5. Mechanical questioning.** "Who does it?" was asked seven times and "is it done in a system?" six times, step by
step, even after "it's the same person".

**Why testing missed it.**
- The evaluation fed whole, typed answers straight into the interviewer, never through the voice loop's turn-taking.
- The browser check was typed.
- The scripted participant answered exactly what was asked.
- The path the Human actually used (speaking naturally, with pauses) was never tested.

## What changes

| # | Change | Fixes |
|---|---|---|
| 1 | Whole answers across pauses: a process interview waits for at least 1.3 s of silence; an interrupted answer is joined to what follows; notes taken from a superseded fragment are undone and the whole answer is noted once | 1, and most of the garbled steps |
| 2 | Corrections by pointing and by confirming: step actions on the map (rename, who, system, remove, move, branch from here), applied directly; spoken structural changes (remove, move, merge) are said back and applied only on a yes; wording is never a conflict | 3 |
| 3 | Branches: decisions with several choices; "after which step does this split off?" and "does it rejoin?"; unnamed branches get named | 4 |
| 4 | Hearing: an interview word list (the organisation, captured terms, corrections) for the recogniser and the note-taker; a corrected word is fixed everywhere | 2 |
| 5 | Conversation shape: who and systems asked once per process, with defaults; short read-backs that point at the map | 5 |
| 6 | Evaluation on the voice path: spoken answers with pauses and interruptions, structural corrections and an early branch, as a replay through the real service | the testing gap |

## As built (engine 1.6.0)

**Whole answers (PI F8)**
- A process interview's turn ends only after 1.3 s of silence (`PROCESS_PATIENCE`), however finished a sentence sounds.
- Speaking again before Tibi's reply continues the same answer. The interview path now joins it (`continuation`),
  as chat did.
- An answer that is superseded, paused or failed is withdrawn (`withdraw_open`). Its notes are cancelled, or undone
  if they were already applied, and it leaves the transcript and pending notes. The loop logs "answer continued".
- The note-taker's time grows with the answer: 2.5 s, rising to 7 s for a long description. The turn's time limit
  allows for it; the fixed 9 s limit had made one reply fail.
- A long answer that is still being noted gets "Anything else to add there?" rather than a question planned on a
  stale model. In the replay, a stale plan had asked the participant to walk through what they had just described.

**Corrections (PI F9)**
- Spoken remove and move are said back ("So you would like me to move … Shall I?") and made only on a yes; a no
  leaves the process as it was.
- **Clicking a step on the map** opens a panel. You can change what happens, who and the system, move it after
  another step, remove it, add a different path after it, or tell Tibi about it. Changes by hand apply at once, over
  the live connection (`process_edit`), and count as confirmed.
- Conflicts are raised only about who does a step and its system; rewording is kept as first said. A correction or a
  conflict lands only on a step the answer or Tibi's question refers to.
- A corrected system also fixes its name in the step ("Refund on till" becomes "Refund on card machine").

**Branches (PI F10)**
- An alternative is placed as a decision after the step where it splits, with a branch named for the usual case to
  what already follows. Three or more choices at one point make one decision with a branch each.
- Tibi asks when an unnamed branch applies, and whether a branch's end joins back into the process.

**Hearing (PI F11)**
- The recogniser gets the interview's own words, from the start and refreshed as they are noted: the organisation,
  process names, roles, systems and corrected words.
- A corrected word ("it's till, not tail") is replaced everywhere.
- A name heard within a letter of a capitalised term ("BeePea") is written as the interview knows it.

**Conversation shape (PI F12)**
- Who does the steps is asked once per process ("the same person throughout?"), with a default owner. Systems are
  asked once, naming the steps.
- Read-backs are at most three steps and never repeat a system already named in the step.

**Evaluation on the voice path (PI F13)**
- `replay_process_interview.py` synthesises a made-up participant sentence by sentence, with real thinking pauses
  (one longer than the patience), and streams it in real time through a disposable copy of the services.
- It covers a system correction, a move to confirm and an early alternative path, and records turns, replies,
  timings, what was heard, and the saved model.

## Measured (engine 1.6.0, evidence in `evaluations/`)

**Latency replay (chat, the gate): within the budget.**

| | First audio p50 | p95 | Budget |
|---|---|---|---|
| All 100 turns | 1,858 ms | 2,901 ms | 1,950 / 3,100 |
| Turns 1–46, machine quiet | 1,467 ms | 1,858 ms | |
| The same turns, engine 1.5.0 | 1,443 ms | 1,831 ms | |

- 100 turns, no errors, 99 speculative replies adopted.
- From turn 47, another project's model server on the same machine was running again, at 20–80% CPU. Speech
  endpointing did not change. The model's reply preparation slowed (p50 about 970 ms, rising to 1,345 ms), and that
  raised the overall figures.
- On the quiet turns, 1.6.0 matches 1.5.0 to within 30 ms: the process-interview changes do not touch chat's turn path.
- Evidence: `evaluation/results/tibi/2026-09-29-latency-replay-engine-1.6.0.json`.

**Typed interviews (the scripted stock-ordering process, three runs)**

| | Run a | Run b | Run c |
|---|---|---|---|
| Steps found (of 7) | 7 | 7 | 7 |
| Owners right | 7 | 7 | 7 |
| Systems right | 7 | 7 | 7 |
| Contradiction raised and settled | yes | yes | yes |
| Correction applied | yes | yes | yes |
| Read-backs | 3 | 4 | 3 |
| Questions repeated in a row | 0 | 0 | 0 |
| Reply p50 / p95 | 2.23 / 3.30 s | 1.89 / 3.38 s | 2.13 / 3.33 s |

Systems right rose from 6 to 7 of 7 against engine 1.5.0; the other measures held.

**Spoken interview (the voice-path replay: customer returns at BeePee, nine spoken answers with pauses)**
- *Turn-taking:* every answer got exactly one reply, and none arrived while the participant was still speaking. One
  answer was carried on over a pause. It was joined and noted once, and no notes were left pending.
- *Checks passed:*
  - the refund moved to the card machine, and the receipt check kept the till;
  - the gift-card path splits after the receipt check;
  - the shelf step was moved before the refund after a spoken "Yes, please";
  - the organisation, heard as "BeePea", was saved as BeePee.
- *Results:* 6 of 6 steps, 5 of 6 owners, 6 of 6 systems.
- *Speed:* on a quiet machine, the reply came 3.1 to 7.1 s after the participant stopped speaking. The long
  description took longest: its notes took 11 s, and it got "anything else to add there?" Replies took 7 to 11 s
  when the other project's model server was busy.
- *Evidence:* `evaluation/results/tibi/2026-09-28-process-interview-voice-replay.json` (the run while the other project's server
  was busy).

**Known limits, for the next engine version**
- *A move "before" a step lands too early.* "The item goes back onto the shelf before the refund" was proposed as
  "after Check receipt on till". In the quiet run it was "after Call duty manager". The refund sits on a decision's
  branch, and a move can only name the step it goes *after*. The replay's check (the shelf somewhere before the
  refund) was too lenient to catch this.
  - *Mitigation:* the proposal is said back before anything changes, and a no leaves it as it was. The map's
    "Move it to after" is exact.
- *A step that names its own subject is read back badly.* "Customer brings item to service desk" is said as "someone
  customers brings item to service desk".
- *"That's the end of it" is not taken as the end of the process.* The question just asked (what starts it) was asked
  again, in other words.
- *The recogniser still hears "BeePee" as "BeePea",* even with the organisation in its word list. The name is corrected
  when noted.

## The second attempt (29 September) and engine 1.7.0

**What happened.** The Human started an interview at 08:12 on the live engine, 1.5.0; 1.6.0 was gated but not yet
live.
- Tibi's voice stuttered.
- After two questions it showed "The local conversation model could not reply".
- BeePee's list showed nine interviews. Seven had nothing said in them, and four of those were from the night before,
  missed by the clean-up.

**Why, from the logs and measurements.**
- *The reply failure:* the first reply took 5.3 s to prepare (about 2 s when the machine is quiet). The second went
  over 1.5.0's fixed 9 s limit. Engine 1.6.0 removed that limit (PI F8).
- *The cause of the slowness:* another project's model server (21 GB) was busy on the same GPU. Memory was not the
  problem: 45% was free.
- *The stutter:* speech is generated while it plays. At 08:19, under that load, the voice was generated at 1.05–1.10×
  real time (1.36× quiet), so playback caught up with it. The 8-bit voice measured 1.44–1.50× with no gaps, but the
  Human kept the standard voice.
- *Not caught before:* the page received a message for every gap in playback, but ignored it.

**What changed (engine 1.7.0).**

| # | Change | Fixes |
|---|---|---|
| PI F16 | Tibi starts speaking only when the audio in hand covers what playback would otherwise overtake (length × (1 − the rate lately measured, taken 15% worse), plus 0.2 s, at most 5 s). The page counts gaps per reply and logs "playback gaps" | the stutter |
| PI F15 | **Delete** on each interview, with a confirmation: the session, its events, timings and conversation-log turns, for good. Saved processes stay; an open interview is refused. An interview with nothing said is not listed, is removed when it closes, and the old ones are removed at start | the empty interviews |
| PI F14 | A move "before" a step stays on that step's branch. A label that names its own subject reads back as it is. A question about the process as a whole that was answered past is not asked again straight away | the known limits of 1.6.0 |

Two faults were found while testing 1.7.0, and fixed:
- **A cut-off reply lost a whole description.** A rule telling the note-taker how a process ends made it add "End"
  steps after every branch. Its reply ran past the 900-token limit and could not be read, so a first spoken replay
  captured 1 of 6 steps. The rule was removed; the original "kind end when they say the process ends there" stays.
  The limit is now 1,500 tokens, and a reply cut off keeps every change it completed (logged as cut off).
- **A correction taken as a misheard word.** "The refund is done on the card machine, not on the till" came back as a
  misheard word, so every "till" became "card machine", the receipt check's too. A misheard word must now sound like
  the right one ("tail" and "till"); otherwise it corrects only the system of the step the answer names.

**Measured (engine 1.7.0, evidence in `evaluations/`)**
- *Latency replay (the gate), machine quiet:* first audio p50 1,482 ms, p95 1,852 ms, max 1,937 ms, no errors. That
  is within the budget (1,950 / 3,100) and level with 1.6.0 (1,467 / 1,858) and 1.5.0 (1,488 / 1,892): the guard costs
  nothing on a quiet machine. The Human paused the other project's jobs for it.
  Evidence: `2026-09-29-latency-replay-engine-1.7.0.json`.
- *Under load* (the other server at 66% CPU on average, 142% at peak): p50 2,007 ms, p95 2,639 ms. That is over the
  p50 budget, but better than 1.6.0 under lighter load (turns 47–100: 2,357 / 2,930).
  Evidence: `2026-09-29-latency-replay-engine-1.7.0-under-load.json`.
- *The guard on the real voice at 13:18,* with that server running: the voice kept 1.6–1.8× real time, so nothing
  waited and there were no gaps. The load varies, and the earlier measurement was the slow case.
- *Delete, checked in headless Chrome* on a throwaway workspace: the confirmation shows, the interview goes, the list
  refreshes, and there are no console errors. The two empty interviews there were removed at start.
- *Spoken replay, machine quiet:*
  - Every answer got exactly one reply, and none arrived while the participant was speaking. One answer continued over
    a pause was joined and noted once.
  - The shelf step moved straight before the refund, on the "No" path (the strict check).
  - The refund moved to the card machine, and the receipt check kept the till.
  - The gift-card path splits after the receipt check.
  - Results: 5 of 6 steps, 4 of 6 owners, 5 of 6 systems.
  - Evidence: `2026-09-29-process-interview-voice-replay-1.7.0.json`.
- *Typed interviews (three runs):* each got 7 of 7 steps, owners and systems. The contradiction was raised and
  settled, the correction applied, and no question was repeated in a row. Evidence:
  `2026-09-29-process-interview-evaluation-1.7.0-{a,b,c}.json`.
- *Tests:* 1,178 Python tests and 65 browser tests pass, as do ruff and the build. CI 20260929.3 passed.

**Still open**
- "The duty manager decides whether to send the item back to the supplier" was placed after the damage decision on an
  unnamed path, not after "Call duty manager". The planner asks when that path applies, and the map's panel can move it.
- "A return starts when a customer brings an item back" was taken as what starts the process, not as a first step.
  That is a fair reading, but the replay's check expects a step.
- Replies to a long description still wait for its notes: 5–7 s after the participant stops, on a quiet machine.

## The third attempt (29 September, 17:20) and engine 1.7.1

**What happened.** After five answers, the Human described "carry out cashiering" in one long spoken answer of 1,321
characters. Tibi said "could not reply" at once, then again for every answer after it.

**Why.** Two faults, both in the joining of an answer across pauses added in 1.6.0 (PI F8):
- **A length limit.** The interviewer refused any answer over 1,200 characters. The refused text then stayed to be
  joined to the next words, so each later answer was refused too. The page showed the generic message, and no cause
  was logged.
- **A lost first part.** Speaking again before the previous part had been transcribed dropped that part. After a
  1.6 s pause the turn ends at 1.3 s, and the speaker was already talking again 0.3 s later. A spoken replay lost a
  description's first 307 characters this way.

Neither was tested: no replay had spoken an answer that long.

**What changed (engine 1.7.1, PI F17).**
- A process answer, spoken or typed, may run to 8,000 characters. A long answer is noted about 700 characters at a
  time, split where sentences end.
- A failed reply keeps its answer for the note-taker, and speaking again starts a new answer. Every failed reply is
  logged with its cause.
- A part still being transcribed when the speaker carries on is heard again with what follows.
- The spoken replay has a long scenario (`--scenario long`): a description of 1,341 characters, with two pauses
  longer than the patience. It allows 90 s for a reply after the answer ends, and waits for the notes with the
  interview still open.

**Measured.**
- *Long spoken replay:* the whole answer was kept (1,332 characters heard), with one reply and no errors. The answer
  after it was replied to, and the notes finished (28 s for the long answer). That gave 17 steps across all three
  paths, plus payment, receipt and thanks. Evidence: `2026-09-29-process-interview-voice-replay-long-1.7.1.json`.
- *Tests:* 1,182 Python tests and 65 browser tests. The audio-path test fails without the fix.
- *Latency replay:* waived by the Human for this fix. Chat's turn path is unchanged.
