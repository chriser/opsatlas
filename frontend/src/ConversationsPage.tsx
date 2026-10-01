// The conversation log (OBS F2): review Tibi's conversations turn by turn and mark what to improve.
import { useEffect, useState } from "react";
import { apiRequest } from "./api";
import { HoverTip } from "./HoverTip";
import { couldNotLoad, useLoad } from "./ui";

export interface ConversationSession {
  session: string;
  started: string;
  last: string;
  turns: number;
  modes: string[];
  engines: string[];
  first: string;
  marks: Partial<Record<Verdict, number>>;
  issues: number;
  median_first_segment_ms: number | null;
}

type Verdict = "good" | "odd" | "wrong";

export interface ConversationTurn {
  at: string;
  session: string;
  turn: number;
  mode?: string;
  engine?: { version: string; fingerprint: string };
  heard: string;
  reply: string;
  route?: string;
  route_reasons?: string[];
  grounding?: string;
  records?: string[];
  guidance?: string[];
  timings?: Record<string, number>;
  interrupted?: boolean;
  issue?: string | null;
  typed?: boolean;
  review?: { verdict: Verdict; note: string | null; at: string } | null;
}

const getSessions = () => apiRequest<{ sessions: ConversationSession[] }>("GET", "/api/conversations");
const getSession = (id: string) => apiRequest<{ turns: ConversationTurn[] }>("GET", `/api/conversations/${encodeURIComponent(id)}`);
const getFlagged = () => apiRequest<{ turns: ConversationTurn[] }>("GET", "/api/conversations/flagged");
const markTurn = (id: string, turn: number, verdict: Verdict | null, note: string) =>
  apiRequest("PUT", `/api/conversations/${encodeURIComponent(id)}/turns/${turn}/review`, { verdict, note });

const VERDICTS: { key: Verdict; label: string }[] = [
  { key: "good", label: "Good" },
  { key: "odd", label: "Odd" },
  { key: "wrong", label: "Wrong" },
];

function when(iso: string) {
  const d = new Date(iso);
  return `${d.toLocaleDateString(undefined, { day: "numeric", month: "short" })}, ${d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}`;
}

function TurnCard({ turn, onMarked }: { turn: ConversationTurn; onMarked: () => void }) {
  const [verdict, setVerdict] = useState<Verdict | null>(turn.review?.verdict ?? null);
  const [note, setNote] = useState(turn.review?.note ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dirty = verdict !== (turn.review?.verdict ?? null) || note !== (turn.review?.note ?? "");

  async function save(next: Verdict | null, text = note) {
    setSaving(true);
    setError(null);
    try {
      await markTurn(turn.session, turn.turn, next, text);
      setVerdict(next);
      onMarked();
    } catch (e) {
      setError(e instanceof Error ? e.message : "The mark was not saved");
    } finally {
      setSaving(false);
    }
  }

  const first = turn.timings?.first_segment;
  return (
    <article className={`convo-turn${verdict ? ` convo-turn--${verdict}` : ""}`}>
      <header className="convo-turn-head">
        <span className="convo-turn-n">Turn {turn.turn + 1}</span>
        <span className="muted-text">{when(turn.at)}</span>
        {turn.route ? (
          <HoverTip tip={turn.route_reasons?.length ? <span>Why: {turn.route_reasons.join("; ")}</span> : <span>No specific reason recorded</span>}>
            <span className="status-pill convo-route">{turn.route}</span>
          </HoverTip>
        ) : null}
        {turn.grounding && turn.grounding !== turn.route ? <span className="status-pill">{turn.grounding.replace(/_/g, " ")}</span> : null}
        {first !== undefined ? <span className={`status-pill${first > 1500 ? " status-pill--warn" : ""}`}>{Math.round(first)} ms</span> : null}
        {turn.engine ? <span className="status-pill convo-engine" title={`Fingerprint ${turn.engine.fingerprint}`}>engine {turn.engine.version}</span> : null}
        {turn.interrupted ? <span className="status-pill status-pill--warn">interrupted</span> : null}
        {turn.issue && turn.issue !== "none" ? <span className="status-pill status-pill--warn">{turn.issue.replace(/_/g, " ")}</span> : null}
      </header>
      <p className="convo-line convo-line--you">
        <b>{turn.typed ? "You typed" : "You"}</b>
        {turn.heard}
      </p>
      <p className="convo-line convo-line--tibi">
        <b>Tibi</b>
        {turn.reply}
      </p>
      {turn.records?.length || turn.guidance?.length ? (
        <p className="convo-used muted-text">
          {turn.records?.length ? `Records: ${turn.records.join(", ")}` : ""}
          {turn.records?.length && turn.guidance?.length ? " · " : ""}
          {turn.guidance?.length ? `Guidance: ${turn.guidance.join(", ")}` : ""}
        </p>
      ) : null}
      <div className="convo-mark">
        <span className="segmented-control" role="group" aria-label="Mark this turn">
          {VERDICTS.map((v) => (
            <button
              key={v.key}
              type="button"
              className={verdict === v.key ? `is-active convo-mark--${v.key}` : ""}
              disabled={saving}
              onClick={() => (verdict === v.key ? void save(null, "") : v.key === "good" ? void save("good") : setVerdict(v.key))}
            >
              {v.label}
            </button>
          ))}
        </span>
        {verdict === "odd" || verdict === "wrong" ? (
          <>
            <input className="convo-note" value={note} placeholder="What should Tibi have done?" onChange={(e) => setNote(e.target.value)} />
            <button type="button" className="primary-button" disabled={saving || !dirty} onClick={() => void save(verdict)}>
              {saving ? "Saving…" : "Save"}
            </button>
          </>
        ) : null}
        {error ? <span className="cm-inline-error">{error}</span> : null}
      </div>
    </article>
  );
}

// Where a session came from, when it is not a plain voice chat.
const MODES: Record<string, string> = {
  digital_sme: "Digital SME",
  rehearsal: "Rehearsal",
  product_interview: "Product interview",
  governance_interview: "Governance interview",
};

export function ConversationsPage() {
  const [tab, setTab] = useState<"sessions" | "improve">("sessions");
  const [sessions, setSessions] = useState<ConversationSession[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [flagged, setFlagged] = useState<ConversationTurn[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [s, f] = await Promise.all([getSessions(), getFlagged()]);
      setSessions(s.sessions);
      setFlagged(f.turns);
      setSelected((current) => current ?? s.sessions[0]?.session ?? null);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "The conversation log could not be read");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  // The selected conversation's turns. An answer shows only under the conversation it belongs to, so a slow answer
  // for one clicked earlier never appears under the one clicked last.
  const detail = useLoad(
    async () => (selected ? { session: selected, turns: (await getSession(selected)).turns } : null),
    [selected],
  );
  const turns = detail.data && detail.data.session === selected ? detail.data.turns : [];

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Conversation log</h1>
        <p>Every Tibi turn, with the route it took, how long it took and the engine that answered. Mark turns to improve.</p>
      </div>
      <span className="segmented-control convo-tabs" role="tablist">
        <button type="button" className={tab === "sessions" ? "is-active" : ""} onClick={() => setTab("sessions")}>
          Conversations
        </button>
        <button type="button" className={tab === "improve" ? "is-active" : ""} onClick={() => setTab("improve")}>
          To improve ({flagged.length})
        </button>
      </span>
      {error ? <p className="cm-inline-error">{error}</p> : null}
      {tab === "improve" ? (
        <div className="panel convo-improve">
          {flagged.length === 0 ? (
            <div className="empty-card">
              <b>Nothing marked yet</b>
              <span>Mark a turn as odd or wrong, with a note, and it is listed here.</span>
            </div>
          ) : (
            flagged.map((t) => <TurnCard key={`${t.session}-${t.turn}`} turn={t} onMarked={() => void load()} />)
          )}
        </div>
      ) : sessions === null ? (
        <p className="muted-text">Reading the conversation log…</p>
      ) : sessions.length === 0 ? (
        <div className="empty-card">
          <b>No conversations yet</b>
          <span>Talk with Tibi and each turn is recorded here.</span>
        </div>
      ) : (
        <div className="convo-layout">
          <nav className="panel convo-sessions" aria-label="Conversations">
            {sessions.map((s) => (
              <button
                key={s.session}
                type="button"
                className={`convo-session${selected === s.session ? " convo-session--active" : ""}`}
                onClick={() => setSelected(s.session)}
              >
                <span className="convo-session-when">
                  {when(s.started)}
                  {s.modes.filter((m) => m !== "chat").map((m) => (
                    <span key={m} className="convo-mode">{MODES[m] ?? m.replace(/_/g, " ")}</span>
                  ))}
                </span>
                <span className="convo-session-first">{s.first || "(no words)"}</span>
                <span className="convo-session-meta">
                  {s.turns} turn{s.turns === 1 ? "" : "s"}
                  {s.engines.length ? ` · engine ${s.engines.join(", ")}` : ""}
                  {s.median_first_segment_ms !== null ? ` · ${Math.round(s.median_first_segment_ms)} ms` : ""}
                </span>
                <span className="convo-session-marks">
                  {(Object.entries(s.marks) as [Verdict, number][]).map(([v, n]) => (
                    <span key={v} className={`convo-dot convo-dot--${v}`}>
                      {n} {v}
                    </span>
                  ))}
                  {s.issues ? <span className="convo-dot convo-dot--odd">{s.issues} issue{s.issues === 1 ? "" : "s"}</span> : null}
                </span>
              </button>
            ))}
          </nav>
          <section className="panel convo-turns" aria-label="Turns">
            {detail.error && turns.length === 0 ? (
              <p className="cm-inline-error">{couldNotLoad("this conversation", detail.error)}</p>
            ) : null}
            {turns.map((t) => (
              <TurnCard key={`${t.session}-${t.turn}-${t.review?.at ?? ""}`} turn={t} onMarked={() => void load()} />
            ))}
          </section>
        </div>
      )}
    </div>
  );
}
