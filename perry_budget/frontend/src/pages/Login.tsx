import { useState } from "react";
import { useAuth } from "../auth";
import { useTheme } from "../theme";
import { ApiError } from "../api";

export default function Login() {
  const { login } = useAuth();
  const { theme, toggle } = useTheme();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(username, password);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ minHeight: "100dvh", display: "grid", placeItems: "center", padding: 20 }}>
      <form onSubmit={submit} className="card" style={{ width: "100%", maxWidth: 380, padding: 28 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h1 style={{ margin: 0, fontSize: 22 }}>Perry Budget</h1>
          <button type="button" className="btn btn-ghost" onClick={toggle} title="Switch theme"
            style={{ padding: "0.3rem 0.6rem" }}>
            {theme === "terminal" ? "🖥️" : "🫧"}
          </button>
        </div>
        <p className="muted" style={{ marginTop: 6, marginBottom: 22, fontSize: 13 }}>
          Sign in to your household budget.
        </p>

        <label className="label" htmlFor="u">Username</label>
        <input id="u" className="input" autoCapitalize="none" autoComplete="username"
          value={username} onChange={(e) => setUsername(e.target.value)} placeholder="alex or rae" />

        <label className="label" htmlFor="p" style={{ marginTop: 14 }}>Password</label>
        <input id="p" className="input" type="password" autoComplete="current-password"
          value={password} onChange={(e) => setPassword(e.target.value)} />

        {error && (
          <p style={{ color: "var(--danger)", fontSize: 13, marginTop: 14, marginBottom: 0 }}>
            {error}
          </p>
        )}

        <button className="btn btn-primary" type="submit" disabled={busy}
          style={{ width: "100%", marginTop: 22 }}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
