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
