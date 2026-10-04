import { useEffect, useState } from "react";
import { login, type Me } from "./api";
import loginBackgroundLogo from "./assets/bi_logo_transparent.png";
import { BrandMark } from "./BrandMark";
import "./iam/iam.css";

type Mode = "signin" | "invitation" | "reset";

interface Preview {
  email: string;
  display_name: string;
  expires_at: string;
  space: { id: string; name: string } | null;
  role: { id: string; name: string } | null;
  message: string;
  bootstrap: boolean;
}

/** A link's token travels in the fragment (never sent to the server or logged) and leaves the address at once. */
function takeLinkToken(): { mode: Mode; token: string } | null {
  const hash = decodeURIComponent(window.location.hash.slice(1));
  const [kind, token] = hash.split(":");
  if ((kind === "invitation" || kind === "reset") && token) {
    window.history.replaceState(null, "", window.location.pathname);
    return { mode: kind, token };
  }
  return null;
}

async function publicPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = (await res.json().catch(() => ({}))) as T & { detail?: string };
  if (!res.ok) throw new Error(data.detail ?? `Request failed (${res.status})`);
  return data;
}

export function LoginScreen({ onSuccess }: { onSuccess: (me: Me) => void }) {
  const [link] = useState(takeLinkToken);
  const [mode, setMode] = useState<Mode>(link?.mode ?? "signin");
  const [loginName, setLoginName] = useState("");
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [displayName, setDisplayName] = useState("");

  useEffect(() => {
    if (!link) return;
    const path = link.mode === "invitation" ? "/api/auth/invitations/preview" : "/api/auth/password/reset/preview";
    publicPost<Preview>(path, { token: link.token })
      .then((found) => {
        setPreview(found);
        setDisplayName(found.display_name);
        setLoginName(found.email);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "That link is not valid any more.");
        setMode("signin");
      });
  }, [link]);

  async function onSignIn(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onSuccess(await login(loginName.trim(), password));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  }

  async function onSetPassword(event: React.FormEvent) {
    event.preventDefault();
    if (!link) return;
    if (password !== again) {
      setError("The two passwords differ.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      if (link.mode === "invitation") {
        await publicPost("/api/auth/invitations/accept", { token: link.token, password, display_name: displayName });
        setNotice("Your account is ready. Sign in with your email address and the password you chose.");
      } else {
        await publicPost("/api/auth/password/reset", { token: link.token, password });
        setNotice("Your password is set and every earlier session has ended. Sign in again.");
      }
      setPassword("");
      setAgain("");
      setMode("signin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "That did not work.");
    } finally {
      setBusy(false);
    }
  }

  const passwordField = (autoComplete: string, placeholder: string, value: string, onChange: (v: string) => void) => (
    <div className="login-password-row">
      <input
        className="login-input"
        type={show ? "text" : "password"}
        autoComplete={autoComplete}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={placeholder}
      />
      <button type="button" className="secondary-button" onClick={() => setShow((s) => !s)} aria-pressed={show}>
        {show ? "Hide" : "Show"}
      </button>
    </div>
  );

  return (
    <div className="login-shell">
      <img className="login-background-mark" src={loginBackgroundLogo} alt="" aria-hidden="true" />
      <section className="login-panel" aria-label="OpsAtlas sign in">
        <p className="login-brand">
          <BrandMark />
        </p>
        {mode === "signin" ? (
          <form className="login-card login-form-stack" onSubmit={onSignIn}>
            <h1>Sign in</h1>
            <p className="muted-text">Your own email address and password.</p>
            {notice ? <p className="iam-notice iam-notice--good">{notice}</p> : null}
            <input
              className="login-input"
              type="email"
              autoComplete="username"
              placeholder="Email address"
              value={loginName}
              autoFocus
              onChange={(e) => setLoginName(e.target.value)}
              aria-label="Email address"
            />
            {passwordField("current-password", "Password", password, setPassword)}
            {error ? <p className="login-error">{error}</p> : null}
            <button className="primary-button" type="submit" disabled={busy || !loginName || !password}>
              {busy ? "Signing in…" : "Sign in"}
            </button>
            <p className="login-note">
              Forgotten your password? An administrator can hand you a one-time recovery link; this installation sends no email.
            </p>
          </form>
        ) : (
          <form className="login-card login-form-stack" onSubmit={onSetPassword}>
            <h1>{mode === "invitation" ? "Welcome to OpsAtlas" : "Choose a new password"}</h1>
            {preview ? (
              <p className="muted-text">
                {mode === "invitation"
                  ? preview.bootstrap
                    ? `This link sets up the platform administrator account for ${preview.email}.`
                    : `${preview.email}${preview.role ? ` as ${preview.role.name}` : ""}${preview.space ? ` in ${preview.space.name}` : ""}.`
                  : `For ${preview.email}. Every earlier session will end.`}
              </p>
            ) : (
              <p className="muted-text">Checking the link…</p>
            )}
            {preview?.message ? <p className="iam-notice iam-notice--blue">{preview.message}</p> : null}
            {mode === "invitation" ? (
              <input className="login-input" placeholder="Your name" value={displayName} onChange={(e) => setDisplayName(e.target.value)}
                aria-label="Your name" autoComplete="name" />
            ) : null}
            {passwordField("new-password", "New password", password, setPassword)}
            {passwordField("new-password", "The same password again", again, setAgain)}
            <p className="login-note">
              At least 15 characters: a sentence or a few words. Spaces are fine; a password manager is welcome. No symbol rules.
            </p>
            {error ? <p className="login-error">{error}</p> : null}
            <button className="primary-button" type="submit" disabled={busy || !preview || password.length < 15 || !again}>
              {busy ? "Saving…" : mode === "invitation" ? "Create my account" : "Set the password"}
            </button>
            <button type="button" className="text-button" onClick={() => setMode("signin")}>
              Back to sign in
            </button>
          </form>
        )}
      </section>
    </div>
  );
}
