import { useEffect, useState } from "react";
import {
  getTibiGovernanceAnswers,
  getTibiGovernanceSummary,
  getTibiStatementReview,
  reviewTibiGovernanceAnswer,
  runTibiStatementReview,
  type TibiGovernanceAnswer,
  type TibiGovernanceSummary,
  type TibiRecordStatement,
  type TibiStatementFinding,
  type TibiStatementReview,
} from "./api";

const DECISIONS: Record<string, string> = {
  define: "Record the definition",
  accept: "Accept as it is",
  fix_later: "Needs a source change (follow-up)",
  fix_link: "Replace the link",
  reword: "Reword",
  supersede: "One record is right; the other is withdrawn from answers",
  merge: "Keep one record; the other is withdrawn from answers",
  distinct_scope: "Both hold, in different situations",
  dispute: "Unresolved: both are withdrawn from answers until settled",
  not_an_issue: "Not an issue; nothing changes",
  intended: "Both intended; nothing changes",
};

const MARKS: Record<string, string> = {
  matches: "✓",
  conflicts: "⚠",
  changes_meaning: "⚠",
  unverified: "?",
  check: "?",
  not_found: "·",
};

function heading(answer: TibiGovernanceAnswer): string {
  if (answer.kind === "statement") return answer.relation === "conflict" ? "Conflict between records" : "Duplicate records";
  if (answer.kind === "acronym") return `Acronym ${answer.detail}`;
  if (answer.kind === "standard") return `Standard abbreviations: ${answer.detail}`;
  return `${answer.check.replace("_", " ")} · ${answer.source_title}`;
}

function resolutionText(answer: TibiGovernanceAnswer): string {
  const r = answer.resolution;
  const parts = [DECISIONS[r.decision] ?? r.decision];
  if (r.definitions?.length) parts.push(r.definitions.map((d) => `${d.acronym} = ${d.expansion}`).join("; "));
  if (r.url) parts.push(r.url);
  if (r.replacement) parts.push(r.replacement);
  if (r.note && r.decision !== "define" && answer.kind !== "statement") parts.push(r.note);
  return parts.join(" · ");
}

/** Answers the Human gave Tibi in governance interviews, approved here beside the issues they resolve. */
export function TibiGovernancePanel({ onResolveWithTibi, onChanged }: { onResolveWithTibi: () => void; onChanged: () => void }) {
  const [answers, setAnswers] = useState<TibiGovernanceAnswer[] | null>(null);
  const [summary, setSummary] = useState<TibiGovernanceSummary | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [statements, setStatements] = useState<TibiStatementReview | null>(null);

  async function load() {
    try {
      const [data, agenda, review] = await Promise.all([getTibiGovernanceAnswers(), getTibiGovernanceSummary(), getTibiStatementReview()]);
      setAnswers(data.answers.filter((a) => a.status !== "superseded"));
      setSummary(agenda);
      setStatements(review);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load Tibi's governance answers.");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  // While a review runs, follow its progress; the findings join the agenda when it finishes.
  useEffect(() => {
    if (statements?.status !== "running") return;
    const timer = window.setTimeout(() => {
      void load().then(() => onChanged());
    }, 3000);
    return () => window.clearTimeout(timer);
  }, [statements]);

  async function runReview() {
    try {
      setStatements(await runTibiStatementReview());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start the review.");
    }
  }

  async function review(answer: TibiGovernanceAnswer, approve: boolean) {
    setBusy(answer.id);
    try {
      await reviewTibiGovernanceAnswer(answer.id, answer.text_sha256, approve);
      await load();
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not record the decision.");
    } finally {
      setBusy(null);
    }
  }

  const pending = (answers ?? []).filter((a) => a.status === "pending");
  const decided = (answers ?? []).filter((a) => a.status !== "pending");

  const wordingOpen = (summary?.items ?? []).filter((item) => !item.answer).length;
  const openFindings = (statements?.open ?? []).filter((finding) => !finding.answer);

  return (
    <div className="panel tibi-review">
      <div className="tibi-review-head">
        <div>
          <h2>Resolve issues with Tibi</h2>
          <p className="muted-text">
            Tibi explains each open issue from the passages involved, checks your answer against the sources and saves it here for your
            approval. Answers never edit a source; a change a source needs stays a follow-up.
          </p>
        </div>
        <button type="button" className="primary-button" onClick={onResolveWithTibi}>
          Resolve with Tibi{summary?.open ? ` (${summary.open})` : ""}
        </button>
      </div>
      {error ? <p className="tibi-review-error">{error}</p> : null}
      <div className="tibi-tiles">
        <ConflictTile review={statements} open={openFindings.length} onRun={runReview} />
        <Tile
          label="Wording checks"
          value={summary ? wordingOpen : null}
          tone={wordingOpen ? "amber" : "good"}
          text={wordingOpen ? "Acronyms, readability, spelling or links to look at" : "Nothing to look at"}
          meta="Shown against each document in Source approval below"
        />
        <Tile
          label="Waiting for your approval"
          value={answers ? pending.length : null}
          tone={pending.length ? "purple" : "good"}
          text={pending.length ? "Answers Tibi saved from governance interviews" : "Nothing waiting"}
          meta={pending.length ? "Approve or reject them below" : "Tibi saves answers here as you give them"}
        />
      </div>
      {openFindings.length ? (
        <section className="tibi-review-section">
          <h3>Conflicts and duplicates to decide</h3>
          <Findings findings={openFindings} onResolveWithTibi={onResolveWithTibi} />
        </section>
      ) : null}
      {pending.length ? (
        <section className="tibi-review-section">
          <h3>Waiting for your approval</h3>
          <div className="result-list" style={{ gap: 10 }}>
            {pending.map((answer) => (
              <AnswerCard key={answer.id} answer={answer} busy={busy === answer.id} onReview={(approve) => review(answer, approve)} />
            ))}
          </div>
        </section>
      ) : null}
      {decided.length ? (
        <details className="tibi-review-section">
          <summary>Decided answers ({decided.length})</summary>
          <div className="result-list" style={{ gap: 10, marginTop: 10 }}>
            {decided.map((answer) => (
              <AnswerCard key={answer.id} answer={answer} busy={false} />
            ))}
          </div>
        </details>
      ) : null}
    </div>
  );
}

function Tile({
  label,
  value,
  tone,
  text,
  meta,
  children,
}: {
  label: string;
  value: number | null;
  tone: "good" | "amber" | "purple" | "red" | "neutral";
  text: string;
  meta?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className={`tibi-tile tibi-tile--${value === null ? "neutral" : tone}`}>
      <span className="tibi-tile-label">{label}</span>
      <b className="tibi-tile-value">{value === null ? "—" : value}</b>
      <span className="tibi-tile-text">{text}</span>
      {meta ? <span className="tibi-tile-meta">{meta}</span> : null}
      {children}
    </div>
  );
}

/** The statement-level review in one tile: its result, when it ran, and the button that runs it. */
function ConflictTile({ review, open, onRun }: { review: TibiStatementReview | null; open: number; onRun: () => void }) {
  const latest = review?.latest ?? null;
  const running = review?.status === "running";
  const setAside = (latest?.set_aside_by_scope?.dates ?? 0) + (latest?.set_aside_by_scope?.phase ?? 0);
  const judge = review
    ? review.profile.data_leaves
      ? `Judged by ${review.profile.judge} (${review.profile.where})`
      : `Judged locally by ${review.profile.judge}${review.profile.reviewer ? `, with ${review.profile.reviewer} as a second opinion on each conflict` : ""}`
    : "";
  const when = latest
    ? new Date(latest.finished_at).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })
    : "";
  const text = running
    ? `Reviewing${review?.progress ? `: ${review.progress.judged} of ${review.progress.total} pairs judged` : "…"}`
    : latest
      ? open
        ? `${open} between records need${open === 1 ? "s" : ""} a decision`
        : "None between records"
      : "Not reviewed yet";
  return (
    <Tile label="Conflicts and duplicates" value={latest ? open : null} tone={open ? "red" : "good"} text={text}>
      <span className="tibi-tile-meta" title={judge}>
        {latest ? `Last review ${when} · ${latest.candidates} pairs in ${Math.round(latest.total_seconds)} s` : judge}
        {setAside ? (
          <span title="Pairs whose phases (the proof of concept against a real deployment) or dates cannot overlap are not judged.">
            {` · ${setAside} set aside by scope`}
          </span>
        ) : null}
      </span>
      {review?.status === "failed" && review.error ? <span className="tibi-review-error">The last review failed: {review.error}</span> : null}
      {review?.queued ? (
        <span className="tibi-tile-meta">Records changed during this review: it runs again as soon as this one finishes.</span>
      ) : review && !running && review.latest && review.up_to_date === false ? (
        <span className="tibi-tile-meta">Records changed since the last review: review again to judge the current wording.</span>
      ) : null}
      <button type="button" className="primary-button tibi-tile-action" disabled={running || !review} onClick={onRun}>
        {running ? "Reviewing…" : "Review records now"}
      </button>
    </Tile>
  );
}

function AnswerCard({
  answer,
  busy,
  onReview,
}: {
  answer: TibiGovernanceAnswer;
  busy: boolean;
  onReview?: (approve: boolean) => void;
}) {
  const issue =
    answer.kind === "issue"
      ? answer.detail
      : `${answer.issues.length} source${answer.issues.length === 1 ? "" : "s"}: ${answer.issues.map((i) => i.source_title).join("; ")}`;
  const keep = answer.resolution.keep;
  const outcome = (n: number): string | undefined => {
    const decision = answer.resolution.decision;
    if (decision === "dispute") return "withdrawn until settled";
    if (decision === "supersede" || decision === "merge") return (n === 0) === (keep === "a") ? "stays" : "withdrawn";
    return undefined;
  };
  return (
    <div className="result-card">
      <div className="result-head">
        <b>{heading(answer)}</b>
        <span className="status-pill">{answer.status}</span>
      </div>
      {answer.kind === "statement" && answer.statements ? (
        <StatementPair statements={answer.statements} outcome={outcome} />
      ) : (
        <p className="result-cite">Issue: {issue}</p>
      )}
      <p>
        <b>{answer.contributor} said:</b> {answer.answer}
      </p>
      <p className="result-cite">Resolution: {resolutionText(answer)}</p>
      {answer.verification.length ? (
        <ul className="tibi-verification">
          {answer.verification.map((v, n) => (
            <li key={n}>
              {MARKS[v.status] ?? ""} {v.message}
            </li>
          ))}
        </ul>
      ) : null}
      {onReview ? (
        <div className="tibi-actions">
          <button type="button" className="approve-button" disabled={busy} onClick={() => onReview(true)}>
            Approve and close the issue
          </button>
          <button type="button" className="reject-button" disabled={busy} onClick={() => onReview(false)}>
            Reject
          </button>
        </div>
      ) : null}
    </div>
  );
}

function StatementPair({
  statements,
  outcome,
}: {
  statements: TibiRecordStatement[];
  outcome?: (n: number) => string | undefined;
}) {
  return (
    <div className="tibi-pair">
      {statements.map((s, n) => (
        <div key={s.statement_id} className="tibi-pair-side">
          <div className="tibi-pair-head">
            <b>
              {n === 0 ? "First" : "Second"} · {s.title}
            </b>
            <span className="status-pill">{s.status}</span>
            {s.contributor ? <span className="status-pill">contributed by {s.contributor}</span> : null}
            {outcome?.(n) ? <span className="status-pill">{outcome(n)}</span> : null}
          </div>
          <p>{s.text}</p>
          {s.applies_to ? <p className="muted-text">Covers {s.applies_to}</p> : null}
        </div>
      ))}
    </div>
  );
}

/** Conflicts and duplicates between the records Tibi speaks from, found by the statement-level review. */
function Findings({ findings, onResolveWithTibi }: { findings: TibiStatementFinding[]; onResolveWithTibi: () => void }) {
  return (
    <div className="result-list" style={{ gap: 10 }}>
      {findings.map((finding) => (
        <div className="result-card" key={finding.key}>
          <div className="result-head">
            <b>{finding.relation === "conflict" ? (finding.same_document ? "A record contradicts itself" : "Two records disagree") : "Two records say the same thing"}</b>
          </div>
          <StatementPair statements={finding.statements} />
          <p className="result-cite">Flagged because: {finding.reason}</p>
          {finding.second_opinion ? (
            <p className="result-cite">Second opinion ({finding.second_opinion.model}): {finding.second_opinion.reason}</p>
          ) : null}
          <div className="tibi-actions">
            <button type="button" className="secondary-button" onClick={onResolveWithTibi}>
              Resolve with Tibi
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

