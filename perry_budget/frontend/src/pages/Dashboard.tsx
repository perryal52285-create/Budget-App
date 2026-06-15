import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  ResponsiveContainer, PieChart, Pie, Cell, AreaChart, Area, XAxis, YAxis, Tooltip,
} from "recharts";
import { apiGet } from "../api";
import { fmtCents, fmtCentsShort } from "../format";
import { useChartColors } from "../theme";
import { Empty } from "../ui";

const PALETTE = ["#5b9bff", "#ff5b5b", "#e3b341", "#b07cff", "#ff79b0", "#28b487", "#ff944d", "#46d970"];

type YM = { year: number; month: number };
type Dash = {
  view: any; allocation: { label: string; value: number; rest?: boolean }[];
  upcoming: any[]; prev: YM; next: YM; is_current: boolean;
  total_debt_cents: number; next_target: string | null; payoff_months: number;
  snowball_points: number[]; net_worth: { net_cents: number; assets_cents: number; liabilities_cents: number };
  alerts: { level: string; kind: string; text: string }[];
};

export default function Dashboard() {
  const [ym, setYm] = useState<YM | null>(null);
  const q = ym ? `?year=${ym.year}&month=${ym.month}` : "";
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard", ym?.year, ym?.month],
    queryFn: () => apiGet<Dash>(`/dashboard${q}`),
  });
  const c = useChartColors();

  if (isLoading || !data) return <p className="muted">Loading dashboard…</p>;
  const v = data.view;

  const allocData = data.allocation.filter((a) => a.value > 0)
    .map((a) => ({ name: a.label, value: a.value / 100, rest: a.rest }));
  const snowData = data.snowball_points.map((c, i) => ({ m: i, bal: c / 100 }));

  const stats: [string, string, string?][] = [
    ["Income this month", fmtCents(v.total_in)],
    ["Bills funded", fmtCents(v.total_bills)],
    ["Left to allocate", fmtCents(v.remaining), v.remaining < 0 ? "neg" : "pos"],
    ["Total debt", fmtCents(data.total_debt_cents)],
    ["Net worth", fmtCents(data.net_worth.net_cents)],
    ["Debt-free in", data.payoff_months ? `${data.payoff_months} mo` : "—"],
  ];

  return (
    <div style={{ display: "grid", gap: 16 }}>
      {/* month nav */}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <button className="btn btn-ghost" onClick={() => setYm(data.prev)}>‹</button>
        <h2 style={{ margin: 0, minWidth: 180, textAlign: "center" }}>{v.label}</h2>
        <button className="btn btn-ghost" onClick={() => setYm(data.next)}>›</button>
        {!data.is_current && (
          <button className="btn btn-ghost" onClick={() => setYm(null)}>Today</button>
        )}
      </div>

      {/* alerts */}
      {data.alerts.length > 0 && (
        <div style={{ display: "grid", gap: 8 }}>
          {data.alerts.map((a, i) => (
            <div key={i} className="card" style={{
              padding: "10px 14px", borderLeft: `3px solid ${a.level === "warn" ? "var(--warn)" : "var(--info)"}`,
            }}>
              <span style={{ fontSize: 14 }}>{a.level === "warn" ? "⚠️ " : "ℹ️ "}{a.text}</span>
            </div>
          ))}
        </div>
      )}

      {/* stat cards */}
      <div className="grid-cards">
        {stats.map(([k, val, flag]) => (
          <div key={k} className="card stat">
            <div className="k">{k}</div>
            <div className="v" style={{ color: flag === "neg" ? "var(--danger)" : flag === "pos" ? "var(--primary)" : "var(--text)" }}>
              {val}
            </div>
          </div>
        ))}
      </div>

      {/* charts */}
      <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" }}>
        <div className="card" style={{ padding: 18 }}>
          <h3 style={{ marginTop: 0 }}>Where the money goes</h3>
          {allocData.length === 0 ? <Empty text="No allocations yet." /> : (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={allocData} dataKey="value" nameKey="name" innerRadius={62} outerRadius={100} paddingAngle={2}>
                  {allocData.map((d, i) => (
                    <Cell key={i} fill={d.rest ? c.primary : PALETTE[i % PALETTE.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(val: number) => `$${val.toLocaleString()}`}
                  contentStyle={{ background: c.surface, border: `1px solid ${c.border}`, borderRadius: 10 }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="card" style={{ padding: 18 }}>
          <h3 style={{ marginTop: 0 }}>Debt payoff projection</h3>
          {snowData.length < 2 ? <Empty text="Add debts to see the snowball." /> : (
            <ResponsiveContainer width="100%" height={260}>
              <AreaChart data={snowData}>
                <defs>
                  <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={c.primary} stopOpacity={0.5} />
                    <stop offset="100%" stopColor={c.primary} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="m" tick={{ fontSize: 11, fill: c.textDim }} tickFormatter={(m) => `${m}mo`} />
                <YAxis tick={{ fontSize: 11, fill: c.textDim }} tickFormatter={(val) => fmtCentsShort(val * 100)} width={48} />
                <Tooltip formatter={(val: number) => fmtCents(val * 100)}
                  contentStyle={{ background: c.surface, border: `1px solid ${c.border}`, borderRadius: 10 }} />
                <Area type="monotone" dataKey="bal" stroke={c.primary} fill="url(#g)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          )}
          {data.next_target && <p className="muted" style={{ marginBottom: 0 }}>Next target: <strong>{data.next_target}</strong></p>}
        </div>
      </div>

      {/* paychecks */}
      <div className="card" style={{ padding: 18 }}>
        <h3 style={{ marginTop: 0 }}>Paychecks &amp; funded bills</h3>
        {v.paychecks.length === 0 ? <Empty text="No paychecks land this month." /> : (
          <div style={{ display: "grid", gap: 12 }}>
            {v.paychecks.map((p: any) => (
              <div key={p.key} style={{ borderLeft: `3px solid ${p.color}`, paddingLeft: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 6 }}>
                  <strong>{p.earner_name} · {p.source_name}{p.is_extra ? " · 3rd ✨" : ""}</strong>
                  <span>{fmtCents(p.amount_cents)} <span className="muted">({p.date})</span></span>
                </div>
                {p.bills.length > 0 && (
                  <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>
                    {p.bills.map((b: any) => `${b.name} ${fmtCents(b.amount_cents)}`).join(" · ")}
                  </div>
                )}
                <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
                  funded {fmtCents(p.assigned)} · leftover {fmtCents(p.remaining)}
                </div>
              </div>
            ))}
            {v.unassigned.length > 0 && (
              <div style={{ borderLeft: "3px solid var(--danger)", paddingLeft: 12 }}>
                <strong style={{ color: "var(--danger)" }}>Unfunded</strong>
                <div className="muted" style={{ fontSize: 13 }}>
                  {v.unassigned.map((b: any) => `${b.name} ${fmtCents(b.amount_cents)}`).join(" · ")}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
