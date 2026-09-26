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

  return (
    <div className="panel">
      <div className="panel-heading">
        <div>
          <h2>Resolve issues with Tibi</h2>
          <p className="muted-text">
            Tibi takes the open issues in priority order, explains each one from the passages involved, checks your answer against
            the sources and saves it here for approval. Approving closes the issue below and keeps your answer as its record.
            Sources are never edited: an answer saying a source needs changing stays a follow-up.
          </p>
        </div>
        <div className="tibi-actions">
          {summary ? (
            <span className="status-pill">
              {summary.open} open for Tibi · {pending.length} waiting for approval
            </span>
          ) : null}
          <button type="button" className="primary-button" onClick={onResolveWithTibi}>
            Resolve with Tibi
          </button>
        </div>
      </div>
      {error ? <p className="muted-text" style={{ color: "var(--red)" }}>{error}</p> : null}
      {statements ? <StatementReview review={statements} onRun={runReview} onResolveWithTibi={onResolveWithTibi} /> : null}
      {answers && !answers.length ? (
        <p className="muted-text">No answers yet. Start a governance interview with Tibi to work through the open issues.</p>
      ) : null}
      <div className="result-list" style={{ gap: 10 }}>
        {pending.map((answer) => (
          <AnswerCard key={answer.id} answer={answer} busy={busy === answer.id} onReview={(approve) => review(answer, approve)} />
        ))}
      </div>
      {decided.length ? (
        <details style={{ marginTop: 12 }}>
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
          <button type="button" className="primary-button" disabled={busy} onClick={() => onReview(true)}>
            Approve and close the issue
          </button>
          <button type="button" className="secondary-button" disabled={busy} onClick={() => onReview(false)}>
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
function StatementReview({
  review,
  onRun,
  onResolveWithTibi,
}: {
  review: TibiStatementReview;
  onRun: () => void;
  onResolveWithTibi: () => void;
}) {
  const latest = review.latest;
  const running = review.status === "running";
  const where = review.profile.data_leaves
    ? `Judged by ${review.profile.judge} (${review.profile.where}).`
    : `Judged locally on this Mac by ${review.profile.judge}` +
      (review.profile.reviewer ? `, with ${review.profile.reviewer} as a second opinion on each conflict.` : ".");
  const open = review.open ?? [];
  const setAside = (latest?.set_aside_by_scope?.dates ?? 0) + (latest?.set_aside_by_scope?.phase ?? 0);
  return (
    <div className="tibi-statements">
      <div className="result-head">
        <b>Conflicts and duplicates between records</b>
        <button type="button" className="secondary-button" disabled={running} onClick={onRun}>
          {running ? "Reviewing…" : "Review records now"}
        </button>
      </div>
      <p className="muted-text">
        Each statement in the records is compared only with the few most similar statements in other records, and every
        pair is judged once. {where}
        {review.profile.note ? ` ${review.profile.note}` : ""}
      </p>
      <p className="muted-text">
        {running
          ? `Reviewing${review.progress ? `: ${review.progress.judged} of ${review.progress.total} pairs judged` : "…"}`
          : latest
            ? `Last review ${new Date(latest.finished_at).toLocaleString()}: ${latest.candidates} pairs checked in ${Math.round(
                latest.total_seconds,
              )} s; ${latest.raised.conflict} conflict${latest.raised.conflict === 1 ? "" : "s"}, ${latest.raised.duplicate} duplicate${
                latest.raised.duplicate === 1 ? "" : "s"
              }` +
              (latest.dismissed_by_second_opinion ? `; ${latest.dismissed_by_second_opinion} dismissed by the second opinion` : "") +
              "." +
              (setAside
                ? ` ${setAside} more pair${setAside === 1 ? " was" : "s were"} set aside without judging, because one covers the proof of concept and the other a real deployment, or their dates cannot overlap.`
                : "")
            : "No review has run yet."}
        {review.status === "failed" && review.error ? ` The last review failed: ${review.error}` : ""}
      </p>
      {open.length ? (
        <div className="result-list" style={{ gap: 10 }}>
          {open.map((finding) => (
            <div className="result-card" key={finding.key}>
              <div className="result-head">
                <b>{finding.relation === "conflict" ? (finding.same_document ? "A record contradicts itself" : "Two records disagree") : "Two records say the same thing"}</b>
                {finding.answer ? <span className="status-pill">answer {finding.answer.status}</span> : null}
              </div>
              <StatementPair statements={finding.statements} />
              <p className="result-cite">Flagged because: {finding.reason}</p>
              {finding.second_opinion ? (
                <p className="result-cite">Second opinion ({finding.second_opinion.model}): {finding.second_opinion.reason}</p>
              ) : null}
              {!finding.answer ? (
                <div className="tibi-actions">
                  <button type="button" className="secondary-button" onClick={onResolveWithTibi}>
                    Resolve with Tibi
                  </button>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : latest && !running ? (
        <p className="muted-text">No open conflicts or duplicates between records.</p>
      ) : null}
    </div>
  );
}

