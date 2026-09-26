import { useEffect, useState } from "react";
import { approveSource, listSources, rejectSource, type SourceRecord } from "./api";
import { TibiGovernancePanel } from "./TibiGovernancePanel";
import { getDocumentSummary, openDocument } from "./content/api";
import { HoverTip } from "./HoverTip";

const CONTENT_STATUS: Record<string, { text: string; tone: string }> = {
  draft: { text: "Draft", tone: "cm-status--draft" },
  submitted: { text: "Waiting for approval", tone: "cm-status--submitted" },
};

// OpsAtlas Sales governs its records with the statement-level review and Tibi (the panel below). The document-pair
// Internal Source Review, the External Source Review, the regulatory-signal triage and the re-analysis snapshot were
// removed on 26 September 2026; they remain in OpsAtlas Classic (docs/opsatlas-classic-and-sales.md).

export function GovernancePage({ onResolveWithTibi }: { onResolveWithTibi?: () => void } = {}) {
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [drafts, setDrafts] = useState<Record<string, { status: string }>>({});
  const [suggestions, setSuggestions] = useState<Record<string, number>>({});
  const [notes, setNotes] = useState<Record<string, string[]>>({});

  async function refresh() {
    try {
      const [list, summary] = await Promise.all([
        listSources(),
        getDocumentSummary().catch(() => ({ documents: {}, suggestions: {} as Record<string, number>, suggestion_notes: {} as Record<string, string[]> })),
      ]);
      setSources(list);
      setDrafts(summary.documents);
      setSuggestions(summary.suggestions ?? {});
      setNotes(summary.suggestion_notes ?? {});
      setError(null);
    } catch {
      setError("Could not reach the backend.");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function act(fn: (id: string) => Promise<void>, id: string) {
    setBusy(true);
    try {
      await fn(id);
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Governance</h1>
        <p>Knowledge intelligence and the human-in-the-loop approval gate. Only approved sources are queryable.</p>
      </div>

      {onResolveWithTibi ? <TibiGovernancePanel onResolveWithTibi={onResolveWithTibi} onChanged={() => void refresh()} /> : null}

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Source approval</h2>
            <p className="muted-text">
              Approve a source before the assistant can use it. Open one to read, comment on, edit or approve it; Review shows its open
              governance suggestions (wording checks, conflicts and duplicates).
            </p>
          </div>
        </div>
        {error ? <p className="muted-text" style={{ color: "var(--red)" }}>{error}</p> : null}
        {sources.length === 0 ? (
          <div className="empty-card"><b>No sources</b><span>Upload and ingest documents first.</span></div>
        ) : (
          <div className="table-frame">
            <table className="data-table">
              <thead>
                <tr><th>Title</th><th>State</th><th>Approval</th><th>Review</th><th /></tr>
              </thead>
              <tbody>
                {sources.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <button type="button" className="table-link" onClick={() => openDocument(s.id)}>
                        {s.title}
                      </button>
                    </td>
                    <td>{s.processing_state}</td>
                    <td>
                      <span className={`status-pill${s.approval_status === "approved" ? " status-pill--good" : s.approval_status === "rejected" ? " status-pill--warn" : ""}`}>
                        {s.approval_status}
                      </span>
                    </td>
                    <td className="review-cell">
                      {suggestions[s.id] ? (
                        <HoverTip
                          tip={
                            <>
                              <b>Open suggestions</b>
                              <ul>
                                {(notes[s.id] ?? []).map((line, n) => (
                                  <li key={n}>{line}</li>
                                ))}
                              </ul>
                              <small>Click to open the document at them.</small>
                            </>
                          }
                        >
                          <button type="button" className="status-pill status-pill--suggestions" onClick={() => openDocument(s.id, "comments")}>
                            {suggestions[s.id]} suggestion{suggestions[s.id] === 1 ? "" : "s"}
                          </button>
                        </HoverTip>
                      ) : null}
                      {drafts[s.id] && CONTENT_STATUS[drafts[s.id].status] ? (
                        <span className={`status-pill ${CONTENT_STATUS[drafts[s.id].status].tone}`}>{CONTENT_STATUS[drafts[s.id].status].text}</span>
                      ) : null}
                    </td>
                    <td className="table-actions">
                      <button type="button" className="secondary-button" disabled={busy} onClick={() => openDocument(s.id)}>
                        Open
                      </button>
                      {s.approval_status !== "approved" ? (
                        <button type="button" className="approve-button" disabled={busy} onClick={() => act(approveSource, s.id)}>
                          Approve
                        </button>
                      ) : null}
                      {s.approval_status !== "rejected" ? (
                        <button type="button" className="reject-button" disabled={busy} onClick={() => act(rejectSource, s.id)}>
                          Reject
                        </button>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
