export default function Placeholder({ title, note }: { title: string; note: string }) {
  return (
    <div style={{ display: "grid", gap: 16 }}>
      <h2 style={{ margin: 0 }}>{title}</h2>
      <div className="card" style={{ padding: 18 }}>
        <p className="muted" style={{ margin: 0 }}>{note}</p>
      </div>
    </div>
  );
}
