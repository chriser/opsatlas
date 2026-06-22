import { useEffect, useMemo, useRef, useState } from "react";
import { getDocument, getRemediation, saveDocument, type IntelligenceIssue, type RemediationSuggestion } from "./api";

// Editable textarea with the flagged lines highlighted: a backdrop layer renders the
// same text with <mark>s, sitting exactly behind a transparent-background textarea
// (identical font/size/padding so glyphs align), with scroll kept in sync.
function HighlightedTextarea({ value, onChange, isHot }: { value: string; onChange: (v: string) => void; isHot: (line: string) => boolean }) {
  const taRef = useRef<HTMLTextAreaElement>(null);
  const backRef = useRef<HTMLDivElement>(null);
  const box = {
    fontFamily: "ui-monospace, monospace",
    fontSize: 12,
    lineHeight: 1.5,
    padding: 10,
    margin: 0,
    border: "none",
    boxSizing: "border-box" as const,
    whiteSpace: "pre-wrap" as const,
    overflowWrap: "break-word" as const,
    width: "100%",
    minHeight: 360,
  };
  function sync() {
    if (backRef.current && taRef.current) {
      backRef.current.scrollTop = taRef.current.scrollTop;
      backRef.current.scrollLeft = taRef.current.scrollLeft;
    }
  }
  const lines = value.split("\n");
  return (
    <div style={{ position: "relative", border: "1px solid var(--border, #e2e8f0)", borderRadius: 4, minHeight: 360 }}>
      <div ref={backRef} aria-hidden="true" style={{ ...box, position: "absolute", inset: 0, overflow: "hidden", color: "transparent", pointerEvents: "none" }}>
        {lines.map((l, i) => (
          <span key={i}>
            {isHot(l) ? <mark style={{ background: "#fde68a", color: "transparent", borderRadius: 2 }}>{l}</mark> : l}
            {i < lines.length - 1 ? "\n" : ""}
          </span>
        ))}
      </div>
      <textarea
        ref={taRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onScroll={sync}
        spellCheck={false}
        style={{ ...box, position: "relative", background: "transparent", color: "inherit", resize: "vertical", display: "block" }}
      />
    </div>
  );
}

function norm(s: string): string {
  return s.trim().toLowerCase().replace(/\s+/g, " ");
}

// Lines shared by both documents (>= 25 chars to skip trivial matches).
function sharedLines(a: string, b: string): Set<string> {
  const bSet = new Set(b.split("\n").map(norm).filter((l) => l.length >= 25));
  const shared = new Set<string>();
  for (const line of a.split("\n")) {
    const n = norm(line);
    if (n.length >= 25 && bSet.has(n)) shared.add(n);
  }
  return shared;
}

// Plain-English fix per check, shown in the workbench.
const SUGGESTIONS: Record<string, string> = {
  undefined_acronym: "Define each acronym on first use, e.g. “Responsible, Accountable, Consulted, Informed (RACI)”.",
  readability: "Split the highlighted long sentences into shorter ones and break up dense paragraphs.",
  localisation: "Choose one locale (UK or US) and apply spelling/currency consistently.",
  content_style: "Replace placeholder markers with final content and standardise on one term.",
  broken_link: "Fix or remove the broken/placeholder link targets.",
  metadata_title: "Give this source a descriptive title (set it on the source, not in the body).",
  not_ingested: "Ingest this source so the assistant can use it.",
  conflict: "Reconcile the contradicting statements between the two documents.",
};

// Terms to highlight for a single-document issue, parsed from the issue detail.
function highlightTerms(issue: IntelligenceIssue): string[] {
  const afterColon = issue.detail.toLowerCase().split(":").slice(1).join(":");
  const out = new Set<string>();
  for (const raw of afterColon.split(/[,/;()]+/)) {
    const t = raw.trim().replace(/[.\s]+$/, "");
    if (t.length >= 2 && t.length <= 40 && !/^\d+$/.test(t)) out.add(t);
  }
  return [...out];
}

function inline(text: string) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((p, i) =>
    p.startsWith("**") && p.endsWith("**") ? <strong key={i}>{p.slice(2, -2)}</strong> : <span key={i}>{p}</span>,
  );
}

function isTableRow(line: string): boolean {
  const t = line.trim();
  return t.startsWith("|") && t.indexOf("|", 1) !== -1;
}

function splitRow(line: string): string[] {
  let t = line.trim();
  if (t.startsWith("|")) t = t.slice(1);
  if (t.endsWith("|")) t = t.slice(0, -1);
  return t.split("|").map((c) => c.trim());
}

function isSeparatorRow(line: string): boolean {
  const cells = splitRow(line);
  return cells.length > 0 && cells.every((c) => /^:?-{1,}:?$/.test(c.replace(/\s/g, "")));
}

function renderLine(line: string, key: number, isHot: (l: string) => boolean) {
  const hl = isHot(line) ? { background: "#fde68a", borderRadius: 3, padding: "0 2px" } : undefined;
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
}

function renderTable(rows: string[], key: number, isHot: (l: string) => boolean) {
  const header = splitRow(rows[0]);
  const bodyRows = rows.slice(rows[1] && isSeparatorRow(rows[1]) ? 2 : 1);
  const cell = { border: "1px solid var(--border, #e2e8f0)", padding: "5px 8px", textAlign: "left" as const, verticalAlign: "top" as const, fontSize: 12 };
  return (
    <table key={key} style={{ borderCollapse: "collapse", width: "100%", margin: "8px 0" }}>
      <thead>
        <tr>{header.map((c, i) => <th key={i} style={{ ...cell, background: "var(--surface-2, #f1f5f9)", fontWeight: 700 }}>{inline(c)}</th>)}</tr>
      </thead>
      <tbody>
        {bodyRows.map((raw, r) => (
          <tr key={r} style={isHot(raw) ? { background: "#fde68a" } : undefined}>
            {splitRow(raw).map((c, i) => <td key={i} style={cell}>{inline(c)}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function MarkdownPreview({ text, isHot }: { text: string; isHot: (line: string) => boolean }) {
  const lines = text.split("\n");
  const blocks = [];
  let i = 0;
  while (i < lines.length) {
    if (isTableRow(lines[i])) {
      const group: string[] = [];
      while (i < lines.length && isTableRow(lines[i])) { group.push(lines[i]); i++; }
      blocks.push(renderTable(group, i, isHot));
      continue;
    }
    blocks.push(renderLine(lines[i], i, isHot));
    i++;
  }
  return <div className="md-preview" style={{ padding: "4px 2px", lineHeight: 1.5 }}>{blocks}</div>;
}

interface PaneProps {
  title: string;
  text: string;
  original: string;
  isHot: (line: string) => boolean;
  onChange: (v: string) => void;
  onSave: () => void;
  saving: boolean;
}

function Pane({ title, text, original, isHot, onChange, onSave, saving }: PaneProps) {
  const [mode, setMode] = useState<"edit" | "preview">("preview");
  const dirty = text !== original;
  return (
    <div className="panel" style={{ flex: 1, minWidth: 0 }}>
      <div className="panel-heading">
        <div>
          <h2 style={{ fontSize: 15 }}>{title}</h2>
          <p className="muted-text">Highlighted text is the flagged content.</p>
        </div>
        <div style={{ display: "flex", gap: 6 }}>
          <button type="button" className={`mini-button${mode === "preview" ? "" : " text-button"}`} onClick={() => setMode("preview")}>Preview</button>
          <button type="button" className={`mini-button${mode === "edit" ? "" : " text-button"}`} onClick={() => setMode("edit")}>Edit</button>
        </div>
      </div>
      {mode === "edit" ? (
        <HighlightedTextarea value={text} onChange={onChange} isHot={isHot} />
      ) : (
        <div style={{ maxHeight: 380, overflow: "auto" }}>
          <MarkdownPreview text={text} isHot={isHot} />
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
  const isPair = Boolean(issue.source_b_id);
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
    const loads = [getDocument(issue.source_id)];
    if (issue.source_b_id) loads.push(getDocument(issue.source_b_id));
    Promise.all(loads)
      .then(([a, b]) => {
        setOrigA(a.text); setTextA(a.text); setTitleA(a.title);
        if (b) { setOrigB(b.text); setTextB(b.text); setTitleB(b.title); }
      })
      .catch(() => setError("Could not load the document(s)."));
    if (issue.source_b_id) getRemediation(issue.source_id, issue.source_b_id).then(setSuggestion).catch(() => setSuggestion(null));
  }, [issue]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const shared = useMemo(() => (isPair ? sharedLines(textA, textB) : new Set<string>()), [isPair, textA, textB]);
  const terms = useMemo(() => (isPair ? [] : highlightTerms(issue)), [isPair, issue]);
  const isHotPair = (line: string) => shared.has(norm(line));
  const isHotSingle = (line: string) =>
    issue.check === "readability"
      ? line.trim().split(/\s+/).length > 40
      : terms.some((t) => line.toLowerCase().includes(t));

  function applySuggestion() {
    if (!suggestion) return;
    if (suggestion.trim_id === issue.source_id) setTextA(suggestion.trim_suggested_text);
    else setTextB(suggestion.trim_suggested_text);
  }

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
      <div className="panel" style={{ maxWidth: isPair ? 1180 : 760, width: "100%", margin: 0 }} onClick={(e) => e.stopPropagation()}>
        <div className="panel-heading">
          <div>
            <h2>{isPair ? "Review duplicate" : "Review issue"}</h2>
            <p className="muted-text">
              {isPair
                ? `${shared.size} overlapping line${shared.size === 1 ? "" : "s"} highlighted. Edit either side, then save.`
                : "The flagged content is highlighted below. Edit and save, or accept the issue."}
            </p>
          </div>
          <button type="button" className="text-button" onClick={onClose}>Close</button>
        </div>
        {error ? <p className="muted-text" style={{ color: "var(--red)" }}>{error}</p> : null}

        {/* Pair suggestion banner */}
        {isPair && suggestion && suggestion.shared_lines > 0 ? (
          <div className="result-card" style={{ marginBottom: 12, borderLeft: "3px solid #db2777" }}>
            <div className="result-head">
              <b>Suggested fix</b>
              <button type="button" className="mini-button" onClick={applySuggestion}>Apply: trim “{suggestion.trim_title}”</button>
            </div>
            <p className="result-text">{suggestion.reason}</p>
            <p className="result-cite">Review the proposed edit in the highlighted pane, then Save &amp; re-ingest.</p>
          </div>
        ) : null}

        {/* Single-issue suggestion banner */}
        {!isPair ? (
          <div className="result-card" style={{ marginBottom: 12, borderLeft: "3px solid #db2777" }}>
            <b>{issue.check.replace(/_/g, " ")}</b>
            <p className="result-text">{issue.detail}</p>
            {SUGGESTIONS[issue.check] ? <p className="result-cite">Suggested fix: {SUGGESTIONS[issue.check]}</p> : null}
          </div>
        ) : null}

        {isPair ? (
          <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
            <Pane title={titleA} text={textA} original={origA} isHot={isHotPair} onChange={setTextA} onSave={() => save("a")} saving={saving === "a"} />
            <Pane title={titleB} text={textB} original={origB} isHot={isHotPair} onChange={setTextB} onSave={() => save("b")} saving={saving === "b"} />
          </div>
        ) : (
          <Pane title={titleA} text={textA} original={origA} isHot={isHotSingle} onChange={setTextA} onSave={() => save("a")} saving={saving === "a"} />
        )}
      </div>
    </div>
  );
}
