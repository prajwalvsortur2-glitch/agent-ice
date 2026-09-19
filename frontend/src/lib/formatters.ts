/** Presentation-only formatters. No business logic. */

export function formatRelativeTime(iso: string | number | Date): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const diff = Date.now() - then;
  const s = Math.round(diff / 1000);
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  if (d < 30) return `${d}d ago`;
  return new Date(iso).toLocaleDateString();
}

export function formatTimestamp(iso: string | number | Date): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  );
}

export function formatNumber(n: number): string {
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString();
}

export function formatLatencyMs(ms: number): string {
  if (!Number.isFinite(ms)) return "—";
  if (ms < 1) return `${(ms * 1000).toFixed(0)}µs`;
  if (ms < 1000) return `${ms.toFixed(1)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

export function truncate(value: string, max = 96): string {
  if (!value) return "";
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}

export function shortHash(hash: string, len = 10): string {
  if (!hash) return "—";
  return hash.length > len * 2
    ? `${hash.slice(0, len)}…${hash.slice(-len)}`
    : hash;
}

export function prettyJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export function humanizeReasonCode(code: string): string {
  return code
    .toLowerCase()
    .split("_")
    .map((p) => (p.length ? p[0].toUpperCase() + p.slice(1) : p))
    .join(" ");
}