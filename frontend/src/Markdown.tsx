import type { ReactNode } from "react";

// Lightweight Markdown renderer (headings, bold, bullet & numbered lists, tables,
// paragraphs) — no dependency. Optional isHot(line) highlights matching lines, used by
// the review workbench; the Ask page uses it without highlighting.

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

type LinePredicate = (line: string, index: number) => boolean;
type LineHighlighter = (line: string, index: number) => ReactNode;

function highlightedInline(line: string, key: number, highlightLine?: LineHighlighter) {
  return highlightLine ? highlightLine(line, key) : inline(line);
}

function renderLine(line: string, key: number, isHot: LinePredicate, highlightLine?: LineHighlighter) {
  const hl = isHot(line, key) ? { background: "#fde68a", borderRadius: 3, padding: "0 2px" } : undefined;
  const h = line.match(/^(#{1,4})\s+(.*)/);
  if (h) {
    const lv = h[1].length;
    return (
      <div key={key} style={{ margin: "10px 0 4px", fontWeight: 700, fontSize: lv <= 1 ? 18 : lv === 2 ? 16 : 14, ...hl }}>
        {highlightedInline(h[2], key, highlightLine)}
      </div>
    );
  }
  const ol = line.match(/^\s*(\d+)\.\s+(.*)/);
  if (ol) return <div key={key} style={{ margin: "3px 0 3px 14px", ...hl }}>{ol[1]}. {highlightedInline(ol[2], key, highlightLine)}</div>;
  const li = line.match(/^\s*[-*]\s+(.*)/);
  if (li) return <div key={key} style={{ margin: "2px 0 2px 14px", ...hl }}>• {highlightedInline(li[1], key, highlightLine)}</div>;
  if (!line.trim()) return <div key={key} style={{ height: 6 }} />;
  return <p key={key} style={{ margin: "4px 0", ...hl }}>{highlightedInline(line, key, highlightLine)}</p>;
}

function renderTable(rows: string[], key: number, isHot: LinePredicate, highlightLine?: LineHighlighter) {
  const header = splitRow(rows[0]);
  const bodyRows = rows.slice(rows[1] && isSeparatorRow(rows[1]) ? 2 : 1);
  const cell = { border: "1px solid var(--border, #e2e8f0)", padding: "5px 8px", textAlign: "left" as const, verticalAlign: "top" as const, fontSize: 12 };
  return (
    <table key={key} style={{ borderCollapse: "collapse", width: "100%", margin: "8px 0" }}>
      <thead>
        <tr>{header.map((c, i) => <th key={i} style={{ ...cell, background: "var(--surface-2, #f1f5f9)", fontWeight: 700 }}>{highlightedInline(c, key, highlightLine)}</th>)}</tr>
      </thead>
      <tbody>
        {bodyRows.map((raw, r) => (
          <tr key={r} style={isHot(raw, key + r) ? { background: "#fde68a" } : undefined}>
            {splitRow(raw).map((c, i) => <td key={i} style={cell}>{highlightedInline(c, key + r, highlightLine)}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function Markdown({
  text,
  isHot = () => false,
  highlightLine,
}: {
  text: string;
  isHot?: LinePredicate;
  highlightLine?: LineHighlighter;
}) {
  const lines = text.split("\n");
  const blocks = [];
  let i = 0;
  while (i < lines.length) {
    if (isTableRow(lines[i])) {
      const group: string[] = [];
      while (i < lines.length && isTableRow(lines[i])) { group.push(lines[i]); i++; }
      blocks.push(renderTable(group, i, isHot, highlightLine));
      continue;
    }
    blocks.push(renderLine(lines[i], i, isHot, highlightLine));
    i++;
  }
  return <div className="md-preview" style={{ lineHeight: 1.5 }}>{blocks}</div>;
}
