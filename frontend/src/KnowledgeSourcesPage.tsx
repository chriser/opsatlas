import { useEffect, useRef, useState } from "react";
import { deleteSource, ingestSource, listSources, uploadSource, type SourceRecord } from "./api";

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

export function KnowledgeSourcesPage() {
  const [sources, setSources] = useState<SourceRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const bulkFileRef = useRef<HTMLInputElement>(null);

  async function refresh() {
    try {
      setSources(await listSources());
      setError(null);
    } catch {
      setSources([]);
      setError("Could not reach the backend. Start it with the backend run command (port 8010).");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function onFileChosen(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    setUploadStatus(null);
    try {
      setUploadStatus(`Uploading ${file.name}`);
      await uploadSource(file);
      await refresh();
      setUploadStatus(`${file.name} uploaded.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
      setUploadStatus(null);
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function onBulkFilesChosen(event: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    if (files.length === 0) return;

    setBusy(true);
    setError(null);
    setUploadStatus(`Preparing ${files.length} documents.`);

    const failures: string[] = [];
    for (const [index, file] of files.entries()) {
      setUploadStatus(`Uploading ${index + 1} of ${files.length}: ${file.name}`);
      try {
        await uploadSource(file);
      } catch (err) {
        const message = err instanceof Error ? err.message : "upload failed";
        failures.push(`${file.name}: ${message}`);
      }
    }

    await refresh();

    const uploadedCount = files.length - failures.length;
    setUploadStatus(`${uploadedCount} of ${files.length} documents uploaded.`);
    if (failures.length > 0) {
      const shownFailures = failures.slice(0, 3).join(" ");
      const extraFailures = failures.length > 3 ? ` ${failures.length - 3} more failed.` : "";
      setError(`${failures.length} document${failures.length === 1 ? "" : "s"} could not be uploaded. ${shownFailures}${extraFailures}`);
    }

    setBusy(false);
    if (bulkFileRef.current) bulkFileRef.current.value = "";
  }

  async function onRemove(id: string) {
    setBusy(true);
    try {
      await deleteSource(id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed.");
    } finally {
      setBusy(false);
    }
  }

  async function onIngest(id: string) {
    setBusy(true);
    setError(null);
    try {
      await ingestSource(id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ingest failed.");
    } finally {
      setBusy(false);
    }
  }

  const count = sources?.length ?? 0;

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Knowledge Sources</h1>
        <p>Upload anonymised source documents and manage the source register.</p>
      </div>
      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Source register</h2>
            <p className="muted-text">Every document the assistant may draw on, with its governance status.</p>
          </div>
          <span className="status-pill">{count} registered</span>
        </div>

        <input
          ref={fileRef}
          type="file"
          accept=".txt,.md,.pdf,.docx,.json"
          style={{ display: "none" }}
          onChange={onFileChosen}
        />
        <input
          ref={bulkFileRef}
          type="file"
          accept=".txt,.md,.pdf,.docx,.json"
          multiple
          style={{ display: "none" }}
          onChange={onBulkFilesChosen}
        />
        <div className="source-upload-actions">
          <button
            type="button"
            className="primary-button"
            disabled={busy}
            onClick={() => fileRef.current?.click()}
          >
            {busy ? "Working…" : "Upload document"}
          </button>
          <button
            type="button"
            className="secondary-button"
            disabled={busy}
            onClick={() => bulkFileRef.current?.click()}
          >
            Bulk upload
          </button>
        </div>

        {uploadStatus ? <p className="source-upload-status">{uploadStatus}</p> : null}

        {error ? (
          <p className="muted-text" style={{ color: "var(--red)", marginTop: 12 }}>
            {error}
          </p>
        ) : null}

        <div style={{ marginTop: 16 }}>
          {sources === null ? (
            <p className="muted-text">Loading…</p>
          ) : count === 0 ? (
            <div className="empty-card">
              <b>The source register is empty</b>
              <span>Upload an anonymised document (.txt, .md, .pdf, .docx, .json) to get started.</span>
            </div>
          ) : (
            <div className="table-frame source-register-frame">
              <table className="data-table source-register-table">
                <thead>
                  <tr>
                    <th className="source-title-column">Title</th>
                    <th className="source-file-column">File</th>
                    <th className="source-sensitivity-column">Sensitivity</th>
                    <th className="source-state-column">State</th>
                    <th className="source-size-column">Size</th>
                    <th className="source-registered-column">Registered</th>
                    <th className="source-actions-column" />
                  </tr>
                </thead>
                <tbody>
                  {sources.map((s) => (
                    <tr key={s.id}>
                      <td className="source-title-cell">{s.title}</td>
                      <td className="source-file-cell">{s.filename}</td>
                      <td>
                        <span className="status-pill status-pill--good">{s.sensitivity}</span>
                      </td>
                      <td>
                        {s.processing_state === "ingested" ? (
                          <span className="status-pill status-pill--good">
                            ingested · {s.section_count} sections
                          </span>
                        ) : (
                          <span className="status-pill">{s.processing_state}</span>
                        )}
                      </td>
                      <td>{formatBytes(s.size_bytes)}</td>
                      <td>{formatDate(s.created_at)}</td>
                      <td className="source-actions-cell">
                        {s.processing_state === "registered" ? (
                          <button
                            type="button"
                            className="mini-button"
                            disabled={busy}
                            onClick={() => onIngest(s.id)}
                          >
                            Ingest
                          </button>
                        ) : null}
                        <button type="button" className="text-button" disabled={busy} onClick={() => onRemove(s.id)}>
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
