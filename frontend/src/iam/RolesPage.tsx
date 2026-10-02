// Roles (IAM F7): what each built-in role allows and deliberately leaves out; custom roles made from the catalogue.
import { useMemo, useState } from "react";
import type { Me } from "../api";
import { createRole, deleteRole, listRoles, updateRole, type Role } from "./api";
import { NAMESPACES, PERMISSIONS, type Permission } from "./permissions";
import { ConfirmDialog, Drawer, Field, Notice, Pill, useLoad } from "./ui";

export function RolesPage({ me }: { me: Me }) {
  const roles = useLoad(listRoles);
  const [viewing, setViewing] = useState<Role | null>(null);
  const [editing, setEditing] = useState<Role | "new" | null>(null);
  const [deleting, setDeleting] = useState<Role | null>(null);
  const canEdit = me.platform_permissions.includes("iam.roles.create");
  const builtin = (roles.data?.roles ?? []).filter((r) => r.builtin);
  const custom = (roles.data?.roles ?? []).filter((r) => !r.builtin);
  return (
    <div className="view-stack">
      <div className="page-intro">
        <div>
          <h1>Roles</h1>
          <p>A role is a named set of exact permissions. It only acts through a grant at a scope: the platform, or one space.</p>
        </div>
        {canEdit ? <button type="button" className="primary-button" onClick={() => setEditing("new")}>New custom role</button> : null}
      </div>
      <div className="panel">
        <div className="panel-heading"><div><h2>Built-in roles</h2><p className="muted-text">Versioned seeds; a custom role can start from one.</p></div></div>
        {roles.error ? <Notice tone="danger">{roles.error}</Notice> : null}
        <div className="iam-role-grid">
          {builtin.map((role) => <RoleCard key={role.id} role={role} onView={() => setViewing(role)} onCopy={canEdit ? () => setEditing({ ...role, id: "", name: `${role.name} (custom)`, builtin: false }) : undefined} />)}
        </div>
      </div>
      <div className="panel">
        <div className="panel-heading"><div><h2>Custom roles</h2><p className="muted-text">Made here from the catalogue; every change is a new version, recorded.</p></div></div>
        {custom.length === 0 ? <p className="muted-text">None yet.</p> : (
          <div className="iam-role-grid">
            {custom.map((role) => <RoleCard key={role.id} role={role} onView={() => setViewing(role)} onEdit={canEdit ? () => setEditing(role) : undefined} onDelete={canEdit ? () => setDeleting(role) : undefined} />)}
          </div>
        )}
      </div>
      <Drawer title={viewing?.name ?? ""} subtitle={viewing?.description} open={viewing !== null} onClose={() => setViewing(null)} wide>
        {viewing ? <PermissionList permissions={viewing.permissions} excluded={viewing.excluded} /> : null}
      </Drawer>
      {editing ? <RoleEditor role={editing === "new" ? null : editing} onClose={() => setEditing(null)} onSaved={() => { roles.reload(); setEditing(null); }} /> : null}
      {deleting ? (
        <ConfirmDialog open title={`Delete the role ${deleting.name}?`} body={<p>Only a custom role nobody holds can be deleted.</p>} confirmLabel="Delete" danger reasonLabel={null}
          onClose={() => setDeleting(null)} onConfirm={async () => { await deleteRole(deleting.id); roles.reload(); }} />
      ) : null}
    </div>
  );
}

function RoleCard({ role, onView, onEdit, onCopy, onDelete }: { role: Role; onView: () => void; onEdit?: () => void; onCopy?: () => void; onDelete?: () => void }) {
  const risky = role.permissions.filter((k) => PERMISSIONS[k as Permission]?.risky).length;
  return (
    <article className="iam-role-card">
      <div className="iam-role-card-foot">
        <h3>{role.name}</h3>
        <Pill tone={role.boundary === "platform" ? "purple" : "blue"}>{role.boundary}</Pill>
      </div>
      <p>{role.description}</p>
      {role.excluded ? <p className="iam-role-excluded">Not included: {role.excluded}</p> : null}
      <div className="iam-role-card-foot">
        <small className="muted-text">{role.permissions.length} permissions{risky ? ` · ${risky} sensitive` : ""}{role.protected ? " · protected" : ""} · v{role.version}</small>
        <div className="iam-actions">
          <button type="button" className="text-button" onClick={onView}>View</button>
          {onCopy ? <button type="button" className="text-button" onClick={onCopy}>Copy</button> : null}
          {onEdit ? <button type="button" className="text-button" onClick={onEdit}>Edit</button> : null}
          {onDelete ? <button type="button" className="text-button" onClick={onDelete}>Delete</button> : null}
        </div>
      </div>
    </article>
  );
}

function PermissionList({ permissions, excluded }: { permissions: string[]; excluded?: string }) {
  const held = new Set(permissions);
  return (
    <div className="iam-stack">
      {excluded ? <Notice tone="neutral">Deliberately not included: {excluded}</Notice> : null}
      <div className="iam-permission-groups">
        {NAMESPACES.map((ns) => {
          const keys = Object.keys(PERMISSIONS).filter((k) => PERMISSIONS[k as Permission].namespace === ns.key && held.has(k));
          if (!keys.length) return null;
          return (
            <details key={ns.key} className="iam-permission-group" open>
              <summary><span>{ns.label}</span><span className="muted-text">{keys.length}</span></summary>
              <div className="iam-permission-grid">
                {keys.map((k) => (
                  <div key={k} className="iam-check"><span>{PERMISSIONS[k as Permission].description}{PERMISSIONS[k as Permission].risky ? <> <span className="iam-risky">sensitive</span></> : null}{PERMISSIONS[k as Permission].reserved ? <> <span className="muted-text" title={PERMISSIONS[k as Permission].reserved}>reserved: guards nothing yet</span></> : null}<br /><code>{k}</code></span></div>
                ))}
              </div>
            </details>
          );
        })}
      </div>
    </div>
  );
}

function RoleEditor({ role, onClose, onSaved }: { role: Role | null; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(role?.name ?? "");
  const [description, setDescription] = useState(role?.description ?? "");
  const [boundary, setBoundary] = useState<"platform" | "space">(role?.boundary ?? "space");
  const [chosen, setChosen] = useState<Set<string>>(new Set(role?.permissions ?? []));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const existing = role !== null && role.id !== "";
  const valid = useMemo(() => new Set(Object.keys(PERMISSIONS).filter((k) => {
    const info = PERMISSIONS[k as Permission];
    if (info.reserved && !(role?.permissions as string[] | undefined ?? []).includes(k)) return false; // guards nothing yet (REF S5)
    return boundary === "space" ? info.scopes.some((s) => s !== "platform") : info.scopes.includes("platform") || (info.scopes.length === 1 && info.scopes[0] === "own");
  })), [boundary, role]);
  function toggle(key: string) {
    setChosen((current) => { const next = new Set(current); if (next.has(key)) next.delete(key); else next.add(key); return next; });
  }
  async function save() {
    setBusy(true);
    setError(null);
    try {
      const permissions = [...chosen].filter((k) => valid.has(k));
      if (existing) await updateRole(role.id, { name, description, permissions });
      else await createRole({ name, boundary, permissions, description, based_on: role?.builtin ? role.id : null });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The role was not saved.");
    } finally {
      setBusy(false);
    }
  }
  const count = [...chosen].filter((k) => valid.has(k)).length;
  return (
    <Drawer title={existing ? `Edit ${role.name}` : "New custom role"} subtitle="Exact permissions from the catalogue; sensitive ones are marked." open onClose={onClose} wide
      footer={<>
        <button type="button" className="secondary-button" onClick={onClose}>Cancel</button>
        <button type="button" className="primary-button" disabled={busy || !name.trim() || count === 0} onClick={() => void save()}>{busy ? "Saving…" : existing ? "Save a new version" : "Create the role"}</button>
      </>}>
      <div className="iam-stack">
        <div className="iam-row">
          <Field label="Name"><input className="iam-input" value={name} onChange={(e) => setName(e.target.value)} maxLength={60} /></Field>
          <Field label="Bound at" hint={existing ? "Fixed once created." : "A space role holds space permissions only; a platform role, platform ones."}>
            <select className="iam-input" value={boundary} disabled={existing} onChange={(e) => setBoundary(e.target.value as "platform" | "space")}>
              <option value="space">A space</option>
              <option value="platform">The platform</option>
            </select>
          </Field>
        </div>
        <Field label="Description"><textarea className="iam-input" value={description} onChange={(e) => setDescription(e.target.value)} maxLength={500} /></Field>
        <p className="muted-text">{count} permissions chosen.</p>
        <div className="iam-permission-groups">
          {NAMESPACES.map((ns) => {
            const keys = Object.keys(PERMISSIONS).filter((k) => PERMISSIONS[k as Permission].namespace === ns.key && valid.has(k));
            if (!keys.length) return null;
            const picked = keys.filter((k) => chosen.has(k)).length;
            return (
              <details key={ns.key} className="iam-permission-group" open={picked > 0}>
                <summary><span>{ns.label}</span><span className="muted-text">{picked}/{keys.length}</span></summary>
                <p className="muted-text">{ns.note}</p>
                <div className="iam-permission-grid">
                  {keys.map((k) => (
                    <label key={k} className="iam-check">
                      <input type="checkbox" checked={chosen.has(k)} onChange={() => toggle(k)} />
                      <span>{PERMISSIONS[k as Permission].description}{PERMISSIONS[k as Permission].risky ? <> <span className="iam-risky">sensitive</span></> : null}<br /><code>{k}</code></span>
                    </label>
                  ))}
                </div>
              </details>
            );
          })}
        </div>
        {error ? <Notice tone="danger">{error}</Notice> : null}
      </div>
    </Drawer>
  );
}
