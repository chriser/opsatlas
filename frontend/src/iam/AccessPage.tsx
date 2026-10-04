// Access (IAM F7): every grant, groups and their roles, explicit denies, access requests, and "why can this person do this?".
import { useState } from "react";
import type { Me } from "../api";
import {
  addDeny,
  addGroupMember,
  cancelRequest,
  createGroup,
  decideRequest,
  deleteGroup,
  explainAccess,
  grant,
  grantableRoles,
  liftDeny,
  listBindings,
  listDenies,
  listGroups,
  listPeople,
  listRequests,
  removeGroupMember,
  revoke,
  type Binding,
  type Explanation,
  type Group,
} from "./api";
import { PERMISSION_KEYS, PERMISSIONS, type Permission } from "./permissions";
import { ConfirmDialog, Drawer, EmptyCard, Field, formatWhen, Notice, Pill, Tabs, useLoad, useReauth } from "./ui";

type Tab = "grants" | "groups" | "denies" | "requests" | "explain";

export function AccessPage({ me }: { me: Me }) {
  const [tab, setTab] = useState<Tab>("grants");
  return (
    <div className="view-stack">
      <div className="page-intro">
        <div>
          <h1>Access</h1>
          <p>Who may do what, where, and why. Grants add; denies and restrictions only take away; nothing here is implied.</p>
        </div>
      </div>
      <Tabs tabs={[{ key: "grants", label: "Grants" }, { key: "groups", label: "Groups" }, { key: "denies", label: "Denies" }, { key: "requests", label: "Requests" }, { key: "explain", label: "Explain" }]} active={tab} onChange={setTab} />
      {tab === "grants" ? <Grants me={me} /> : tab === "groups" ? <Groups me={me} /> : tab === "denies" ? <Denies me={me} /> : tab === "requests" ? <Requests me={me} /> : <Explain me={me} />}
    </div>
  );
}

function scopeLabel(b: Binding) {
  return b.scope_type === "platform" ? "Platform" : b.space_name ?? b.scope_id;
}

function Grants({ me }: { me: Me }) {
  const [spaceId, setSpaceId] = useState("");
  const [system, setSystem] = useState(false);
  const bindings = useLoad(() => listBindings({ space_id: spaceId || undefined, include_system: system }), [spaceId, system]);
  const [revoking, setRevoking] = useState<Binding | null>(null);
  return (
    <div className="panel">
      <div className="panel-heading">
        <div><h2>Grants</h2><p className="muted-text">{bindings.data ? `${bindings.data.length} grants` : "Loading…"}</p></div>
        <div className="iam-toolbar">
          <select className="iam-input" value={spaceId} onChange={(e) => setSpaceId(e.target.value)} aria-label="Space">
            <option value="">Everywhere</option>
            {me.spaces.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <label className="toggle-chip"><input type="checkbox" checked={system} onChange={(e) => setSystem(e.target.checked)} /> Show entitlements that follow the account</label>
        </div>
      </div>
      {bindings.error ? <Notice tone="danger">{bindings.error}</Notice> : null}
      {bindings.data && bindings.data.length === 0 ? <EmptyCard title="No grants here" /> : (
        <div className="iam-table-wrap">
          <table className="data-table">
            <thead><tr><th>Who</th><th>Role</th><th>Where</th><th>Since</th><th>Until</th><th>Reason</th><th /></tr></thead>
            <tbody>
              {(bindings.data ?? []).map((b) => (
                <tr key={b.id}>
                  <td><div className="iam-cell-main"><b>{b.subject?.display_name ?? b.subject_id}</b><small>{b.subject_type === "group" ? "group" : b.subject?.login}</small></div></td>
                  <td>{b.role_name}{b.system ? <> <Pill>follows the account</Pill></> : null}</td>
                  <td>{scopeLabel(b)}</td>
                  <td>{formatWhen(b.starts_at)}</td>
                  <td>{b.ends_at ? formatWhen(b.ends_at) : "—"}</td>
                  <td className="muted-text">{b.reason}</td>
                  <td><div className="iam-actions">{!b.system ? <button type="button" className="text-button" onClick={() => setRevoking(b)}>Revoke</button> : null}</div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {revoking ? (
        <ConfirmDialog open title="Revoke this grant?" body={<p><b>{revoking.subject?.display_name}</b>: {revoking.role_name} · {scopeLabel(revoking)}</p>} confirmLabel="Revoke" danger
          onClose={() => setRevoking(null)} onConfirm={async (reason) => { await revoke(revoking.id, reason); bindings.reload(); }} />
      ) : null}
    </div>
  );
}

function Groups({ me }: { me: Me }) {
  const groups = useLoad(() => listGroups());
  const people = useLoad(listPeople);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [spaceId, setSpaceId] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [granting, setGranting] = useState<Group | null>(null);
  const [deleting, setDeleting] = useState<Group | null>(null);
  const [reauthElement, withReauth] = useReauth();
  const [member, setMember] = useState<Record<string, string>>({});
  async function create() {
    try {
      await createGroup({ name, space_id: spaceId || null, description });
      setCreating(false); setName(""); setSpaceId(""); setDescription("");
      groups.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The group was not created.");
    }
  }
  async function act(fn: () => Promise<unknown>) {
    try { await withReauth(fn); groups.reload(); setError(null); } catch (err) { setError(err instanceof Error ? err.message : "That did not work."); }
  }
  return (
    <div className="panel">
      <div className="panel-heading">
        <div><h2>Groups</h2><p className="muted-text">A group grants nothing until a role is given to it; adding a member is checked against what you may give.</p></div>
        <button type="button" className="primary-button" onClick={() => setCreating(true)}>New group</button>
      </div>
      {error ? <Notice tone="danger">{error}</Notice> : null}
      {groups.data && groups.data.length === 0 ? <EmptyCard title="No groups" hint="Groups collect people who should hold the same roles." /> : null}
      <div className="iam-stack">
        {(groups.data ?? []).map((g) => (
          <article key={g.id} className="iam-role-card">
            <div className="iam-role-card-foot">
              <h3>{g.name} <Pill tone={g.space_id ? "blue" : "purple"}>{g.space_id ? me.spaces.find((s) => s.id === g.space_id)?.name ?? g.space_id : "platform"}</Pill></h3>
              <div className="iam-actions">
                <button type="button" className="text-button" onClick={() => setGranting(g)}>Give a role</button>
                <button type="button" className="text-button" onClick={() => setDeleting(g)}>Delete</button>
              </div>
            </div>
            {g.description ? <p>{g.description}</p> : null}
            <div className="iam-chips">
              {g.bindings.length === 0 ? <small className="muted-text">No role yet.</small> : g.bindings.map((b) => (
                <Pill key={b.id} tone="blue">{b.role_name} · {scopeLabel(b)} <button type="button" className="text-button" style={{ padding: "0 4px" }} onClick={() => void act(() => revoke(b.id, "removed from the group"))}>✕</button></Pill>
              ))}
            </div>
            <div className="iam-chips">
              {g.members.map((m) => (
                <Pill key={m.user_id} tone={m.state === "active" ? "good" : "warn"}>{m.display_name} <button type="button" className="text-button" style={{ padding: "0 4px" }} onClick={() => void act(() => removeGroupMember(g.id, m.user_id))}>✕</button></Pill>
              ))}
            </div>
            <div className="iam-toolbar">
              <select className="iam-input" value={member[g.id] ?? ""} onChange={(e) => setMember({ ...member, [g.id]: e.target.value })} aria-label="Add a member">
                <option value="">Add a member…</option>
                {(people.data ?? []).filter((p) => p.state !== "deactivated" && !g.members.some((m) => m.user_id === p.id)).map((p) => <option key={p.id} value={p.id}>{p.display_name} · {p.email}</option>)}
              </select>
              <button type="button" className="secondary-button" disabled={!member[g.id]} onClick={() => void act(() => addGroupMember(g.id, member[g.id])).then(() => setMember({ ...member, [g.id]: "" }))}>Add</button>
            </div>
          </article>
        ))}
      </div>
      <Drawer title="New group" open={creating} onClose={() => setCreating(false)}
        footer={<><button type="button" className="secondary-button" onClick={() => setCreating(false)}>Cancel</button><button type="button" className="primary-button" disabled={!name.trim()} onClick={() => void create()}>Create</button></>}>
        <div className="iam-stack">
          <Field label="Name"><input className="iam-input" value={name} onChange={(e) => setName(e.target.value)} maxLength={60} autoFocus /></Field>
          <Field label="Space" hint="A space group may only carry roles in that space; a platform group is for platform roles.">
            <select className="iam-input" value={spaceId} onChange={(e) => setSpaceId(e.target.value)}>
              <option value="">Platform</option>
              {me.spaces.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </Field>
          <Field label="Description"><input className="iam-input" value={description} onChange={(e) => setDescription(e.target.value)} maxLength={300} /></Field>
        </div>
      </Drawer>
      {granting ? <GroupGrant me={me} group={granting} onClose={() => setGranting(null)} onDone={() => { groups.reload(); setGranting(null); }} /> : null}
      {deleting ? (
        <ConfirmDialog open title={`Delete the group ${deleting.name}?`} body={<p>Its grants are revoked and its members lose what the group gave them.</p>} confirmLabel="Delete" danger reasonLabel={null}
          onClose={() => setDeleting(null)} onConfirm={async () => { await deleteGroup(deleting.id); groups.reload(); }} />
      ) : null}
      {reauthElement}
    </div>
  );
}

function GroupGrant({ me, group, onClose, onDone }: { me: Me; group: Group; onClose: () => void; onDone: () => void }) {
  const [roleId, setRoleId] = useState("");
  const [days, setDays] = useState("");
  const [error, setError] = useState<string | null>(null);
  const roles = useLoad(() => grantableRoles(group.space_id), [group.id]);
  const options = (roles.data ?? []).filter((r) => (group.space_id ? r.boundary === "space" : r.boundary === "platform"));
  const [reauthElement, withReauth] = useReauth();
  async function submit() {
    try {
      await withReauth(() => grant({ subject_type: "group", subject_id: group.id, role_id: roleId, scope_type: group.space_id ? "space" : "platform",
        scope_id: group.space_id ?? "", days: days ? Number(days) : null, reason: `group ${group.name}` }));
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The role was not given.");
    }
  }
  return (
    <Drawer title={`Give ${group.name} a role`} open onClose={onClose}
      footer={<><button type="button" className="secondary-button" onClick={onClose}>Cancel</button><button type="button" className="primary-button" disabled={!roleId} onClick={() => void submit()}>Give the role</button></>}>
      <div className="iam-stack">
        <Field label="Role">
          <select className="iam-input" value={roleId} onChange={(e) => setRoleId(e.target.value)}>
            <option value="">Choose…</option>
            {options.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </select>
        </Field>
        <Field label="Expires after (days)"><input className="iam-input" type="number" min={1} value={days} onChange={(e) => setDays(e.target.value)} /></Field>
        <p className="muted-text">Every member holds it {group.space_id ? `in ${me.spaces.find((s) => s.id === group.space_id)?.name ?? group.space_id}` : "at the platform"}.</p>
        {error ? <Notice tone="danger">{error}</Notice> : null}
      </div>
      {reauthElement}
    </Drawer>
  );
}

function Denies({ me }: { me: Me }) {
  const denies = useLoad(listDenies);
  const people = useLoad(listPeople);
  const [adding, setAdding] = useState(false);
  const [userId, setUserId] = useState("");
  const [permission, setPermission] = useState("");
  const [spaceId, setSpaceId] = useState("");
  const [reason, setReason] = useState("");
  const [days, setDays] = useState("");
  const [error, setError] = useState<string | null>(null);
  async function add() {
    try {
      await addDeny({ subject_id: userId, permission, scope_type: spaceId ? "space" : "platform", scope_id: spaceId, reason, days: days ? Number(days) : null });
      setAdding(false); setUserId(""); setPermission(""); setReason(""); setDays("");
      denies.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The deny was not added.");
    }
  }
  return (
    <div className="panel">
      <div className="panel-heading">
        <div><h2>Explicit denies</h2><p className="muted-text">A deny beats every grant for that exact permission, at the platform or in one space.</p></div>
        <button type="button" className="primary-button" onClick={() => setAdding(true)}>Add a deny</button>
      </div>
      {denies.data && denies.data.length === 0 ? <EmptyCard title="No denies" /> : (
        <table className="data-table">
          <thead><tr><th>Who</th><th>Permission</th><th>Where</th><th>Until</th><th>Reason</th><th /></tr></thead>
          <tbody>
            {(denies.data ?? []).map((d) => (
              <tr key={d.id}>
                <td>{d.subject?.display_name ?? d.subject_id}</td>
                <td><code>{d.permission}</code></td>
                <td>{d.scope_type === "platform" ? "Platform" : me.spaces.find((s) => s.id === d.scope_id)?.name ?? d.scope_id}</td>
                <td>{d.ends_at ? formatWhen(d.ends_at) : "—"}</td>
                <td className="muted-text">{d.reason}</td>
                <td><div className="iam-actions"><button type="button" className="text-button" onClick={() => void liftDeny(d.id, "lifted").then(() => denies.reload())}>Lift</button></div></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <Drawer title="Add an explicit deny" open={adding} onClose={() => setAdding(false)}
        footer={<><button type="button" className="secondary-button" onClick={() => setAdding(false)}>Cancel</button><button type="button" className="primary-button" disabled={!userId || !PERMISSION_KEYS.includes(permission as Permission)} onClick={() => void add()}>Add</button></>}>
        <div className="iam-stack">
          <Field label="Person">
            <select className="iam-input" value={userId} onChange={(e) => setUserId(e.target.value)}>
              <option value="">Choose…</option>
              {(people.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.display_name} · {p.email}</option>)}
            </select>
          </Field>
          <Field label="Permission" hint={permission && PERMISSIONS[permission as Permission] ? PERMISSIONS[permission as Permission].description : "An exact key from the catalogue."}>
            <input className="iam-input" list="iam-permission-keys" value={permission} onChange={(e) => setPermission(e.target.value)} />
            <datalist id="iam-permission-keys">{PERMISSION_KEYS.map((k) => <option key={k} value={k} />)}</datalist>
          </Field>
          <div className="iam-row">
            <Field label="Where">
              <select className="iam-input" value={spaceId} onChange={(e) => setSpaceId(e.target.value)}>
                <option value="">Platform (everywhere)</option>
                {me.spaces.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </Field>
            <Field label="Expires after (days)"><input className="iam-input" type="number" min={1} value={days} onChange={(e) => setDays(e.target.value)} /></Field>
          </div>
          <Field label="Reason (recorded and shown to the person)"><input className="iam-input" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={200} /></Field>
          {error ? <Notice tone="danger">{error}</Notice> : null}
        </div>
      </Drawer>
    </div>
  );
}

function Requests({ me }: { me: Me }) {
  const requests = useLoad(() => listRequests(false));
  const [deciding, setDeciding] = useState<{ id: string; approve: boolean } | null>(null);
  const pending = (requests.data ?? []).filter((r) => r.status === "pending");
  const decided = (requests.data ?? []).filter((r) => r.status !== "pending");
  return (
    <div className="panel">
      <div className="panel-heading"><div><h2>Access requests</h2><p className="muted-text">Decided by someone else, never by the requester; an approval is an ordinary grant with an expiry.</p></div></div>
      {pending.length === 0 ? <p className="muted-text">Nothing pending.</p> : (
        <table className="data-table">
          <thead><tr><th>Who</th><th>Asks for</th><th>Where</th><th>For</th><th>Reason</th><th /></tr></thead>
          <tbody>
            {pending.map((r) => (
              <tr key={r.id}>
                <td>{r.display_name}</td>
                <td>{r.role_id}</td>
                <td>{r.space_id ? me.spaces.find((s) => s.id === r.space_id)?.name ?? r.space_id : "Platform"}</td>
                <td>{r.requested_days ? `${r.requested_days} days` : "no expiry asked"}</td>
                <td className="muted-text">{r.reason}</td>
                <td><div className="iam-actions">
                  {r.user_id !== me.user.id ? <>
                    <button type="button" className="approve-button" onClick={() => setDeciding({ id: r.id, approve: true })}>Approve</button>
                    <button type="button" className="reject-button" onClick={() => setDeciding({ id: r.id, approve: false })}>Reject</button>
                  </> : <button type="button" className="text-button" onClick={() => void cancelRequest(r.id).then(() => requests.reload())}>Cancel mine</button>}
                </div></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {decided.length ? (
        <details>
          <summary className="muted-text">{decided.length} decided</summary>
          <table className="data-table">
            <thead><tr><th>Who</th><th>Role</th><th>Outcome</th><th>When</th><th>Reason</th></tr></thead>
            <tbody>{decided.map((r) => <tr key={r.id}><td>{r.display_name}</td><td>{r.role_id}</td><td><Pill tone={r.status === "approved" ? "good" : "warn"}>{r.status}</Pill></td><td>{formatWhen(r.decided_at)}</td><td className="muted-text">{r.decision_reason}</td></tr>)}</tbody>
          </table>
        </details>
      ) : null}
      {deciding ? (
        <ConfirmDialog open title={deciding.approve ? "Approve this request?" : "Reject this request?"} body={<p>{deciding.approve ? "The grant expires as asked, or after the default period." : "The requester is told."}</p>}
          confirmLabel={deciding.approve ? "Approve" : "Reject"} danger={!deciding.approve} onClose={() => setDeciding(null)}
          onConfirm={async (reason) => { await decideRequest(deciding.id, deciding.approve, reason); requests.reload(); }} />
      ) : null}
    </div>
  );
}

function Explain({ me }: { me: Me }) {
  const people = useLoad(listPeople);
  const [userId, setUserId] = useState("");
  const [permission, setPermission] = useState("documents.read");
  const [spaceId, setSpaceId] = useState("");
  const [result, setResult] = useState<Explanation | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function ask() {
    setError(null);
    try {
      setResult(await explainAccess({ user_id: userId, permission, space_id: spaceId || null }));
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Could not explain.");
    }
  }
  return (
    <div className="panel">
      <div className="panel-heading"><div><h2>Why can this person do this?</h2><p className="muted-text">The decision as the server takes it, with the grants and denies it looked at.</p></div></div>
      <div className="iam-row">
        <Field label="Person">
          <select className="iam-input" value={userId} onChange={(e) => setUserId(e.target.value)}>
            <option value="">Choose…</option>
            {(people.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.display_name}</option>)}
          </select>
        </Field>
        <Field label="Permission">
          <input className="iam-input" list="iam-permission-keys-explain" value={permission} onChange={(e) => setPermission(e.target.value)} />
          <datalist id="iam-permission-keys-explain">{PERMISSION_KEYS.map((k) => <option key={k} value={k} />)}</datalist>
        </Field>
        <Field label="Where">
          <select className="iam-input" value={spaceId} onChange={(e) => setSpaceId(e.target.value)}>
            <option value="">Platform</option>
            {me.spaces.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </Field>
      </div>
      <div className="iam-toolbar" style={{ marginTop: 12 }}>
        <button type="button" className="primary-button" disabled={!userId || !permission} onClick={() => void ask()}>Explain</button>
      </div>
      {error ? <Notice tone="danger">{error}</Notice> : null}
      {result ? (
        <div className="iam-stack" style={{ marginTop: 14 }}>
          <Notice tone={result.allowed ? "good" : "warn"}><b>{result.allowed ? "Allowed" : "Denied"}</b> · {result.code}: {result.reason}{result.membership_active === false ? " · no active membership in the space" : ""}</Notice>
          <table className="data-table">
            <thead><tr><th>Grant</th><th>Where</th><th>Grants it?</th><th>Applies here?</th><th>Until</th></tr></thead>
            <tbody>
              {result.bindings.map((b) => (
                <tr key={b.binding_id}><td>{b.role_name}{b.via_group ? " (via a group)" : ""}</td><td>{b.scope_type === "platform" ? "Platform" : b.scope_id}</td><td>{b.grants_permission ? "yes" : "no"}</td><td>{b.applies_here ? "yes" : "no"}</td><td>{b.ends_at ? formatWhen(b.ends_at) : "—"}</td></tr>
              ))}
              {result.denies.map((d) => (
                <tr key={d.id}><td>Explicit deny</td><td>{d.scope_type === "platform" ? "Platform" : d.scope_id}</td><td>—</td><td>yes</td><td>{d.ends_at ? formatWhen(d.ends_at) : "—"}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
