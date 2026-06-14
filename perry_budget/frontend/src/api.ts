// Centralized API client. Resolves the Home Assistant ingress prefix at runtime
// so every request and route is correct whether we're behind ingress, on the
// standalone :8099 port, or in the Vite dev server.

function clean(v: unknown): string {
  // Unreplaced server markers (e.g. "__INGRESS_PATH__") -> treat as empty.
  if (typeof v !== "string" || v.startsWith("__")) return "";
  return v;
}

const w = window as unknown as { __INGRESS__?: string; __ROUTER_BASE__?: string };

export const ingressPath = clean(w.__INGRESS__);
export const routerBase = clean(w.__ROUTER_BASE__);
export const apiBase = `${ingressPath}/api`;

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${apiBase}${path}`, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${path} -> ${res.status} ${body}`.trim());
  }
  return (await res.json()) as T;
}
