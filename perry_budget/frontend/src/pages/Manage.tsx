import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiDelete, api } from "../api";
import { fmtCents, dollarsToCents, centsToInput, MONTHS } from "../format";
import { Modal, Field, Row, Empty } from "../ui";

type Earner = { id: number; name: string; color: string; is_primary: number };
type Source = { id: number; earner_id: number; name: string; employer: string; kind: string; amount_cents: number; frequency: string; anchor_date: string; day1: number; day2: number; month: number; active: number; notes: string; preview: string[] };
type Bill = { id: number; name: string; amount_cents: number; due_dom: number; category: string; autopay: number; where_to_pay: string; responsible_earner_id: number | null; funding_mode: string; funding_source_id: number | null; funding_occurrence: number | null };
type Debt = { id: number; name: string; balance_cents: number; min_payment_cents: number; apr: number; roll_order: number };
type Data = {
  earners: Earner[]; sources: Source[]; bills: Bill[]; debts: Debt[];
  frequencies: string[]; kinds: string[]; ha_available: boolean;
  settings: { timezone: string; sensors_enabled: boolean; notify_service: string; alert_days_ahead: number };
};

const put = (path: string, body: unknown) => api(path, { method: "PUT", body: JSON.stringify(body) });

export default function Manage() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["manage"], queryFn: () => apiGet<Data>("/manage") });
  const inv = () => qc.invalidateQueries({ queryKey: ["manage"] });
  const [modal, setModal] = useState<null | { type: string; item?: any }>(null);
  const del = useMutation({ mutationFn: (p: string) => apiDelete(p), onSuccess: inv });

  if (isLoading || !data) return <p className="muted">Loading…</p>;
  const earnerName = (id: number | null) => data.earners.find((e) => e.id === id)?.name ?? "joint";

  return (
    <div style={{ display: "grid", gap: 20 }}>
      <h2 style={{ margin: 0 }}>Manage</h2>

      {/* Earners */}
      <Section title="Earners" onAdd={() => setModal({ type: "earner" })}>
        {data.earners.map((e) => (
          <RowItem key={e.id} onEdit={() => setModal({ type: "earner", item: e })}
            onDelete={() => confirm(`Delete ${e.name}?`) && del.mutate(`/earners/${e.id}`)}>
            <span style={{ display: "inline-block", width: 12, height: 12, borderRadius: 3, background: e.color, marginRight: 8 }} />
            <strong>{e.name}</strong>{e.is_primary ? <span className="chip" style={{ marginLeft: 8 }}>primary</span> : null}
          </RowItem>
        ))}
      </Section>

      {/* Income */}
      <Section title="Income sources" onAdd={() => setModal({ type: "income" })}>
        {data.sources.length === 0 ? <Empty text="No income sources." /> : data.sources.map((s) => (
          <RowItem key={s.id} onEdit={() => setModal({ type: "income", item: s })}
            onDelete={() => confirm(`Delete ${s.name}?`) && del.mutate(`/income/${s.id}`)}>
            <strong>{s.name}</strong> <span className="chip">{s.kind}</span> <span className="chip">{s.frequency}</span>
            <span className="muted"> · {earnerName(s.earner_id)} · {fmtCents(s.amount_cents)}{s.active ? "" : " · inactive"}</span>
            {s.preview?.length > 0 && <div className="muted" style={{ fontSize: 12 }}>next: {s.preview.slice(0, 3).join(", ")}</div>}
          </RowItem>
        ))}
      </Section>

      {/* Bills */}
      <Section title="Bills" onAdd={() => setModal({ type: "bill" })}>
        {data.bills.length === 0 ? <Empty text="No bills." /> : data.bills.map((b) => (
          <RowItem key={b.id} onEdit={() => setModal({ type: "bill", item: b })}
            onDelete={() => confirm(`Delete ${b.name}?`) && del.mutate(`/bills/${b.id}`)}>
            <strong>{b.name}</strong> <span className="muted">· {fmtCents(b.amount_cents)} · due {b.due_dom} · {earnerName(b.responsible_earner_id)}</span>
            {b.category && <span className="chip" style={{ marginLeft: 6 }}>{b.category}</span>}
            {b.autopay ? <span className="chip" style={{ marginLeft: 6 }}>autopay</span> : null}
          </RowItem>
        ))}
      </Section>

      {/* Debts */}
      <Section title="Debts (snowball order)" onAdd={() => setModal({ type: "debt" })}>
        {data.debts.length === 0 ? <Empty text="No debts. 🎉" /> : data.debts.map((d) => (
          <RowItem key={d.id} onEdit={() => setModal({ type: "debt", item: d })}
            onDelete={() => confirm(`Delete ${d.name}?`) && del.mutate(`/debts/${d.id}`)}>
            <span className="chip">#{d.roll_order}</span> <strong style={{ marginLeft: 6 }}>{d.name}</strong>
            <span className="muted"> · {fmtCents(d.balance_cents)} · min {fmtCents(d.min_payment_cents)} · {d.apr}% APR</span>
          </RowItem>
        ))}
      </Section>

      {/* Settings */}
      <SettingsCard data={data} onSaved={inv} />

      {modal?.type === "earner" && <EarnerModal item={modal.item} onClose={() => setModal(null)} onSaved={inv} />}
      {modal?.type === "income" && <IncomeModal item={modal.item} data={data} onClose={() => setModal(null)} onSaved={inv} />}
      {modal?.type === "bill" && <BillModal item={modal.item} data={data} onClose={() => setModal(null)} onSaved={inv} />}
      {modal?.type === "debt" && <DebtModal item={modal.item} onClose={() => setModal(null)} onSaved={inv} />}
    </div>
  );

  function SettingsCard({ data, onSaved }: { data: Data; onSaved: () => void }) {
    const [tz, setTz] = useState(data.settings.timezone);
    const [sensors, setSensors] = useState(data.settings.sensors_enabled);
    const [notify, setNotify] = useState(data.settings.notify_service);
    const [ahead, setAhead] = useState(String(data.settings.alert_days_ahead));
    const save = useMutation({
      mutationFn: () => put("/settings", { timezone: tz, sensors_enabled: sensors ? 1 : 0, notify_service: notify, alert_days_ahead: parseInt(ahead) || 3 }),
      onSuccess: onSaved,
    });
    const test = useMutation({ mutationFn: () => apiPost("/alerts/test") });
    return (
      <div className="card" style={{ padding: 18 }}>
        <h3 style={{ marginTop: 0 }}>Settings</h3>
        <Row>
          <div style={{ flex: 1, minWidth: 160 }}><Field label="Timezone"><input className="input" value={tz} onChange={(e) => setTz(e.target.value)} /></Field></div>
          <div style={{ flex: 1, minWidth: 160 }}><Field label="Notify service"><input className="input" value={notify} onChange={(e) => setNotify(e.target.value)} /></Field></div>
          <div style={{ width: 140 }}><Field label="Alert days ahead"><input className="input" inputMode="numeric" value={ahead} onChange={(e) => setAhead(e.target.value)} /></Field></div>
        </Row>
        <label className="chip" style={{ cursor: "pointer" }}>
          <input type="checkbox" checked={sensors} onChange={(e) => setSensors(e.target.checked)} /> Export HA sensors
        </label>
        <span className="muted" style={{ fontSize: 12, marginLeft: 10 }}>HA link: {data.ha_available ? "available ✓" : "unavailable"}</span>
        <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
          <button className="btn btn-primary" onClick={() => save.mutate()} disabled={save.isPending}>Save settings</button>
          <button className="btn btn-ghost" onClick={() => test.mutate()} disabled={test.isPending}>
            {test.isSuccess ? "Sent ✓" : "Test HA alert"}
          </button>
        </div>
      </div>
    );
  }
}

function Section({ title, onAdd, children }: { title: string; onAdd: () => void; children: React.ReactNode }) {
  return (
    <div className="card" style={{ padding: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h3 style={{ margin: 0 }}>{title}</h3>
        <button className="btn btn-primary" onClick={onAdd} style={{ padding: "0.4rem 0.8rem" }}>+ Add</button>
      </div>
      <div style={{ display: "grid", gap: 8 }}>{children}</div>
    </div>
  );
}

function RowItem({ children, onEdit, onDelete }: { children: React.ReactNode; onEdit: () => void; onDelete: () => void }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
      <div style={{ minWidth: 0 }}>{children}</div>
      <div style={{ display: "flex", gap: 6 }}>
        <button className="btn btn-ghost" onClick={onEdit} style={{ padding: "0.3rem 0.6rem" }}>Edit</button>
        <button className="btn btn-ghost" onClick={onDelete} style={{ padding: "0.3rem 0.5rem" }}>🗑</button>
      </div>
    </div>
  );
}

function saveMutation(item: any, base: string, body: () => unknown, onDone: () => void) {
  return useMutation({
    mutationFn: () => (item ? put(`${base}/${item.id}`, body()) : apiPost(base, body())),
    onSuccess: onDone,
  });
}

function EarnerModal({ item, onClose, onSaved }: any) {
  const [name, setName] = useState(item?.name ?? "");
  const [color, setColor] = useState(item?.color ?? "#46d970");
  const m = saveMutation(item, "/earners", () => ({ name, color, is_primary: item?.is_primary ?? 0 }), () => { onSaved(); onClose(); });
  return (
    <Modal title={item ? "Edit earner" : "Add earner"} onClose={onClose}
      footer={<button className="btn btn-primary" disabled={!name || m.isPending} onClick={() => m.mutate()} style={{ flex: 1 }}>Save</button>}>
      <Field label="Name"><input className="input" value={name} onChange={(e) => setName(e.target.value)} /></Field>
      <Field label="Color"><input className="input" type="color" value={color} onChange={(e) => setColor(e.target.value)} style={{ height: 44 }} /></Field>
    </Modal>
  );
}

function IncomeModal({ item, data, onClose, onSaved }: any) {
  const [f, setF] = useState({
    earner_id: item?.earner_id ?? data.earners[0]?.id ?? 1, name: item?.name ?? "", employer: item?.employer ?? "",
    kind: item?.kind ?? "payroll", amount: centsToInput(item?.amount_cents ?? 0), frequency: item?.frequency ?? "biweekly",
    anchor_date: item?.anchor_date ?? "", day1: String(item?.day1 ?? 1), day2: String(item?.day2 ?? 0),
    month: String(item?.month ?? 1), active: item?.active ?? 1, notes: item?.notes ?? "",
  });
  const up = (k: string, v: any) => setF((p) => ({ ...p, [k]: v }));
  const m = saveMutation(item, "/income", () => ({
    earner_id: Number(f.earner_id), name: f.name, employer: f.employer, kind: f.kind,
    amount_cents: dollarsToCents(f.amount), frequency: f.frequency, anchor_date: f.anchor_date,
    day1: Number(f.day1), day2: Number(f.day2), month: Number(f.month), active: f.active ? 1 : 0, notes: f.notes,
  }), () => { onSaved(); onClose(); });
  const needsAnchor = ["weekly", "biweekly", "one_time"].includes(f.frequency);
  const needsDays = ["semimonthly", "monthly", "annual"].includes(f.frequency);
  return (
    <Modal title={item ? "Edit income" : "Add income"} onClose={onClose}
      footer={<button className="btn btn-primary" disabled={!f.name || m.isPending} onClick={() => m.mutate()} style={{ flex: 1 }}>Save</button>}>
      <Field label="Name"><input className="input" value={f.name} onChange={(e) => up("name", e.target.value)} /></Field>
      <Row>
        <div style={{ flex: 1 }}><Field label="Earner"><select className="input" value={f.earner_id} onChange={(e) => up("earner_id", e.target.value)}>{data.earners.map((e: Earner) => <option key={e.id} value={e.id}>{e.name}</option>)}</select></Field></div>
        <div style={{ flex: 1 }}><Field label="Kind"><select className="input" value={f.kind} onChange={(e) => up("kind", e.target.value)}>{data.kinds.map((k: string) => <option key={k}>{k}</option>)}</select></Field></div>
      </Row>
      <Field label="Employer"><input className="input" value={f.employer} onChange={(e) => up("employer", e.target.value)} /></Field>
      <Row>
        <div style={{ flex: 1 }}><Field label="Amount"><input className="input" inputMode="decimal" value={f.amount} onChange={(e) => up("amount", e.target.value)} /></Field></div>
        <div style={{ flex: 1 }}><Field label="Frequency"><select className="input" value={f.frequency} onChange={(e) => up("frequency", e.target.value)}>{data.frequencies.map((x: string) => <option key={x}>{x}</option>)}</select></Field></div>
      </Row>
      {needsAnchor && <Field label="Anchor / date"><input className="input" type="date" value={f.anchor_date} onChange={(e) => up("anchor_date", e.target.value)} /></Field>}
      {needsDays && (
        <Row>
          <div style={{ flex: 1 }}><Field label="Day 1 (0=last)"><input className="input" inputMode="numeric" value={f.day1} onChange={(e) => up("day1", e.target.value)} /></Field></div>
          {f.frequency === "semimonthly" && <div style={{ flex: 1 }}><Field label="Day 2"><input className="input" inputMode="numeric" value={f.day2} onChange={(e) => up("day2", e.target.value)} /></Field></div>}
          {f.frequency === "annual" && <div style={{ flex: 1 }}><Field label="Month"><select className="input" value={f.month} onChange={(e) => up("month", e.target.value)}>{MONTHS.slice(1).map((mn, i) => <option key={mn} value={i + 1}>{mn}</option>)}</select></Field></div>}
        </Row>
      )}
      <label className="chip" style={{ cursor: "pointer" }}><input type="checkbox" checked={!!f.active} onChange={(e) => up("active", e.target.checked ? 1 : 0)} /> Active</label>
    </Modal>
  );
}

function BillModal({ item, data, onClose, onSaved }: any) {
  const [f, setF] = useState({
    name: item?.name ?? "", amount: centsToInput(item?.amount_cents ?? 0), due_dom: String(item?.due_dom ?? 1),
    category: item?.category ?? "", autopay: item?.autopay ?? 0, where_to_pay: item?.where_to_pay ?? "",
    responsible_earner_id: item?.responsible_earner_id ?? "", funding_mode: item?.funding_mode ?? "auto",
    funding_source_id: item?.funding_source_id ?? "", funding_occurrence: item?.funding_occurrence ?? "",
  });
  const up = (k: string, v: any) => setF((p) => ({ ...p, [k]: v }));
  const m = saveMutation(item, "/bills", () => ({
    name: f.name, amount_cents: dollarsToCents(f.amount), due_dom: Number(f.due_dom), category: f.category,
    autopay: f.autopay ? 1 : 0, where_to_pay: f.where_to_pay,
    responsible_earner_id: f.responsible_earner_id ? Number(f.responsible_earner_id) : null,
    funding_mode: f.funding_mode, funding_source_id: f.funding_source_id ? Number(f.funding_source_id) : null,
    funding_occurrence: f.funding_occurrence ? Number(f.funding_occurrence) : null,
  }), () => { onSaved(); onClose(); });
  return (
    <Modal title={item ? "Edit bill" : "Add bill"} onClose={onClose}
      footer={<button className="btn btn-primary" disabled={!f.name || m.isPending} onClick={() => m.mutate()} style={{ flex: 1 }}>Save</button>}>
      <Field label="Name"><input className="input" value={f.name} onChange={(e) => up("name", e.target.value)} /></Field>
      <Row>
        <div style={{ flex: 1 }}><Field label="Amount"><input className="input" inputMode="decimal" value={f.amount} onChange={(e) => up("amount", e.target.value)} /></Field></div>
        <div style={{ width: 110 }}><Field label="Due day"><input className="input" inputMode="numeric" value={f.due_dom} onChange={(e) => up("due_dom", e.target.value)} /></Field></div>
      </Row>
      <Row>
        <div style={{ flex: 1 }}><Field label="Category"><input className="input" value={f.category} onChange={(e) => up("category", e.target.value)} /></Field></div>
        <div style={{ flex: 1 }}><Field label="Responsible"><select className="input" value={f.responsible_earner_id} onChange={(e) => up("responsible_earner_id", e.target.value)}><option value="">joint</option>{data.earners.map((e: Earner) => <option key={e.id} value={e.id}>{e.name}</option>)}</select></Field></div>
      </Row>
      <Field label="Funding"><select className="input" value={f.funding_mode} onChange={(e) => up("funding_mode", e.target.value)}><option value="auto">auto (latest check before due)</option><option value="manual">manual (pin to a source)</option></select></Field>
      {f.funding_mode === "manual" && (
        <Row>
          <div style={{ flex: 1 }}><Field label="Source"><select className="input" value={f.funding_source_id} onChange={(e) => up("funding_source_id", e.target.value)}><option value="">—</option>{data.sources.map((s: Source) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></Field></div>
          <div style={{ width: 120 }}><Field label="Occurrence"><input className="input" inputMode="numeric" value={f.funding_occurrence} onChange={(e) => up("funding_occurrence", e.target.value)} /></Field></div>
        </Row>
      )}
      <label className="chip" style={{ cursor: "pointer" }}><input type="checkbox" checked={!!f.autopay} onChange={(e) => up("autopay", e.target.checked ? 1 : 0)} /> Autopay</label>
    </Modal>
  );
}

function DebtModal({ item, onClose, onSaved }: any) {
  const [f, setF] = useState({
    name: item?.name ?? "", balance: centsToInput(item?.balance_cents ?? 0),
    min_payment: centsToInput(item?.min_payment_cents ?? 0), apr: String(item?.apr ?? 0), roll_order: String(item?.roll_order ?? 0),
  });
  const up = (k: string, v: any) => setF((p) => ({ ...p, [k]: v }));
  const m = saveMutation(item, "/debts", () => ({
    name: f.name, balance_cents: dollarsToCents(f.balance), min_payment_cents: dollarsToCents(f.min_payment),
    apr: parseFloat(f.apr) || 0, roll_order: Number(f.roll_order),
  }), () => { onSaved(); onClose(); });
  return (
    <Modal title={item ? "Edit debt" : "Add debt"} onClose={onClose}
      footer={<button className="btn btn-primary" disabled={!f.name || m.isPending} onClick={() => m.mutate()} style={{ flex: 1 }}>Save</button>}>
      <Field label="Name"><input className="input" value={f.name} onChange={(e) => up("name", e.target.value)} /></Field>
      <Row>
        <div style={{ flex: 1 }}><Field label="Balance"><input className="input" inputMode="decimal" value={f.balance} onChange={(e) => up("balance", e.target.value)} /></Field></div>
        <div style={{ flex: 1 }}><Field label="Min payment"><input className="input" inputMode="decimal" value={f.min_payment} onChange={(e) => up("min_payment", e.target.value)} /></Field></div>
      </Row>
      <Row>
        <div style={{ flex: 1 }}><Field label="APR %"><input className="input" inputMode="decimal" value={f.apr} onChange={(e) => up("apr", e.target.value)} /></Field></div>
        <div style={{ width: 130 }}><Field label="Snowball order"><input className="input" inputMode="numeric" value={f.roll_order} onChange={(e) => up("roll_order", e.target.value)} /></Field></div>
      </Row>
    </Modal>
  );
}
