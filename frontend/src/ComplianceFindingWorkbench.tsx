import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  getDocument,
  saveComplianceResolution,
  saveDocument,
  type ComplianceFinding,
  type ComplianceResolution,
  type ComplianceResolutionAction,
} from "./api";
import { Markdown } from "./Markdown";

function mark(text: string, key: string | number) {
  return <mark key={key} style={{ background: "#fde68a", borderRadius: 3, padding: "0 2px" }}>{text}</mark>;
}

function norm(value: string): string {
  return value.trim().replace(/\s+/g, " ").toLowerCase();
}

function lineMatchesNeedle(line: string, needle: string): boolean {
  if (!needle.trim()) return false;
  const a = norm(line);
  const b = norm(needle);
  return a.includes(b) || b.includes(a);
}

function highlightNeedle(line: string, needle: string): ReactNode {
  const trimmed = needle.trim();
  if (!trimmed) return line;
  const index = line.toLowerCase().indexOf(trimmed.toLowerCase());
  if (index < 0) return line;
  return (
    <>
      {line.slice(0, index)}
      {mark(line.slice(index, index + trimmed.length), "needle")}
      {line.slice(index + trimmed.length)}
    </>
  );
}

function replaceFirstEvidence(sourceText: string, evidenceText: string, replacement: string): string {
  if (!evidenceText.trim() || !replacement.trim()) return sourceText;
  if (sourceText.includes(evidenceText)) return sourceText.replace(evidenceText, replacement);
  const evidenceNorm = norm(evidenceText);
  const lines = sourceText.split("\n");
  const index = lines.findIndex((line) => lineMatchesNeedle(line, evidenceNorm));
  if (index < 0) return sourceText;
  lines[index] = replacement;
  return lines.join("\n");
}

function actionLabel(action: ComplianceResolutionAction): string {
  return {
    acknowledged_supported: "Acknowledge",
    fixed: "Mark fixed",
    accepted_risk: "Accept risk",
    dismissed: "Dismiss",
    needs_sme_review: "SME review",
  }[action];
}

export function ComplianceFindingWorkbench({
  finding,
  existingResolution,
  onClose,
  onResolved,
}: {
  finding: ComplianceFinding;
  existingResolution?: ComplianceResolution;
  onClose: () => void;
  onResolved: (record: ComplianceResolution) => void;
}) {
  const internalSourceId = finding.internal_evidence?.source_id ?? "";
  const [originalText, setOriginalText] = useState("");
  const [draftText, setDraftText] = useState("");
  const [note, setNote] = useState(existingResolution?.note ?? "");
  const [saving, setSaving] = useState<ComplianceResolutionAction | "document" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"preview" | "edit">("preview");
  const internalEvidenceText = finding.internal_evidence?.text ?? "";
  const proposed = finding.proposed_internal_text;

  useEffect(() => {
    if (!internalSourceId) return;
    getDocument(internalSourceId)
      .then((doc) => {
        setOriginalText(doc.text);
        setDraftText(doc.text);
      })
      .catch(() => setError("Could not load the internal source document."));
  }, [internalSourceId]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const dirty = draftText !== originalText;
  const canEdit = Boolean(internalSourceId && originalText);
  const hasProposal = Boolean(proposed.trim());
  const evidenceNeedle = useMemo(() => internalEvidenceText.trim(), [internalEvidenceText]);

  function applyProposal() {
    if (!hasProposal) return;
    setDraftText((current) => replaceFirstEvidence(current, internalEvidenceText, proposed));
    setMode("edit");
  }

  async function resolve(action: ComplianceResolutionAction) {
    setSaving(action);
    setError(null);
    try {
      if (action === "fixed" && dirty && internalSourceId) {
        await saveDocument(internalSourceId, draftText);
        setOriginalText(draftText);
      }
      const record = await saveComplianceResolution({
        finding_id: finding.id,
        action,
        note,
        source_id: finding.internal_evidence?.source_id ?? "",
        source_title: finding.internal_evidence?.source_title ?? "",
        classification: finding.classification,
        severity: finding.severity,
        external_source_title: finding.external_evidence?.source_title ?? "",
        internal_evidence_text: internalEvidenceText,
        proposed_internal_text: proposed,
      });
      onResolved(record);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the compliance resolution.");
    } finally {
      setSaving(null);
    }
  }

  async function saveOnly() {
    if (!internalSourceId) return;
    setSaving("document");
    setError(null);
    try {
      await saveDocument(internalSourceId, draftText);
      setOriginalText(draftText);
    } catch {
      setError("Could not save the source document. Your edits are still here.");
    } finally {
      setSaving(null);
    }
  }

  return (
    <div
      className="modal-overlay"
      style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.55)", display: "flex", alignItems: "flex-start", justifyContent: "center", padding: "4vh 2vw", zIndex: 1000, overflow: "auto" }}
      onClick={onClose}
    >
      <div className="panel compliance-workbench" style={{ maxWidth: 1240, width: "100%", margin: 0 }} onClick={(event) => event.stopPropagation()}>
        <div className="panel-heading">
          <div>
            <h2>Resolve compliance finding</h2>
            <p className="muted-text">{finding.advisor_summary || finding.rationale}</p>
          </div>
          <button type="button" className="text-button" onClick={onClose}>Close</button>
        </div>
        {error ? <p className="muted-text" style={{ color: "var(--red)" }}>{error}</p> : null}
        {existingResolution ? (
          <p className="result-cite" style={{ color: "#166534" }}>
            Current decision: {actionLabel(existingResolution.action)} · {new Date(existingResolution.resolved_at).toLocaleString()}
          </p>
        ) : null}

        <div className="compliance-workbench-grid">
          <div className="compliance-workbench-pane">
            <div className="result-head">
              <b>External evidence</b>
              <span className="status-pill">read only</span>
            </div>
            {finding.external_evidence ? (
              <>
                <p className="result-cite">{finding.external_evidence.source_title}</p>
                <p className="result-cite">{finding.external_evidence.citation || finding.external_evidence.heading}</p>
                <div className="compliance-evidence-scroll">
                  <Markdown text={finding.external_evidence.text} />
                </div>
              </>
            ) : (
              <p className="muted-text">No external evidence attached.</p>
            )}
            <div className="result-card compliance-advisor-card">
              <b>Why it matters</b>
              <p className="result-text">{finding.why_it_matters || "Human review is required before changing approved knowledge."}</p>
              <p className="result-cite">{finding.confidence_interpretation}</p>
            </div>
          </div>

          <div className="compliance-workbench-pane">
            <div className="result-head">
              <b>Internal evidence</b>
              <span style={{ display: "inline-flex", gap: 6 }}>
                <button type="button" className={`mini-button${mode === "preview" ? "" : " text-button"}`} onClick={() => setMode("preview")}>Preview</button>
                <button type="button" className={`mini-button${mode === "edit" ? "" : " text-button"}`} onClick={() => setMode("edit")} disabled={!canEdit}>Edit</button>
              </span>
            </div>
            {finding.internal_evidence ? (
              <>
                <p className="result-cite">{finding.internal_evidence.source_title}</p>
                <p className="result-cite">{finding.internal_evidence.citation || finding.internal_evidence.heading}</p>
                {mode === "edit" ? (
                  <textarea
                    value={draftText}
                    onChange={(event) => setDraftText(event.target.value)}
                    spellCheck={false}
                    className="compliance-source-editor"
                  />
                ) : (
                  <div className="compliance-evidence-scroll">
                    <Markdown
                      text={draftText || finding.internal_evidence.text}
                      isHot={(line) => lineMatchesNeedle(line, evidenceNeedle)}
                      highlightLine={(line) => highlightNeedle(line, evidenceNeedle)}
                    />
                  </div>
                )}
              </>
            ) : (
              <p className="muted-text">No aligned internal wording was attached.</p>
            )}
            {hasProposal ? (
              <div className="result-card compliance-advisor-card">
                <div className="result-head">
                  <b>Suggested wording</b>
                  <button type="button" className="mini-button" disabled={!canEdit} onClick={applyProposal}>Apply</button>
                </div>
                <p className="result-text">{proposed}</p>
              </div>
            ) : null}
          </div>
        </div>

        <div className="compliance-resolution-footer">
          <label className="compliance-note-label">
            <span className="result-cite">Review note</span>
            <input value={note} onChange={(event) => setNote(event.target.value)} placeholder="Optional short note" />
          </label>
          <span className="compliance-resolution-actions">
            <button type="button" className="mini-button" disabled={!dirty || saving === "document"} onClick={saveOnly}>
              {saving === "document" ? "Saving..." : "Save edit only"}
            </button>
            {finding.classification === "supported" ? (
              <button type="button" className="mini-button" disabled={Boolean(saving)} onClick={() => resolve("acknowledged_supported")}>
                {saving === "acknowledged_supported" ? "Saving..." : "Acknowledge"}
              </button>
            ) : (
              <>
                <button type="button" className="mini-button" disabled={Boolean(saving)} onClick={() => resolve("fixed")}>
                  {saving === "fixed" ? "Saving..." : "Save & mark fixed"}
                </button>
                <button type="button" className="mini-button" disabled={Boolean(saving)} onClick={() => resolve("needs_sme_review")}>SME review</button>
                <button type="button" className="mini-button" disabled={Boolean(saving)} onClick={() => resolve("accepted_risk")}>Accept risk</button>
                <button type="button" className="text-button" disabled={Boolean(saving)} onClick={() => resolve("dismissed")}>Dismiss</button>
              </>
            )}
          </span>
        </div>
      </div>
    </div>
  );
}
