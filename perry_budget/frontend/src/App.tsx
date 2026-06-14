import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./auth";
import Shell from "./components/Shell";
import Login from "./pages/Login";
import ChangePassword from "./pages/ChangePassword";
import Dashboard from "./pages/Dashboard";
import Placeholder from "./pages/Placeholder";

export default function App() {
  const { user, loading } = useAuth();

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
        <Route path="/accounts" element={<Placeholder title="Net Worth"
          note="Accounts + balance history → net-worth-over-time. Coming in the accounts phase." />} />
        <Route path="/budgets" element={<Placeholder title="Budgets"
          note="Category budgets with month-end rollover and live spend tracking. Coming soon." />} />
        <Route path="/goals" element={<Placeholder title="Goals"
          note="Sinking funds for the January bonus, the 3-check surplus, and savings targets. Coming soon." />} />
        <Route path="/manage" element={<Placeholder title="Manage"
          note="Earners, income sources, bills, debts, and settings. Coming in the manage phase." />} />
        <Route path="/reports" element={<Placeholder title="Reports"
          note="Cash flow, spending-by-category trends, and net worth over time. Coming soon." />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  );
}
