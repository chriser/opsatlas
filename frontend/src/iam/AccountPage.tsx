// My account (IAM F7): picture, name, password, where I am signed in, what I may reach, and my access requests.
import { useState } from "react";
import { fetchMe, pictureUrl, type Me } from "../api";
import { initials } from "../ui";
import {
  cancelRequest, changePassword, listRequests, listRoles, mySessions, removePicture, requestAccess, revokeMySession, signOutEverywhere,
  updateProfile, uploadPicture,
} from "./api";
import { notify } from "../notices";
import { PictureCropper } from "./PictureCropper";
import { Field, formatWhen, Pill, useLoad, useReauth } from "./ui";

export function AccountPage({ me }: { me: Me }) {
  const [name, setName] = useState(me.user.display_name);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  // What happened is said in the sidebar's messages, so the page never moves (OBS F7).
  const setMessage = (message: { tone: "good" | "danger"; text: string }) => notify(message.text, message.tone);
  const sessions = useLoad(mySessions);
  const requests = useLoad(() => listRequests(true));
  const roles = useLoad(listRoles);
  const [roleId, setRoleId] = useState("");
  const [spaceId, setSpaceId] = useState("");
  const [reason, setReason] = useState("");
  const [reauthElement, withReauth] = useReauth();
  const [chosen, setChosen] = useState<File | null>(null);
  const picture = pictureUrl(me.user);

  async function saveName() {
    try {
      await updateProfile(name);
      setMessage({ tone: "good", text: "Your name is saved." });
    } catch (err) {
      setMessage({ tone: "danger", text: err instanceof Error ? err.message : "Not saved." });
    }
  }
  async function savePicture(blob: Blob) {
    await uploadPicture(blob);
    setChosen(null);
    setMessage({ tone: "good", text: "Your picture is saved; it is in the sidebar now." });
  }
  async function dropPicture() {
    try {
      await removePicture();
      setMessage({ tone: "good", text: "Your picture is removed; your initials show instead." });
    } catch (err) {
      setMessage({ tone: "danger", text: err instanceof Error ? err.message : "Not removed." });
    }
  }
  async function savePassword() {
    if (next !== again) {
      setMessage({ tone: "danger", text: "The two new passwords differ." });
      return;
    }
    try {
      await changePassword(current, next);
      await fetchMe();
      setCurrent(""); setNext(""); setAgain("");
      setMessage({ tone: "good", text: "Your password is changed; your other sessions have ended." });
      sessions.reload();
    } catch (err) {
      setMessage({ tone: "danger", text: err instanceof Error ? err.message : "Not changed." });
    }
  }
  async function endOthers() {
    try {
      const done = await withReauth(signOutEverywhere);
      setMessage({ tone: "good", text: `${done.revoked} session(s) ended; sign in again.` });
    } catch (err) {
      setMessage({ tone: "danger", text: err instanceof Error ? err.message : "Not done." });
    }
  }
  async function ask() {
    try {
      await requestAccess({ role_id: roleId, space_id: spaceId || null, reason });
      setRoleId(""); setSpaceId(""); setReason("");
      requests.reload();
      setMessage({ tone: "good", text: "Your request is with the administrators." });
    } catch (err) {
      setMessage({ tone: "danger", text: err instanceof Error ? err.message : "Not sent." });
    }
  }
  const requestable = (roles.data?.roles ?? []).filter((r) => !r.protected && !r.system);
  const role = requestable.find((r) => r.id === roleId);

  return (
    <div className="view-stack">
      <div className="page-intro">
        <div>
          <h1>My account</h1>
          <p>{me.user.email} · {me.user.role_label}{me.session.privileged ? " · administrator session" : ""}</p>
        </div>
      </div>
      <div className="dashboard-grid">
        <div className="column-stack">
          <div className="panel">
            <div className="panel-heading"><div><h2>Profile</h2><p className="muted-text">Your name appears beside what you write and approve. Your email is changed by an administrator.</p></div></div>
            <div className="iam-stack">
              <div className="account-picture">
                <span className="account-picture-frame">
                  {picture ? <img src={picture} alt="Your picture" /> : <span aria-hidden="true">{initials(me.user.display_name)}</span>}
                </span>
                <div className="account-picture-actions">
                  <div className="account-picture-buttons">
                    <label className="secondary-button account-picture-choose">
                      {picture ? "Change the picture…" : "Choose a picture…"}
                      <input
                        type="file"
                        accept="image/*"
                        onChange={(e) => {
                          setChosen(e.target.files?.[0] ?? null);
                          e.target.value = ""; // the same file can be chosen again
                        }}
                      />
                    </label>
                    {picture ? <button type="button" className="text-button" onClick={() => void dropPicture()}>Remove</button> : null}
                  </div>
                  <span className="muted-text">Shown in the sidebar under the logo. You size it and move it in the square before it is saved.</span>
                </div>
              </div>
              <Field label="Name"><input className="iam-input" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} /></Field>
              <div><button type="button" className="primary-button" disabled={!name.trim() || name === me.user.display_name} onClick={() => void saveName()}>Save</button></div>
            </div>
          </div>
          <div className="panel">
            <div className="panel-heading"><div><h2>Password</h2><p className="muted-text">At least 15 characters; a sentence works. Your other sessions end when it changes.</p></div></div>
            <form className="iam-stack" onSubmit={(e) => { e.preventDefault(); void savePassword(); }}>
              <Field label="Current password"><input className="iam-input" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} /></Field>
              <Field label="New password"><input className="iam-input" type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} /></Field>
              <Field label="The same again"><input className="iam-input" type="password" autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} /></Field>
              <div><button type="submit" className="primary-button" disabled={!current || next.length < 15 || !again}>Change the password</button></div>
            </form>
          </div>
        </div>
        <div className="column-stack">
          <div className="panel">
            <div className="panel-heading">
              <div><h2>Where I am signed in</h2><p className="muted-text">Sessions end after {me.session.idle_minutes} minutes without activity, and in any case at their end time.</p></div>
              <button type="button" className="secondary-button" onClick={() => void endOthers()}>Sign out everywhere</button>
            </div>
            <table className="data-table">
              <thead><tr><th>Since</th><th>Last seen</th><th>Ends</th><th>Device</th><th /></tr></thead>
              <tbody>
                {(sessions.data ?? []).map((s) => (
                  <tr key={s.id}>
                    <td>{formatWhen(s.created_at)}{s.current ? <> <Pill tone="good">this one</Pill></> : null}</td><td>{formatWhen(s.last_seen_at)}</td><td>{formatWhen(s.absolute_expires_at)}</td>
                    <td className="muted-text">{s.device || "—"}</td>
                    <td>{!s.current ? <button type="button" className="text-button" onClick={() => void withReauth(() => revokeMySession(s.id)).then(() => sessions.reload()).catch((err) => setMessage({ tone: "danger", text: err instanceof Error ? err.message : "Not ended." }))}>End</button> : null}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="panel">
            <div className="panel-heading"><div><h2>My access</h2><p className="muted-text">The spaces I can reach and how much I may do in each.</p></div></div>
            <div className="iam-chips">
              {me.spaces.map((s) => <Pill key={s.id} tone={s.kind === "organisation" ? "blue" : "purple"} title={`${s.permissions.length} permissions`}>{s.name} · {s.permissions.length}</Pill>)}
            </div>
            <p className="muted-text" style={{ marginTop: 8 }}>Platform: {me.platform_permissions.length} permissions.</p>
          </div>
          <div className="panel">
            <div className="panel-heading"><div><h2>Ask for access</h2><p className="muted-text">Someone with the authority decides; an approval is a grant with an expiry.</p></div></div>
            <div className="iam-stack">
              <div className="iam-row">
                <Field label="Role"><select className="iam-input" value={roleId} onChange={(e) => setRoleId(e.target.value)}><option value="">Choose…</option>{requestable.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}</select></Field>
                <Field label="Space"><select className="iam-input" value={spaceId} onChange={(e) => setSpaceId(e.target.value)} disabled={role?.boundary === "platform"}><option value="">—</option>{me.spaces.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></Field>
              </div>
              <Field label="Why"><input className="iam-input" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500} /></Field>
              <div><button type="button" className="primary-button" disabled={!roleId || !reason.trim() || (role?.boundary === "space" && !spaceId)} onClick={() => void ask()}>Send the request</button></div>
              {(requests.data ?? []).length ? (
                <table className="data-table">
                  <thead><tr><th>Role</th><th>Space</th><th>Status</th><th>Asked</th><th /></tr></thead>
                  <tbody>{(requests.data ?? []).map((r) => <tr key={r.id}><td>{r.role_id}</td><td>{r.space_id ?? "—"}</td><td><Pill tone={r.status === "approved" ? "good" : r.status === "pending" ? "blue" : "warn"}>{r.status}</Pill></td><td>{formatWhen(r.requested_at)}</td><td>{r.status === "pending" ? <button type="button" className="text-button" onClick={() => void cancelRequest(r.id).then(() => requests.reload())}>Cancel</button> : null}</td></tr>)}</tbody>
                </table>
              ) : null}
            </div>
          </div>
        </div>
      </div>
      {reauthElement}
      {chosen ? <PictureCropper file={chosen} onCancel={() => setChosen(null)} onSave={savePicture} /> : null}
    </div>
  );
}
