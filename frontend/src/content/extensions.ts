// Editor extensions for content management: comment and suggestion highlights (CM S20), capitalisation (CM S3),
// and small table and text helpers the toolbar needs.
import { Extension, type Editor } from "@tiptap/core";
import type { Node as PMNode } from "@tiptap/pm/model";
import { Plugin, PluginKey, TextSelection } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";

export interface Anchor {
  id: string;
  quote: string;
  prefix?: string;
  suffix?: string;
  kind: "comment" | "suggestion";
  active?: boolean;
}

interface Flat {
  text: string; // the document's text, whitespace squashed, blocks separated by one space
  positions: number[]; // the document position of each character (-1 where a block boundary stands in)
}

/** The document's text with a map back to positions, so a quote taken from rendered text can be found again. */
export function flatten(doc: PMNode): Flat {
  let text = "";
  const positions: number[] = [];
  const push = (ch: string, pos: number) => {
    const space = /\s/.test(ch);
    if (space && (text.length === 0 || text[text.length - 1] === " ")) return;
    text += space ? " " : ch;
    positions.push(pos);
  };
  doc.descendants((node, pos) => {
    if (node.isText && node.text) {
      for (let i = 0; i < node.text.length; i++) push(node.text[i], pos + i);
    } else if (node.isBlock && text.length) {
      push(" ", -1);
    }
    return true;
  });
  return { text, positions };
}

const squash = (s: string) => s.replace(/\s+/g, " ");

function commonSuffix(a: string, b: string) {
  let n = 0;
  while (n < Math.min(a.length, b.length) && a[a.length - 1 - n] === b[b.length - 1 - n]) n++;
  return n;
}

function commonPrefix(a: string, b: string) {
  let n = 0;
  while (n < Math.min(a.length, b.length) && a[n] === b[n]) n++;
  return n;
}

/** Document range of a quote: the occurrence whose surroundings best match its context, or null if it is gone. */
export function locate(flat: Flat, quote: string, prefix = "", suffix = ""): { from: number; to: number } | null {
  const needle = squash(quote).trim();
  if (!needle) return null;
  let best = -1;
  let bestScore = -1;
  for (let at = flat.text.indexOf(needle); at !== -1; at = flat.text.indexOf(needle, at + 1)) {
    const score = commonSuffix(flat.text.slice(0, at), squash(prefix)) + commonPrefix(flat.text.slice(at + needle.length), squash(suffix));
    if (score > bestScore) {
      best = at;
      bestScore = score;
    }
  }
  if (best < 0) return null;
  let start = best;
  while (start < best + needle.length && flat.positions[start] < 0) start++;
  let end = best + needle.length - 1;
  while (end > start && flat.positions[end] < 0) end--;
  if (flat.positions[start] < 0 || flat.positions[end] < 0) return null;
  return { from: flat.positions[start], to: flat.positions[end] + 1 };
}

/** What a comment is anchored to: the selected text with a little context either side. */
export function selectionAnchor(editor: Editor): { quote: string; prefix: string; suffix: string } | null {
  const { from, to } = editor.state.selection;
  if (from === to) return null;
  const doc = editor.state.doc;
  const quote = doc.textBetween(from, to, " ", " ").trim();
  if (!quote) return null;
  return {
    quote,
    prefix: doc.textBetween(Math.max(0, from - 60), from, " ", " "),
    suffix: doc.textBetween(to, Math.min(doc.content.size, to + 60), " ", " "),
  };
}

const anchorsKey = new PluginKey<{ anchors: Anchor[]; decorations: DecorationSet }>("cmAnchors");

function decorate(doc: PMNode, anchors: Anchor[]): DecorationSet {
  const flat = flatten(doc);
  const decorations: Decoration[] = [];
  for (const anchor of anchors) {
    const range = locate(flat, anchor.quote, anchor.prefix, anchor.suffix);
    if (!range || range.from >= range.to) continue;
    decorations.push(
      Decoration.inline(range.from, range.to, {
        class: `cm-mark cm-mark--${anchor.kind}${anchor.active ? " cm-mark--active" : ""}`,
        "data-anchor": anchor.id,
      }),
    );
  }
  return DecorationSet.create(doc, decorations);
}

export interface AnchorOptions {
  onActivate: (id: string) => void;
}

/** Highlights commented and suggested passages; clicking one tells the page which thread to open. */
export const AnchorHighlights = Extension.create<AnchorOptions>({
  name: "cmAnchors",
  addOptions() {
    return { onActivate: () => undefined };
  },
  addProseMirrorPlugins() {
    const options = this.options;
    return [
      new Plugin({
        key: anchorsKey,
        state: {
          init: (_, state): { anchors: Anchor[]; decorations: DecorationSet } => ({
            anchors: [],
            decorations: DecorationSet.create(state.doc, []),
          }),
          apply(tr, value, _old, state) {
            const next = tr.getMeta(anchorsKey) as Anchor[] | undefined;
            if (next) return { anchors: next, decorations: decorate(state.doc, next) };
            if (tr.docChanged) return { anchors: value.anchors, decorations: decorate(state.doc, value.anchors) };
            return value;
          },
        },
        props: {
          decorations: (state) => anchorsKey.getState(state)?.decorations,
          handleClick: (_view, _pos, event) => {
            const target = (event.target as HTMLElement | null)?.closest?.("[data-anchor]");
            const id = target?.getAttribute("data-anchor");
            if (id) options.onActivate(id);
            return false;
          },
        },
      }),
    ];
  },
});

export function setAnchors(editor: Editor, anchors: Anchor[]) {
  editor.view.dispatch(editor.state.tr.setMeta(anchorsKey, anchors).setMeta("addToHistory", false));
}

/** Scroll the editor to a passage and select it. */
export function revealQuote(editor: Editor, quote: string, prefix = "", suffix = "", select = true): boolean {
  const range = locate(flatten(editor.state.doc), quote, prefix, suffix);
  if (!range) return false;
  const tr = editor.state.tr;
  if (select) tr.setSelection(TextSelection.create(editor.state.doc, range.from, range.to));
  editor.view.dispatch(tr.scrollIntoView());
  const dom = editor.view.domAtPos(range.from).node as HTMLElement;
  (dom.nodeType === 1 ? dom : dom.parentElement)?.scrollIntoView({ block: "center", behavior: "smooth" });
  return true;
}

/** Replace the first whole-word occurrence of a term (a governance fix such as spelling out an acronym). With
 * avoidHeadings, the first use in the text wins over one in a heading, as style guides spell a term out there. */
export function replaceQuote(editor: Editor, find: string, replace: string, options: { avoidHeadings?: boolean } = {}): boolean {
  const matches: { from: number; to: number; heading: boolean }[] = [];
  // A whole word, not part of a compound ("RAG-only" stays as it is).
  const word = new RegExp(`(^|[^\\p{L}\\p{N}-])(${find.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})(?=$|[^\\p{L}\\p{N}-])`, "gu");
  editor.state.doc.descendants((node, pos, parent) => {
    if (!node.isText || !node.text) return;
    for (const m of node.text.matchAll(word)) {
      const start = pos + (m.index ?? 0) + m[1].length;
      matches.push({ from: start, to: start + find.length, heading: parent?.type.name === "heading" });
    }
  });
  const chosen = (options.avoidHeadings && matches.find((m) => !m.heading)) || matches[0];
  if (!chosen) return false;
  editor.chain().focus().insertContentAt({ from: chosen.from, to: chosen.to }, replace).run();
  return true;
}

export type CaseStyle = "sentence" | "lower" | "upper" | "title";

const SMALL_WORDS = new Set("a an and as at but by for from in into nor of on or so the to up via with".split(" "));

export function changeCase(text: string, style: CaseStyle): string {
  if (style === "lower") return text.toLowerCase();
  if (style === "upper") return text.toUpperCase();
  if (style === "sentence") {
    const lower = text.toLowerCase();
    return lower.replace(/(^\s*\p{L})|([.!?]\s+\p{L})/gu, (m) => m.toUpperCase());
  }
  let first = true;
  return text.toLowerCase().replace(/\p{L}[\p{L}'’-]*/gu, (word) => {
    const keep = !first && SMALL_WORDS.has(word);
    first = false;
    return keep ? word : word[0].toUpperCase() + word.slice(1);
  });
}

/** Change the case of the selection in place, keeping its formatting (bold, links) intact. */
export function applyCase(editor: Editor, style: CaseStyle) {
  const { from, to } = editor.state.selection;
  if (from === to) return;
  const segments: { from: number; to: number; text: string }[] = [];
  editor.state.doc.nodesBetween(from, to, (node, pos) => {
    if (!node.isText || !node.text) return;
    const start = Math.max(from, pos);
    const end = Math.min(to, pos + node.text.length);
    if (end > start) segments.push({ from: start, to: end, text: node.text.slice(start - pos, end - pos) });
  });
  const joined = segments.map((s) => s.text).join("");
  const changed = changeCase(joined, style);
  const tr = editor.state.tr;
  let offset = 0;
  const parts = segments.map((s) => {
    const part = changed.length === joined.length ? changed.slice(offset, offset + s.text.length) : changeCase(s.text, style);
    offset += s.text.length;
    return part;
  });
  for (let i = segments.length - 1; i >= 0; i--) {
    const s = segments[i];
    if (parts[i] !== s.text) tr.insertText(parts[i], s.from, s.to);
  }
  tr.setSelection(TextSelection.create(tr.doc, from, to));
  editor.view.dispatch(tr);
  editor.commands.focus();
}

/** Duplicate the table row the cursor is in. */
export function duplicateRow(editor: Editor): boolean {
  const { $from } = editor.state.selection;
  for (let depth = $from.depth; depth > 0; depth--) {
    const node = $from.node(depth);
    if (node.type.name === "tableRow") {
      const after = $from.after(depth);
      editor.view.dispatch(editor.state.tr.insert(after, node.copy(node.content)));
      return true;
    }
  }
  return false;
}

/** Empty the cell the cursor is in (a cell selection is cleared by the table extension itself). */
export function clearCell(editor: Editor): boolean {
  const { $from } = editor.state.selection;
  for (let depth = $from.depth; depth > 0; depth--) {
    const node = $from.node(depth);
    if (node.type.name === "tableCell" || node.type.name === "tableHeader") {
      const start = $from.start(depth);
      const end = $from.end(depth);
      const empty = editor.state.schema.nodes.paragraph.create();
      editor.view.dispatch(editor.state.tr.replaceWith(start, end, empty));
      return true;
    }
  }
  return false;
}

export function countWords(text: string): number {
  return (text.match(/[\p{L}\p{N}][\p{L}\p{N}'’-]*/gu) ?? []).length;
}
