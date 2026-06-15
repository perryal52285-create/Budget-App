import { useEffect, useRef, useState } from "react";
import { apiPost } from "../api";

type Line = { kind: "in" | "out"; text: string };
const PROMPT = "perry//budget $";

export default function Terminal() {
  const [lines, setLines] = useState<Line[]>([]);
  const [input, setInput] = useState("");
  const [history, setHistory] = useState<string[]>([]);
  const [hIdx, setHIdx] = useState(-1);
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const run = async (raw: string) => {
    const line = raw.trim();
    if (!line) return;
    setLines((l) => [...l, { kind: "in", text: line }]);
    setHistory((h) => [...h, line]);
    setHIdx(-1);
    setBusy(true);
    try {
      const r = await apiPost<{ output: string }>("/term/exec", { line });
      setLines((l) => [...l, { kind: "out", text: r.output ?? "" }]);
    } catch (e) {
      setLines((l) => [...l, { kind: "out", text: `error: ${(e as Error).message}` }]);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { run("help"); /* eslint-disable-next-line */ }, []);
  useEffect(() => { endRef.current?.scrollIntoView(); }, [lines]);

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") { run(input); setInput(""); }
    else if (e.key === "ArrowUp") {
      e.preventDefault();
      const i = hIdx < 0 ? history.length - 1 : Math.max(0, hIdx - 1);
      if (history[i] !== undefined) { setHIdx(i); setInput(history[i]); }
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      const i = hIdx < 0 ? -1 : hIdx + 1;
      if (i >= history.length || i < 0) { setHIdx(-1); setInput(""); }
      else { setHIdx(i); setInput(history[i]); }
    }
  };

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <h2 style={{ margin: 0 }}>Terminal</h2>
      <div className="card" onClick={() => inputRef.current?.focus()} style={{
        padding: 16, fontFamily: "ui-monospace, Menlo, Consolas, monospace", fontSize: 13.5,
        minHeight: "60dvh", maxHeight: "72dvh", overflow: "auto", cursor: "text", lineHeight: 1.5,
      }}>
        {lines.map((l, i) => (
          <div key={i} style={{ whiteSpace: "pre-wrap", color: l.kind === "in" ? "var(--primary)" : "var(--text)" }}>
            {l.kind === "in" ? `${PROMPT} ${l.text}` : l.text}
          </div>
        ))}
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{ color: "var(--primary)" }}>{PROMPT}</span>
          <input
            ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onKey}
            autoFocus spellCheck={false} autoCapitalize="none" autoComplete="off"
            style={{
              flex: 1, background: "transparent", border: "none", outline: "none",
              color: "var(--text)", font: "inherit",
            }}
          />
          {busy && <span className="muted">…</span>}
        </div>
        <div ref={endRef} />
      </div>
      <p className="muted" style={{ margin: 0, fontSize: 12 }}>
        Type <code>help</code> for commands · ↑/↓ for history
      </p>
    </div>
  );
}
