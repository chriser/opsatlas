// Review a process interview (TIBI E5, PI F6): what Tibi captured, process by process, with its map. Edit anything,
// then save a process to its organisation's space: a document that waits for your approval in Governance Review and,
// approved, feeds that space's process registry, activity model and maps.
import { useEffect, useMemo, useState } from "react";
import {
  getProcessInterview,
  saveProcessCapture,
  type InterviewedProcess,
  type ProcessInterviewSession,
  type ProcessModel,
  type ProcessStep,
} from "../api";
import { openDocument } from "../content/api";
import { InterviewMap } from "./InterviewMap";

const STATUS: Record<string, string> = { heard: "Heard", confirmed: "Confirmed", disputed: "To check" };
const DETAILS: [string, string][] = [
  ["purpose", "What it is for"],
  ["trigger", "What starts it"],
  ["outcome", "How it ends"],
  ["frequency", "How often"],
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

export function ProcessReviewPage({ sessionId }: { sessionId: string }) {
  const [session, setSession] = useState<ProcessInterviewSession | null>(null);
  const [draft, setDraft] = useState<ProcessModel | null>(null);
  const [chosen, setChosen] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<Record<string, { source_id: string; title: string }>>({});
  const [edited, setEdited] = useState(false);

  useEffect(() => {
    getProcessInterview(sessionId)
      .then((data) => {
        setSession(data);
        setDraft(data.process_model ? structuredClone(data.process_model) : null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "The interview could not be loaded."));
  }, [sessionId]);

  const settings = session?.evidence.process_interview;
  const process = draft?.processes.find((p) => p.id === chosen) ?? draft?.processes.find((p) => p.id === draft.focus) ?? draft?.processes[0];
  const steps = useMemo(() => (process ? ordered(process) : []), [process]);
  const numbers = new Map(steps.filter((s) => s.kind !== "end").map((s, n) => [s.id, n + 1]));

  function change(update: (p: InterviewedProcess) => void) {
    if (!draft || !process) return;
    const next = structuredClone(draft);
    const target = next.processes.find((p) => p.id === process.id)!;
    update(target);
    setDraft(next);
    setEdited(true);
  }

  function editStep(id: string, field: "label" | "who" | "system", value: string) {
    // Your edit is your confirmation of that step.
    change((p) => {
      const step = p.steps.find((s) => s.id === id);
      if (step) Object.assign(step, { [field]: value, status: "confirmed" });
    });
  }

  async function save() {
    if (!draft || !process || !settings) return;
    setSaving(true);
    setError(null);
    try {
      const result = await saveProcessCapture(settings.space, draft, process.id, sessionId, settings.space_name || settings.space);
      setSaved({ ...saved, [process.id]: result });
    } catch (e) {
      setError(e instanceof Error ? e.message : "The process could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  if (error && !session) return <div className="panel"><p className="tibi-alert">{error}</p></div>;
  if (!session) return <div className="panel"><p className="muted-text">Loading the interview…</p></div>;
  const people = draft?.participant ?? {};
  const open = (draft?.open ?? []).filter((o) => o.status !== "resolved");
  const pending = session.process_pending?.length ?? 0;
  const done = process ? saved[process.id] : undefined;

  return (
    <div className="page-stack process-review">
      <div className="page-heading">
        <h1>Review a process interview</h1>
        <p>
          {settings?.space_name || settings?.space} · with {people.name?.value ?? "a participant"}
          {people.role ? `, ${people.role.value}` : ""}
          {people.team ? ` (${people.team.value})` : ""} · {session.status === "active" ? "in progress" : session.status}
        </p>
      </div>
      {pending ? (
        <p className="tibi-alert tibi-alert--soft">
          {pending} answer{pending === 1 ? " is" : "s are"} still waiting to be noted. Continue the interview and Tibi will note {pending === 1 ? "it" : "them"} first.
        </p>
      ) : null}
      {!draft || !draft.processes.length ? (
        <div className="panel"><p className="muted-text">Nothing about a process has been captured yet.</p></div>
      ) : (
        <>
          {draft.processes.length > 1 ? (
            <div className="imap-tabs review-tabs" role="tablist">
              {draft.processes.map((p) => (
                <button key={p.id} type="button" role="tab" aria-selected={p.id === process?.id} onClick={() => setChosen(p.id)}>
                  {p.name || "Unnamed"} · {p.steps.filter((s) => s.kind !== "end").length} steps
                </button>
              ))}
            </div>
          ) : null}
          {process ? (
            <div className="review-grid">
              <div className="panel review-map">
                <InterviewMap space={settings?.space ?? ""} model={{ ...draft, focus: process.id }} title="Map" />
              </div>
              <div className="panel review-detail">
                <div className="panel-heading">
                  <div>
                    <h2>
                      <input
                        className="review-name"
                        value={process.name}
                        placeholder="Name this process"
                        aria-label="Process name"
                        onChange={(e) => change((p) => (p.name = e.target.value))}
                      />
                    </h2>
                    <p className="muted-text">Edit anything that is not right. An edited step counts as confirmed by you.</p>
                  </div>
                </div>
                <div className="review-details">
                  {DETAILS.map(([field, label]) => (
                    <label key={field} className="field-label">
                      {label}
                      <input
                        value={process.details[field]?.value ?? ""}
                        onChange={(e) =>
                          change((p) => {
                            p.details[field] = { value: e.target.value, quote: p.details[field]?.quote ?? "", turn: p.details[field]?.turn ?? 0, status: "confirmed" };
                          })
                        }
                      />
                    </label>
                  ))}
                </div>
                <div className="table-frame">
                  <table className="data-table review-steps">
                    <thead>
                      <tr><th>#</th><th>Step</th><th>Who</th><th>System</th><th>Status</th></tr>
                    </thead>
                    <tbody>
                      {steps.filter((s) => s.kind !== "end").map((s) => (
                        <tr key={s.id} className={`review-step review-step--${s.status}`}>
                          <td>{numbers.get(s.id)}</td>
                          <td>
                            <input value={s.label} aria-label="Step" onChange={(e) => editStep(s.id, "label", e.target.value)} />
                            {s.kind === "decision" ? (
                              <small className="review-branches">
                                {s.next.map((n) => `${n.label || "otherwise"} → ${numbers.get(n.to) ? `step ${numbers.get(n.to)}` : "end"}`).join(" · ")}
                              </small>
                            ) : null}
                            {s.quotes[0] ? <small className="review-quote">“{s.quotes[0].text}”</small> : null}
                          </td>
                          <td>{s.kind === "task" ? <input value={s.who} aria-label="Who" onChange={(e) => editStep(s.id, "who", e.target.value)} /> : "—"}</td>
                          <td>{s.kind === "task" ? <input value={s.system} aria-label="System" onChange={(e) => editStep(s.id, "system", e.target.value)} /> : "—"}</td>
                          <td><span className={`status-pill review-status review-status--${s.status}`}>{STATUS[s.status] ?? s.status}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {process.exceptions.length || process.controls.length ? (
                  <div className="review-notes">
                    {process.exceptions.length ? (
                      <div>
                        <b>What goes wrong</b>
                        <ul>{process.exceptions.map((x) => <li key={x.id}>{x.text}{x.handling ? ` — ${x.handling}` : ""}</li>)}</ul>
                      </div>
                    ) : null}
                    {process.controls.length ? (
                      <div>
                        <b>Checks and approvals</b>
                        <ul>{process.controls.map((c) => <li key={c.id}>{c.text}</li>)}</ul>
                      </div>
                    ) : null}
                  </div>
                ) : null}
                {open.length ? (
                  <p className="muted-text">
                    {open.length} point{open.length === 1 ? "" : "s"} still to check (listed under the map). They are saved as open points; settle them by
                    continuing the interview, or by editing the step here.
                  </p>
                ) : null}
                {error ? <p className="tibi-alert">{error}</p> : null}
                {done ? (
                  <div className="space-notice" role="status">
                    Saved as “{done.title}”. It waits for your approval in Governance Review; once approved, it feeds{" "}
                    {settings?.space_name}'s process registry, activity model and maps.
                    <div className="review-saved-actions">
                      <button type="button" className="secondary-button" onClick={() => openDocument(done.source_id, undefined, settings?.space)}>
                        Open the document
                      </button>
                      <button type="button" className="secondary-button" onClick={() => (window.location.hash = "#governance")}>
                        Governance Review
                      </button>
                    </div>
                  </div>
                ) : null}
                <div className="review-actions">
                  <button type="button" className="primary-button" disabled={saving || !process.name.trim()} onClick={() => void save()}>
                    {saving ? "Saving…" : `${done ? "Save again" : "Save"} to ${settings?.space_name || "the organisation"}`}
                  </button>
                  <button type="button" className="secondary-button" onClick={() => (window.location.hash = "#tibi")}>
                    Continue the interview
                  </button>
                  {edited ? <span className="muted-text">Your edits go into the saved document; the interview keeps what was said.</span> : null}
                </div>
              </div>
            </div>
          ) : null}
        </>
      )}
    </div>
  );
}
