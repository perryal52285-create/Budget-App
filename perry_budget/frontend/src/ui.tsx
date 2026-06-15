import type { ReactNode } from "react";

export function Modal({ title, onClose, children, footer }: {
  title: string; onClose: () => void; children: ReactNode; footer?: ReactNode;
}) {
  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, zIndex: 60, background: "rgba(0,0,0,0.5)",
      display: "grid", placeItems: "center", padding: 16,
    }}>
      <div className="card" onClick={(e) => e.stopPropagation()} style={{
        width: "100%", maxWidth: 460, maxHeight: "90dvh", overflow: "auto", padding: 22,
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
          <h3 style={{ margin: 0 }}>{title}</h3>
          <button className="btn btn-ghost" onClick={onClose} style={{ padding: "0.25rem 0.55rem" }}>✕</button>
        </div>
        {children}
        {footer && <div style={{ display: "flex", gap: 8, marginTop: 18 }}>{footer}</div>}
      </div>
    </div>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <label className="label">{label}</label>
      {children}
    </div>
  );
}

export function Row({ children, gap = 10 }: { children: ReactNode; gap?: number }) {
  return <div style={{ display: "flex", gap, flexWrap: "wrap" }}>{children}</div>;
}

export function Empty({ text }: { text: string }) {
  return <div className="card" style={{ padding: 24, textAlign: "center" }}><span className="muted">{text}</span></div>;
}

export function ProgressBar({ pct, over }: { pct: number; over?: boolean }) {
  return (
    <div style={{ height: 8, borderRadius: 999, background: "var(--surface-2)", overflow: "hidden" }}>
      <div style={{
        width: `${Math.min(100, Math.max(0, pct))}%`, height: "100%",
        background: over ? "var(--danger)" : "var(--primary)", transition: "width .3s ease",
      }} />
    </div>
  );
}
