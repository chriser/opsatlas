// Library controls (CM S27, CM S28): a title renamed in place with the pen, and where a document sits.
import { useEffect, useRef, useState, type ReactNode } from "react";
import { listSources, type SourceRecord } from "../api";
import { getDocumentSpace } from "./api";
import { buildTree, createGroup, getLibrary, placeOptions, setParent, type Library } from "./library";

export function PenIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </svg>
  );
}

/** Six dots: the handle a library row is dragged by (CM S31). */
export function GripIcon() {
  return (
    <svg width="10" height="16" viewBox="0 0 10 16" fill="currentColor" aria-hidden="true">
      {[2, 8, 14].flatMap((y) => [2, 8].map((x) => <circle key={`${x}-${y}`} cx={x} cy={y} r="1.5" />))}
    </svg>
  );
}

export function FolderIcon({ open }: { open: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {open ? (
        <path d="m6 14 1.5-2.9A2 2 0 0 1 9.24 10H20a2 2 0 0 1 1.94 2.5l-1.54 6a2 2 0 0 1-1.95 1.5H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H18a2 2 0 0 1 2 2v2" />
      ) : (
        <path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" />
      )}
    </svg>
  );
}

/** A padlock: a space, its own boundary (KS S5). */
export function LockIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="4" y="11" width="16" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
    </svg>
  );
}

/** A title with a pen: click the pen to rename in place. Enter saves, Escape cancels. ``onSave`` returns false to
 *  keep the field open (the change was refused). */
export function InlineTitle({
  value,
  onSave,
  children,
  label = "Rename",
  hint,
}: {
  value: string;
  onSave: (title: string) => Promise<boolean>;
  children: ReactNode;
  label?: string;
  hint?: string;
}) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(value);
  const [saving, setSaving] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) input.current?.select();
  }, [editing]);

  async function commit() {
    const next = text.trim();
    if (!next || next === value) {
      setEditing(false);
      setText(value);
      return;
    }
    setSaving(true);
    const ok = await onSave(next);
    setSaving(false);
    if (ok) setEditing(false);
    else input.current?.focus();
  }

  if (editing) {
    return (
      <span className="inline-title inline-title--editing">
        <input
          ref={input}
          value={text}
          disabled={saving}
          aria-label={label}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void commit();
            if (e.key === "Escape") {
              setText(value);
              setEditing(false);
            }
          }}
          onBlur={() => void commit()}
        />
        {hint ? <small className="inline-title-hint">{hint}</small> : null}
      </span>
    );
  }
  return (
    <span className="inline-title">
      {children}
      <button
        type="button"
        className="pen-button"
        title={label}
        aria-label={`${label}: ${value}`}
        onClick={() => {
          setText(value);
          setEditing(true);
        }}
      >
        <PenIcon />
      </button>
    </span>
  );
}

/** Where a document sits in the library: under a group, under another document, or at the top level. A new
 *  group can be made here, inside whatever is chosen, and the document moved into it. */
export function LocationCard({ sourceId, onMoved }: { sourceId: string; onMoved: (message: string) => void }) {
  const [library, setLibrary] = useState<Library | null>(null);
  const [sources, setSources] = useState<SourceRecord[]>([]);
  const [parent, setParentValue] = useState("");
  const [newGroup, setNewGroup] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    Promise.all([getLibrary(), listSources(getDocumentSpace())])
      .then(([lib, list]) => {
        if (!live) return;
        setLibrary(lib);
        setSources(list);
        setParentValue(lib.placements[sourceId]?.parent ?? "");
      })
      .catch(() => live && setError("The library could not be loaded."));
    return () => {
      live = false;
    };
  }, [sourceId]);

  const tree = buildTree(library, sources);
  const options = placeOptions(tree, `source:${sourceId}`);
  const current = library?.placements[sourceId]?.parent ?? "";
  const describe = (key: string) =>
    key ? (options.find((o) => o.value === key)?.label.replace(/^[\s ]*(▸ )?/, "") ?? "") : "the top level";

  async function move(target: string) {
    setBusy(true);
    setError(null);
    try {
      const lib = await setParent(sourceId, target || null);
      setLibrary(lib);
      setParentValue(target);
      onMoved(`Moved to ${target ? `“${describe(target)}”` : "the top level"}.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "That move was refused.");
    } finally {
      setBusy(false);
    }
  }

  async function addGroup() {
    const title = (newGroup ?? "").trim();
    if (!title) return;
    setBusy(true);
    setError(null);
    try {
      const made = await createGroup(title, parent || null);
      const lib = await setParent(sourceId, `group:${made.id}`);
      setLibrary(lib);
      setParentValue(`group:${made.id}`);
      setNewGroup(null);
      onMoved(`Created the group “${title}” and moved this document into it.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "The group could not be created.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="cm-card cm-form">
      <h3 className="cm-card-title">Location</h3>
      <p className="muted-text">Where this document sits in the library: in a group, under another document, or at the top level.</p>
      <label>
        Sits under
        <select value={parent} disabled={!library || busy} onChange={(e) => setParentValue(e.target.value)}>
          <option value="">Top level</option>
          <optgroup label="Groups">
            {options.filter((o) => o.kind === "group").map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </optgroup>
          <optgroup label="Documents">
            {options.filter((o) => o.kind === "source").map((o) => (
              <option key={o.value} value={o.value}>
                {o.label.replace(/ /g, "")}
              </option>
            ))}
          </optgroup>
        </select>
      </label>
      {newGroup !== null ? (
        <label>
          New group{parent ? ` inside “${describe(parent)}”` : " at the top level"}
          <input
            autoFocus
            value={newGroup}
            placeholder="e.g. Pricing and packaging"
            onChange={(e) => setNewGroup(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void addGroup();
              if (e.key === "Escape") setNewGroup(null);
            }}
          />
        </label>
      ) : null}
      {error ? <p className="cm-inline-error">{error}</p> : null}
      <div className="cm-thread-actions">
        {newGroup !== null ? (
          <>
            <button type="button" className="secondary-button" disabled={busy} onClick={() => setNewGroup(null)}>
              Cancel
            </button>
            <button type="button" className="primary-button" disabled={busy || !newGroup.trim()} onClick={() => void addGroup()}>
              Create and move here
            </button>
          </>
        ) : (
          <>
            <button type="button" className="secondary-button" disabled={!library || busy} onClick={() => setNewGroup("")}>
              New group
            </button>
            <button type="button" className="primary-button" disabled={!library || busy || parent === current} onClick={() => void move(parent)}>
              {busy ? "Moving…" : "Move"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
