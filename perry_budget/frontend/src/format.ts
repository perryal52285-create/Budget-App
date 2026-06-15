export function fmtCents(cents: number | null | undefined): string {
  const v = cents ?? 0;
  const neg = v < 0;
  const s = `$${(Math.abs(v) / 100).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
  return neg ? `-${s}` : s;
}

export function fmtCentsShort(cents: number | null | undefined): string {
  const v = (cents ?? 0) / 100;
  const neg = v < 0;
  const a = Math.abs(v);
  let s: string;
  if (a >= 1_000_000) s = `${(a / 1_000_000).toFixed(1)}M`;
  else if (a >= 1_000) s = `${(a / 1_000).toFixed(1)}k`;
  else s = a.toFixed(0);
  return `${neg ? "-" : ""}$${s}`;
}

export function dollarsToCents(input: string | number): number {
  const n = typeof input === "number" ? input : parseFloat(String(input).replace(/[,$\s]/g, ""));
  return Number.isFinite(n) ? Math.round(n * 100) : 0;
}

export function centsToInput(cents: number | null | undefined): string {
  return ((cents ?? 0) / 100).toFixed(2);
}

export const MONTHS = ["", "January", "February", "March", "April", "May", "June", "July",
  "August", "September", "October", "November", "December"];
