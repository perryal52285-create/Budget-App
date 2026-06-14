import { useQuery } from "@tanstack/react-query";
import { api, apiBase, routerBase } from "./api";

type Health = {
  ok: boolean;
  app: string;
  version: string;
  now: string;
  period: { year: number; month: number };
};

export default function App() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["health"],
    queryFn: () => api<Health>("/health"),
  });

  return (
    <main style={{ maxWidth: 680, margin: "0 auto", padding: "32px 20px" }}>
      <h1 style={{ marginBottom: 4 }}>Perry Budget</h1>
      <p style={{ color: "var(--muted)", marginTop: 0 }}>
        React rebuild — Phase 0 scaffold. The engine still serves the live app
        at <code>/</code>; this is the new shell.
      </p>

      <section
        style={{
          border: "1px solid var(--muted)",
          borderRadius: 10,
          padding: 16,
          marginTop: 24,
        }}
      >
        <h2 style={{ marginTop: 0, fontSize: 16 }}>API connectivity</h2>
        {isLoading && <p>Pinging API…</p>}
        {error && (
          <p style={{ color: "#ff5b5b" }}>
            ✗ API unreachable: {String((error as Error).message)}
          </p>
        )}
        {data && (
          <>
            <p style={{ color: "var(--accent)" }}>
              ✓ Connected — {data.app} v{data.version}
            </p>
            <pre style={{ overflowX: "auto", fontSize: 13 }}>
              {JSON.stringify(data, null, 2)}
            </pre>
          </>
        )}
      </section>

      <section style={{ marginTop: 24, fontSize: 13, color: "var(--muted)" }}>
        <div>
          ingress base: <code>{routerBase || "(none)"}</code>
        </div>
        <div>
          api base: <code>{apiBase}</code>
        </div>
      </section>
    </main>
  );
}
