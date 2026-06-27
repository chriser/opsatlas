import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { getDocument, getRemediation, saveDocument, type IntelligenceIssue, type RemediationSuggestion } from "./api";
import { Markdown } from "./Markdown";

type LinePredicate = (line: string, index: number) => boolean;
type LineHighlighter = (line: string, index: number) => ReactNode;

// Editable textarea with the flagged lines highlighted: a backdrop layer renders the
// same text with <mark>s, sitting exactly behind a transparent-background textarea
// (identical font/size/padding so glyphs align), with scroll kept in sync.
function HighlightedTextarea({ value, onChange, highlightLine }: { value: string; onChange: (v: string) => void; highlightLine: LineHighlighter }) {
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
            {highlightLine(l, i)}
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

function isFenceMarker(line: string): boolean {
  const trimmed = line.trim();
  return trimmed.startsWith("```") || trimmed.startsWith("~~~");
}

function isHorizontalRule(line: string): boolean {
  return /^[-*_]{3,}$/.test(line.trim());
}

function isHeadingLine(line: string): boolean {
  return /^#{1,6}\s+\S/.test(line.trim());
}

function isMetadataLabelLine(line: string): boolean {
  return /^\*\*[^*]{2,60}:\*\*/.test(line.trim());
}

function isTableSeparatorLine(line: string): boolean {
  if (!isTableLine(line)) return false;
  const cells = line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim().replace(/\s/g, ""));
  return cells.length > 0 && cells.every((cell) => /^:?-{1,}:?$/.test(cell));
}

function isTableHeaderLine(lines: string[], index: number): boolean {
  return isTableLine(lines[index]) && index + 1 < lines.length && isTableSeparatorLine(lines[index + 1]);
}

function isStructuralSharedLine(lines: string[], index: number, inFence: boolean): boolean {
  const line = lines[index];
  return (
    inFence ||
    isFenceMarker(line) ||
    isHeadingLine(line) ||
    isHorizontalRule(line) ||
    isMetadataLabelLine(line) ||
    isTableSeparatorLine(line) ||
    isTableHeaderLine(lines, index)
  );
}

function substantiveSharedLines(text: string): Set<string> {
  const lines = text.split("\n");
  const out = new Set<string>();
  let inFence = false;
  lines.forEach((line, index) => {
    if (!isStructuralSharedLine(lines, index, inFence)) {
      const n = norm(line);
      if (n.length >= 25) out.add(n);
    }
    if (isFenceMarker(line)) inFence = !inFence;
  });
  return out;
}

// Lines shared by both documents, excluding reusable Markdown/template structure.
function sharedLines(a: string, b: string): Set<string> {
  const bSet = substantiveSharedLines(b);
  const shared = new Set<string>();
  substantiveSharedLines(a).forEach((line) => {
    if (bSet.has(line)) shared.add(line);
  });
  return shared;
}

function isTableLine(line: string): boolean {
  const trimmed = line.trim();
  return trimmed.startsWith("|") && trimmed.indexOf("|", 1) !== -1;
}

function fencedCodeLineIndexes(text: string): Set<number> {
  const out = new Set<number>();
  let inFence = false;
  text.split("\n").forEach((line, index) => {
    const trimmed = line.trim();
    if (trimmed.startsWith("```") || trimmed.startsWith("~~~")) {
      out.add(index);
      inFence = !inFence;
    } else if (inFence) {
      out.add(index);
    }
  });
  return out;
}

function wordCount(text: string): number {
  return text.match(/[A-Za-z0-9][A-Za-z0-9'’-]*/g)?.length ?? 0;
}

function sentenceParts(line: string): string[] {
  return line.match(/[^.!?]+(?:[.!?]+["')\]]*)?\s*/g) ?? [line];
}

function hasLongSentence(line: string): boolean {
  return sentenceParts(line).some((part) => wordCount(part) > 40);
}

function mark(text: string, key: string | number, hidden: boolean) {
  return <mark key={key} style={{ background: "#fde68a", color: hidden ? "transparent" : "inherit", borderRadius: 2 }}>{text}</mark>;
}

function isWordChar(char: string | undefined): boolean {
  return Boolean(char && /[A-Za-z0-9]/.test(char));
}

function termHasWordChars(term: string): boolean {
  return /[A-Za-z0-9]/.test(term);
}

function termBoundaryOk(line: string, start: number, end: number, term: string): boolean {
  if (!termHasWordChars(term)) return true;
  return !isWordChar(line[start - 1]) && !isWordChar(line[end]);
}

function termRanges(line: string, terms: string[]): { start: number; end: number }[] {
  const candidates = terms
    .filter(Boolean)
    .sort((a, b) => b.length - a.length)
    .map((term) => ({ raw: term, lower: term.toLowerCase() }));
  const lowerLine = line.toLowerCase();
  const ranges: { start: number; end: number }[] = [];
  let index = 0;
  while (index < line.length) {
    const match = candidates.find((term) => {
      const end = index + term.raw.length;
      return lowerLine.startsWith(term.lower, index) && termBoundaryOk(line, index, end, term.raw);
    });
    if (match) {
      const end = index + match.raw.length;
      ranges.push({ start: index, end });
      index = end;
    } else {
      index += 1;
    }
  }
  return ranges;
}

function highlightTermsInLine(line: string, terms: string[], hidden: boolean): ReactNode {
  const ranges = termRanges(line, terms);
  if (!ranges.length) return line;
  const nodes: ReactNode[] = [];
  let cursor = 0;
  ranges.forEach((range, index) => {
    if (range.start > cursor) nodes.push(<span key={`text-${index}`}>{line.slice(cursor, range.start)}</span>);
    nodes.push(mark(line.slice(range.start, range.end), `term-${index}`, hidden));
    cursor = range.end;
  });
  if (cursor < line.length) nodes.push(<span key="text-end">{line.slice(cursor)}</span>);
  return nodes;
}

function highlightLongSentences(line: string, hidden: boolean): ReactNode {
  const parts = sentenceParts(line);
  let found = false;
  const nodes = parts.map((part, index) => {
    if (wordCount(part) > 40) {
      found = true;
      return mark(part, index, hidden);
    }
    return <span key={index}>{part}</span>;
  });
  return found ? nodes : line;
}

// Plain-English fix per check, shown in the workbench.
const SUGGESTIONS: Record<string, string> = {
  undefined_acronym: "Define each acronym on first use, e.g. “Responsible, Accountable, Consulted, Informed (RACI)” or “RACI (Responsible, Accountable, Consulted, Informed)”.",
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
    if ((t === "$" || t === "£") || (t.length >= 2 && t.length <= 40 && !/^\d+$/.test(t))) out.add(t);
  }
  return [...out];
}

interface PaneProps {
  title: string;
  text: string;
  original: string;
  isHot: LinePredicate;
  highlightLine: LineHighlighter;
  highlightLineHidden: LineHighlighter;
  onChange: (v: string) => void;
  onSave: () => void;
  saving: boolean;
}

function Pane({ title, text, original, isHot, highlightLine, highlightLineHidden, onChange, onSave, saving }: PaneProps) {
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
        <HighlightedTextarea value={text} onChange={onChange} highlightLine={highlightLineHidden} />
      ) : (
        <div style={{ maxHeight: 380, overflow: "auto" }}>
          <Markdown text={text} isHot={isHot} highlightLine={highlightLine} />
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
  const codeLinesA = useMemo(() => fencedCodeLineIndexes(textA), [textA]);
  const isHotPair: LinePredicate = (line) => shared.has(norm(line));
  const pairHighlight = (hidden: boolean): LineHighlighter => (line, index) => (
    isHotPair(line, index) ? mark(line, "line", hidden) : line
  );
  const readabilityHot = (line: string, index: number) => (
    !codeLinesA.has(index) && !isTableLine(line) && hasLongSentence(line)
  );
  const singleHighlight = (hidden: boolean): LineHighlighter => (line, index) => {
    if (issue.check === "readability") {
      return readabilityHot(line, index) ? highlightLongSentences(line, hidden) : line;
    }
    return highlightTermsInLine(line, terms, hidden);
  };

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
            <Pane
              title={titleA}
              text={textA}
              original={origA}
              isHot={isHotPair}
              highlightLine={pairHighlight(false)}
              highlightLineHidden={pairHighlight(true)}
              onChange={setTextA}
              onSave={() => save("a")}
              saving={saving === "a"}
            />
            <Pane
              title={titleB}
              text={textB}
              original={origB}
              isHot={isHotPair}
              highlightLine={pairHighlight(false)}
              highlightLineHidden={pairHighlight(true)}
              onChange={setTextB}
              onSave={() => save("b")}
              saving={saving === "b"}
            />
          </div>
        ) : (
          <Pane
            title={titleA}
            text={textA}
            original={origA}
            isHot={() => false}
            highlightLine={singleHighlight(false)}
            highlightLineHidden={singleHighlight(true)}
            onChange={setTextA}
            onSave={() => save("a")}
            saving={saving === "a"}
          />
        )}
      </div>
    </div>
  );
}
