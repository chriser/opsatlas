// The library (CM S27): groups that are not documents, and where each document sits. A parent is "group:<id>",
// "source:<id>" (a document under another document) or null for the top level.
import { apiRequest } from "../api";
import type { ContentDocument } from "./api";

export interface LibraryGroup {
  id: string;
  title: string;
  parent: string | null;
  position: number;
  created_at: string;
}

export interface Library {
  groups: LibraryGroup[];
  placements: Record<string, { parent: string | null; position: number }>;
}

const enc = encodeURIComponent;
export const getLibrary = () => apiRequest<Library>("GET", "/api/content/library");
export const createGroup = (title: string, parent: string | null) =>
  apiRequest<Library & { id: string }>("POST", "/api/content/groups", { title, parent });
export const renameGroup = (id: string, title: string) => apiRequest<Library>("PATCH", `/api/content/groups/${enc(id)}`, { fields: { title } });
export const moveGroup = (id: string, parent: string | null) =>
  apiRequest<Library>("PATCH", `/api/content/groups/${enc(id)}`, { fields: { parent } });
export const deleteGroup = (id: string) => apiRequest<Library>("DELETE", `/api/content/groups/${enc(id)}`);
export const setParent = (sourceId: string, parent: string | null) =>
  apiRequest<Library>("PUT", `/api/content/documents/${enc(sourceId)}/parent`, { parent });
/** Drag and drop (CM S30): put a document or group ("source:<id>" / "group:<id>") under ``parent`` just before
 *  ``before``, or last. */
export const moveNode = (node: string, parent: string | null, before: string | null) =>
  apiRequest<Library & { moved: string }>("POST", "/api/content/library/move", { node, parent, before });
export const renameDocument = (sourceId: string, title: string) =>
  apiRequest<ContentDocument>("POST", `/api/content/documents/${enc(sourceId)}/rename`, { title });

export interface TreeNode<T> {
  key: string;
  kind: "group" | "source";
  group?: LibraryGroup;
  item?: T;
  children: TreeNode<T>[];
  /** Documents anywhere below this node. */
  documents: T[];
}

/** The library as a tree over the given documents. Anything whose parent is missing, or that would sit inside
 *  itself, is shown at the top level; documents not yet placed come last. */
export function buildTree<T extends { id: string; title: string }>(library: Library | null, items: T[]): TreeNode<T>[] {
  const nodes = new Map<string, TreeNode<T> & { parent: string | null; position: number; title: string }>();
  for (const g of library?.groups ?? []) {
    nodes.set(`group:${g.id}`, { key: `group:${g.id}`, kind: "group", group: g, children: [], documents: [], parent: g.parent, position: g.position, title: g.title });
  }
  for (const item of items) {
    const at = library?.placements[item.id];
    nodes.set(`source:${item.id}`, {
      key: `source:${item.id}`, kind: "source", item, children: [], documents: [],
      parent: at?.parent ?? null, position: at ? at.position : Number.MAX_SAFE_INTEGER, title: item.title,
    });
  }
  const parentOf = (key: string): string | null => {
    const parent = nodes.get(key)?.parent ?? null;
    if (!parent || !nodes.has(parent)) return null;
    // Walk up: a loop (which the server refuses) would hide the whole branch, so break it here.
    const seen = new Set([key]);
    for (let at: string | null = parent; at; at = nodes.get(at)?.parent ?? null) {
      if (seen.has(at)) return null;
      seen.add(at);
      if (!nodes.has(at)) break;
    }
    return parent;
  };
  const roots: TreeNode<T>[] = [];
  for (const node of nodes.values()) {
    const parent = parentOf(node.key);
    (parent ? nodes.get(parent)!.children : roots).push(node);
  }
  const order = (a: TreeNode<T>, b: TreeNode<T>) => {
    const x = nodes.get(a.key)!;
    const y = nodes.get(b.key)!;
    return x.position - y.position || x.title.localeCompare(y.title);
  };
  const finish = (list: TreeNode<T>[]): T[] => {
    list.sort(order);
    const all: T[] = [];
    for (const node of list) {
      node.documents = finish(node.children);
      if (node.item) all.push(node.item);
      all.push(...node.documents);
    }
    return all;
  };
  finish(roots);
  return roots;
}

/** The rows to show, depth first, skipping what sits under a collapsed node. */
export function visibleRows<T>(roots: TreeNode<T>[], collapsed: Set<string>): { node: TreeNode<T>; depth: number }[] {
  const out: { node: TreeNode<T>; depth: number }[] = [];
  const walk = (list: TreeNode<T>[], depth: number) => {
    for (const node of list) {
      out.push({ node, depth });
      if (!collapsed.has(node.key)) walk(node.children, depth + 1);
    }
  };
  walk(roots, 0);
  return out;
}

/** Every place something can sit, indented, for a picker. ``exclude`` and everything under it are left out. */
export function placeOptions<T extends { id: string; title: string }>(roots: TreeNode<T>[], exclude?: string) {
  const out: { value: string; label: string; kind: "group" | "source" }[] = [];
  const walk = (list: TreeNode<T>[], depth: number) => {
    for (const node of list) {
      if (node.key === exclude) continue;
      const title = node.group?.title ?? node.item?.title ?? "";
      out.push({ value: node.key, label: `${" ".repeat(depth)}${node.kind === "group" ? "▸ " : ""}${title}`, kind: node.kind });
      walk(node.children, depth + 1);
    }
  };
  walk(roots, 0);
  return out;
}

const COLLAPSED = "opsatlas-library-collapsed";

export function loadCollapsed(): Set<string> {
  try {
    return new Set(JSON.parse(localStorage.getItem(COLLAPSED) ?? "[]") as string[]);
  } catch {
    return new Set();
  }
}

export function saveCollapsed(keys: Set<string>) {
  try {
    localStorage.setItem(COLLAPSED, JSON.stringify([...keys]));
  } catch {
    // A convenience only; the tree still works without it.
  }
}
