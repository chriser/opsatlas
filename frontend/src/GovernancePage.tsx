import { Fragment, useEffect, useMemo, useState } from "react";
import { approveSource, listSources, rejectSource, type SourceRecord } from "./api";
import { TibiGovernancePanel } from "./TibiGovernancePanel";
import { getDocumentSummary, openDocument } from "./content/api";
import {
  buildTree,
  createGroup,
  deleteGroup,
  getLibrary,
  loadCollapsed,
  renameDocument,
  renameGroup,
  saveCollapsed,
  visibleRows,
  type Library,
  type TreeNode,
} from "./content/library";
import { FolderIcon, InlineTitle } from "./content/LibraryControls";
import { HoverTip } from "./HoverTip";

const CONTENT_STATUS: Record<string, { text: string; tone: string }> = {
  draft: { text: "Draft", tone: "cm-status--draft" },
  submitted: { text: "Waiting for approval", tone: "cm-status--submitted" },
};

// OpsAtlas Sales governs its records with the statement-level review and Tibi (the panel below). The document-pair
// Internal Source Review, the External Source Review, the regulatory-signal triage and the re-analysis snapshot were
// removed on 26 September 2026; they remain in OpsAtlas Classic (docs/opsatlas-classic-and-sales.md).

export function GovernancePage({ onResolveWithTibi }: { onResolveWithTibi?: () => void } = {}) {
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [drafts, setDrafts] = useState<Record<string, { status: string }>>({});
  const [suggestions, setSuggestions] = useState<Record<string, number>>({});
  const [notes, setNotes] = useState<Record<string, string[]>>({});
  const [library, setLibrary] = useState<Library | null>(null);
  const [collapsed, setCollapsed] = useState<Set<string>>(loadCollapsed);
  // Where a new group is being named: "" for the top level, or the key of the group it goes in.
  const [adding, setAdding] = useState<string | null>(null);
  const [groupName, setGroupName] = useState("");
  const tree = useMemo(() => buildTree(library, sources), [library, sources]);
  const rows = useMemo(() => visibleRows(tree, collapsed), [tree, collapsed]);

  async function refresh() {
    try {
      const [list, summary, lib] = await Promise.all([
        listSources(),
        getDocumentSummary().catch(() => ({ documents: {}, suggestions: {} as Record<string, number>, suggestion_notes: {} as Record<string, string[]> })),
        getLibrary().catch(() => null),
      ]);
      setSources(list);
      setLibrary(lib);
      setDrafts(summary.documents);
      setSuggestions(summary.suggestions ?? {});
      setNotes(summary.suggestion_notes ?? {});
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
    const parent = adding || null;
    if (await change(() => createGroup(title, parent))) {
      if (parent) toggle(parent, true);
      setAdding(null);
      setGroupName("");
    }
  }

  async function removeGroup(node: TreeNode<SourceRecord>) {
    const n = node.documents.length;
    if (!window.confirm(`Remove the group “${node.group!.title}”? ${n ? `Its ${n} document${n === 1 ? "" : "s"} and any groups in it move up a level. ` : ""}No document is deleted.`)) return;
    await change(() => deleteGroup(node.group!.id));
  }

  function groupForm(depth: number) {
    return (
      <tr className="tree-add-row">
        <td colSpan={5}>
          <div className="tree-cell" style={{ paddingLeft: depth * 22 }}>
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

  async function act(fn: (id: string) => Promise<void>, id: string) {
    setBusy(true);
    try {
      await fn(id);
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
              governance suggestions (wording checks, conflicts and duplicates). Rename anything with its pen; move a document from
              its Details panel.
            </p>
          </div>
          <div className="library-toolbar">
            <button type="button" className="text-button" onClick={() => setAll(true)}>
              Expand all
            </button>
            <button type="button" className="text-button" onClick={() => setAll(false)}>
              Collapse all
            </button>
            <button type="button" className="secondary-button" onClick={() => { setAdding(""); setGroupName(""); }}>
              New group
            </button>
          </div>
        </div>
        {error ? <p className="muted-text" style={{ color: "var(--red)" }}>{error}</p> : null}
        {sources.length === 0 ? (
          <div className="empty-card"><b>No sources</b><span>Upload and ingest documents first.</span></div>
        ) : (
          <div className="table-frame">
            <table className="data-table library-table">
              <thead>
                <tr><th>Title</th><th>State</th><th>Approval</th><th>Review</th><th /></tr>
              </thead>
              <tbody>
                {adding === "" ? groupForm(0) : null}
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
                  if (node.kind === "group") {
                    const g = node.group!;
                    const waiting = node.documents.filter((d) => d.approval_status !== "approved").length;
                    const openSuggestions = node.documents.reduce((n, d) => n + (suggestions[d.id] ?? 0), 0);
                    return (
                      <Fragment key={node.key}>
                        <tr className="library-group-row">
                          <td colSpan={4}>
                            <div className="tree-cell" style={{ paddingLeft: depth * 22 }}>
                              {toggleButton}
                              <span className="tree-folder"><FolderIcon open={open && node.children.length > 0} /></span>
                              <InlineTitle value={g.title} label="Rename group" onSave={(title) => change(() => renameGroup(g.id, title))}>
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
                  return (
                    <tr key={node.key}>
                      <td>
                        <div className="tree-cell" style={{ paddingLeft: depth * 22 }}>
                          {toggleButton}
                          <InlineTitle
                            value={s.title}
                            onSave={(title) => change(() => renameDocument(s.id, title))}
                          >
                            <button type="button" className="table-link" onClick={() => openDocument(s.id)}>
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
                            <button type="button" className="status-pill status-pill--suggestions" onClick={() => openDocument(s.id, "comments")}>
                              {suggestions[s.id]} suggestion{suggestions[s.id] === 1 ? "" : "s"}
                            </button>
                          </HoverTip>
                        ) : null}
                        {drafts[s.id] && CONTENT_STATUS[drafts[s.id].status] ? (
                          <span className={`status-pill ${CONTENT_STATUS[drafts[s.id].status].tone}`}>{CONTENT_STATUS[drafts[s.id].status].text}</span>
                        ) : null}
                      </td>
                      <td className="table-actions">
                        <button type="button" className="secondary-button" disabled={busy} onClick={() => openDocument(s.id)}>
                          Open
                        </button>
                        {s.approval_status !== "approved" ? (
                          <button type="button" className="approve-button" disabled={busy} onClick={() => act(approveSource, s.id)}>
                            Approve
                          </button>
                        ) : null}
                        {s.approval_status !== "rejected" ? (
                          <button type="button" className="reject-button" disabled={busy} onClick={() => act(rejectSource, s.id)}>
                            Reject
                          </button>
                        ) : null}
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
