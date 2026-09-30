// People (IAM F7): who has an account, in what state, with which roles; invitations, suspension, recovery, offboarding.
import { useMemo, useState } from "react";
import type { Me } from "../api";
import {
  capabilitiesOf,
  deactivatePerson,
  grant,
  grantableRoles,
  invitePerson,
  listBindings,
  listPeople,
  personSessions,
  reactivatePerson,
  recoveryLink,
  resendInvitation,
  revoke,
  signOutPerson,
  suspendPerson,
  type Binding,
  type Person,
  type Role,
  type Session,
} from "./api";
import { ConfirmDialog, Drawer, EmptyCard, Field, formatWhen, LinkOnce, Notice, Pill, STATE_TONE, useLoad, useReauth } from "./ui";

type Action = { kind: "suspend" | "reactivate" | "deactivate" | "recovery" | "signout"; person: Person };

export function PeoplePage({ me }: { me: Me }) {
  const people = useLoad(listPeople);
  const [query, setQuery] = useState("");
  const [state, setState] = useState("all");
  const [inviting, setInviting] = useState(false);
  const [granting, setGranting] = useState<Person | null>(null);
  const [opened, setOpened] = useState<Person | null>(null);
  const [action, setAction] = useState<Action | null>(null);
  const [link, setLink] = useState<{ link: string; expires_at: string | null; what: string } | null>(null);
  const [reauthElement, withReauth] = useReauth();
  const canInvite = me.platform_permissions.includes("iam.users.invite") || me.spaces.some((s) => s.permissions.includes("spaces.members.invite"));

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (people.data ?? []).filter((p) => (state === "all" || p.state === state) &&
      (!q || p.display_name.toLowerCase().includes(q) || p.email.toLowerCase().includes(q) || p.roles.some((r) => r.role_name.toLowerCase().includes(q))));
  }, [people.data, query, state]);

  async function perform(reason: string) {
    if (!action) return;
    const { kind, person } = action;
    if (kind === "suspend") await suspendPerson(person.id, reason);
    else if (kind === "reactivate") await reactivatePerson(person.id, reason);
    else if (kind === "deactivate") await withReauth(() => deactivatePerson(person.id, reason));
    else if (kind === "signout") await signOutPerson(person.id);
    else if (kind === "recovery") {
      const issued = await withReauth(() => recoveryLink(person.id, reason));
      setLink({ link: issued.link, expires_at: issued.expires_at, what: `Recovery link for ${person.display_name}` });
    }
    people.reload();
  }

  const dialogText: Record<Action["kind"], { title: string; body: string; label: string; danger?: boolean; reason?: boolean }> = {
    suspend: { title: "Suspend this account?", body: "They are denied at once; their sessions end. Their content and history stay.", label: "Suspend", reason: true },
    reactivate: { title: "Reactivate this account?", body: "Their roles come back as they were. Old sessions do not.", label: "Reactivate", reason: true },
    deactivate: { title: "Deactivate (offboard) this account?", body: "Every role, membership, invitation and session goes. Attribution of past actions stays. This is not undone by reactivation.", label: "Deactivate", danger: true, reason: true },
    recovery: { title: "Issue a recovery link?", body: "A one-use link, valid for a short while, shown once for you to hand over. Their current sessions continue until the password is reset.", label: "Issue the link", reason: true },
    signout: { title: "Sign them out everywhere?", body: "Every session of theirs ends now; they sign in again with their password.", label: "Sign out", reason: false },
  };

  return (
    <div className="view-stack">
      <div className="page-intro">
        <div>
          <h1>People</h1>
          <p>Everyone with an account on this installation: their state, their roles and where they hold them.</p>
        </div>
        {canInvite ? (
          <button type="button" className="primary-button" onClick={() => setInviting(true)}>
            Invite a person
          </button>
        ) : null}
      </div>
      <div className="panel">
        <div className="panel-heading">
          <div>
            <h2>Accounts</h2>
            <p className="muted-text">{people.data ? `${people.data.length} people` : "Loading…"}</p>
          </div>
          <div className="iam-toolbar">
            <input className="iam-input" placeholder="Search name, email or role" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search people" />
            <select className="iam-input" value={state} onChange={(e) => setState(e.target.value)} aria-label="Filter by state">
              <option value="all">All states</option>
              <option value="active">Active</option>
              <option value="invited">Invited</option>
              <option value="suspended">Suspended</option>
              <option value="deactivated">Deactivated</option>
            </select>
          </div>
        </div>
        {people.error ? <Notice tone="danger">{people.error}</Notice> : null}
        {rows.length === 0 && !people.loading ? (
          <EmptyCard title="No one matches" hint="Change the filter, or invite someone." />
        ) : (
          <div className="iam-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Person</th>
                  <th>State</th>
                  <th>Roles</th>
                  <th>Last sign-in</th>
                  <th>Sessions</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((person) => (
                  <tr key={person.id}>
                    <td>
                      <div className="iam-cell-main">
                        <button type="button" className="text-button" style={{ padding: 0, textAlign: "left" }} onClick={() => setOpened(person)}>
                          <b>{person.display_name}</b>
                        </button>
                        <small>{person.email}{person.id === me.user.id ? " · you" : ""}</small>
                      </div>
                    </td>
                    <td>
                      <Pill tone={STATE_TONE[person.state] ?? "neutral"}>{person.state}</Pill>
                      {person.state === "invited" && person.invitation ? <div><small className="muted-text">link until {formatWhen(person.invitation.expires_at)}</small></div> : null}
                    </td>
                    <td>
                      <div className="iam-chips">
                        {person.roles.length === 0 ? <small className="muted-text">Product Guide reader only</small> : null}
                        {person.roles.map((r) => (
                          <Pill key={r.binding_id} tone={r.scope_type === "platform" ? "purple" : "blue"} title={r.ends_at ? `until ${formatWhen(r.ends_at)}` : undefined}>
                            {r.role_name}{r.space_name ? ` · ${r.space_name}` : ""}
                          </Pill>
                        ))}
                      </div>
                    </td>
                    <td>{formatWhen(person.last_sign_in_at)}</td>
                    <td>{person.sessions}</td>
                    <td>
                      <div className="iam-actions">
                        {person.state !== "deactivated" ? (
                          <button type="button" className="text-button" onClick={() => setGranting(person)}>Give a role</button>
                        ) : null}
                        {person.state === "invited" ? (
                          <button type="button" className="text-button" onClick={() => void resendInvitation(person.id).then((r) => {
                            setLink({ link: r.link, expires_at: r.expires_at, what: `Invitation for ${person.display_name}` });
                            people.reload();
                          })}>Resend invitation</button>
                        ) : null}
                        {person.state === "active" && person.id !== me.user.id ? (
                          <>
                            <button type="button" className="text-button" onClick={() => setAction({ kind: "recovery", person })}>Recovery link</button>
                            <button type="button" className="text-button" onClick={() => setAction({ kind: "signout", person })}>Sign out</button>
                            <button type="button" className="text-button" onClick={() => setAction({ kind: "suspend", person })}>Suspend</button>
                          </>
                        ) : null}
                        {person.state === "suspended" ? (
                          <button type="button" className="text-button" onClick={() => setAction({ kind: "reactivate", person })}>Reactivate</button>
                        ) : null}
                        {person.state !== "deactivated" && person.id !== me.user.id ? (
                          <button type="button" className="text-button" onClick={() => setAction({ kind: "deactivate", person })}>Deactivate</button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <InviteDrawer me={me} open={inviting} onClose={() => setInviting(false)} onDone={(issued) => { people.reload(); if (issued) setLink(issued); }} />
      <GrantDrawer me={me} person={granting} onClose={() => setGranting(null)} onDone={() => people.reload()} />
      <PersonDrawer me={me} person={opened} onClose={() => setOpened(null)} onChanged={() => people.reload()} />
      {action ? (
        <ConfirmDialog
          open
          title={dialogText[action.kind].title}
          body={<p>{dialogText[action.kind].body}<br /><b>{action.person.display_name}</b> · {action.person.email}</p>}
          confirmLabel={dialogText[action.kind].label}
          danger={dialogText[action.kind].danger}
          reasonLabel={dialogText[action.kind].reason ? "Reason (recorded)" : null}
          onClose={() => setAction(null)}
          onConfirm={perform}
        />
      ) : null}
      <Drawer title={link?.what ?? ""} open={link !== null} onClose={() => setLink(null)}>
        {link ? <LinkOnce link={link.link} expiresAt={link.expires_at} what={link.what} /> : null}
      </Drawer>
      {reauthElement}
    </div>
  );
}

function spaceOptions(me: Me) {
  return me.spaces.map((s) => ({ id: s.id, name: s.name, kind: s.kind }));
}

function InviteDrawer({ me, open, onClose, onDone }: { me: Me; open: boolean; onClose: () => void;
  onDone: (issued: { link: string; expires_at: string | null; what: string } | null) => void }) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [roleId, setRoleId] = useState("");
  const [spaceId, setSpaceId] = useState("");
  const [days, setDays] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const roles = useLoad(() => grantableRoles(spaceId || null), [spaceId, open]);
  const role = roles.data?.find((r) => r.id === roleId);
  const needsSpace = role?.boundary === "space";

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const issued = await invitePerson({ email: email.trim(), display_name: name.trim(), role_id: roleId || null,
        space_id: needsSpace ? spaceId : null, days: days ? Number(days) : null, message });
      onDone(issued.link ? { link: issued.link, expires_at: issued.expires_at, what: `Invitation for ${issued.user.display_name}` } : null);
      setEmail(""); setName(""); setRoleId(""); setDays(""); setMessage("");
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "The invitation was not created.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Drawer title="Invite a person" subtitle="A new account waits until the one-time link is used; an existing account receives the role at once." open={open} onClose={onClose}
      footer={<>
        <button type="button" className="secondary-button" onClick={onClose}>Cancel</button>
        <button type="button" className="primary-button" disabled={busy || !email || (needsSpace && !spaceId)} onClick={() => void submit()}>{busy ? "Inviting…" : "Invite"}</button>
      </>}>
      <div className="iam-stack">
        <Field label="Email address"><input className="iam-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus /></Field>
        <Field label="Name" hint="They can change it later."><input className="iam-input" value={name} onChange={(e) => setName(e.target.value)} /></Field>
        <div className="iam-row">
          <Field label="Role" hint="None: they read the Product Guide only.">
            <select className="iam-input" value={roleId} onChange={(e) => setRoleId(e.target.value)}>
              <option value="">No role yet</option>
              {(roles.data ?? []).map((r) => <option key={r.id} value={r.id}>{r.name} ({r.boundary})</option>)}
            </select>
          </Field>
          <Field label="Space" hint={needsSpace ? "Required for a space role." : "Only for a space role."}>
            <select className="iam-input" value={spaceId} onChange={(e) => setSpaceId(e.target.value)} disabled={role !== undefined && !needsSpace}>
              <option value="">—</option>
              {spaceOptions(me).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </Field>
        </div>
        <div className="iam-row">
          <Field label="Expires after (days)" hint="Blank: no expiry. Guests should expire."><input className="iam-input" type="number" min={1} max={3650} value={days} onChange={(e) => setDays(e.target.value)} /></Field>
        </div>
        <Field label="Message shown on the invitation"><textarea className="iam-input" value={message} onChange={(e) => setMessage(e.target.value)} maxLength={500} /></Field>
        {role ? <Notice tone="blue"><b>{role.name}</b>: {role.description}</Notice> : null}
        {error ? <Notice tone="danger">{error}</Notice> : null}
      </div>
    </Drawer>
  );
}

function GrantDrawer({ me, person, onClose, onDone }: { me: Me; person: Person | null; onClose: () => void; onDone: () => void }) {
  const [roleId, setRoleId] = useState("");
  const [spaceId, setSpaceId] = useState("");
  const [days, setDays] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reauthElement, withReauth] = useReauth();
  const roles = useLoad(() => grantableRoles(spaceId || null), [spaceId, person?.id]);
  const role = roles.data?.find((r) => r.id === roleId);
  const needsSpace = role?.boundary === "space";

  async function submit() {
    if (!person || !role) return;
    setBusy(true);
    setError(null);
    try {
      await withReauth(() => grant({ subject_id: person.id, role_id: role.id, scope_type: needsSpace ? "space" : "platform",
        scope_id: needsSpace ? spaceId : "", days: days ? Number(days) : null, reason }));
      onDone();
      onClose();
      setRoleId(""); setDays(""); setReason("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "The role was not given.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Drawer title={person ? `Give ${person.display_name} a role` : ""} subtitle="Within what you may give; a protected role asks for your password again." open={person !== null} onClose={onClose}
      footer={<>
        <button type="button" className="secondary-button" onClick={onClose}>Cancel</button>
        <button type="button" className="primary-button" disabled={busy || !role || (needsSpace && !spaceId)} onClick={() => void submit()}>{busy ? "Giving…" : "Give the role"}</button>
      </>}>
      <div className="iam-stack">
        <div className="iam-row">
          <Field label="Role">
            <select className="iam-input" value={roleId} onChange={(e) => setRoleId(e.target.value)}>
              <option value="">Choose…</option>
              {(roles.data ?? []).map((r) => <option key={r.id} value={r.id}>{r.name} ({r.boundary}){r.protected ? " · protected" : ""}</option>)}
            </select>
          </Field>
          <Field label="Space">
            <select className="iam-input" value={spaceId} onChange={(e) => setSpaceId(e.target.value)} disabled={role !== undefined && !needsSpace}>
              <option value="">—</option>
              {spaceOptions(me).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </Field>
        </div>
        <div className="iam-row">
          <Field label="Expires after (days)"><input className="iam-input" type="number" min={1} max={3650} value={days} onChange={(e) => setDays(e.target.value)} /></Field>
          <Field label="Reason (recorded)"><input className="iam-input" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={200} /></Field>
        </div>
        {role ? <Notice tone="blue"><b>{role.name}</b>: {role.description}{role.excluded ? <><br /><span className="muted-text">Not included: {role.excluded}</span></> : null}</Notice> : null}
        {error ? <Notice tone="danger">{error}</Notice> : null}
      </div>
      {reauthElement}
    </Drawer>
  );
}

function PersonDrawer({ me, person, onClose, onChanged }: { me: Me; person: Person | null; onClose: () => void; onChanged: () => void }) {
  const bindings = useLoad(() => (person ? listBindings({ user_id: person.id, include_system: true }) : Promise.resolve([] as Binding[])), [person?.id]);
  const sessions = useLoad(() => (person && me.platform_permissions.includes("iam.sessions.read") ? personSessions(person.id) : Promise.resolve([] as Session[])), [person?.id]);
  const caps = useLoad(() => (person ? capabilitiesOf(person.id) : Promise.resolve(null)), [person?.id]);
  const [revoking, setRevoking] = useState<Binding | null>(null);
  return (
    <Drawer title={person?.display_name ?? ""} subtitle={person ? `${person.email} · ${person.state}` : ""} open={person !== null} onClose={onClose} wide>
      {person ? (
        <div className="iam-stack">
          <dl className="iam-kv">
            <dt>Created</dt><dd>{formatWhen(person.created_at)}</dd>
            <dt>Activated</dt><dd>{formatWhen(person.activated_at)}</dd>
            <dt>Last sign-in</dt><dd>{formatWhen(person.last_sign_in_at)}</dd>
            {person.note ? <><dt>Note</dt><dd>{person.note}</dd></> : null}
          </dl>
          <section>
            <h3>Grants</h3>
            {(bindings.data ?? []).length === 0 ? <p className="muted-text">None.</p> : (
              <table className="data-table">
                <thead><tr><th>Role</th><th>Where</th><th>Until</th><th>Reason</th><th /></tr></thead>
                <tbody>
                  {(bindings.data ?? []).map((b) => (
                    <tr key={b.id}>
                      <td>{b.role_name}{b.system ? <> <Pill tone="neutral">follows the account</Pill></> : null}</td>
                      <td>{b.scope_type === "platform" ? "Platform" : b.space_name ?? b.scope_id}</td>
                      <td>{b.ends_at ? formatWhen(b.ends_at) : "—"}</td>
                      <td className="muted-text">{b.reason}</td>
                      <td>{!b.system ? <button type="button" className="text-button" onClick={() => setRevoking(b)}>Revoke</button> : null}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
          {caps.data ? (
            <section>
              <h3>Effective access</h3>
              <p className="muted-text">Platform: {caps.data.platform.length} permissions. {Object.entries(caps.data.spaces).map(([id, keys]) => `${id}: ${keys.length}`).join(" · ") || "No space."}</p>
            </section>
          ) : null}
          {sessions.data && sessions.data.length ? (
            <section>
              <h3>Sessions</h3>
              <table className="data-table">
                <thead><tr><th>Since</th><th>Last seen</th><th>Ends</th><th>Device</th></tr></thead>
                <tbody>
                  {sessions.data.map((s) => (
                    <tr key={s.id}><td>{formatWhen(s.created_at)}</td><td>{formatWhen(s.last_seen_at)}</td><td>{formatWhen(s.absolute_expires_at)}</td><td className="muted-text">{s.device || "—"}{s.address ? ` · ${s.address}` : ""}</td></tr>
                  ))}
                </tbody>
              </table>
            </section>
          ) : null}
        </div>
      ) : null}
      {revoking ? (
        <ConfirmDialog open title="Revoke this grant?" body={<p><b>{revoking.role_name}</b> {revoking.space_name ? `in ${revoking.space_name}` : "at the platform"}.</p>}
          confirmLabel="Revoke" danger onClose={() => setRevoking(null)}
          onConfirm={async (reason) => { await revoke(revoking.id, reason); bindings.reload(); onChanged(); }} />
      ) : null}
    </Drawer>
  );
}

export type { Role };
