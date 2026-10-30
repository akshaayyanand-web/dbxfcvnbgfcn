// Display formatting. Numbers are never rounded in the data, only here, and missing values render as an em dash.

export const DASH = "—";

export function fmt(x: number | null | undefined, digits = 2): string {
  if (x === null || x === undefined || Number.isNaN(x)) return DASH;
  if (!Number.isFinite(x)) return x > 0 ? "∞" : "−∞";
  const a = Math.abs(x);
  if (a !== 0 && (a >= 1e5 || a < 1e-3)) return x.toExponential(Math.max(1, digits - 1)).replace("-", "−");
  return x.toFixed(digits).replace("-", "−");
}

/** Value with its 1σ, the σ rounded to two significant figures and the value to match. */
export function fmtSigma(x: number | null | undefined, s: number | null | undefined, fallbackDigits = 2): [string, string | null] {
  if (x == null || Number.isNaN(x)) return [DASH, null];
  if (s == null || !Number.isFinite(s) || s <= 0) return [fmt(x, fallbackDigits), null];
  const d = Math.max(0, Math.min(6, 1 - Math.floor(Math.log10(s))));
  return [fmt(x, d), fmt(s, d)];
}

export function pct(x: number | null | undefined, digits = 0): string {
  return x == null || Number.isNaN(x) ? DASH : `${(x * 100).toFixed(digits)} %`;
}

export function bytes(n: number | null | undefined): string {
  if (n == null) return DASH;
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0, v = n;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(v < 10 && i ? 1 : 0)} ${u[i]}`;
}

export function duration(s: number | null | undefined): string {
  if (s == null) return DASH;
  if (s < 1) return `${Math.round(s * 1000)} ms`;
  if (s < 60) return `${s.toFixed(1)} s`;
  const m = Math.floor(s / 60);
  return m < 60 ? `${m} min ${Math.round(s % 60)} s` : `${Math.floor(m / 60)} h ${m % 60} min`;
}

let dateMode: "iso" | "local" = "local";
export function setDateMode(m: "iso" | "local") { dateMode = m; }

export function date(iso: string | null | undefined, withTime = true): string {
  if (!iso) return DASH;
  const d = new Date(iso.endsWith("Z") || /[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`);
  if (Number.isNaN(d.getTime())) return iso;
  if (dateMode === "iso") return withTime ? d.toISOString().replace("T", " ").slice(0, 19) + "Z" : d.toISOString().slice(0, 10);
  return withTime ? d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : d.toLocaleDateString(undefined, { dateStyle: "medium" });
}

export function ago(iso: string | null | undefined): string {
  if (!iso) return DASH;
  const d = new Date(iso.endsWith("Z") || /[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`).getTime();
  const s = Math.round((Date.now() - d) / 1000);
  if (Number.isNaN(s)) return iso;
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}

export const DATA_CLASS_LABEL: Record<string, string> = { user: "User upload", nasa_psi: "NASA PSI", synthetic: "Synthetic demo" };

export const ISSUE_LABEL: Record<string, string> = { info: "info", warning: "warn", error: "bad" };
