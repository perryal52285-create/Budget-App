import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiDelete, api } from "../api";
import { fmtCents, dollarsToCents, centsToInput } from "../format";
import { Modal, Field, Empty, ProgressBar } from "../ui";

type Goal = { id: number; name: string; target_cents: number; current_cents: number; target_date: string; pct: number };

export default function Goals() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["goals"], queryFn: () => apiGet<{ goals: Goal[] }>("/goals") });
  const [edit, setEdit] = useState<Goal | "new" | null>(null);
  const invalidate = () => qc.invalidateQueries({ queryKey: ["goals"] });
  const del = useMutation({ mutationFn: (id: number) => apiDelete(`/goals/${id}`), onSuccess: invalidate });

  if (isLoading || !data) return <p className="muted">Loading…</p>;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <h2 style={{ margin: 0 }}>Goals &amp; Sinking Funds</h2>
          <p className="muted" style={{ margin: "4px 0 0" }}>For the January bonus, the 3rd-paycheck surplus, and savings targets.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setEdit("new")}>+ Goal</button>
      </div>

      {data.goals.length === 0 ? <Empty text="No goals yet. Add a sinking fund to start stashing." /> : (
        <div className="grid-cards">
          {data.goals.map((g) => (
            <div key={g.id} className="card" style={{ padding: 18 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
                <strong style={{ fontSize: 16 }}>{g.name}</strong>
                <span className="chip">{g.pct}%</span>
              </div>
              <div style={{ margin: "12px 0 8px" }}><ProgressBar pct={g.pct} /></div>
              <div className="muted" style={{ fontSize: 13 }}>{fmtCents(g.current_cents)} of {fmtCents(g.target_cents)}</div>
              {g.target_date && <div className="muted" style={{ fontSize: 12 }}>by {g.target_date}</div>}
              <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                <button className="btn btn-ghost" onClick={() => setEdit(g)} style={{ flex: 1 }}>Edit</button>
                <button className="btn btn-ghost" onClick={() => confirm(`Delete ${g.name}?`) && del.mutate(g.id)}>🗑</button>
              </div>
            </div>
          ))}
        </div>
      )}

      {edit && <EditGoal goal={edit === "new" ? null : edit} onClose={() => setEdit(null)} onSaved={invalidate} />}
    </div>
  );
}

function EditGoal({ goal, onClose, onSaved }: { goal: Goal | null; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState(goal?.name ?? "");
  const [target, setTarget] = useState(centsToInput(goal?.target_cents ?? 0));
  const [current, setCurrent] = useState(centsToInput(goal?.current_cents ?? 0));
  const [date, setDate] = useState(goal?.target_date ?? "");
  const m = useMutation({
    mutationFn: () => {
      const body = { name, target_cents: dollarsToCents(target), current_cents: dollarsToCents(current), target_date: date };
      return goal ? api(`/goals/${goal.id}`, { method: "PUT", body: JSON.stringify(body) }) : apiPost("/goals", body);
    },
    onSuccess: () => { onSaved(); onClose(); },
  });
  return (
    <Modal title={goal ? "Edit goal" : "New goal"} onClose={onClose} footer={
      <button className="btn btn-primary" disabled={!name || m.isPending} onClick={() => m.mutate()} style={{ flex: 1 }}>
        {m.isPending ? "Saving…" : "Save"}
      </button>}>
      <Field label="Name"><input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="Christmas fund" /></Field>
      <Field label="Target amount"><input className="input" inputMode="decimal" value={target} onChange={(e) => setTarget(e.target.value)} /></Field>
      <Field label="Saved so far"><input className="input" inputMode="decimal" value={current} onChange={(e) => setCurrent(e.target.value)} /></Field>
      <Field label="Target date (optional)"><input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
    </Modal>
  );
}
