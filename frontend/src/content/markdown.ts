// Keep saved Markdown in the repository's own style, so an edit's version diff shows the edit and not the editor's
// reformatting: compact table rows (| a | b |, |---|---|) and no runs of blank lines.

const SEPARATOR_CELL = /^:?-{1,}:?$/;

function splitRow(line: string): string[] | null {
  const body = line.trim();
  if (!body.startsWith("|") || !body.endsWith("|") || body.length < 2) return null;
  const cells: string[] = [];
  let cell = "";
  for (let i = 1; i < body.length - 1; i++) {
    const ch = body[i];
    if (ch === "\\" && body[i + 1] === "|") {
      cell += "\\|";
      i++;
    } else if (ch === "|") {
      cells.push(cell.trim());
      cell = "";
    } else {
      cell += ch;
    }
  }
  cells.push(cell.trim());
  return cells;
}

export function tidyMarkdown(markdown: string): string {
  const lines = markdown.split("\n").map((line) => {
    const cells = splitRow(line);
    if (!cells) return line;
    if (cells.every((c) => SEPARATOR_CELL.test(c))) {
      return `|${cells.map((c) => `${c.startsWith(":") ? ":" : ""}---${c.endsWith(":") && c.length > 1 ? ":" : ""}`).join("|")}|`;
    }
    return `|${cells.map((c) => (c ? ` ${c} ` : " ")).join("|")}|`;
  });
  return lines.join("\n").replace(/\n{3,}/g, "\n\n").replace(/\s*$/, "\n");
}
