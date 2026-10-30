// Flame in Freefall design system: React versions of the published components (classes in styles/ds.css).
import { useEffect, useId, useRef, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";
import { ArrowUpRight, X } from "lucide-react";
import type { QuantityKind } from "../types/api";

const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "lime" | "ink" | "sky" | "outline" | "ghost" | "danger";
  size?: "md" | "sm";
  arrow?: boolean;
  icon?: ReactNode;
  busy?: boolean;
}
export function Button({ variant = "outline", size, arrow, icon, busy, className, children, disabled, ...rest }: ButtonProps) {
  const showArrow = arrow ?? variant === "lime";
  return (
    <button type="button" {...rest} disabled={disabled || busy} aria-busy={busy || undefined}
      className={cx("fif-btn", `fif-btn-${variant}`, size === "sm" && "fif-btn-sm", className)}>
      {icon}
      <span>{busy ? "Working…" : children}</span>
      {showArrow && <span className="fif-btn-disc"><ArrowUpRight aria-hidden /></span>}
    </button>
  );
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return <span className="fif-label fif-eyebrow">{children}</span>;
}

const STATES: Record<string, [string, string]> = {
  operational: ["ok", "Operational"], completed: ["ok", "Completed"], ready: ["ok", "Ready"], detected: ["ok", "Detected"],
  degraded: ["warn", "Degraded"], warning: ["warn", "Warning"], partial: ["warn", "Partial"], low_confidence: ["warn", "Low confidence"],
  rejected_discontinuity: ["warn", "Rejected"], unavailable: ["bad", "Unavailable"], failed: ["bad", "Failed"], error: ["bad", "Error"],
  not_detected: ["neutral", "No flame"], frame_error: ["bad", "Frame error"],
  processing: ["info", "Processing"], queued: ["neutral", "Queued"], cancelled: ["neutral", "Cancelled"], draft: ["neutral", "Draft"],
};
export function StatusPill({ state, children }: { state: string; children?: ReactNode }) {
  const s = STATES[state] ?? ["neutral", state];
  return (
    <span className={cx("fif-pill", `fif-pill-${s[0]}`, state === "processing" && "fif-pill-busy")}>
      <span className="fif-pill-dot" aria-hidden />{children ?? s[1]}
    </span>
  );
}

const QLABEL: Record<QuantityKind, string> = { measured: "Measured", image_derived: "Image-derived", calculated: "Calculated", predicted: "Predicted", simulated: "Synthetic" };
export function QuantityTag({ kind, children }: { kind: QuantityKind; children?: ReactNode }) {
  return <span className={`fif-qtag fif-qtag-${kind}`} title={`${QLABEL[kind]} quantity`}>{children ?? QLABEL[kind]}</span>;
}

export interface MetricCardProps {
  label: string; value?: ReactNode; unit?: string; sigma?: ReactNode; quantity?: QuantityKind;
  tone?: "surface" | "raised" | "lime" | "ink"; footnote?: ReactNode; className?: string; loading?: boolean;
}
export function MetricCard({ label, value, unit, sigma, quantity, tone = "surface", footnote, className, loading }: MetricCardProps) {
  const has = value !== null && value !== undefined && value !== "";
  return (
    <div className={cx("fif-metric", tone !== "surface" && `fif-metric-${tone}`, className)}>
      <div className="fif-metric-head"><span className="fif-label">{label}</span>{quantity && <QuantityTag kind={quantity} />}</div>
      {loading ? <Skeleton height={44} width="60%" /> : (
        <div className={cx("fif-metric-value", !has && "fif-metric-empty")}>
          {has ? value : "—"}
          {has && unit && <span className="fif-metric-unit">{unit}</span>}
          {has && sigma != null && <span className="fif-metric-sigma">± {sigma}</span>}
        </div>
      )}
      {footnote && <div className="fif-metric-foot">{footnote}</div>}
    </div>
  );
}

export function Panel({ title, eyebrow, actions, raised, children, className, id }: {
  title?: ReactNode; eyebrow?: ReactNode; actions?: ReactNode; raised?: boolean; children?: ReactNode; className?: string; id?: string;
}) {
  return (
    <section className={cx("fif-panel", raised && "fif-panel-raised", className)} id={id} aria-label={typeof title === "string" ? title : undefined}>
      {(title || eyebrow || actions) && (
        <div className="fif-panel-head">
          <div>{eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}{title && <h2 className="fif-panel-title">{title}</h2>}</div>
          {actions && <div className="fif-panel-actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

export interface FieldProps extends InputHTMLAttributes<HTMLInputElement> { label: string; unit?: string; hint?: ReactNode; error?: string | null }
export function Field({ label, unit, hint, error, className, id, ...rest }: FieldProps) {
  const auto = useId();
  const fid = id ?? auto;
  return (
    <div className={cx("fif-field", className)}>
      <label className="fif-label" htmlFor={fid}>{label}</label>
      <div className={cx("fif-input-wrap", error && "is-invalid")}>
        <input className="fif-input" id={fid} aria-invalid={error ? true : undefined} aria-describedby={error ? `${fid}-e` : hint ? `${fid}-h` : undefined} {...rest} />
        {unit && <span className="fif-input-unit">{unit}</span>}
      </div>
      {error ? <span className="fif-error" id={`${fid}-e`}>{error}</span> : hint ? <span className="fif-help" id={`${fid}-h`}>{hint}</span> : null}
    </div>
  );
}

export function SelectField({ label, hint, className, id, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement> & { label: string; hint?: ReactNode }) {
  const auto = useId();
  const fid = id ?? auto;
  return (
    <div className={cx("fif-field", className)}>
      <label className="fif-label" htmlFor={fid}>{label}</label>
      <div className="fif-input-wrap"><select className="fif-input fif-select" id={fid} {...rest}>{children}</select></div>
      {hint && <span className="fif-help">{hint}</span>}
    </div>
  );
}

export function TextArea({ label, className, id, ...rest }: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { label: string }) {
  const auto = useId();
  const fid = id ?? auto;
  return (
    <div className={cx("fif-field", className)}>
      <label className="fif-label" htmlFor={fid}>{label}</label>
      <textarea className="fif-textarea" id={fid} {...rest} />
    </div>
  );
}

export function Segmented<T extends string>({ options, value, onChange, label }: {
  options: (T | { value: T; label: string })[]; value: T; onChange: (v: T) => void; label: string;
}) {
  return (
    <div className="fif-seg" role="group" aria-label={label}>
      {options.map((o) => {
        const v = (typeof o === "string" ? o : o.value) as T;
        const l = typeof o === "string" ? o : o.label;
        return <button key={v} type="button" aria-pressed={v === value} onClick={() => onChange(v)}>{l}</button>;
      })}
    </div>
  );
}

export interface Column<R> { key: string; label: ReactNode; numeric?: boolean; sortable?: boolean; render?: (row: R) => ReactNode; sortValue?: (row: R) => number | string | null }
export function DataTable<R extends Record<string, unknown>>({ columns, rows, rowKey, selectedKey, onRowClick, initialSort, emptyText, caption, maxHeight }: {
  columns: Column<R>[]; rows: R[]; rowKey: (r: R) => string; selectedKey?: string | null; onRowClick?: (r: R) => void;
  initialSort?: { key: string; dir: "asc" | "desc" }; emptyText?: ReactNode; caption?: string; maxHeight?: number;
}) {
  const [sort, setSort] = useState(initialSort ?? null);
  const sorted = [...rows];
  if (sort) {
    const col = columns.find((c) => c.key === sort.key);
    const val = (r: R) => (col?.sortValue ? col.sortValue(r) : (r[sort.key] as number | string | null));
    sorted.sort((a, b) => {
      const x = val(a), y = val(b);
      if (x == null) return 1; if (y == null) return -1;
      const d = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
      return sort.dir === "asc" ? d : -d;
    });
  }
  return (
    <div className="fif-table-wrap" style={maxHeight ? { maxHeight, overflowY: "auto" } : undefined}>
      <table className="fif-table">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead><tr>{columns.map((c) => {
          const active = sort?.key === c.key;
          return (
            <th key={c.key} className={c.numeric ? "is-num" : undefined} aria-sort={active ? (sort!.dir === "asc" ? "ascending" : "descending") : undefined}>
              {c.sortable === false ? c.label : (
                <button className="fif-sort" type="button" onClick={() => setSort({ key: c.key, dir: active && sort!.dir === "asc" ? "desc" : "asc" })}>
                  {c.label}{active ? (sort!.dir === "asc" ? " ↑" : " ↓") : ""}
                </button>
              )}
            </th>
          );
        })}</tr></thead>
        <tbody>
          {sorted.length ? sorted.map((r) => {
            const k = rowKey(r);
            return (
              <tr key={k} aria-selected={selectedKey === k || undefined} onClick={onRowClick ? () => onRowClick(r) : undefined}
                style={onRowClick ? { cursor: "pointer" } : undefined}>
                {columns.map((c) => <td key={c.key} className={c.numeric ? "is-num" : undefined}>{c.render ? c.render(r) : fmtCell(r[c.key])}</td>)}
              </tr>
            );
          }) : <tr><td colSpan={columns.length} className="fif-table-empty">{emptyText ?? "No rows"}</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
function fmtCell(v: unknown): ReactNode {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "number") return Number.isInteger(v) ? v : v.toFixed(3);
  if (typeof v === "boolean") return v ? "yes" : "no";
  return String(v);
}

export function Alert({ tone = "info", title, children }: { tone?: "info" | "warn" | "bad" | "ok"; title: ReactNode; children?: ReactNode }) {
  const mark = { info: "Info", warn: "Warning", bad: "Error", ok: "Done" }[tone];
  return (
    <div className={`fif-alert fif-alert-${tone}`} role={tone === "bad" ? "alert" : "status"}>
      <span className="fif-alert-mark">{mark}</span>
      <span className="fif-alert-title">{title}</span>
      {children && <span className="fif-alert-body">{children}</span>}
    </div>
  );
}

export function Progress({ value, label, detail, state }: { value: number; label?: string; detail?: string; state?: "processing" | "completed" | "failed" | string }) {
  const v = Math.max(0, Math.min(1, value || 0));
  return (
    <div className="fif-progress">
      <div className="fif-progress-top"><span className="fif-label">{label ?? "Progress"}</span><span className="data-s fif-num">{detail ?? `${Math.round(v * 100)} %`}</span></div>
      <div className="fif-progress-track" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(v * 100)} aria-label={label ?? "Progress"}>
        <div className={cx("fif-progress-fill", state === "completed" && "is-done", state === "failed" && "is-failed")} style={{ width: `${v * 100}%` }} />
      </div>
    </div>
  );
}

export function IntervalBar({ median, lower, upper, min, max, observed, unit, label, kind = "predicted", format }: {
  median: number; lower: number; upper: number; min?: number; max?: number; observed?: number | null; unit?: string; label?: string;
  kind?: "predicted" | "measured"; format?: (x: number) => string;
}) {
  const lo = min ?? lower, hi = max ?? upper, span = hi - lo || 1;
  const pos = (x: number) => Math.max(0, Math.min(100, ((x - lo) / span) * 100));
  const f = format ?? ((x: number) => (Math.round(x * 100) / 100).toString());
  const u = unit ? ` ${unit}` : "";
  return (
    <div className="fif-interval">
      {label && <span className="fif-label">{label}</span>}
      <div className="fif-interval-track" role="img" aria-label={`${label ?? "Interval"}: ${f(median)}${u}, interval ${f(lower)} to ${f(upper)}${u}${observed != null ? `, observed ${f(observed)}${u}` : ""}`}>
        <div className={cx("fif-interval-band", kind === "measured" && "is-measured")} style={{ left: `${pos(lower)}%`, width: `${pos(upper) - pos(lower)}%` }} />
        <div className="fif-interval-mark" style={{ left: `${pos(median)}%` }} />
        {observed != null && <div className="fif-interval-mark fif-interval-observed" style={{ left: `${pos(observed)}%` }} />}
      </div>
      <div className="fif-interval-scale"><span>{f(lo)}{u}</span><span>{f(hi)}{u}</span></div>
    </div>
  );
}

export function EmptyState({ title, body, eyebrow, action }: { title: string; body?: ReactNode; eyebrow?: string; action?: ReactNode }) {
  return (
    <div className="fif-empty">
      {eyebrow && <Eyebrow>{eyebrow}</Eyebrow>}
      <p className="fif-empty-title">{title}</p>
      {body && <p className="fif-empty-body">{body}</p>}
      {action}
    </div>
  );
}

export function Skeleton({ height = 16, width = "100%", radius = 8 }: { height?: number; width?: number | string; radius?: number }) {
  return <span className="fif-skeleton" style={{ height, width, borderRadius: radius }} aria-hidden />;
}

export function LoadingBlock({ rows = 3, label = "Loading" }: { rows?: number; label?: string }) {
  return <div className="fif-loading" role="status" aria-label={label}>{Array.from({ length: rows }, (_, i) => <Skeleton key={i} height={18} width={`${90 - i * 12}%`} />)}</div>;
}

export function Dialog({ open, title, onClose, children, footer, wide }: { open: boolean; title: string; onClose: () => void; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    const first = ref.current?.querySelector<HTMLElement>("input, select, textarea, button");
    first?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); prev?.focus(); };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fif-dialog-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className={cx("fif-dialog", wide && "fif-dialog-wide")} role="dialog" aria-modal="true" aria-label={title} ref={ref}>
        <div className="fif-dialog-head"><h2 className="title">{title}</h2><button className="fif-icon-btn" aria-label="Close" onClick={onClose}><X size={18} /></button></div>
        <div className="fif-dialog-body">{children}</div>
        {footer && <div className="fif-dialog-foot">{footer}</div>}
      </div>
    </div>
  );
}

export function ConfirmDialog({ open, title, body, confirmLabel, tone = "ink", onConfirm, onCancel, busy }: {
  open: boolean; title: string; body: ReactNode; confirmLabel: string; tone?: "ink" | "danger"; onConfirm: () => void; onCancel: () => void; busy?: boolean;
}) {
  return (
    <Dialog open={open} title={title} onClose={onCancel}
      footer={<><Button variant="ghost" onClick={onCancel}>Cancel</Button><Button variant={tone} busy={busy} onClick={onConfirm}>{confirmLabel}</Button></>}>
      <p className="body" style={{ margin: 0, color: "var(--ink-muted)" }}>{body}</p>
    </Dialog>
  );
}

export function Kv({ rows }: { rows: [ReactNode, ReactNode][] }) {
  return (
    <dl className="fif-kv">
      {rows.map(([k, v], i) => (<div key={i} className="fif-kv-row"><dt className="fif-label">{k}</dt><dd>{v ?? "—"}</dd></div>))}
    </dl>
  );
}

export function SubNav({ items, active, onChange }: { items: { id: string; label: string }[]; active: string; onChange: (id: string) => void }) {
  return (
    <div className="fif-subnav" role="tablist">
      {items.map((it) => (
        <button key={it.id} role="tab" aria-selected={active === it.id} className="fif-subnav-item" onClick={() => onChange(it.id)}>{it.label}</button>
      ))}
    </div>
  );
}
