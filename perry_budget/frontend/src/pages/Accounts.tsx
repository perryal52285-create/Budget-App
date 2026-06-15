import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip } from "recharts";
import { apiGet, apiPost, apiDelete } from "../api";
import { fmtCents, fmtCentsShort, dollarsToCents, centsToInput } from "../format";
import { useChartColors } from "../theme";
import { Modal, Field, Empty } from "../ui";

type Account = {
  id: number; name: string; kind: string; is_liability: number; institution: string;
  balance_cents: number; as_of: string | null;
};
type Data = {
  summary: { assets_cents: number; liabilities_cents: number; net_cents: number; accounts: Account[] };
  series: { date: string; net_cents: number }[];
  kinds: string[];
};

export default function Accounts() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["accounts"], queryFn: () => apiGet<Data>("/accounts") });
  const c = useChartColors();
  const [addOpen, setAddOpen] = useState(false);
  const [balFor, setBalFor] = useState<Account | null>(null);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["accounts"] });
  const del = useMutation({ mutationFn: (id: number) => apiDelete(`/accounts/${id}`), onSuccess: invalidate });

  if (isLoading || !data) return <p className="muted">Loading…</p>;
  const { summary, series, kinds } = data;
  const assets = summary.accounts.filter((a) => !a.is_liability);
  const liabs = summary.accounts.filter((a) => a.is_liability);
  const chart = series.map((s) => ({ date: s.date.slice(5), net: s.net_cents / 100 }));

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>Net Worth</h2>
        <button className="btn btn-primary" onClick={() => setAddOpen(true)}>+ Account</button>
      </div>

      <div className="grid-cards">
        <div className="card stat"><div className="k">Net worth</div><div className="v">{fmtCents(summary.net_cents)}</div></div>
        <div className="card stat"><div className="k">Assets</div><div className="v" style={{ color: "var(--primary)" }}>{fmtCents(summary.assets_cents)}</div></div>
        <div className="card stat"><div className="k">Liabilities</div><div className="v" style={{ color: "var(--danger)" }}>{fmtCents(summary.liabilities_cents)}</div></div>
      </div>

      <div className="card" style={{ padding: 18 }}>
        <h3 style={{ marginTop: 0 }}>Net worth over time</h3>
        {chart.length < 2 ? <Empty text="Record balances on a couple of dates to chart your trend." /> : (
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={chart}>
              <defs><linearGradient id="nw" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={c.primary} stopOpacity={0.5} />
                <stop offset="100%" stopColor={c.primary} stopOpacity={0} />
              </linearGradient></defs>
              <XAxis dataKey="date" tick={{ fontSize: 11, fill: c.textDim }} />
              <YAxis tick={{ fontSize: 11, fill: c.textDim }} tickFormatter={(val) => fmtCentsShort(val * 100)} width={48} />
              <Tooltip formatter={(v: number) => fmtCents(v * 100)}
                contentStyle={{ background: c.surface, border: `1px solid ${c.border}`, borderRadius: 10 }} />
              <Area type="monotone" dataKey="net" stroke={c.primary} fill="url(#nw)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>

      {[["Assets", assets], ["Liabilities", liabs]].map(([title, list]) => (
        <div key={title as string} className="card" style={{ padding: 18 }}>
          <h3 style={{ marginTop: 0 }}>{title as string}</h3>
          {(list as Account[]).length === 0 ? <span className="muted">None yet.</span> : (
            <div style={{ display: "grid", gap: 8 }}>
              {(list as Account[]).map((a) => (
                <div key={a.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                  <div>
                    <strong>{a.name}</strong> <span className="chip">{a.kind}</span>
                    {a.institution && <span className="muted" style={{ fontSize: 12 }}> · {a.institution}</span>}
                    <div className="muted" style={{ fontSize: 12 }}>{a.as_of ? `as of ${a.as_of}` : "no balance yet"}</div>
                  </div>
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <strong style={{ color: a.is_liability ? "var(--danger)" : "var(--text)" }}>{fmtCents(a.balance_cents)}</strong>
                    <button className="btn btn-ghost" onClick={() => setBalFor(a)} style={{ padding: "0.3rem 0.6rem" }}>Update</button>
                    <button className="btn btn-ghost" onClick={() => confirm(`Delete ${a.name}?`) && del.mutate(a.id)} style={{ padding: "0.3rem 0.5rem" }}>🗑</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}

      {addOpen && <AddAccount kinds={kinds} onClose={() => setAddOpen(false)} onSaved={invalidate} />}
      {balFor && <UpdateBalance account={balFor} onClose={() => setBalFor(null)} onSaved={invalidate} />}
    </div>
  );
}

function AddAccount({ kinds, onClose, onSaved }: { kinds: string[]; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState("");
  const [kind, setKind] = useState("checking");
  const [inst, setInst] = useState("");
  const [liab, setLiab] = useState(false);
  const m = useMutation({
    mutationFn: () => apiPost("/accounts", { name, kind, institution: inst, is_liability: liab ? 1 : 0 }),
    onSuccess: () => { onSaved(); onClose(); },
  });
  return (
    <Modal title="Add account" onClose={onClose} footer={
      <button className="btn btn-primary" disabled={!name || m.isPending} onClick={() => m.mutate()} style={{ flex: 1 }}>
        {m.isPending ? "Saving…" : "Add"}
      </button>}>
      <Field label="Name"><input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Checking" /></Field>
      <Field label="Type">
        <select className="input" value={kind} onChange={(e) => setKind(e.target.value)}>
          {kinds.map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
      </Field>
      <Field label="Institution (optional)"><input className="input" value={inst} onChange={(e) => setInst(e.target.value)} /></Field>
      <label className="chip" style={{ cursor: "pointer" }}>
        <input type="checkbox" checked={liab} onChange={(e) => setLiab(e.target.checked)} /> This is a liability (debt)
      </label>
    </Modal>
  );
}

function UpdateBalance({ account, onClose, onSaved }: { account: Account; onClose: () => void; onSaved: () => void }) {
  const [amt, setAmt] = useState(centsToInput(account.balance_cents));
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const m = useMutation({
    mutationFn: () => apiPost(`/accounts/${account.id}/balance`, { as_of: date, balance_cents: dollarsToCents(amt) }),
    onSuccess: () => { onSaved(); onClose(); },
  });
  return (
    <Modal title={`Update ${account.name}`} onClose={onClose} footer={
      <button className="btn btn-primary" disabled={m.isPending} onClick={() => m.mutate()} style={{ flex: 1 }}>
        {m.isPending ? "Saving…" : "Save balance"}
      </button>}>
      <Field label="Balance"><input className="input" inputMode="decimal" value={amt} onChange={(e) => setAmt(e.target.value)} /></Field>
      <Field label="As of"><input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
    </Modal>
  );
}
