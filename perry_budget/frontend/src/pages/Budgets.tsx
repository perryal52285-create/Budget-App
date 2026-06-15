import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiDelete } from "../api";
import { fmtCents, dollarsToCents } from "../format";
import { Modal, Field, Empty, ProgressBar } from "../ui";

type Row = { id: number; category: string; limit_cents: number; spent_cents: number; remaining_cents: number; pct: number; over: boolean };
type Txn = { id: number; category: string; description: string; amount_cents: number; txn_date: string };
type Data = {
  year: number; month: number; label: string; rows: Row[];
  untracked: { category: string; spent_cents: number }[]; transactions: Txn[]; categories: string[];
};

export default function Budgets() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["budgets"], queryFn: () => apiGet<Data>("/budgets") });
  const [budgetOpen, setBudgetOpen] = useState(false);
  const [spendOpen, setSpendOpen] = useState(false);
  const invalidate = () => qc.invalidateQueries({ queryKey: ["budgets"] });
  const delBudget = useMutation({ mutationFn: (id: number) => apiDelete(`/budgets/${id}`), onSuccess: invalidate });
  const delTxn = useMutation({ mutationFn: (id: number) => apiDelete(`/transactions/${id}`), onSuccess: invalidate });

  if (isLoading || !data) return <p className="muted">Loading…</p>;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
        <h2 style={{ margin: 0 }}>Budgets · <span className="muted">{data.label}</span></h2>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="btn btn-ghost" onClick={() => setSpendOpen(true)}>+ Spend</button>
          <button className="btn btn-primary" onClick={() => setBudgetOpen(true)}>+ Budget</button>
        </div>
      </div>

      {data.rows.length === 0 ? <Empty text="No category budgets yet. Set one to track spending caps." /> : (
        <div className="grid-cards">
          {data.rows.map((r) => (
            <div key={r.id} className="card" style={{ padding: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <strong>{r.category}</strong>
                <button className="btn btn-ghost" onClick={() => confirm(`Delete budget for ${r.category}?`) && delBudget.mutate(r.id)} style={{ padding: "0 .4rem" }}>🗑</button>
              </div>
              <div style={{ margin: "10px 0 6px" }}><ProgressBar pct={r.pct} over={r.over} /></div>
              <div className="muted" style={{ fontSize: 13 }}>
                {fmtCents(r.spent_cents)} / {fmtCents(r.limit_cents)} ·{" "}
                <span style={{ color: r.over ? "var(--danger)" : "var(--primary)" }}>
                  {r.over ? `${fmtCents(-r.remaining_cents)} over` : `${fmtCents(r.remaining_cents)} left`}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {data.untracked.length > 0 && (
        <div className="card" style={{ padding: 16 }}>
          <h3 style={{ marginTop: 0, fontSize: 15 }}>Spending without a budget</h3>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {data.untracked.map((u) => <span key={u.category} className="chip">{u.category}: {fmtCents(u.spent_cents)}</span>)}
          </div>
        </div>
      )}

      <div className="card" style={{ padding: 16 }}>
        <h3 style={{ marginTop: 0, fontSize: 15 }}>Spending log</h3>
        {data.transactions.length === 0 ? <span className="muted">No transactions logged this month.</span> : (
          <div style={{ display: "grid", gap: 6 }}>
            {data.transactions.map((t) => (
              <div key={t.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: 14 }}>
                  <span className="chip">{t.category || "—"}</span> {t.description} <span className="muted" style={{ fontSize: 12 }}>{t.txn_date}</span>
                </span>
                <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <strong>{fmtCents(t.amount_cents)}</strong>
                  <button className="btn btn-ghost" onClick={() => delTxn.mutate(t.id)} style={{ padding: "0 .4rem" }}>✕</button>
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {budgetOpen && <SetBudget categories={data.categories} onClose={() => setBudgetOpen(false)} onSaved={invalidate} />}
      {spendOpen && <AddSpend categories={data.categories} onClose={() => setSpendOpen(false)} onSaved={invalidate} />}
    </div>
  );
}

function SetBudget({ categories, onClose, onSaved }: { categories: string[]; onClose: () => void; onSaved: () => void }) {
  const [category, setCategory] = useState(categories[0] ?? "");
  const [limit, setLimit] = useState("0.00");
  const m = useMutation({
    mutationFn: () => apiPost("/budgets", { category, monthly_limit_cents: dollarsToCents(limit) }),
    onSuccess: () => { onSaved(); onClose(); },
  });
  return (
    <Modal title="Set category budget" onClose={onClose} footer={
      <button className="btn btn-primary" disabled={!category || m.isPending} onClick={() => m.mutate()} style={{ flex: 1 }}>Save</button>}>
      <Field label="Category"><input className="input" list="cats" value={category} onChange={(e) => setCategory(e.target.value)} />
        <datalist id="cats">{categories.map((c) => <option key={c} value={c} />)}</datalist></Field>
      <Field label="Monthly limit"><input className="input" inputMode="decimal" value={limit} onChange={(e) => setLimit(e.target.value)} /></Field>
    </Modal>
  );
}

function AddSpend({ categories, onClose, onSaved }: { categories: string[]; onClose: () => void; onSaved: () => void }) {
  const [category, setCategory] = useState(categories[0] ?? "");
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");
  const [date, setDate] = useState(new Date().toISOString().slice(0, 10));
  const m = useMutation({
    mutationFn: () => apiPost("/transactions", { category, description, amount_cents: dollarsToCents(amount), txn_date: date }),
    onSuccess: () => { onSaved(); onClose(); },
  });
  return (
    <Modal title="Log spending" onClose={onClose} footer={
      <button className="btn btn-primary" disabled={!amount || m.isPending} onClick={() => m.mutate()} style={{ flex: 1 }}>Add</button>}>
      <Field label="Category"><input className="input" list="cats2" value={category} onChange={(e) => setCategory(e.target.value)} />
        <datalist id="cats2">{categories.map((c) => <option key={c} value={c} />)}</datalist></Field>
      <Field label="Description"><input className="input" value={description} onChange={(e) => setDescription(e.target.value)} /></Field>
      <Field label="Amount"><input className="input" inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} /></Field>
      <Field label="Date"><input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
    </Modal>
  );
}
