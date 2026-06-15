import { useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./auth";
import { useTheme } from "./theme";
import Shell from "./components/Shell";
import Login from "./pages/Login";
import ChangePassword from "./pages/ChangePassword";
import Dashboard from "./pages/Dashboard";
import Accounts from "./pages/Accounts";
import Budgets from "./pages/Budgets";
import Goals from "./pages/Goals";
import Manage from "./pages/Manage";
import Reports from "./pages/Reports";

export default function App() {
  const { user, loading } = useAuth();
  const { setTheme } = useTheme();

  // Per-user theme lock: apply the signed-in user's saved theme on login.
  useEffect(() => {
    if (user?.theme === "terminal" || user?.theme === "bubbly") setTheme(user.theme);
  }, [user?.id, user?.theme, setTheme]);

  if (loading) {
    return (
      <div className="muted" style={{ display: "grid", placeItems: "center", minHeight: "100dvh" }}>
        Loading…
      </div>
    );
  }
  if (!user) return <Login />;
  if (user.must_change_password) return <ChangePassword />;

  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/accounts" element={<Accounts />} />
        <Route path="/budgets" element={<Budgets />} />
        <Route path="/goals" element={<Goals />} />
        <Route path="/manage" element={<Manage />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  );
}
