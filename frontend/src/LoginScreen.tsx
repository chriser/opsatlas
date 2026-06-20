import { useState } from "react";
import { login } from "./api";

export function LoginScreen({ onSuccess }: { onSuccess: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(password);
      onSuccess();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-shell">
      <form className="login-card" onSubmit={onSubmit}>
        <p className="login-brand">
          Knowledge<span>.</span>
        </p>
        <h1>Operator sign in</h1>
        <p className="muted-text">Enter the operator password to access the control panel.</p>
        <input
          className="login-input"
          type="password"
          placeholder="Operator password"
          value={password}
          autoFocus
          onChange={(e) => setPassword(e.target.value)}
        />
        {error ? <p className="login-error">{error}</p> : null}
        <button className="primary-button" type="submit" disabled={busy || !password}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
