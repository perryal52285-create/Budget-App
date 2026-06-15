import { NavLink, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "../auth";
import { useTheme } from "../theme";
import { apiPost } from "../api";

const NAV = [
  { to: "/", label: "Dashboard", icon: "📊", end: true },
  { to: "/accounts", label: "Net Worth", icon: "🏦" },
  { to: "/budgets", label: "Budgets", icon: "🧮" },
  { to: "/goals", label: "Goals", icon: "🎯" },
  { to: "/manage", label: "Manage", icon: "⚙️" },
  { to: "/reports", label: "Reports", icon: "📈" },
  { to: "/terminal", label: "Terminal", icon: "›_" },
];

export default function Shell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const { theme, setTheme } = useTheme();
  const loc = useLocation();

  // Switch theme and remember it for this login (persists their per-user lock).
  const switchTheme = () => {
    const next = theme === "terminal" ? "bubbly" : "terminal";
    setTheme(next);
    apiPost("/theme", { theme: next }).catch(() => { /* non-fatal */ });
  };
  const title = NAV.find((n) => (n.end ? loc.pathname === n.to : loc.pathname.startsWith(n.to)))?.label
    ?? "Perry Budget";

  return (
    <div style={{ minHeight: "100dvh", display: "flex", flexDirection: "column" }}>
      {/* header */}
      <header style={{
        position: "sticky", top: 0, zIndex: 20, display: "flex", alignItems: "center",
        gap: 12, padding: "12px 16px", borderBottom: "1px solid var(--border)",
        background: "color-mix(in srgb, var(--surface) 88%, transparent)",
        backdropFilter: "blur(8px)",
      }}>
        <strong style={{ fontSize: 16 }}>Perry Budget</strong>
        <span className="muted" style={{ fontSize: 13 }}>· {title}</span>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
          <button className="btn btn-ghost" onClick={switchTheme} title="Switch theme"
            style={{ padding: "0.35rem 0.6rem" }}>
            {theme === "terminal" ? "🖥️" : "🫧"}
          </button>
          <span className="chip" title={user?.username}>{user?.display_name || user?.username}</span>
          <button className="btn btn-ghost" onClick={() => logout()} style={{ padding: "0.35rem 0.7rem" }}>
            Sign out
          </button>
        </div>
      </header>

      <div style={{ display: "flex", flex: 1, minHeight: 0 }}>
        {/* desktop sidebar */}
        <nav className="pb-sidebar">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className="pb-navlink">
              <span style={{ width: 22 }}>{n.icon}</span>
              <span>{n.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* content */}
        <main style={{ flex: 1, minWidth: 0, padding: "20px 16px 96px", maxWidth: 1100, margin: "0 auto", width: "100%" }}>
          {children}
        </main>
      </div>

      {/* mobile bottom tabs */}
      <nav className="pb-tabbar">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end} className="pb-tab">
            <span style={{ fontSize: 18 }}>{n.icon}</span>
            <span style={{ fontSize: 10 }}>{n.label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
