import { Fragment, useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { approveSource, listSources, listSpaces, rejectSource, transferDocument, type SourceRecord, type Space } from "./api";
import { TibiGovernancePanel } from "./TibiGovernancePanel";
import { getDocumentSummary, openDocument, type SettledSummary } from "./content/api";
import {
  buildTree,
  createGroup,
  deleteGroup,
  getLibrary,
  loadCollapsed,
  moveNode,
  renameDocument,
  renameGroup,
  saveCollapsed,
  visibleRows,
  type Library,
  type TreeNode,
} from "./content/library";
import { FolderIcon, GripIcon, InlineTitle, LockIcon } from "./content/LibraryControls";
import { HoverTip } from "./HoverTip";

/** Where a dragged row would land: above or below a row, or inside a group or a space's top level (CM S31, KS S5). */
type DropAt = { target: string; where: "before" | "after" | "inside" };

const SPACE_KIND: Record<Space["kind"], string> = {
  product: "Product guide · every user",
  playbook: "Internal",
  system: "Administrators",
  organisation: "Organisation",
};
const spaceKey = (id: string) => `space:${id}`;

const CONTENT_STATUS: Record<string, { text: string; tone: string }> = {
  draft: { text: "Draft", tone: "cm-status--draft" },
  submitted: { text: "Waiting for approval", tone: "cm-status--submitted" },
};

// OpsAtlas Sales governs its records with the statement-level review and Tibi (the panel below). The document-pair
// Internal Source Review, the External Source Review, the regulatory-signal triage and the re-analysis snapshot were
// removed on 26 September 2026; they remain in OpsAtlas Classic (docs/opsatlas-classic-and-sales.md).

export function GovernancePage({ onResolveWithTibi }: { onResolveWithTibi?: () => void } = {}) {
  // Every space's documents and library (KS S5): spaces are the top level, their folders inside.
  const [spaces, setSpaces] = useState<Space[]>([]);
  const [sourcesBy, setSourcesBy] = useState<Record<string, SourceRecord[]>>({});
  const [libraries, setLibraries] = useState<Record<string, Library | null>>({});
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [drafts, setDrafts] = useState<Record<string, { status: string }>>({});
  const [suggestions, setSuggestions] = useState<Record<string, number>>({});
  const [notes, setNotes] = useState<Record<string, string[]>>({});
  const [settled, setSettled] = useState<Record<string, SettledSummary>>({});
  const [collapsed, setCollapsed] = useState<Set<string>>(loadCollapsed);
  // Where a new group is being named: a space's key for its top level, or the key of the group it goes in.
  const [adding, setAdding] = useState<string | null>(null);
  const [groupName, setGroupName] = useState("");
  const tree = useMemo(
    () =>
      spaces.map((space) => {
        const children = buildTree(libraries[space.id] ?? null, sourcesBy[space.id] ?? []);
        const documents: SourceRecord[] = [];
        const collect = (list: TreeNode<SourceRecord>[]) =>
          list.forEach((n) => {
            if (n.item) documents.push(n.item);
            collect(n.children);
          });
        collect(children);
        return { key: spaceKey(space.id), kind: "space" as const, space, children, documents } as TreeNode<SourceRecord>;
      }),
    [spaces, libraries, sourcesBy],
  );
  // The space each row belongs to: drops, moves and every request stay inside it.
  const spaceOf = useMemo(() => {
    const map = new Map<string, string>();
    const walk = (list: TreeNode<SourceRecord>[], space: string) =>
      list.forEach((n) => {
        map.set(n.key, space);
        walk(n.children, space);
      });
    tree.forEach((root) => {
      map.set(root.key, root.space!.id);
      walk(root.children, root.space!.id);
    });
    return map;
  }, [tree]);
  const sources = useMemo(() => Object.values(sourcesBy).flat(), [sourcesBy]);
  const rows = useMemo(() => visibleRows(tree, collapsed), [tree, collapsed]);
  // Drag and drop (CM S31): what is being dragged, where it would land, and the row that just moved.
  const [dragging, setDragging] = useState<string | null>(null);
  const [dropAt, setDropAt] = useState<DropAt | null>(null);
  const [moved, setMoved] = useState<string | null>(null);
  const opening = useRef<{ key: string; timer: number } | null>(null);
  const places = useMemo(() => {
    const parent = new Map<string, string | null>();
    const children = new Map<string | null, TreeNode<SourceRecord>[]>([[null, tree]]);
    const walk = (list: TreeNode<SourceRecord>[], at: string | null) =>
      list.forEach((n) => {
        parent.set(n.key, at);
        children.set(n.key, n.children);
        walk(n.children, n.key);
      });
    walk(tree, null);
    return { parent, children };
  }, [tree]);

  async function refresh() {
    try {
      const listed = (await listSpaces()).spaces;
      const loaded = await Promise.all(
        listed.map((space) =>
          Promise.all([
            listSources(space.id),
            getDocumentSummary(space.id).catch(() => ({
              documents: {},
              suggestions: {} as Record<string, number>,
              suggestion_notes: {} as Record<string, string[]>,
              settled: {} as Record<string, SettledSummary>,
            })),
            getLibrary(space.id).catch(() => null),
          ]),
        ),
      );
      setSpaces(listed);
      setSourcesBy(Object.fromEntries(listed.map((space, n) => [space.id, loaded[n][0]])));
      setLibraries(Object.fromEntries(listed.map((space, n) => [space.id, loaded[n][2]])));
      // Document ids are unique across spaces: one map each for drafts, suggestions and settled ones.
      setDrafts(Object.assign({}, ...loaded.map(([, summary]) => summary.documents)));
      setSuggestions(Object.assign({}, ...loaded.map(([, summary]) => summary.suggestions ?? {})));
      setNotes(Object.assign({}, ...loaded.map(([, summary]) => summary.suggestion_notes ?? {})));
      setSettled(Object.assign({}, ...loaded.map(([, summary]) => summary.settled ?? {})));
      setError(null);
    } catch {
      setError("Could not reach the backend.");
    }
  }

  useEffect(() => {
    void refresh();
  }, []);

  function toggle(key: string, open?: boolean) {
    setCollapsed((current) => {
      const next = new Set(current);
      if (open ?? next.has(key)) next.delete(key);
      else next.add(key);
      saveCollapsed(next);
      return next;
    });
  }

  function setAll(open: boolean) {
    const keys = new Set<string>();
    const walk = (list: TreeNode<SourceRecord>[]) =>
      list.forEach((n) => {
        if (n.children.length) keys.add(n.key);
        walk(n.children);
      });
    if (!open) walk(tree);
    saveCollapsed(keys);
    setCollapsed(keys);
  }

  /** Run a library change; a refusal is shown and the pen's field stays open. */
  async function change(fn: () => Promise<unknown>): Promise<boolean> {
    try {
      await fn();
      setError(null);
      await refresh();
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "That change was refused.");
      return false;
    }
  }

  async function addGroup() {
    const title = groupName.trim();
    if (!title || adding === null) return;
    const space = spaceOf.get(adding) ?? null;
    const parent = adding.startsWith("space:") ? null : adding;
    if (await change(() => createGroup(title, parent, space))) {
      toggle(adding, true);
      setAdding(null);
      setGroupName("");
    }
  }

  async function removeGroup(node: TreeNode<SourceRecord>) {
    const n = node.documents.length;
    if (!window.confirm(`Remove the group “${node.group!.title}”? ${n ? `Its ${n} document${n === 1 ? "" : "s"} and any groups in it move up a level. ` : ""}No document is deleted.`)) return;
    await change(() => deleteGroup(node.group!.id, spaceOf.get(node.key)));
  }

  function groupForm(depth: number) {
    return (
      <tr className="tree-add-row">
        <td colSpan={5}>
          <div className="tree-cell" style={{ paddingLeft: depth * 22 }}>
            <span className="drag-grip-spacer" />
            <span className="tree-toggle-spacer" />
            <FolderIcon open={false} />
            <input
              autoFocus
              className="tree-add-input"
              value={groupName}
              placeholder="Name the new group"
              aria-label="New group name"
              onChange={(e) => setGroupName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void addGroup();
                if (e.key === "Escape") setAdding(null);
              }}
            />
            <button type="button" className="primary-button tree-add-save" disabled={!groupName.trim()} onClick={() => void addGroup()}>
              Create group
            </button>
            <button type="button" className="secondary-button tree-add-save" onClick={() => setAdding(null)}>
              Cancel
            </button>
          </div>
        </td>
      </tr>
    );
  }

  /** The dragged node and everything under it: it cannot be dropped there. */
  function inside(key: string, of: string | null): boolean {
    for (let at: string | null = key; at; at = places.parent.get(at) ?? null) if (at === of) return true;
    return false;
  }

  function stopOpening() {
    if (opening.current) window.clearTimeout(opening.current.timer);
    opening.current = null;
  }

  function endDrag() {
    stopOpening();
    setDragging(null);
    setDropAt(null);
  }

  function startDrag(event: DragEvent<HTMLElement>, key: string) {
    event.dataTransfer.effectAllowed = "move";
    event.dataTransfer.setData("text/plain", key);
    const row = event.currentTarget.closest("tr");
    if (row) event.dataTransfer.setDragImage(row, 24, row.clientHeight / 2);
    setDragging(key);
    setMoved(null);
  }

  function overRow(event: DragEvent<HTMLTableRowElement>, node: TreeNode<SourceRecord>) {
    // Drag and drop stays inside a space: another space is reached by Move to space (KS S5).
    if (!dragging || inside(node.key, dragging) || spaceOf.get(node.key) !== spaceOf.get(dragging)) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    const box = event.currentTarget.getBoundingClientRect();
    const y = (event.clientY - box.top) / box.height;
    const where =
      node.kind === "space" ? "inside" : node.kind === "group" ? (y < 0.28 ? "before" : y > 0.72 ? "after" : "inside") : y < 0.5 ? "before" : "after";
    if (dropAt?.target !== node.key || dropAt.where !== where) setDropAt({ target: node.key, where });
    // Held over a closed group, it opens so the drop can go further in.
    if (where === "inside" && node.children.length && collapsed.has(node.key)) {
      if (opening.current?.key !== node.key) {
        stopOpening();
        opening.current = { key: node.key, timer: window.setTimeout(() => toggle(node.key, true), 700) };
      }
    } else if (opening.current) stopOpening();
  }

  /** Where a drop puts the dragged node: its new parent, and the sibling it goes before (null: last). */
  function placement(at: DropAt): { parent: string | null; before: string | null } {
    if (at.where === "inside") return { parent: at.target, before: null };
    const parent = places.parent.get(at.target) ?? null;
    if (at.where === "before") return { parent, before: at.target };
    const own = places.children.get(at.target) ?? [];
    if (own.length && !collapsed.has(at.target)) return { parent: at.target, before: own[0].key };  // below an open row: first inside it
    const siblings = places.children.get(parent) ?? [];
    return { parent, before: siblings[siblings.findIndex((n) => n.key === at.target) + 1]?.key ?? null };
  }

  async function drop(event: DragEvent<HTMLElement>) {
    event.preventDefault();
    const node = dragging;
    const at = dropAt;
    endDrag();
    if (!node || !at) return;
    const { parent, before } = placement(at);
    // A space's own row is its top level: no parent.
    if (await change(() => moveNode(node, parent?.startsWith("space:") ? null : parent, before, spaceOf.get(node)))) {
      if (parent && collapsed.has(parent)) toggle(parent, true);
      setMoved(node);
      window.setTimeout(() => setMoved((current) => (current === node ? null : current)), 1600);
    }
  }

  function dropClass(key: string): string {
    const classes = [];
    if (dragging === key) classes.push("is-dragging");
    if (moved === key) classes.push("just-moved");
    if (dropAt && dropAt.target === key) classes.push(`drop-${dropAt.where}`);
    return classes.join(" ");
  }

  function grip(node: TreeNode<SourceRecord>) {
    const title = node.group?.title ?? node.item?.title ?? "";
    return (
      <span
        className="drag-grip"
        draggable
        role="button"
        aria-label={`Drag to move ${title}`}
        title="Drag to reorder, move into a group, or onto its space to take it out of every group"
        onDragStart={(event) => startDrag(event, node.key)}
        onDragEnd={endDrag}
      >
        <GripIcon />
      </span>
    );
  }

  const rowDrop = (node: TreeNode<SourceRecord>) => ({
    onDragOver: (event: DragEvent<HTMLTableRowElement>) => overRow(event, node),
    onDrop: (event: DragEvent<HTMLTableRowElement>) => void drop(event),
  });

  async function act(fn: (id: string, space?: string | null) => Promise<void>, id: string, space?: string) {
    setBusy(true);
    try {
      await fn(id, space);
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="view-stack">
      <div className="page-intro">
        <h1>Governance</h1>
        <p>Knowledge intelligence and the human-in-the-loop approval gate. Only approved sources are queryable.</p>
      </div>

      {onResolveWithTibi ? <TibiGovernancePanel onResolveWithTibi={onResolveWithTibi} onChanged={() => void refresh()} /> : null}

      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Source approval</h2>
            <p className="muted-text">
              Approve a source before the assistant can use it. Open one to read, comment on, edit or approve it; Review shows its open
              governance suggestions (wording checks, conflicts and duplicates). Each space is its own boundary: the OpsAtlas Product
              Guide, the internal Sales Playbook, System settings and, later, each organisation. Rename anything with its pen; drag a
              row to reorder it or move it into a group within its space; use Move to space to take a document to another space.
            </p>
          </div>
          <div className="library-toolbar">
            <button type="button" className="text-button" onClick={() => setAll(true)}>
              Expand all
            </button>
            <button type="button" className="text-button" onClick={() => setAll(false)}>
              Collapse all
            </button>
          </div>
        </div>
        {error ? <p className="muted-text" style={{ color: "var(--red)" }}>{error}</p> : null}
        {sources.length === 0 ? (
          <div className="empty-card"><b>No sources</b><span>Upload and ingest documents first.</span></div>
        ) : (
          <div className="table-frame">
            <table className={`data-table library-table${dragging ? " is-dragging-rows" : ""}`}>
              <thead>
                <tr><th>Title</th><th>State</th><th>Approval</th><th>Review</th><th /></tr>
              </thead>
              <tbody>
                {rows.map(({ node, depth }) => {
                  const open = !collapsed.has(node.key);
                  const toggleButton = node.children.length ? (
                    <button
                      type="button"
                      className={`tree-toggle${open ? " is-open" : ""}`}
                      aria-expanded={open}
                      aria-label={`${open ? "Collapse" : "Expand"} ${node.group?.title ?? node.item?.title}`}
                      onClick={() => toggle(node.key)}
                    >
                      ›
                    </button>
                  ) : (
                    <span className="tree-toggle-spacer" />
                  );
                  if (node.kind === "space") {
                    const space = node.space!;
                    const waiting = node.documents.filter((d) => d.approval_status !== "approved").length;
                    const openSuggestions = node.documents.reduce((n, d) => n + (suggestions[d.id] ?? 0), 0);
                    return (
                      <Fragment key={node.key}>
                        <tr className={`library-space-row ${dropClass(node.key)}`} {...rowDrop(node)}>
                          <td colSpan={4}>
                            <div className="tree-cell">
                              {toggleButton}
                              <span className="tree-space-lock" title="A space: its own boundary"><LockIcon /></span>
                              <button type="button" className="tree-space-title" onClick={() => toggle(node.key)} title={space.about}>
                                {space.name}
                              </button>
                              <span className={`space-kind space-kind--${space.kind}`}>{SPACE_KIND[space.kind]}</span>
                              <span className="tree-count">
                                {node.documents.length} document{node.documents.length === 1 ? "" : "s"}
                              </span>
                              {waiting ? <span className="status-pill tree-pill">{waiting} not approved</span> : null}
                              {openSuggestions ? <span className="status-pill status-pill--suggestions tree-pill">{openSuggestions} suggestion{openSuggestions === 1 ? "" : "s"}</span> : null}
                            </div>
                          </td>
                          <td className="table-actions">
                            <button type="button" className="icon-text-button" title="New group at the top of this space" onClick={() => { setAdding(node.key); setGroupName(""); }}>
                              + Group
                            </button>
                          </td>
                        </tr>
                        {adding === node.key ? groupForm(1) : null}
                        {open && !node.children.length ? (
                          <tr className="tree-empty-row"><td colSpan={5}>No documents in this space yet.</td></tr>
                        ) : null}
                      </Fragment>
                    );
                  }
                  if (node.kind === "group") {
                    const g = node.group!;
                    const waiting = node.documents.filter((d) => d.approval_status !== "approved").length;
                    const openSuggestions = node.documents.reduce((n, d) => n + (suggestions[d.id] ?? 0), 0);
                    return (
                      <Fragment key={node.key}>
                        <tr className={`library-group-row ${dropClass(node.key)}`} {...rowDrop(node)}>
                          <td colSpan={4}>
                            <div className="tree-cell" style={{ paddingLeft: depth * 22 }}>
                              {grip(node)}
                              {toggleButton}
                              <span className="tree-folder"><FolderIcon open={open && node.children.length > 0} /></span>
                              <InlineTitle value={g.title} label="Rename group" onSave={(title) => change(() => renameGroup(g.id, title, spaceOf.get(node.key)))}>
                                <button type="button" className="tree-group-title" onClick={() => toggle(node.key)}>
                                  {g.title}
                                </button>
                              </InlineTitle>
                              <span className="tree-count">
                                {node.documents.length} document{node.documents.length === 1 ? "" : "s"}
                              </span>
                              {waiting ? <span className="status-pill tree-pill">{waiting} not approved</span> : null}
                              {openSuggestions ? <span className="status-pill status-pill--suggestions tree-pill">{openSuggestions} suggestion{openSuggestions === 1 ? "" : "s"}</span> : null}
                            </div>
                          </td>
                          <td className="table-actions">
                            <button type="button" className="icon-text-button" title="New group inside this one" onClick={() => { setAdding(node.key); setGroupName(""); }}>
                              + Group
                            </button>
                            <button type="button" className="icon-text-button icon-text-button--danger" title="Remove this group; what it holds moves up a level" onClick={() => void removeGroup(node)}>
                              Remove
                            </button>
                          </td>
                        </tr>
                        {adding === node.key ? groupForm(depth + 1) : null}
                      </Fragment>
                    );
                  }
                  const s = node.item!;
                  const space = spaceOf.get(node.key) ?? null;
                  return (
                    <tr key={node.key} className={dropClass(node.key)} {...rowDrop(node)}>
                      <td>
                        <div className="tree-cell" style={{ paddingLeft: depth * 22 }}>
                          {grip(node)}
                          {toggleButton}
                          <InlineTitle
                            value={s.title}
                            onSave={(title) => change(() => renameDocument(s.id, title, space))}
                          >
                            <button type="button" className="table-link" onClick={() => openDocument(s.id, undefined, space)}>
                              {s.title}
                            </button>
                          </InlineTitle>
                          {node.children.length && !open ? <span className="tree-count">+{node.documents.length}</span> : null}
                        </div>
                      </td>
                      <td>{s.processing_state}</td>
                      <td>
                        <span className={`status-pill${s.approval_status === "approved" ? " status-pill--good" : s.approval_status === "rejected" ? " status-pill--warn" : ""}`}>
                          {s.approval_status}
                        </span>
                      </td>
                      <td className="review-cell">
                        {suggestions[s.id] ? (
                          <HoverTip
                            tip={
                              <>
                                <b>Open suggestions</b>
                                <ul>
                                  {(notes[s.id] ?? []).map((line, n) => (
                                    <li key={n}>{line}</li>
                                  ))}
                                </ul>
                                <small>Click to open the document at them.</small>
                              </>
                            }
                          >
                            <button type="button" className="status-pill status-pill--suggestions" onClick={() => openDocument(s.id, "comments", space)}>
                              {suggestions[s.id]} suggestion{suggestions[s.id] === 1 ? "" : "s"}
                            </button>
                          </HoverTip>
                        ) : null}
                        {(["corrected", "accepted"] as const).map((outcome) =>
                          settled[s.id]?.[outcome] ? (
                            <HoverTip
                              key={outcome}
                              tip={
                                <>
                                  <b>{outcome === "corrected" ? "Corrected by an edit" : "Accepted as it is"}</b>
                                  <ul>
                                    {settled[s.id].notes
                                      .filter((line) => line.startsWith(outcome === "corrected" ? "Corrected" : "Accepted"))
                                      .map((line, n) => (
                                        <li key={n}>{line}</li>
                                      ))}
                                  </ul>
                                  <small>Click to see them in the document.</small>
                                </>
                              }
                            >
                              <button type="button" className={`status-pill status-pill--${outcome}`} onClick={() => openDocument(s.id, "comments", space)}>
                                {settled[s.id][outcome]} {outcome}
                              </button>
                            </HoverTip>
                          ) : null,
                        )}
                        {drafts[s.id] && CONTENT_STATUS[drafts[s.id].status] ? (
                          <span className={`status-pill ${CONTENT_STATUS[drafts[s.id].status].tone}`}>{CONTENT_STATUS[drafts[s.id].status].text}</span>
                        ) : null}
                      </td>
                      <td className="table-actions">
                        <button type="button" className="secondary-button" disabled={busy} onClick={() => openDocument(s.id, undefined, space)}>
                          Open
                        </button>
                        {s.approval_status !== "approved" ? (
                          <button type="button" className="approve-button" disabled={busy} onClick={() => act(approveSource, s.id, space ?? undefined)}>
                            Approve
                          </button>
                        ) : null}
                        {s.approval_status !== "rejected" ? (
                          <button type="button" className="reject-button" disabled={busy} onClick={() => act(rejectSource, s.id, space ?? undefined)}>
                            Reject
                          </button>
                        ) : null}
                        <MoveToSpace
                          title={s.title}
                          from={space}
                          spaces={spaces}
                          onMove={(to) => change(() => transferDocument(s.id, to))}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

/** Move a document to another space (KS S5): it arrives unapproved there, to be reviewed. Confirmed first. */
function MoveToSpace({
  title,
  from,
  spaces,
  onMove,
}: {
  title: string;
  from: string | null;
  spaces: Space[];
  onMove: (to: string) => Promise<boolean>;
}) {
  const others = spaces.filter((space) => space.id !== from);
  if (!others.length) return null;
  return (
    <select
      className="move-space-select"
      value=""
      aria-label={`Move ${title} to another space`}
      title="Move to another space: it arrives unapproved there"
      onChange={(e) => {
        const to = others.find((space) => space.id === e.target.value);
        if (to && window.confirm(`Move “${title}” to ${to.name}? It arrives there unapproved, to be reviewed, and leaves this space.`)) {
          void onMove(to.id);
        }
      }}
    >
      <option value="">Move…</option>
      {others.map((space) => (
        <option key={space.id} value={space.id}>
          {space.name}
        </option>
      ))}
    </select>
  );
}
