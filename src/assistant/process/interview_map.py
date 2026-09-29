"""Process interviews on the process map (TIBI E5, PI F5 and F6).

A process interview keeps a working process model (``opsatlas.process-model.v1``, written by Tibi's note-taker). Here
it becomes:

* the process diagram service's input, for the live map beside the interview and, once approved, the Process
  Registry's map of the same process: one converter, so the map the Human approves is the map they reviewed;
* a readable capture document for the organisation's space (steps, roles, systems, decisions, exceptions, controls,
  open points and the participant's words), with the model in a JSON block that the registry parser reads.

Pure functions over plain dicts; nothing here calls a model or a service.
"""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_ID = "opsatlas.process-model.v1"
BLOCK = re.compile(r"^## Process model\s*\n+```json\n(.*?)\n```", re.S | re.M)


def pick(model: dict, process_id: str | None = None) -> dict | None:
    processes = model.get("processes") or []
    wanted = process_id or model.get("focus")
    return next((p for p in processes if p.get("id") == wanted), processes[0] if processes else None)


def ordered(process: dict) -> list[dict]:
    """Steps in flow order from the start (branches depth first), then any not yet connected."""
    by_id = {s["id"]: s for s in process.get("steps") or []}
    seen: set[str] = set()
    out: list[dict] = []

    def walk(step_id: str) -> None:
        stack = [step_id]
        while stack:
            current = stack.pop()
            if current in seen or current not in by_id:
                continue
            seen.add(current)
            out.append(by_id[current])
            stack.extend(link["to"] for link in reversed(by_id[current].get("next") or []))

    if process.get("start"):
        walk(process["start"])
    for step in process.get("steps") or []:
        walk(step["id"])
    return out


def _lane(who: str) -> str:
    return "role_" + (re.sub(r"[^a-z0-9]+", "_", who.casefold()).strip("_") or "unknown")


def _detail(process: dict, field: str) -> str:
    return ((process.get("details") or {}).get(field) or {}).get("value", "")


def diagram_payload(model: dict, process_id: str | None = None) -> dict[str, Any]:
    """The diagram service's input for one process of the model: roles as lanes, the trigger as the start, tasks,
    decisions as gateways with their branches, systems, controls and exceptions beside their steps. An unfinished flow
    ends in "still being described" rather than a made-up end. Each step carries its status (heard, confirmed,
    disputed) for the live map."""
    process = pick(model, process_id)
    if process is None:
        raise ValueError("The interview has no process yet.")
    steps = ordered(process)
    lanes: dict[str, str] = {}
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    lane_of: dict[str, str] = {}
    previous_lane = "process"
    for step in steps:
        if step.get("kind") == "task" and step.get("who"):
            lane = _lane(step["who"])
            lanes.setdefault(lane, step["who"][:1].upper() + step["who"][1:])
            previous_lane = lane
        lane_of[step["id"]] = lane_of.get(step["id"]) or (
            _lane(step["who"]) if step.get("kind") == "task" and step.get("who") else previous_lane)
    nodes.extend({"id": lane, "type": "lane", "label": label} for lane, label in lanes.items())
    first_lane = lane_of.get(steps[0]["id"], "process") if steps else "process"
    trigger = _detail(process, "trigger")
    nodes.append({"id": "start", "type": "start", "label": (trigger[:1].upper() + trigger[1:]) if trigger else "Start",
                  "lane": first_lane})
    if process.get("start"):
        edges.append({"from": "start", "to": process["start"], "label": ""})
    ends = [s for s in steps if s.get("kind") == "end"]
    for step in steps:
        if step.get("kind") == "end":
            continue
        nodes.append({"id": step["id"], "type": "gateway" if step.get("kind") == "decision" else "task",
                      "label": step["label"], "lane": lane_of[step["id"]],
                      "metadata": {"status": step.get("status", "heard"), "who": step.get("who", ""),
                                   "system": step.get("system", ""),
                                   # xor, and or or (ANY): only one, all, or any number of the paths are followed.
                                   **({"gateway": step.get("gateway") or "xor"} if step.get("kind") == "decision" else {})}})
    outcome = _detail(process, "outcome")
    tails = [s for s in steps if s.get("kind") != "end" and not s.get("next")]
    if ends or not steps:
        end_label = (outcome[:1].upper() + outcome[1:]) if outcome else "End"
        end_lane = lane_of.get(steps[-1]["id"], first_lane) if steps else first_lane
        nodes.append({"id": "end", "type": "end", "label": end_label, "lane": end_lane,
                      "metadata": {"status": "confirmed" if ends and ends[0].get("status") == "confirmed" else "heard"}})
    else:
        nodes.append({"id": "end", "type": "end", "label": "Still being described",
                      "lane": lane_of[tails[-1]["id"]] if tails else first_lane, "metadata": {"status": "open"}})
    end_ids = {s["id"] for s in ends}
    for step in steps:
        for link in step.get("next") or []:
            target = "end" if link["to"] in end_ids else link["to"]
            if step["id"] in end_ids:
                continue
            edges.append({"from": step["id"], "to": target, "label": link.get("label", "")})
    for tail in tails:  # what follows it has not been described yet
        edges.append({"from": tail["id"], "to": "end", "label": "…"})
    known = {s["id"] for s in steps}
    for step in steps:
        if step.get("kind") == "task" and step.get("system"):
            node = f"sys_{step['id']}"
            nodes.append({"id": node, "type": "system", "label": step["system"], "lane": "systems"})
            edges.append({"from": step["id"], "to": node, "label": "", "type": "association"})
    for control in process.get("controls") or []:
        nodes.append({"id": control["id"], "type": "control", "label": control["text"], "lane": "controls"})
        anchor = control.get("at") if control.get("at") in known else "start"
        edges.append({"from": control["id"], "to": anchor, "label": "", "type": "control"})
    for exception in process.get("exceptions") or []:
        label = exception["text"] + (f" → {exception['handling']}" if exception.get("handling") else "")
        nodes.append({"id": exception["id"], "type": "risk", "label": label, "lane": "risks"})
        anchor = exception.get("at") if exception.get("at") in known else "start"
        edges.append({"from": exception["id"], "to": anchor, "label": "", "type": "association"})
    return {"style": "plain", "format": "cross-functional-flowchart", "animation": False,
            "process_model": {"title": process.get("name") or "Process being described", "nodes": nodes, "edges": edges}}


def _cell(value: str) -> str:
    return " ".join(str(value).split()).replace("|", "/")


def capture_markdown(model: dict, process_id: str, *, organisation: str, interview: str, captured: str) -> tuple[str, str]:
    """A readable capture of one process for the organisation's space, with the model it came from. Returns the title
    and the Markdown. The sections the registry parser reads (roles, systems, key business rules) are included, and
    the model block gives it the steps and flow exactly."""
    process = pick(model, process_id)
    if process is None or process.get("id") != process_id:
        raise ValueError("No such process in the interview.")
    people = {k: v.get("value", "") for k, v in (model.get("participant") or {}).items()}
    who = people.get("name") or "a participant"
    role = f", {people['role']}" if people.get("role") else ""
    name = process.get("name") or "Unnamed process"
    title = f"{name} · {organisation}"
    steps = ordered(process)
    tasks = [s for s in steps if s.get("kind") == "task"]
    lines = [f"# {title}", "",
             f"Captured in a process interview with {who}{role}, {captured}. Interview {interview}. "
             "Every item below is the participant's account; confirmed items were read back to them and agreed.", ""]
    summary = [(label, _detail(process, field)) for label, field in
               (("Purpose", "purpose"), ("What starts it", "trigger"), ("How it ends", "outcome"), ("How often", "frequency"))]
    if any(value for _, value in summary):
        lines += ["## Summary", ""] + [f"- **{label}:** {value}" for label, value in summary if value] + [""]
    lines += ["## Steps", ""]
    numbering = {s["id"]: n for n, s in enumerate([s for s in steps if s.get("kind") != "end"], start=1)}
    for step in steps:
        if step.get("kind") == "end":
            continue
        n = numbering[step["id"]]
        status = "" if step.get("status") == "confirmed" else f" _({step.get('status', 'heard')})_"
        if step.get("kind") == "decision":
            branches = "; ".join(f"{link.get('label') or 'otherwise'} → step {numbering.get(link['to'], 'end')}"
                                 for link in step.get("next") or [])
            lines.append(f"{n}. **Decision: {step['label']}** {branches}{status}")
        else:
            detail = ", ".join(x for x in (step.get("who") and f"by {step['who']}", step.get("system") and f"in {step['system']}") if x)
            lines.append(f"{n}. {step['label']}{' (' + detail + ')' if detail else ''}{status}")
    lines.append("")
    roles = list(dict.fromkeys(s["who"] for s in tasks if s.get("who")))
    if roles:
        lines += ["## Roles and responsibilities", "", "| Role | Steps |", "|---|---|"]
        lines += [f"| {_cell(r)} | {_cell(', '.join(str(numbering[s['id']]) for s in tasks if s.get('who') == r))} |" for r in roles]
        lines.append("")
    systems = list(dict.fromkeys(s["system"] for s in tasks if s.get("system")))
    if systems:
        lines += ["## Systems and data dependencies", "", "| System | Steps |", "|---|---|"]
        lines += [f"| {_cell(x)} | {_cell(', '.join(str(numbering[s['id']]) for s in tasks if s.get('system') == x))} |" for x in systems]
        lines.append("")
    rules = [f"{s['label'].rstrip('?')}: " + "; ".join(f"{link.get('label') or 'otherwise'}, then "
                                                        f"{next((t['label'] for t in steps if t['id'] == link['to']), 'the end')}"
                                                        for link in s.get("next") or [])
             for s in steps if s.get("kind") == "decision"]
    rules += [f"Control: {c['text']}" for c in process.get("controls") or []]
    if rules:
        lines += ["## Key business rules", ""] + [f"- {rule}" for rule in rules] + [""]
    if process.get("exceptions"):
        lines += ["## Exceptions", ""] + [f"- {x['text']}" + (f" Handled by: {x['handling']}" if x.get("handling") else "")
                                         for x in process["exceptions"]] + [""]
    open_items = [o for o in model.get("open") or [] if o.get("status") != "resolved"]
    if open_items:
        lines += ["## Open points", ""]
        for o in open_items:
            if o.get("kind") == "conflict":
                lines.append(f"- To check: {o.get('field')} of {o.get('item')} was \"{o.get('earlier')}\", later \"{o.get('now')}\"")
            else:
                lines.append(f"- To check: {o.get('text')}")
        lines.append("")
    quotes = [(numbering.get(s["id"]), q["text"]) for s in steps if s.get("kind") != "end" for q in (s.get("quotes") or [])[:1]]
    if quotes:
        lines += ["## In the participant's words", ""] + [f"- Step {n}: \"{text}\"" for n, text in quotes] + [""]
    block = {"schema": SCHEMA_ID, "participant": people, "process": {k: process.get(k) for k in (
        "id", "name", "details", "start", "steps", "exceptions", "controls")}}
    lines += ["## Process model", "", "```json", json.dumps(block, ensure_ascii=False, indent=1), "```", ""]
    return title, "\n".join(lines)


def model_from_capture(text: str) -> dict | None:
    """The process model block of a capture document, as a one-process model; None when the text has none."""
    match = BLOCK.search(text)
    if not match:
        return None
    try:
        block = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    if not isinstance(block, dict) or block.get("schema") != SCHEMA_ID or not isinstance(block.get("process"), dict):
        return None
    process = block["process"]
    return {"schema": SCHEMA_ID, "participant": {k: {"value": v} for k, v in (block.get("participant") or {}).items()},
            "processes": [process], "focus": process.get("id"), "open": []}
