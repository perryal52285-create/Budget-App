import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../api";
import { useAuth } from "../auth";

type Health = { ok: boolean; version: string; period: { year: number; month: number } };
const MONTHS = ["", "January", "February", "March", "April", "May", "June", "July",
  "August", "September", "October", "November", "December"];

export default function Dashboard() {
  const { user } = useAuth();
  const { data } = useQuery({ queryKey: ["health"], queryFn: () => apiGet<Health>("/health") });

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div>
        <h2 style={{ margin: 0 }}>Welcome back, {user?.display_name}.</h2>
        <p className="muted" style={{ marginTop: 4 }}>
          {data ? `${MONTHS[data.period.month]} ${data.period.year}` : "…"} · engine v{data?.version}
        </p>
      </div>

      <div className="grid-cards">
        {[
          ["Income this month", "—"],
          ["Bills funded", "—"],
          ["Left to allocate", "—"],
          ["Total debt", "—"],
        ].map(([k, v]) => (
          <div key={k} className="card stat">
            <div className="k">{k}</div>
            <div className="v">{v}</div>
          </div>
        ))}
      </div>

      <div className="card" style={{ padding: 18 }}>
        <h3 style={{ marginTop: 0 }}>Phase 1 shipped ✓</h3>
        <p className="muted" style={{ marginTop: 0 }}>
          Two-user login, sessions, dual themes, and the responsive shell are live.
          Live dashboard numbers, net-worth accounts, sinking-fund goals, and reports
          land in the next phases — the cards above wire up to the engine then.
        </p>
      </div>
    </div>
  );
}
