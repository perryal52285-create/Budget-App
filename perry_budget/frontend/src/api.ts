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

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${apiBase}${path}`, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const body = await res.json();
      detail = body?.detail || JSON.stringify(body);
    } catch {
      detail = (await res.text().catch(() => "")) || `${res.status}`;
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const apiGet = <T>(path: string) => api<T>(path);
export const apiPost = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
export const apiDelete = <T>(path: string) => api<T>(path, { method: "DELETE" });
