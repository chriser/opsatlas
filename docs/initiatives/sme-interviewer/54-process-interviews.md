# 54 · Process interviews: Tibi captures an organisation's processes, with a live map

TIBI E5 (ADO). Asked by the Human on 28 September 2026. Data for this work is made-up or anonymised (the Human's
answer on 28 September): the knowledge-spaces rule of no real client data before phase 5 stands.

## What the Human asked for

- A new organisation space, **BiPi**.
- An interview with Tibi to capture a couple of BiPi's business processes. Tibi asks the questions: the Human's role,
  what they would like to talk about, which process, and then the process itself.
- It feels natural and easy. Tibi is patient and listens. It checks back on anything that does not make sense, or
  that conflicts with something already said.
- The interview can be paused or stopped, and picked up later.
- The Human reviews what was captured.
- A business process map takes shape from the interview, drawn by our process diagram service. The Human can correct
  it and comment on it by talking to Tibi.
- The process diagram service appears in the sidebar's Status.

## What exists, and what is missing

| Need | Today | Missing |
|---|---|---|
| An organisation space | Every space gets its own process registry, ontology, EAM and maps (KS F1) | Creating a space; spaces are only built when the core starts |
| A process interview | Product and governance interviews; a legacy supplier interview (trigger, steps, owner, systems, controls, exceptions) that the control panel cannot reach and that knows only "supplier" | A general process interview in the control panel |
| Checking back | Chat flags a contradiction only with two exact quotes; governance reads answers back | A running record of what was said, checked every turn |
| Pause and continue | The ledger can resume a session; the control panel cannot reopen one | **Continue** in the control panel, restoring the place |
| Review | Interview contributions (product claims) | A process review: steps, roles, systems, decisions, open questions, each with the Human's words |
| A live map | The diagram service (`services/process_diagram`, port 5300) lays out swimlane charts from lanes, tasks, gateways, systems and controls | Nothing feeds it from an interview; the registry builds maps only from learning packs |
| Status | Core API, Compliance reasoning, Tibi voice | The diagram service is not started by OpsAtlas Sales and not in Status |

## The design

**Two loops.**
- *The conversation* (the voice path): `qwen2.5:7b-instruct`, as for the other interviews. A deterministic planner
  chooses what to ask next from the gaps in the working model (below); the model phrases it naturally, in reply to
  what was just said. One question at a time, short, no filler. A process interview waits for the participant: no
  silence cut-off (`TurnBoundary(fallback=None)`).
- *The note-taker* (off the voice path): `qwen2.5:14b-instruct` reads each answer with the question and the working
  model, and returns changes to the model. Every change carries an exact quote from the answer; changes whose quote
  is not in the answer, or that name an item that does not exist, are dropped. It also returns what is unclear and
  what conflicts with an earlier statement, quoting both. The planner raises the oldest open conflict first, on the
  next turn.

**The working model** (`opsatlas.process-model.v1`, saved with the interview):
- the participant (name, role, team), each with the quote it came from;
- the agenda (the processes they want to cover);
- per process: name, purpose, trigger, outcome, frequency; steps (task, decision or end) with who does it, the
  system used, and where it goes next (a decision has labelled branches); exceptions; controls;
- each item is *heard* until the participant confirms a read-back, then *confirmed*; *disputed* while a conflict is open;
- open items: conflicts, unclear points and gaps, each with its status.

**The interview's shape**, which the planner follows and the participant can steer at any time:
1. Introductions: name, role, team, how long in the role.
2. What they would like to talk about: the processes, in their words. The agenda.
3. For each process: what it is for and what starts it; the steps in order, and for each who does it and in which
   system; the decisions and what happens either way; what goes wrong and how it is handled; the checks and
   approvals; how it ends. After two or three new steps, Tibi reads them back and asks if that is right.
4. A read-back of the whole process, then the next process, or wrapping up.

"Pause", "stop", "recap", "go back", "that's wrong", and "give me a moment" work by voice and by typing.

**The live map.** The working model is converted to a `process_model` (lanes by role, tasks, gateways with labelled
branches, systems, controls; heard steps shown as provisional) and drawn by the diagram service beside the
conversation. It updates as the note-taker changes the model. The Human corrects it by talking or typing to Tibi,
or by clicking a step and writing a comment, which goes to Tibi as a message about that step. Tibi confirms each
correction.

**Pause, stop, continue.** The model and the place in the interview are saved with the session after every turn.
The Tibi page lists the space's paused process interviews under **Continue**. Tibi picks up with where they were.

**Review and approval.** A review of the capture per process: the steps table, decisions, exceptions, controls,
open items and the quotes behind each, with the map. The Human edits, then **Save to BiPi**: a governed document in
BiPi, in a readable format with the process model in a JSON block. Once the Human approves it in Governance Review,
BiPi's Process Registry, ontology, EAM and maps are built from it. The registry reads the model block, so the
approved map is the one reviewed.

**Engine.** The interviewer is a new engine file: Tibi's engine becomes 1.5.0, with the scorecard and latency
replay before it goes live. It is developed in a worktree (`claude/process-interview`).

## Plan

| Feature | Delivers |
|---|---|
| KS F2 (part) | Create, rename and archive an organisation space without a restart. BiPi created. |
| PI F1 | The diagram service in the Sales services (launchd), in Status with a restart, its log in the workspace logs |
| PI F2 | The process interview mode: settings, opening, planner, phrasing, read-backs, voice commands |
| PI F3 | The working model and the note-taker: quoted changes, conflicts, unclear points, gaps |
| PI F4 | Pause, stop and continue across sessions |
| PI F5 | The live map beside the interview, with corrections by voice, typing or clicking a step |
| PI F6 | Review and approval into the organisation's registry, ontology, EAM and maps |
| PI F7 | Evaluation: scripted interviews about a made-up process (captured steps against the script, conflicts caught, repeated questions, read-backs), the scorecard and the latency replay |

## As built (28 September 2026, engine 1.5.0)

**How to use it**
1. **Governance Review › + Organisation space**: name it (BeePee, first created as BiPi). It is ready at once, with its own documents, process
   registry, activity model and maps. Rename it with the pen; **Archive** hides it and keeps its documents (**Restore**
   brings it back).
2. **Status** in the sidebar shows **Process maps**. If it is not running, press **Start** there.
3. **Talk with Tibi › Settings › Mode: Interview about a process**, choose the organisation, voice or typing, and
   **Start process interview**. Tibi asks who you are, what you would like to cover, then walks through each process.
4. The **process map** takes shape beside the conversation: dashed steps are heard, green ones confirmed with you, red
   ones to check. Points to check are listed under it. **Click a step** to change it by hand (what happens, who, the
   system, move it after another step, remove it, or add a different path after it) or to tell Tibi about it. Changes
   by hand apply at once. When you ask Tibi to remove or move something, it says what it will do and does it only when
   you say yes. **Fit / − / +** size the map.
5. Say or type **pause**, **stop**, **recap** or **give me a moment**. **Pause** and **End conversation** keep
   everything. **Settings › Interviews in BiPi › Continue** picks up where you were; Tibi says where that was.
   **Delete** (engine 1.7.0) removes an interview for good: its notes, map, timings and transcript lines; processes
   already saved to the space stay. An interview in which nothing was said is not listed, and is removed when it closes.
6. **Review what was captured** (or **Review** in the list): the map, and each process as a table you can edit.
   **Save to BiPi** makes a document that waits for your approval in Governance Review; approved, it feeds BiPi's
   Process Registry, activity model and maps, drawn from the same model.

**Where it lives**

| Part | Where |
|---|---|
| Organisation spaces | `services/opsatlas_sales/spaces.py` (`Spaces.create`, `change`), `app.py` (`POST /api/spaces`, `PATCH /api/spaces/{id}`, a core built at once) |
| Process map service | `services/opsatlas_sales/manage.py` (`diagrams` under launchd, port 5300), `POST /api/services/start`, restart choices; `frontend/src/App.tsx` (Status row) |
| The working model and planner | `services/sme_interviewer/process_model.py`: applying the note-taker's quoted changes, conflicts and corrections, joins and branches, the planner, exact read-backs |
| The interviewer | `services/sme_interviewer/process_interviewer.py`: notes first (2.5 s budget), the reply, commands, durable pending answers; `continuous.py` (the loop), `interview.py` (settings), `sales_preview.py` (the mode, `GET /api/process-interviews`) |
| Map and capture | `src/assistant/process/interview_map.py` (model → diagram service input, capture document, and back), `routes_process.py` (`POST /api/process/interview-map`, `POST /api/process/captures`); the registry parser and map builder read a capture's model |
| Control panel | `frontend/src/tibi/InterviewMap.tsx`, `tibi/ProcessReviewPage.tsx`, `TibiPage.tsx`, `tibi/voice.ts` |
| Evaluation | `services/sme_interviewer/evaluate_process_interview.py` (a tool, outside the engine fingerprint) |

**What changed on the way, from the evaluation** (a scripted made-up participant against the real local models):
- The first run captured 3 of 7 steps. The planner worked on the model from before the latest answer, so Tibi asked
  again for what had just been said. The note-taker now reads the answer first, within 2.5 s (about 1 s typically),
  and the reply is planned on the updated model; a longer answer is replied to at once and noted in the background.
- Replies without a question left the participant nothing to answer; read-backs rephrased by the conversation model
  stated things that were never said. A goal's reply now always asks its question, and read-backs are said exactly as
  captured, from the model.
- Note-taker fixes: changes applied in dependency order; the same step on another branch by another role is its own
  step, and two paths that continue to the same step join there; more detail is not a conflict; a conflict is settled
  by keeping the first account, the new one, or both; who the participant is changes only when they speak about
  themselves (a run had turned the participant into "buyer" from a correction about the process).
- Moving to the next process waits for the participant to agree; an end on one branch does not end the others.

**Measured (engine 1.5.0, evidence in `evaluations/`)**

| | Run a | Run b | Run c |
|---|---|---|---|
| Steps found (of 7) | 7 | 7 | 7 |
| Owners right | 7 | 7 | 7 |
| Systems right | 6 | 6 | 6 |
| Contradiction raised and settled | yes | yes | yes |
| Correction applied | yes | yes | yes |
| Read-backs | 3 | 3 | 3 |
| Questions repeated in a row | 0 | 0 | 0 |
| Reply p50 / p95 | 2.08 / 3.70 s | 1.93 / 3.50 s | 1.96 / 3.40 s |
| Notes p50 / p95 | 1.24 / 5.26 s | 1.27 / 5.02 s | 1.21 / 5.18 s |

The first run, before the fixes above, found 3 of 7 steps.

**Latency replay (chat, the gate)**
- A replay right after the evaluations first failed: first audio p95 3,403 ms. Its first 20 turns were slow and the
  rest normal. With the note-taker's model loaded on purpose, a 20-turn replay gave p95 3,342 ms; with it unloaded, 1,857 ms.
- The note-taker's model is now kept 5 minutes between notes and unloaded when the interview closes.
- Replay right after three interviews: first audio p50 1,488 ms and p95 1,892 ms, within the budget (1,950 / 3,100).
  Evidence: `evaluations/2026-09-28T2000-latency-replay-engine-1.5.0.json`.

**Known limits**
- The note-taker sometimes models a condition inside a step ("if anything is low she raises an order") as a decision.
  It is harmless in the map and can be edited in the review.
- It sometimes asks about two statements that can both be true (a weekly check and a stock trigger). The participant
  answers "both", and it is settled.
- When the participant says they have nothing to add, Tibi can say "Please go on." once more before moving on (seen once
  in the evaluation runs); to be fixed in the next engine version.
- During a process interview the note-taker's model is loaded, so a chat with Tibi at the same time is slower. It is
  unloaded when the interview closes.
- Process interviews reply in about 2 s (notes first) against about 1.5 s for chat. That is the price of planning on
  what was just said; the chat latency budget is unchanged and still gated by the latency replay.
