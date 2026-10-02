// Who can read a document (REF S13, per-document grants): everyone with access to the space, or a named audience.
import { useEffect, useState } from "react";
import { can, getActiveSpace } from "../api";
import { setRestriction, spaceMembers, spaceRestrictions } from "../iam/api";

type Member = { user_id: string; display_name: string };

export function AccessCard({ sourceId }: { sourceId: string }) {
  const space = getActiveSpace();
  const canManage = can("resources.permissions.manage");
  const [audience, setAudience] = useState<string[] | null>(null);
  const [members, setMembers] = useState<Member[]>([]);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    spaceRestrictions(space)
      .then((rows) => {
        if (!live) return;
        const row = rows.find((r) => r.resource_type === "document" && r.resource_id === sourceId);
        setAudience(row ? row.restricted_to : []);
        setChosen(new Set(row ? row.restricted_to : []));
      })
      .catch((e: Error) => live && setError(e.message));
    if (canManage) spaceMembers(space).then((m) => live && setMembers(m)).catch(() => undefined);
    return () => {
      live = false;
    };
  }, [space, sourceId, canManage]);

  async function save(next: string[]) {
    setBusy(true);
    setError(null);
    try {
      const row = await setRestriction(space, "document", sourceId, next, next.length ? "Restricted from the document page" : "Restriction lifted");
      setAudience(row.restricted_to);
      setEditing(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const name = (entry: string) => {
    const id = entry.split(":")[1];
    return members.find((m) => m.user_id === id)?.display_name ?? (entry.startsWith("group:") ? "a group" : "a person");
  };
  const toggle = (entry: string) =>
    setChosen((current) => {
      const next = new Set(current);
      if (next.has(entry)) next.delete(entry);
      else next.add(entry);
      return next;
    });

  return (
    <div className="cm-card">
      <h3 className="cm-card-title">Who can read</h3>
      {audience === null ? (
        <p className="muted-text">{error ?? "Loading…"}</p>
      ) : audience.length === 0 ? (
        <p className="muted-text">Everyone with access to this space.</p>
      ) : (
        <p className="muted-text">Only {audience.map(name).join(", ")}, and those who administer this space.</p>
      )}
      {canManage && audience !== null && !editing ? (
        <div className="cm-thread-actions">
          <button type="button" className="text-button" onClick={() => setEditing(true)}>
            {audience.length ? "Change who can read" : "Restrict to named people"}
          </button>
          {audience.length ? (
            <button type="button" className="text-button" disabled={busy} onClick={() => save([])}>
              Lift the restriction
            </button>
          ) : null}
        </div>
      ) : null}
      {editing ? (
        <div className="cm-form">
          {members.map((m) => (
            <label key={m.user_id} className="iam-check">
              <input type="checkbox" checked={chosen.has(`user:${m.user_id}`)} onChange={() => toggle(`user:${m.user_id}`)} />
              <span>{m.display_name}</span>
            </label>
          ))}
          <p className="muted-text">
            People outside the list no longer find this document, its sections, or answers drawn from it. The facts map,
            activity model and process views of this space are withheld from them.
          </p>
          <div className="cm-thread-actions">
            <button type="button" className="primary-button" disabled={busy || chosen.size === 0} onClick={() => save([...chosen])}>
              Restrict
            </button>
            <button type="button" className="text-button" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </div>
      ) : null}
      {error && audience !== null ? <p className="cm-inline-error">{error}</p> : null}
    </div>
  );
}
