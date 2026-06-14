import { useState } from "react";
import { useAuth } from "../auth";
import { useTheme } from "../theme";
import { ApiError, apiPost } from "../api";

export default function ChangePassword() {
  const { refresh, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (next !== confirm) return setError("New passwords don't match");
    if (next.length < 6) return setError("New password must be at least 6 characters");
    setBusy(true);
    try {
      await apiPost("/change-password", { current_password: current, new_password: next });
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not change password");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={{ minHeight: "100dvh", display: "grid", placeItems: "center", padding: 20 }}>
      <form onSubmit={submit} className="card" style={{ width: "100%", maxWidth: 380, padding: 28 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h1 style={{ margin: 0, fontSize: 20 }}>Set a new password</h1>
          <button type="button" className="btn btn-ghost" onClick={toggle} style={{ padding: "0.3rem 0.6rem" }}>
            {theme === "terminal" ? "🖥️" : "🫧"}
          </button>
        </div>
        <p className="muted" style={{ marginTop: 6, marginBottom: 20, fontSize: 13 }}>
          You're using a temporary password. Choose your own to continue.
        </p>

        <label className="label">Current password</label>
        <input className="input" type="password" value={current} onChange={(e) => setCurrent(e.target.value)} />
        <label className="label" style={{ marginTop: 12 }}>New password</label>
        <input className="input" type="password" value={next} onChange={(e) => setNext(e.target.value)} />
        <label className="label" style={{ marginTop: 12 }}>Confirm new password</label>
        <input className="input" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />

        {error && <p style={{ color: "var(--danger)", fontSize: 13, marginTop: 14, marginBottom: 0 }}>{error}</p>}

        <button className="btn btn-primary" type="submit" disabled={busy} style={{ width: "100%", marginTop: 20 }}>
          {busy ? "Saving…" : "Save password"}
        </button>
        <button type="button" className="btn btn-ghost" onClick={() => logout()} style={{ width: "100%", marginTop: 8 }}>
          Sign out
        </button>
      </form>
    </div>
  );
}
