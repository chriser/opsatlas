import { useEffect, useMemo, useState } from "react";
import { getDocument, getRemediation, saveDocument, type IntelligenceIssue, type RemediationSuggestion } from "./api";

// A line counts as "shared" when its normalised form (>= 25 chars to skip trivial
// matches) appears in both documents. Highlighting these shows exactly what to trim.
function norm(s: string): string {
  return s.trim().toLowerCase().replace(/\s+/g, " ");
}

function sharedLines(a: string, b: string): Set<string> {
  const bSet = new Set(b.split("\n").map(norm).filter((l) => l.length >= 25));
  const shared = new Set<string>();
  for (const line of a.split("\n")) {
    const n = norm(line);
    if (n.length >= 25 && bSet.has(n)) shared.add(n);
  }
  return shared;
}

function inline(text: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((p, i) =>
    p.startsWith("**") && p.endsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong> : <span key={i}>{p}</span>,
  );
}

// Lightweight Markdown line renderer (headings, bullets, bold, paragraphs) with an
// overlap highlight — enough to display the packs nicely without a Markdown dependency.
function MarkdownPreview({ text, shared }: { text: string; shared: Set<string> }) {
  return (
    <div className="md-preview" style={{ padding: "4px 2px", lineHeight: 1.5 }}>
      {text.split("\n").map((line, key) => {
        const hot = shared.has(norm(line));
        const hl = hot ? { background: "#fde68a", borderRadius: 3, padding: "0 2px" } : undefined;
        const h = line.match(/^(#{1,4})\s+(.*)/);
        if (h) {
          const lv = h[1].length;
          return (
            <div key={key} style={{ margin: "10px 0 4px", fontWeight: 700, fontSize: lv <= 1 ? 18 : lv === 2 ? 16 : 14, ...hl }}>
              {inline(h[2])}
            </div>
          );
        }
        const li = line.match(/^[-*]\s+(.*)/);
        if (li) return <div key={key} style={{ margin: "2px 0 2px 14px", ...hl }}>• {inline(li[1])}</div>;
        if (!line.trim()) return <div key={key} style={{ height: 6 }} />;
        return <p key={key} style={{ margin: "4px 0", ...hl }}>{inline(line)}</p>;
      })}
    </div>
  );
}

interface PaneProps {
  title: string;
  text: string;
  original: string;
  shared: Set<string>;
  onChange: (v: string) => void;
  onSave: () => void;
  saving: boolean;
}

function Pane({ title, text, original, shared, onChange, onSave, saving }: PaneProps) {
  const [mode, setMode] = useState<"edit" | "preview">("preview");
  const dirty = text !== original;
  return (
    <div className="panel" style={{ flex: 1, minWidth: 0 }}>
      <div className="panel-heading">
        <div>
          <h2 style={{ fontSize: 15 }}>{title}</h2>
          <p className="muted-text">Highlighted text appears in both documents.</p>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <button type="button" className={`mini-button${mode === "preview" ? "" : " text-button"}`} onClick={() => setMode("preview")}>Preview</button>
          <button type="button" className={`mini-button${mode === "edit" ? "" : " text-button"}`} onClick={() => setMode("edit")}>Edit</button>
        </div>
      </div>
      {mode === "edit" ? (
        <textarea
          value={text}
          onChange={(e) => onChange(e.target.value)}
          spellCheck={false}
          style={{ width: "100%", minHeight: 360, fontFamily: "ui-monospace, monospace", fontSize: 12, padding: 10, boxSizing: "border-box" }}
        />
      ) : (
        <div style={{ maxHeight: 380, overflow: "auto" }}>
          <MarkdownPreview text={text} shared={shared} />
        </div>
      )}
      <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
        <button type="button" className="mini-button" disabled={!dirty || saving} onClick={onSave}>
          {saving ? "Saving…" : dirty ? "Save & re-ingest" : "No changes"}
        </button>
      </div>
    </div>
  );
}

export function ReviewWorkbench({ issue, onClose, onSaved }: { issue: IntelligenceIssue; onClose: () => void; onSaved: () => void }) {
  const [origA, setOrigA] = useState("");
  const [origB, setOrigB] = useState("");
  const [textA, setTextA] = useState("");
  const [textB, setTextB] = useState("");
  const [titleA, setTitleA] = useState(issue.source_title);
  const [titleB, setTitleB] = useState(issue.source_b_title ?? "");
  const [saving, setSaving] = useState<"a" | "b" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [suggestion, setSuggestion] = useState<RemediationSuggestion | null>(null);

  useEffect(() => {
    if (!issue.source_b_id) return;
    const bId = issue.source_b_id;
    Promise.all([getDocument(issue.source_id), getDocument(bId)])
      .then(([a, b]) => {
        setOrigA(a.text); setTextA(a.text); setTitleA(a.title);
        setOrigB(b.text); setTextB(b.text); setTitleB(b.title);
      })
      .catch(() => setError("Could not load the documents."));
    getRemediation(issue.source_id, bId).then(setSuggestion).catch(() => setSuggestion(null));
  }, [issue]);

  function applySuggestion() {
    if (!suggestion) return;
    if (suggestion.trim_id === issue.source_id) setTextA(suggestion.trim_suggested_text);
    else setTextB(suggestion.trim_suggested_text);
  }

  const shared = useMemo(() => sharedLines(textA, textB), [textA, textB]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function save(side: "a" | "b") {
    const id = side === "a" ? issue.source_id : issue.source_b_id;
    if (!id) return;
    setSaving(side);
    try {
      await saveDocument(id, side === "a" ? textA : textB);
      if (side === "a") setOrigA(textA); else setOrigB(textB);
      onSaved();
    } catch {
      setError("Could not save. Your edits are still here — try again.");
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
      <div className="panel" style={{ maxWidth: 1180, width: "100%", margin: 0 }} onClick={(e) => e.stopPropagation()}>
      <div className="panel-heading">
        <div>
          <h2>Review duplicate</h2>
          <p className="muted-text">{shared.size} overlapping line{shared.size === 1 ? "" : "s"} highlighted. Edit either side to remove the duplication, then save.</p>
        </div>
        <button type="button" className="text-button" onClick={onClose}>Close</button>
      </div>
      {error ? <p className="muted-text" style={{ color: "var(--red)" }}>{error}</p> : null}
      {suggestion && suggestion.shared_lines > 0 ? (
        <div className="result-card" style={{ marginBottom: 12, borderLeft: "3px solid #db2777" }}>
          <div className="result-head">
            <b>Suggested fix</b>
            <button type="button" className="mini-button" onClick={applySuggestion}>
              Apply: trim “{suggestion.trim_title}”
            </button>
          </div>
          <p className="result-text">{suggestion.reason}</p>
          <p className="result-cite">Review the proposed edit in the highlighted pane, then Save &amp; re-ingest.</p>
        </div>
      ) : null}
      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        <Pane title={titleA} text={textA} original={origA} shared={shared} onChange={setTextA} onSave={() => save("a")} saving={saving === "a"} />
        <Pane title={titleB} text={textB} original={origB} shared={shared} onChange={setTextB} onSave={() => save("b")} saving={saving === "b"} />
      </div>
      </div>
    </div>
  );
}
