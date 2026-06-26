import { useEffect, useState } from "react";
import {
  deleteExternalSource,
  listExternalSnapshots,
  listExternalSources,
  snapshotGovUkSource,
  type PublicContentSnapshot,
  type PublicContentSource,
} from "./api";

function formatDate(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

function topicList(value: string): string[] {
  return value.split(",").map((topic) => topic.trim()).filter(Boolean);
}

const GOVUK_VAT_EXAMPLE_URL = "https://www.gov.uk/guidance/vat-guide-notice-700";
const GOVUK_VAT_EXAMPLE_TOPICS = "vat, tax, compliance";
const LEGISLATION_BRIBERY_EXAMPLE_URL = "https://www.legislation.gov.uk/ukpga/2010/23/data.xml";
const LEGISLATION_BRIBERY_EXAMPLE_TOPICS = "bribery, legislation, compliance";
const SOURCE_GUIDANCE = [
  ["Purpose", "Capture a dated public guidance or legislation snapshot so internal answers can show what external reference was available at that point."],
  ["Supported sources", "Public GOV.UK guidance and legislation.gov.uk XML pages are supported. Other domains remain blocked until explicitly approved."],
  ["Topics", "Comma-separated labels used for later discovery and matching, such as vat, tax or compliance."],
  ["Snapshot", "A local version of the public page with source URL, update date, retrieval date and content hash."],
  ["Not approved content", "External snapshots are reference evidence; they do not replace the internal approval and ingestion workflow."],
];

export function ExternalSourcesPage() {
  const [sources, setSources] = useState<PublicContentSource[] | null>(null);
  const [snapshots, setSnapshots] = useState<PublicContentSnapshot[] | null>(null);
  const [url, setUrl] = useState("");
  const [topics, setTopics] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [rowBusy, setRowBusy] = useState<string | null>(null);

  async function refresh() {
    try {
      const [sourceRows, snapshotRows] = await Promise.all([listExternalSources(), listExternalSnapshots()]);
      setSources(sourceRows);
      setSnapshots(snapshotRows);
      setError(null);
    } catch {
      setSources([]);
      setSnapshots([]);
      setError("Could not load external source snapshots.");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function onSnapshot(event: React.FormEvent) {
    event.preventDefault();
    if (!url.trim()) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const result = await snapshotGovUkSource(url, topicList(topics));
      setUrl("");
      setMessage(`Snapshot v${result.snapshot.version} stored for ${result.source.title}.`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Snapshot failed.");
    } finally {
      setBusy(false);
    }
  }

  async function refreshSource(source: PublicContentSource) {
    setRowBusy(`refresh:${source.id}`);
    setError(null);
    setMessage(null);
    try {
      const result = await snapshotGovUkSource(source.url, source.topics);
      setMessage(`Snapshot v${result.snapshot.version} stored for ${result.source.title}.`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Refresh failed.");
    } finally {
      setRowBusy(null);
    }
  }

  async function removeSource(source: PublicContentSource) {
    const title = source.title || source.url;
    if (!window.confirm(`Remove ${title} and its snapshots?`)) return;
    setRowBusy(`delete:${source.id}`);
    setError(null);
    setMessage(null);
    try {
      await deleteExternalSource(source.id);
      setMessage(`Removed ${title}.`);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Remove failed.");
    } finally {
      setRowBusy(null);
    }
  }

  const sourceCount = sources?.length ?? 0;
  const snapshotCount = snapshots?.length ?? 0;

  function useVatExample() {
    setUrl(GOVUK_VAT_EXAMPLE_URL);
    setTopics(GOVUK_VAT_EXAMPLE_TOPICS);
    setMessage(null);
    setError(null);
  }

  function useBriberyExample() {
    setUrl(LEGISLATION_BRIBERY_EXAMPLE_URL);
    setTopics(LEGISLATION_BRIBERY_EXAMPLE_TOPICS);
    setMessage(null);
    setError(null);
  }

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>External Sources</h1>
        <p>Snapshot selected public UK government guidance and legislation with attribution and local version history.</p>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Public source snapshot</h2>
            <p className="muted-text">Only the selected public URL is fetched. Use snapshots to retain dated public reference evidence.</p>
          </div>
          <span className="status-pill">{snapshotCount} snapshots</span>
        </div>
        <div className="result-card" style={{ marginBottom: 12 }}>
          <div className="result-head">
            <b>Example public sources</b>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              <button type="button" className="secondary-button" onClick={useVatExample}>Use VAT Notice 700</button>
              <button type="button" className="secondary-button" onClick={useBriberyExample}>Use Bribery Act 2010</button>
            </div>
          </div>
          <p className="result-cite">
            GOV.UK VAT guide (VAT Notice 700) · suggested topics: {GOVUK_VAT_EXAMPLE_TOPICS}
          </p>
          <p className="result-cite">{GOVUK_VAT_EXAMPLE_URL}</p>
          <p className="result-cite">
            legislation.gov.uk Bribery Act 2010 · suggested topics: {LEGISLATION_BRIBERY_EXAMPLE_TOPICS}
          </p>
          <p className="result-cite">{LEGISLATION_BRIBERY_EXAMPLE_URL}</p>
        </div>
        <form onSubmit={onSnapshot} style={{ display: "grid", gridTemplateColumns: "minmax(260px, 1fr) minmax(160px, 240px) auto", gap: 10 }}>
          <input
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://www.gov.uk/... or https://www.legislation.gov.uk/..."
            style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "12px 14px", minWidth: 0 }}
          />
          <input
            value={topics}
            onChange={(event) => setTopics(event.target.value)}
            placeholder="topics"
            style={{ border: "1px solid var(--line)", borderRadius: 8, padding: "12px 14px", minWidth: 0 }}
          />
          <button type="submit" className="primary-button" disabled={busy || !url.trim()}>
            {busy ? "Snapshotting…" : "Snapshot"}
          </button>
        </form>
        {error ? <p className="muted-text" style={{ color: "var(--red)", marginTop: 12 }}>{error}</p> : null}
        {message ? <p className="muted-text" style={{ color: "var(--green)", marginTop: 12 }}>{message}</p> : null}
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>How to use external sources</h2>
            <p className="muted-text">Public snapshots support comparison, attribution and regulatory discovery.</p>
          </div>
        </div>
        <div className="result-list" style={{ gap: 10 }}>
          {SOURCE_GUIDANCE.map(([label, text]) => (
            <div className="result-card" key={label}>
              <div className="result-head"><b>{label}</b></div>
              <p className="result-cite">{text}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Public source registry</h2>
            <p className="muted-text">Attribution, licence and latest retrieved version.</p>
          </div>
          <span className="status-pill">{sourceCount} sources</span>
        </div>
        {sources === null ? (
          <p className="muted-text">Loading…</p>
        ) : sourceCount === 0 ? (
          <div className="empty-card">
            <b>No external sources yet</b>
            <span>Snapshot a selected public UK government page to create the first public source record.</span>
          </div>
        ) : (
          <div className="table-frame">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Public body</th>
                  <th>Versions</th>
                  <th>Updated</th>
                  <th>Licence</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((source) => (
                  <tr key={source.id}>
                    <td><a href={source.url} target="_blank" rel="noreferrer">{source.title || source.url}</a></td>
                    <td>{source.public_body || "Public source"}</td>
                    <td>{source.snapshot_count}</td>
                    <td>{formatDate(source.latest_update_date || source.latest_snapshot_date)}</td>
                    <td>{source.licence}</td>
                    <td>
                      {source.last_error ? (
                        <div style={{ display: "grid", gap: 4 }}>
                          <span className="status-pill status-pill--warn">last fetch failed</span>
                          <small className="result-cite">{source.last_error}</small>
                        </div>
                      ) : (
                        <span className="status-pill status-pill--good">ready</span>
                      )}
                    </td>
                    <td>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                        <button
                          type="button"
                          className="mini-button"
                          disabled={rowBusy !== null}
                          onClick={() => void refreshSource(source)}
                        >
                          {rowBusy === `refresh:${source.id}` ? "Refreshing..." : "Refresh"}
                        </button>
                        <button
                          type="button"
                          className="text-button"
                          disabled={rowBusy !== null}
                          onClick={() => void removeSource(source)}
                        >
                          {rowBusy === `delete:${source.id}` ? "Removing..." : "Remove"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Recent snapshots</h2>
            <p className="muted-text">Local versions retained for comparison.</p>
          </div>
        </div>
        {snapshots && snapshots.length ? (
          <div className="result-list">
            {snapshots.slice(0, 6).map((snapshot) => (
              <div className="result-card" key={snapshot.id}>
                <div className="result-head">
                  <b>{snapshot.title}</b>
                  <span className="status-pill">v{snapshot.version}</span>
                </div>
                <p className="result-cite">
                  {snapshot.public_body || "Public source"} · {snapshot.document_type || "content"} · {formatDate(snapshot.snapshot_date)}
                </p>
                <p className="result-cite">sha256 {snapshot.content_sha256.slice(0, 12)} · {snapshot.url}</p>
              </div>
            ))}
          </div>
        ) : (
          <p className="muted-text">No snapshots stored yet.</p>
        )}
      </div>
    </div>
  );
}
