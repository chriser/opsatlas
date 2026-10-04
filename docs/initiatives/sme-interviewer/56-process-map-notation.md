# 56 · The process map notation: branches, events, several roles

TIBI E5 (ADO), PI F18.

**What was wrong.** On 29 September 2026 the Human described "carry out cashiering" to Tibi. It is a process with
three paths from one point, an interface to the age check, and steps where the cashier and the customer act
together. The Human found the map linear:
- Tibi's working model did hold the branches, but the process diagram service drew every step in one column, in the
  order given.
- Only one kind of connector was drawn.
- There were no events between steps, no interfaces to other processes, and only one role per step.
- The live interview map drew in an older style: rounded start and end, and diamonds marked "?".

The Human compared it with their organisation's own map of the process and its shape legend (not kept in the
repository).

**Decided by the Human.**
- One notation for every process map.
- The map service first; Tibi's capture follows.
- Tibi asks, when it is unclear, whether one, all or any number of the paths are followed.

**Built (map service and pages).** The notation and its rules are in `services/process_diagram/README.md`.
- `layout.py`:
  - applies the notation (branch conditions as events, joins, "Non-system activity");
  - gives each path its own column.
- `engine.py`:
  - places steps with their systems on the left and roles on the right;
  - routes the flow (fan-out bars, join bars, a column of its own for a path straight to its join, loops through the
    gaps);
  - draws the shapes.
- `frontend/src/processShapes.tsx`: the same shapes for the live interview map and the animated process map.
  - The live map still shows how sure Tibi is of a step: dashed while heard, solid once confirmed, red to check.
- `interview_map.py`: passes a decision's kind, XOR until Tibi records one.

**Checked.**
- 7 new tests for the notation and layout, and the diagram service's earlier tests unchanged.
- The Human's cashiering capture drawn in the page, on a throwaway copy: branches side by side, joins, events and
  roles.
- A made-up age-restricted sale in the gallery, in the same shape as the Human's example.

**Next (Tibi, PI F19).**
- Capture two roles on a step ("the customer asks the cashier").
- Ask "can more than one of these apply?" to record XOR, ANY or AND.
- Ask whether a step is a process of its own (an interface).
- Take trigger and outcome events.
- Stop using the process's name as a role ("Cashiering").
