// A step on the live process map, clicked (TIBI E5, PI F9): change it by hand, or tell Tibi about it.
// Changes made here apply at once and count as confirmed; Tibi is not asked to interpret them.
import { useEffect, useState } from "react";
import type { InterviewedProcess, ProcessModel, ProcessStep } from "../api";

export type ProcessEdit =
  | { op: "label" | "who" | "system" | "with" | "gateway"; item: string; value: string }
  | { op: "remove"; item: string }
  | { op: "move"; item: string; after: string }
  | { op: "repath"; item: string; items: string[]; path: string; condition: string }
  | { op: "branch"; item: string; question: string; condition: string; first: string }
  | { op: "add"; item: string; value: string; who: string };

const KINDS: [string, string][] = [
  ["xor", "XOR: only one path is followed"],
  ["or", "ANY: any number of paths may be followed"],
  ["and", "AND: all paths are followed"],
];

function ordered(process: InterviewedProcess): ProcessStep[] {
  const byId = new Map(process.steps.map((s) => [s.id, s]));
  const seen = new Set<string>();
  const out: ProcessStep[] = [];
  const walk = (id: string) => {
    const stack = [id];
    while (stack.length) {
      const current = stack.pop()!;
      const step = byId.get(current);
      if (!step || seen.has(current)) continue;
      seen.add(current);
      out.push(step);
      stack.push(...[...step.next].reverse().map((n) => n.to));
    }
  };
  if (process.start) walk(process.start);
  process.steps.forEach((s) => walk(s.id));
  return out;
}

export function StepPanel({
  model,
  stepId,
  live,
  onEdit,
  onComment,
  onClose,
}: {
  model: ProcessModel;
  stepId: string;
  live: boolean;
  onEdit: (change: ProcessEdit) => void;
  onComment: (text: string) => void;
  onClose: () => void;
}) {
  const process = model.processes.find((p) => p.steps.some((s) => s.id === stepId));
  const step = process?.steps.find((s) => s.id === stepId);
  const [fields, setFields] = useState({ label: "", who: "", with: "", system: "" });
  const [path, setPath] = useState("");
  const [after, setAfter] = useState("");
  const [branch, setBranch] = useState({ condition: "", first: "" });
  const [next, setNext] = useState({ label: "", who: "" });
  const [comment, setComment] = useState("");
  useEffect(() => {
    if (step) setFields({ label: step.label, who: step.who, with: step.with ?? "", system: step.system });
    // Only when another step is chosen: an edit arriving from Tibi should not wipe what is being typed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stepId]);
  if (!process || !step) return null;
  const others = ordered(process).filter((s) => s.id !== step.id && s.kind !== "end");
  const task = step.kind === "task";
  const changed = (["label", "who", "with", "system"] as const).filter((f) => (task || f === "label") && fields[f].trim() !== (step[f] ?? ""));
  // The paths of the process's decisions, for a step put on the wrong one ("it belongs under the second option").
  const paths = process.steps
    .filter((s) => s.kind === "decision")
    .flatMap((d) => d.next.filter((n) => n.label).map((n) => {
      const target = process.steps.find((s) => s.id === n.to);
      return { value: target?.kind === "open" ? target.id : `${d.id}|${n.label}`, label: `${d.label.replace(/\?$/, "")}: ${n.label}` };
    }));

  function save(event: React.FormEvent) {
    event.preventDefault();
    for (const field of changed) onEdit({ op: field, item: step!.id, value: fields[field].trim() });
  }

  return (
    <section className="step-panel" aria-label={`Step: ${step.label}`}>
      <header className="step-panel-head">
        <div>
          <b>{step.kind === "decision" ? "Decision" : "Step"}</b>
          <span className={`status-pill review-status review-status--${step.status}`}>
            {step.status === "confirmed" ? "Confirmed" : step.status === "disputed" ? "To check" : "Heard"}
          </span>
        </div>
        <button type="button" className="text-button" onClick={onClose} aria-label="Close">
          Close
        </button>
      </header>
      {!live ? <p className="muted-text">Continue the interview to change the map.</p> : null}
      <fieldset disabled={!live}>
        <form className="step-panel-fields" onSubmit={save}>
          <label className="field-label">
            {task ? "What happens" : "The question"}
            <input value={fields.label} maxLength={120} onChange={(e) => setFields({ ...fields, label: e.target.value })} />
          </label>
          {task ? (
            <div className="step-panel-row">
              <label className="field-label">
                Who
                <input value={fields.who} maxLength={80} placeholder="e.g. cashier" onChange={(e) => setFields({ ...fields, who: e.target.value })} />
              </label>
              <label className="field-label">
                Also taking part
                <input value={fields.with} maxLength={80} placeholder="e.g. customer" onChange={(e) => setFields({ ...fields, with: e.target.value })} />
              </label>
              <label className="field-label">
                System or tool
                <input value={fields.system} maxLength={80} placeholder="none" onChange={(e) => setFields({ ...fields, system: e.target.value })} />
              </label>
            </div>
          ) : null}
          <button type="submit" className="primary-button" disabled={!changed.length || !fields.label.trim()}>
            Save
          </button>
        </form>
        {step.kind === "decision" ? (
          <label className="field-label">
            How many paths are followed
            <select value={step.gateway || "xor"} onChange={(e) => onEdit({ op: "gateway", item: step.id, value: e.target.value })}>
              {KINDS.map(([value, text]) => (
                <option key={value} value={value}>
                  {text}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        {task && paths.length ? (
          <div className="step-panel-row step-panel-actions">
            <label className="field-label">
              Move it to the path
              <select value={path} onChange={(e) => setPath(e.target.value)}>
                <option value="">Choose a path…</option>
                {paths.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="secondary-button"
              disabled={!path}
              onClick={() => {
                const [target, condition = ""] = path.split("|");
                onEdit({ op: "repath", item: step.id, items: [step.id], path: target, condition });
                setPath("");
              }}
            >
              Move to path
            </button>
          </div>
        ) : null}
        <div className="step-panel-row step-panel-actions">
          <label className="field-label">
            Move it to after
            <select value={after} onChange={(e) => setAfter(e.target.value)}>
              <option value="">Choose a step…</option>
              <option value="start">(the very start)</option>
              {others.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
          <button type="button" className="secondary-button" disabled={!after} onClick={() => after && onEdit({ op: "move", item: step.id, after })}>
            Move
          </button>
          <button
            type="button"
            className="reject-button"
            onClick={() => window.confirm(`Remove “${step.label}” from the map?`) && onEdit({ op: "remove", item: step.id })}
          >
            Remove
          </button>
        </div>
        {step.kind === "task" || step.kind === "open" ? (
          <form
            className="step-panel-branch"
            onSubmit={(e) => {
              e.preventDefault();
              if (!next.label.trim()) return;
              onEdit({ op: "add", item: step.id, value: next.label.trim(), who: next.who.trim() });
              setNext({ label: "", who: "" });
            }}
          >
            <b>{step.kind === "open" ? "The first step on this path" : "A step after this one"}</b>
            <div className="step-panel-row">
              <label className="field-label">
                What happens
                <input value={next.label} maxLength={120} placeholder="e.g. Check the customer's ID" onChange={(e) => setNext({ ...next, label: e.target.value })} />
              </label>
              <label className="field-label">
                Who does it
                <input value={next.who} maxLength={80} placeholder={step.who || "e.g. Cashier"} onChange={(e) => setNext({ ...next, who: e.target.value })} />
              </label>
            </div>
            <button type="submit" className="secondary-button" disabled={!next.label.trim()}>
              Add the step
            </button>
          </form>
        ) : null}
        <form
          className="step-panel-branch"
          onSubmit={(e) => {
            e.preventDefault();
            if (!branch.first.trim()) return;
            onEdit({ op: "branch", item: step.id, question: "", condition: branch.condition.trim(), first: branch.first.trim() });
            setBranch({ condition: "", first: "" });
          }}
        >
          <b>A different path after this step</b>
          <div className="step-panel-row">
            <label className="field-label">
              When
              <input value={branch.condition} maxLength={80} placeholder="e.g. Energy drink" onChange={(e) => setBranch({ ...branch, condition: e.target.value })} />
            </label>
            <label className="field-label">
              What happens first
              <input value={branch.first} maxLength={120} placeholder="e.g. Check they look over 16" onChange={(e) => setBranch({ ...branch, first: e.target.value })} />
            </label>
          </div>
          <button type="submit" className="secondary-button" disabled={!branch.first.trim()}>
            Add the path
          </button>
        </form>
        <form
          className="step-panel-comment"
          onSubmit={(e) => {
            e.preventDefault();
            if (!comment.trim()) return;
            onComment(comment.trim());
            setComment("");
          }}
        >
          <label className="field-label">
            Or tell Tibi about it
            <textarea rows={2} maxLength={1000} value={comment} placeholder="Tibi will say what it understood before changing anything." onChange={(e) => setComment(e.target.value)} />
          </label>
          <button type="submit" className="secondary-button" disabled={!comment.trim()}>
            Send to Tibi
          </button>
        </form>
      </fieldset>
    </section>
  );
}
