// The document's side panels (CM S15, S19, S21–S24) and the version compare view (CM S16).
import { useState } from "react";
import { OPERATOR } from "../operator";
import { InlineTitle, LocationCard } from "./LibraryControls";
import {
  timeAgo,
  type ActivityEntry,
  type Comment,
  type ContentDocument,
  type DiffOp,
  type SettledSuggestion,
  type Suggestion,
  type VersionEntry,
} from "./api";

export function Avatar({ name }: { name: string }) {
  if (name === OPERATOR.name) return <img className="cm-avatar" src={OPERATOR.photo} alt="" />;
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase())
    .join("");
  return <span className={`cm-avatar cm-avatar--initials${name === "Tibi" ? " cm-avatar--tibi" : ""}`}>{initials || "?"}</span>;
}

function Row({ label, value, hint, onClick }: { label: string; value: React.ReactNode; hint?: string; onClick?: () => void }) {
  const body = (
    <>
      <span className="cm-row-label">
        {label}
        {hint ? <small>{hint}</small> : null}
      </span>
      <span className="cm-row-value">{value}</span>
    </>
  );
  return onClick ? (
    <button type="button" className="cm-row cm-row--link" onClick={onClick}>
      {body}
      <span className="cm-row-chevron">›</span>
    </button>
  ) : (
    <div className="cm-row">{body}</div>
  );
}

const STATUS_TEXT: Record<string, string> = { published: "Published", draft: "Draft", submitted: "Waiting for approval" };

export function OverviewPanel({
  doc,
  suggestions,
  settled,
  onShow,
}: {
  doc: ContentDocument;
  suggestions: Suggestion[];
  settled: SettledSuggestion[];
  onShow: (panel: "comments" | "versions" | "activity" | "details") => void;
}) {
  const corrected = settled.filter((s) => s.outcome === "corrected").length;
  const accepted = settled.filter((s) => s.outcome === "accepted").length;
  const settledHint = [corrected ? `${corrected} corrected` : "", accepted ? `${accepted} accepted as they are` : ""].filter(Boolean).join(", ");
  const stats = doc.draft?.stats ?? doc.published.stats;
  const overlaps = suggestions.filter((s) => s.kind === "duplicate").length;
  const conflicts = suggestions.filter((s) => s.kind === "conflict").length;
  const open = suggestions.filter((s) => !s.answer).length;
  const last = doc.last_activity;
  return (
    <div className="cm-panel-body">
      <div className="cm-card">
        <Row label="Status" value={<span className={`status-pill cm-status cm-status--${doc.status}`}>{STATUS_TEXT[doc.status]}</span>} />
        <Row label="Version" value={`v${doc.source.version}`} hint={doc.draft ? "The draft is not live yet" : "Live for answers and Tibi"} />
        <Row
          label="Approval"
          value={
            <span className={`status-pill${doc.source.approval_status === "approved" ? " status-pill--good" : doc.source.approval_status === "rejected" ? " status-pill--warn" : ""}`}>
              {doc.source.approval_status}
            </span>
          }
        />
        {doc.record ? (
          <Row
            label="Tibi uses this record"
            value={<span className={`status-pill${doc.record.eligible ? " status-pill--good" : ""}`}>{doc.record.eligible ? "yes" : "not yet"}</span>}
            hint={doc.record.review_block ?? undefined}
          />
        ) : null}
      </div>
      <div className="cm-card">
        <h3 className="cm-card-title">Content audit</h3>
        <Row label="Word count" value={<span className="cm-chip">{stats.words} words</span>} hint={`About ${stats.reading_minutes} min to read`} />
        <Row
          label="Readability"
          value={<span className="cm-chip">{stats.grade === null ? "—" : `Grade ${Math.round(stats.grade)}`}</span>}
          hint={stats.readability ? `${stats.readability} (reading ease ${Math.round(stats.flesch ?? 0)})` : undefined}
        />
        <Row
          label="Content suggestions"
          value={<span className={`cm-chip${open ? " cm-chip--amber" : ""}`}>{open}</span>}
          hint={[conflicts ? `${conflicts} possible conflict${conflicts === 1 ? "" : "s"}` : "", settledHint].filter(Boolean).join("; ") || "From governance checks"}
          onClick={() => onShow("comments")}
        />
        <Row
          label="Overlap with other records"
          value={<span className="cm-chip">{overlaps}</span>}
          hint="From the statement-level review"
          onClick={() => onShow("comments")}
        />
      </div>
      <button type="button" className="cm-card cm-link-card" onClick={() => onShow("activity")}>
        <span>
          <small className="muted-text">Last modified by</small>
          <b>{last ? `${last.actor}, ${timeAgo(last.at)}` : "No changes yet"}</b>
        </span>
        <span className="cm-row-chevron">›</span>
      </button>
      <button type="button" className="cm-card cm-link-card" onClick={() => onShow("comments")}>
        <b>Comments ({doc.comments.open})</b>
        <span className="cm-row-chevron">›</span>
      </button>
      <button type="button" className="cm-card cm-link-card" onClick={() => onShow("versions")}>
        <b>Version history ({doc.versions})</b>
        <span className="cm-row-chevron">›</span>
      </button>
      <button type="button" className="cm-card cm-link-card" onClick={() => onShow("details")}>
        <b>Details and scope</b>
        <span className="cm-row-chevron">›</span>
      </button>
    </div>
  );
}

function Clamp({ text, lines = 3 }: { text: string; lines?: number }) {
  const [open, setOpen] = useState(false);
  const long = text.length > 180;
  return (
    <>
      <span className={open || !long ? "" : "cm-clamp"} style={{ WebkitLineClamp: lines }}>
        {text}
      </span>
      {long ? (
        <button type="button" className="cm-link" onClick={() => setOpen((v) => !v)}>
          {open ? "Show less" : "Show more"}
        </button>
      ) : null}
    </>
  );
}

export function CommentsPanel({
  comments,
  suggestions,
  settled,
  draftText,
  activeId,
  composer,
  editable,
  onReveal,
  onAdd,
  onCancelComposer,
  onReply,
  onResolve,
  onDelete,
  onApplyFix,
  onAccept,
  onReopen,
}: {
  comments: Comment[];
  suggestions: Suggestion[];
  settled: SettledSuggestion[];
  draftText: string | null;
  activeId: string | null;
  composer: { quote: string } | null;
  editable: boolean;
  onReveal: (id: string) => void;
  onAdd: (text: string) => Promise<void>;
  onCancelComposer: () => void;
  onReply: (id: string, text: string) => Promise<void>;
  onResolve: (id: string, resolved: boolean) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onApplyFix: (s: Suggestion) => void;
  onAccept: (s: Suggestion, note: string) => Promise<void>;
  onReopen: (id: string) => Promise<void>;
}) {
  const [draft, setDraft] = useState("");
  const open = comments.filter((c) => c.status === "open");
  const resolved = comments.filter((c) => c.status === "resolved");
  return (
    <div className="cm-panel-body">
      {composer ? (
        <div className="cm-thread cm-thread--active">
          <div className="cm-quote">
            <Clamp text={composer.quote} />
          </div>
          <textarea autoFocus rows={3} placeholder="Write a comment…" value={draft} onChange={(e) => setDraft(e.target.value)} />
          <div className="cm-thread-actions">
            <button type="button" className="secondary-button" onClick={() => { setDraft(""); onCancelComposer(); }}>
              Cancel
            </button>
            <button
              type="button"
              className="primary-button"
              disabled={!draft.trim()}
              onClick={() => void onAdd(draft).then(() => setDraft(""))}
            >
              Comment
            </button>
          </div>
        </div>
      ) : null}
      {suggestions.length ? (
        <div className="cm-group">
          <h3 className="cm-card-title">Suggestions from governance ({suggestions.length})</h3>
          {suggestions.map((s) => (
            <SuggestionCard
              key={s.key}
              suggestion={s}
              active={activeId === s.key}
              editable={editable}
              fixedInDraft={Boolean(draftText && s.acronyms?.some((a) => draftText.includes(`(${a})`)))}
              onReveal={onReveal}
              onApplyFix={onApplyFix}
              onAccept={onAccept}
            />
          ))}
        </div>
      ) : null}
      {settled.length ? (
        <details className="cm-group cm-settled-group" open>
          <summary>
            Settled ({settled.length})
            <span className="cm-settled-counts">
              {(["corrected", "accepted", "resolved"] as const).map((o) => {
                const n = settled.filter((x) => x.outcome === o).length;
                return n ? <span key={o} className={`cm-outcome cm-outcome--${o}`}>{n} {o}</span> : null;
              })}
            </span>
          </summary>
          {settled.map((x) => (
            <div key={x.id} className={`cm-settled cm-settled--${x.outcome}`}>
              <div className="cm-settled-head">
                <span className={`cm-outcome cm-outcome--${x.outcome}`}>{x.words}</span>
                <small>
                  {x.actor}, {new Date(x.at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}
                </small>
              </div>
              <p>{x.text}</p>
              {x.note ? <p className="cm-settled-note">{x.outcome === "accepted" ? `Reason: ${x.note}` : x.note}</p> : null}
              {x.outcome === "accepted" ? (
                <button type="button" className="text-button" onClick={() => void onReopen(x.id)}>
                  Reopen
                </button>
              ) : null}
            </div>
          ))}
        </details>
      ) : null}
      <div className="cm-group">
        <h3 className="cm-card-title">Comments ({open.length})</h3>
        {!open.length && !composer ? <p className="muted-text">No open comments. Select text in the document to comment on it.</p> : null}
        {open.map((c) => (
          <Thread key={c.id} comment={c} active={activeId === c.id} onReveal={onReveal} onReply={onReply} onResolve={onResolve} onDelete={onDelete} />
        ))}
      </div>
      {resolved.length ? (
        <details className="cm-group">
          <summary>Resolved ({resolved.length})</summary>
          {resolved.map((c) => (
            <Thread key={c.id} comment={c} active={activeId === c.id} onReveal={onReveal} onReply={onReply} onResolve={onResolve} onDelete={onDelete} />
          ))}
        </details>
      ) : null}
    </div>
  );
}

/** An open suggestion. Its status says whether it is still open, fixed in the draft (publish to record the
 *  correction) or answered through Tibi; it can be fixed in one click, or accepted as it is with a reason. */
function SuggestionCard({
  suggestion: s,
  active,
  editable,
  fixedInDraft,
  onReveal,
  onApplyFix,
  onAccept,
}: {
  suggestion: Suggestion;
  active: boolean;
  editable: boolean;
  fixedInDraft: boolean;
  onReveal: (id: string) => void;
  onApplyFix: (s: Suggestion) => void;
  onAccept: (s: Suggestion, note: string) => Promise<void>;
}) {
  const [accepting, setAccepting] = useState(false);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const between = s.kind === "conflict" || s.kind === "duplicate";
  const status = s.answer
    ? { text: s.answer === "pending" ? "Answered, waiting for approval" : `Answer ${s.answer}`, tone: "answered" }
    : fixedInDraft
      ? { text: "Fixed in the draft", tone: "draft" }
      : { text: "Open", tone: "open" };
  return (
    <div className={`cm-thread cm-thread--suggestion${active ? " cm-thread--active" : ""}`}>
      <div className="cm-thread-head">
        <Avatar name="Tibi" />
        <span className="cm-thread-who">
          <b>{s.label}</b>
          <small>Tibi · governance</small>
        </span>
        <span className={`cm-outcome cm-outcome--${status.tone}`}>{status.text}</span>
      </div>
      {s.quote ? (
        <button type="button" className="cm-quote cm-quote--button" onClick={() => onReveal(s.key)}>
          <Clamp text={s.quote} />
        </button>
      ) : null}
      <p>{s.text}</p>
      {s.other ? (
        <div className="cm-other">
          <small>{s.other.title} says:</small>
          <Clamp text={s.other.text} />
        </div>
      ) : null}
      {s.hint ? <p className="result-cite">{s.hint}</p> : null}
      {fixedInDraft ? <p className="result-cite">Publish the draft to record this as corrected.</p> : null}
      {between ? <p className="result-cite">Settle it with Tibi from the Governance page, or edit the passage here.</p> : null}
      {accepting ? (
        <div className="cm-accept">
          <input
            autoFocus
            value={reason}
            placeholder="Why keep it as it is? (optional)"
            aria-label="Reason for keeping it"
            onChange={(e) => setReason(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Escape") setAccepting(false);
            }}
          />
          <div className="cm-thread-actions">
            <button type="button" className="secondary-button" disabled={saving} onClick={() => setAccepting(false)}>
              Cancel
            </button>
            <button
              type="button"
              className="approve-button"
              disabled={saving}
              onClick={() => {
                setSaving(true);
                void onAccept(s, reason).finally(() => setSaving(false));
              }}
            >
              Accept as it is
            </button>
          </div>
        </div>
      ) : s.fix || (!between && !s.answer) ? (
        <div className="cm-thread-actions">
          {!between && !s.answer ? (
            <button type="button" className="secondary-button" title="Keep the wording; governance and Tibi stop raising it here" onClick={() => setAccepting(true)}>
              Accept as it is
            </button>
          ) : null}
          {s.fix && !fixedInDraft ? (
            <button type="button" className="primary-button" disabled={!editable} title={editable ? undefined : "Switch to Editing first"} onClick={() => onApplyFix(s)}>
              {s.fix.label}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function Thread({
  comment,
  active,
  onReveal,
  onReply,
  onResolve,
  onDelete,
}: {
  comment: Comment;
  active: boolean;
  onReveal: (id: string) => void;
  onReply: (id: string, text: string) => Promise<void>;
  onResolve: (id: string, resolved: boolean) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}) {
  const [reply, setReply] = useState("");
  const [menu, setMenu] = useState(false);
  const resolved = comment.status === "resolved";
  return (
    <div className={`cm-thread${active ? " cm-thread--active" : ""}${resolved ? " cm-thread--resolved" : ""}`} id={`cm-thread-${comment.id}`}>
      <button type="button" className="cm-quote cm-quote--button" onClick={() => onReveal(comment.id)}>
        <Clamp text={comment.quote} />
        {!comment.anchored ? <span className="cm-badge">text changed</span> : null}
      </button>
      {[{ id: comment.id, author: comment.author, role: comment.role, at: comment.at, text: comment.text }, ...comment.replies].map((m, n) => (
        <div key={m.id} className="cm-message">
          <div className="cm-thread-head">
            <Avatar name={m.author} />
            <span className="cm-thread-who">
              <b>{m.author}</b>
              <small>
                {m.role} | {timeAgo(m.at)}
              </small>
            </span>
            {n === 0 ? (
              <span className="cm-thread-tools">
                <button
                  type="button"
                  className="cm-icon-button"
                  title={resolved ? "Reopen" : "Resolve"}
                  aria-label={resolved ? "Reopen" : "Resolve"}
                  onClick={() => void onResolve(comment.id, !resolved)}
                >
                  {resolved ? "↺" : "✓"}
                </button>
                <span className="cm-menu">
                  <button type="button" className="cm-icon-button" aria-label="More" onClick={() => setMenu((v) => !v)}>
                    ⋮
                  </button>
                  {menu ? (
                    <span className="cm-menu-list cm-menu-list--right">
                      <button type="button" className="cm-menu-item cm-menu-item--danger" onClick={() => { setMenu(false); void onDelete(comment.id); }}>
                        Delete comment
                      </button>
                    </span>
                  ) : null}
                </span>
              </span>
            ) : null}
          </div>
          <p className="cm-message-text">{m.text}</p>
        </div>
      ))}
      {resolved ? (
        <p className="result-cite">Resolved by {comment.resolved_by}, {timeAgo(comment.resolved_at)}</p>
      ) : (
        <form
          className="cm-reply"
          onSubmit={(e) => {
            e.preventDefault();
            if (reply.trim()) void onReply(comment.id, reply).then(() => setReply(""));
          }}
        >
          <input placeholder="Write a reply…" value={reply} onChange={(e) => setReply(e.target.value)} />
          <button type="submit" className="cm-icon-button" aria-label="Send reply" disabled={!reply.trim()}>
            ➤
          </button>
        </form>
      )}
    </div>
  );
}

const LABELS: Record<string, { text: string; tone: string }> = {
  approved: { text: "Approved", tone: "good" },
  imported: { text: "Written", tone: "blue" },
  restored: { text: "Restored", tone: "purple" },
};

export function VersionsPanel({
  versions,
  hasDraft,
  editable,
  comparing,
  onCompare,
  onRestore,
}: {
  versions: VersionEntry[];
  hasDraft: boolean;
  editable: boolean;
  comparing: number | null;
  onCompare: (n: number) => void;
  onRestore: (n: number) => void;
}) {
  return (
    <div className="cm-panel-body">
      {hasDraft ? (
        <div className="cm-card cm-version cm-version--draft">
          <b>Working draft</b>
          <small className="muted-text">Not live until it is approved</small>
        </div>
      ) : null}
      {versions.map((v) => {
        const label = LABELS[v.label] ?? { text: v.label, tone: "" };
        return (
          <div key={v.n} className={`cm-card cm-version${comparing === v.n ? " cm-version--active" : ""}`}>
            <div className="cm-version-head">
              <b>{new Date(v.at).toLocaleString(undefined, { day: "numeric", month: "short", year: "numeric", hour: "numeric", minute: "2-digit" })}</b>
              <span className={`status-pill status-pill--${label.tone}`}>{label.text}</span>
            </div>
            {v.current ? <i className="cm-version-current">Current version</i> : null}
            <span className="cm-version-who">
              <span className="cm-dot" /> {v.author} | {v.role}
            </span>
            {v.note ? <p className="cm-version-note">{v.note}</p> : null}
            <div className="cm-thread-actions">
              <button type="button" className="text-button" onClick={() => onCompare(v.n)}>
                Compare with {hasDraft ? "the draft" : "the current text"}
              </button>
              {!v.current || hasDraft ? (
                <button type="button" className="text-button" disabled={!editable} title={editable ? undefined : "This format is read-only"} onClick={() => onRestore(v.n)}>
                  Restore to draft
                </button>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function ActivityPanel({ activity }: { activity: ActivityEntry[] }) {
  if (!activity.length) return <div className="cm-panel-body"><p className="muted-text">No activity yet.</p></div>;
  return (
    <div className="cm-panel-body">
      <ol className="cm-timeline">
        {activity.map((a, n) => (
          <li key={n}>
            <span className="cm-dot" />
            <div>
              <b>{a.actor}</b> {a.action}
              {a.detail ? <p className="muted-text">{a.detail}</p> : null}
              <small className="muted-text">{timeAgo(a.at)}</small>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

const PHASE_LABELS: Record<string, string> = {
  day_one: "Day one",
  end_state: "End state",
  proof_of_concept: "Proof of concept",
  real_deployment: "Real deployment",
};

export function DetailsPanel({
  doc,
  onSave,
  onRename,
  onMoved,
  onOpen,
}: {
  doc: ContentDocument;
  onSave: (fields: Record<string, unknown>) => Promise<void>;
  onRename: (title: string) => Promise<boolean>;
  onMoved: (message: string) => void;
  onOpen: (sourceId: string) => void;
}) {
  const s = doc.source;
  const [from, setFrom] = useState(s.effective_from ?? "");
  const [to, setTo] = useState(s.effective_to ?? "");
  const [phases, setPhases] = useState<string[]>(s.phases ?? []);
  const [applies, setApplies] = useState((s.applies_to ?? []).join(", "));
  const [saving, setSaving] = useState(false);
  const dirty =
    from !== (s.effective_from ?? "") ||
    to !== (s.effective_to ?? "") ||
    phases.join() !== (s.phases ?? []).join() ||
    applies !== (s.applies_to ?? []).join(", ");

  async function save() {
    setSaving(true);
    try {
      const fields: Record<string, unknown> = {
        effective_from: from || null,
        effective_to: to || null,
        phases,
        applies_to: applies.split(",").map((a) => a.trim()).filter(Boolean),
      };
      await onSave(fields);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="cm-panel-body">
      <div className="cm-card cm-form">
        <h3 className="cm-card-title">Document</h3>
        <div className="cm-row cm-title-row">
          <span className="cm-row-label">Title</span>
          <InlineTitle
            value={s.title}
            onSave={onRename}
            hint={doc.title_from_heading ? "Renaming a record rewrites its heading as a new version; its approval stays as it is." : undefined}
          >
            <b className="cm-title-value">{s.title}</b>
          </InlineTitle>
        </div>
        <Row label="File" value={s.filename} />
        <Row label="Format" value={s.editable ? s.format.toUpperCase() : `${s.format.toUpperCase()} (read-only)`} />
        <Row label="Sensitivity" value={s.sensitivity} />
        <Row label="Sections" value={s.section_count} />
        <Row label="Registered" value={new Date(s.created_at).toLocaleDateString()} />
      </div>
      <LocationCard sourceId={s.id} onMoved={onMoved} />
      <div className="cm-card cm-form">
        <h3 className="cm-card-title">Scope and lifecycle</h3>
        <p className="muted-text">Governance sets aside pairs whose phases or dates cannot overlap.</p>
        <div className="cm-form-two">
          <label>
            In force from
            <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          </label>
          <label>
            Until
            <input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
          </label>
        </div>
        <fieldset className="cm-phases">
          <legend>Phase</legend>
          {Object.entries(PHASE_LABELS).map(([key, label]) => (
            <label key={key} className="cm-check">
              <input
                type="checkbox"
                checked={phases.includes(key)}
                onChange={(e) => setPhases((p) => (e.target.checked ? [...p, key] : p.filter((x) => x !== key)))}
              />
              {label}
            </label>
          ))}
        </fieldset>
        <label>
          Applies to
          <input value={applies} placeholder="e.g. pilot sites, motorway sites" onChange={(e) => setApplies(e.target.value)} />
        </label>
        <div className="cm-thread-actions">
          <button type="button" className="primary-button" disabled={!dirty || saving} onClick={() => void save()}>
            {saving ? "Saving…" : "Save details"}
          </button>
        </div>
      </div>
      {doc.record ? (
        <div className="cm-card">
          <h3 className="cm-card-title">Tibi record</h3>
          <Row label="Record" value={doc.record.id} />
          <Row label="Status" value={doc.record.status} />
          {doc.record.contributor ? <Row label="Contributed by" value={doc.record.contributor} /> : null}
          {doc.record.review_block ? <p className="cm-inline-error">{doc.record.review_block}</p> : null}
        </div>
      ) : null}
      {doc.cites?.length ? (
        <div className="cm-card">
          <h3 className="cm-card-title">Evidence it cites</h3>
          {doc.cites.map((c) => (
            <button key={c.source_id} type="button" className="cm-row cm-row--link" onClick={() => onOpen(c.source_id)}>
              <span className="cm-row-label">{c.title}</span>
              <span className="cm-row-chevron">›</span>
            </button>
          ))}
        </div>
      ) : null}
      {doc.cited_by?.length ? (
        <div className="cm-card">
          <h3 className="cm-card-title">Records citing this document</h3>
          {doc.cited_by.map((c) => (
            <button key={c.id} type="button" className="cm-row cm-row--link" onClick={() => onOpen(c.source_id)}>
              <span className="cm-row-label">{c.title}</span>
              <span className="cm-row-chevron">›</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

/** A version compared with another: insertions coloured, deletions struck through, in the document's own layout. */
export function DiffView({ ops, title, onClose }: { ops: DiffOp[]; title: string; onClose: () => void }) {
  const inserted = ops.filter((o) => o.op === "insert").length;
  const deleted = ops.filter((o) => o.op === "delete").length;
  return (
    <div className="cm-diff">
      <div className="cm-diff-banner">
        <span>
          <b>{title}</b> · {inserted} addition{inserted === 1 ? "" : "s"}, {deleted} removal{deleted === 1 ? "" : "s"}
        </span>
        <button type="button" className="secondary-button" onClick={onClose}>
          Close comparison
        </button>
      </div>
      <div className="cm-page cm-diff-text">
        {ops.map((o, n) =>
          o.op === "equal" ? (
            <span key={n}>{o.text}</span>
          ) : o.op === "insert" ? (
            <ins key={n}>{o.text}</ins>
          ) : (
            <del key={n}>{o.text}</del>
          ),
        )}
      </div>
    </div>
  );
}
