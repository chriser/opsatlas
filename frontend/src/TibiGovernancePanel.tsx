import { useEffect, useState } from "react";
import {
  getTibiGovernanceAnswers,
  getTibiGovernanceSummary,
  reviewTibiGovernanceAnswer,
  type TibiGovernanceAnswer,
  type TibiGovernanceSummary,
} from "./api";

const DECISIONS: Record<string, string> = {
  define: "Record the definition",
  accept: "Accept as it is",
  fix_later: "Needs a source change (follow-up)",
  fix_link: "Replace the link",
  reword: "Reword",
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
  if (r.note && r.decision !== "define") parts.push(r.note);
  return parts.join(" · ");
}

/** Answers the Human gave Tibi in governance interviews, approved here beside the issues they resolve. */
export function TibiGovernancePanel({ onResolveWithTibi, onChanged }: { onResolveWithTibi: () => void; onChanged: () => void }) {
  const [answers, setAnswers] = useState<TibiGovernanceAnswer[] | null>(null);
  const [summary, setSummary] = useState<TibiGovernanceSummary | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    try {
      const [data, agenda] = await Promise.all([getTibiGovernanceAnswers(), getTibiGovernanceSummary()]);
      setAnswers(data.answers.filter((a) => a.status !== "superseded"));
      setSummary(agenda);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load Tibi's governance answers.");
    }
  }

  useEffect(() => {
    void load();
  }, []);

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
  return (
    <div className="result-card">
      <div className="result-head">
        <b>{heading(answer)}</b>
        <span className="status-pill">{answer.status}</span>
      </div>
      <p className="result-cite">Issue: {issue}</p>
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
