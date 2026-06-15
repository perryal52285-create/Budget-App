import { useQuery } from "@tanstack/react-query";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend,
  AreaChart, Area, CartesianGrid,
} from "recharts";
import { apiGet } from "../api";
import { fmtCents, fmtCentsShort } from "../format";
import { useChartColors } from "../theme";
import { Empty, ProgressBar } from "../ui";

type Data = {
  cashflow: { label: string; income_cents: number; bills_cents: number; net_cents: number }[];
  category: { category: string; amount_cents: number }[];
  net_worth: { date: string; net_cents: number }[];
  snowball: number[];
  label: string;
};

export default function Reports() {
  const { data, isLoading } = useQuery({ queryKey: ["reports"], queryFn: () => apiGet<Data>("/reports?months=12") });
  const c = useChartColors();
  const tip = { background: c.surface, border: `1px solid ${c.border}`, borderRadius: 10 };
  if (isLoading || !data) return <p className="muted">Loading…</p>;

  const cf = data.cashflow.map((c) => ({
    label: c.label, Income: c.income_cents / 100, Bills: c.bills_cents / 100, Net: c.net_cents / 100,
  }));
  const nw = data.net_worth.map((s) => ({ date: s.date.slice(5), net: s.net_cents / 100 }));
  const maxCat = Math.max(1, ...data.category.map((c) => c.amount_cents));

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <h2 style={{ margin: 0 }}>Reports</h2>

      <div className="card" style={{ padding: 18 }}>
        <h3 style={{ marginTop: 0 }}>Cash flow — last 12 months</h3>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={cf}>
            <CartesianGrid strokeDasharray="3 3" stroke={c.border} vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 10, fill: c.textDim }} />
            <YAxis tick={{ fontSize: 11, fill: c.textDim }} tickFormatter={(val) => fmtCentsShort(val * 100)} width={48} />
            <Tooltip formatter={(v: number) => fmtCents(v * 100)} contentStyle={tip} />
            <Legend />
            <Bar dataKey="Income" fill={c.primary} radius={[4, 4, 0, 0]} />
            <Bar dataKey="Bills" fill={c.danger} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))" }}>
        <div className="card" style={{ padding: 18 }}>
          <h3 style={{ marginTop: 0 }}>Spending by category · {data.label}</h3>
          {data.category.length === 0 ? <Empty text="No spending this month." /> : (
            <div style={{ display: "grid", gap: 10 }}>
              {data.category.slice(0, 10).map((c) => (
                <div key={c.category}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 4 }}>
                    <span>{c.category}</span><strong>{fmtCents(c.amount_cents)}</strong>
                  </div>
                  <ProgressBar pct={(c.amount_cents / maxCat) * 100} />
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card" style={{ padding: 18 }}>
          <h3 style={{ marginTop: 0 }}>Net worth trend</h3>
          {nw.length < 2 ? <Empty text="Record account balances over time to chart net worth." /> : (
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={nw}>
                <defs><linearGradient id="rnw" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={c.primary} stopOpacity={0.5} />
                  <stop offset="100%" stopColor={c.primary} stopOpacity={0} />
                </linearGradient></defs>
                <XAxis dataKey="date" tick={{ fontSize: 11, fill: c.textDim }} />
                <YAxis tick={{ fontSize: 11, fill: c.textDim }} tickFormatter={(val) => fmtCentsShort(val * 100)} width={48} />
                <Tooltip formatter={(v: number) => fmtCents(v * 100)} contentStyle={tip} />
                <Area type="monotone" dataKey="net" stroke={c.primary} fill="url(#rnw)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
}
