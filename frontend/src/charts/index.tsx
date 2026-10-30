// Chart components on Recharts. Each series draws from its own points, so a frame without a value is a gap, never
// a bridged line. Series colours follow a fixed order (--chart-1..4); predicted series are also dashed,
// so identity never rests on colour alone. Every chart has a legend (2+ series), a hover tooltip and a table view.
import { useMemo, useState, type ReactNode } from "react";
import {
  Area, Bar, BarChart, CartesianGrid, ComposedChart, ErrorBar, Line, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart,
  Tooltip, XAxis, YAxis, type TooltipProps,
} from "recharts";
import { DataTable, QuantityTag, Segmented, type Column } from "../design-system";
import { fmt } from "../lib/format";
import type { QuantityKind } from "../types/api";

export const SERIES_COLOR = (i: number) => `var(--chart-${(i % 4) + 1})`;
const AXIS = { stroke: "var(--chart-axis)", fontSize: 11, fontFamily: "var(--font-mono)" };

export interface SeriesPoint { x: number; y: number | null; lo?: number | null; hi?: number | null }
export interface Series { id: string; name: string; kind?: QuantityKind; color?: number; points: SeriesPoint[]; dashed?: boolean; band?: boolean; dots?: boolean }

function Legend({ series }: { series: Series[] }) {
  if (series.length < 2 && !series[0]?.kind) return null;
  return (
    <div className="legend" aria-label="Legend">
      {series.map((s, i) => (
        <span key={s.id}>
          <i className={s.dashed || s.kind === "predicted" ? "dashed" : undefined} style={{ background: SERIES_COLOR(s.color ?? i), color: SERIES_COLOR(s.color ?? i) }} />
          {s.name}{s.kind && <QuantityTag kind={s.kind} />}{s.band && <span className="subtle">(band ±1σ)</span>}
        </span>
      ))}
    </div>
  );
}

function ChartFrame({ title, legend, chart, table, actions }: { title?: ReactNode; legend?: ReactNode; chart: ReactNode; table: ReactNode; actions?: ReactNode }) {
  const [view, setView] = useState<"chart" | "table">("chart");
  return (
    <div className="stack-s chart-box">
      <div className="row-between">
        <div className="stack-s">{title && <span className="fif-label">{title}</span>}{legend}</div>
        <div className="row">{actions}<Segmented label="Chart or table view" options={[{ value: "chart", label: "Chart" }, { value: "table", label: "Table" }]} value={view} onChange={setView} /></div>
      </div>
      {view === "chart" ? chart : table}
    </div>
  );
}

function TipBox({ title, rows }: { title: string; rows: { name: string; value: string; color?: string }[] }) {
  return (
    <div className="chart-tooltip">
      <div className="t">{title}</div>
      {rows.map((r) => <div key={r.name} className="row" style={{ gap: 6 }}>{r.color && <span className="swatch" style={{ background: r.color }} />}<span>{r.name}</span><strong style={{ marginLeft: "auto" }}>{r.value}</strong></div>)}
    </div>
  );
}

/** Time series with optional ±σ bands, a frame cursor, reference lines and click-to-seek. */
export function TimeSeriesChart({ series, xLabel, yLabel, height = 260, cursorX, refLines, onPick, title, digits = 2, actions }: {
  series: Series[]; xLabel: string; yLabel: string; height?: number; cursorX?: number | null; refLines?: { x: number; label: string }[];
  onPick?: (x: number) => void; title?: ReactNode; digits?: number; actions?: ReactNode;
}) {
  const data = useMemo(() => {
    const map = new Map<number, Record<string, number | null | [number, number]>>();
    for (const s of series) {
      for (const p of s.points) {
        const row = map.get(p.x) ?? { x: p.x };
        row[s.id] = p.y;
        if (s.band && p.lo != null && p.hi != null) row[`${s.id}__band`] = [p.lo, p.hi];
        map.set(p.x, row);
      }
    }
    return [...map.values()].sort((a, b) => (a.x as number) - (b.x as number));
  }, [series]);
  const empty = !series.some((s) => s.points.some((p) => p.y != null));
  const tip = ({ active, payload, label }: TooltipProps<number, string>) => {
    if (!active || !payload?.length) return null;
    const rows = series.map((s, i) => {
      const v = payload.find((p) => p.dataKey === s.id)?.value;
      return v == null ? null : { name: s.name, value: fmt(v as number, digits), color: SERIES_COLOR(s.color ?? i) };
    }).filter(Boolean) as { name: string; value: string; color: string }[];
    return <TipBox title={`${xLabel} ${fmt(Number(label), 3)}`} rows={rows} />;
  };
  const columns: Column<Record<string, unknown>>[] = [
    { key: "x", label: xLabel, numeric: true, render: (r) => fmt(r.x as number, 3) },
    ...series.map((s) => ({ key: s.id, label: s.name, numeric: true, render: (r: Record<string, unknown>) => fmt(r[s.id] as number | null, digits) })),
  ];
  return (
    <ChartFrame title={title} actions={actions} legend={<Legend series={series} />}
      table={<DataTable columns={columns} rows={data.slice(0, 2000) as Record<string, unknown>[]} rowKey={(r) => String(r.x)} maxHeight={height + 60} caption={`${yLabel} against ${xLabel}`} />}
      chart={empty ? <div className="fif-empty" style={{ maxWidth: "none" }}><p className="fif-empty-body">No values to plot for this quantity.</p></div> : (
        <div style={{ width: "100%", height }} role="img" aria-label={`${yLabel} against ${xLabel}: ${series.map((s) => s.name).join(", ")}`}>
          <ResponsiveContainer>
            <ComposedChart data={data} margin={{ top: 22, right: 16, bottom: 18, left: 4 }}
              onClick={onPick ? (e) => { if (e && e.activeLabel != null) onPick(Number(e.activeLabel)); } : undefined}
              style={onPick ? { cursor: "pointer" } : undefined}>
              <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
              <XAxis dataKey="x" type="number" domain={["dataMin", "dataMax"]} tick={AXIS} stroke="var(--chart-grid)" tickFormatter={(v) => fmt(v, 1)}
                label={{ value: xLabel, position: "insideBottom", offset: -10, fill: "var(--chart-axis)", fontSize: 11, fontFamily: "var(--font-mono)" }} />
              <YAxis tick={AXIS} stroke="var(--chart-grid)" width={56} tickFormatter={(v) => fmt(v, 1)}
                label={{ value: yLabel, angle: -90, position: "insideLeft", fill: "var(--chart-axis)", fontSize: 11, fontFamily: "var(--font-mono)", style: { textAnchor: "middle" } }} />
              <Tooltip content={tip} cursor={{ stroke: "var(--line-strong)", strokeWidth: 1 }} />
              {series.filter((s) => s.band).map((s) => (
                <Area key={`${s.id}-band`} data={s.points.map((p) => ({ x: p.x, [`${s.id}__band`]: p.lo != null && p.hi != null ? [p.lo, p.hi] : null }))} dataKey={`${s.id}__band`}
                  stroke="none" fill={s.kind === "predicted" ? "var(--chart-band-pred)" : "var(--chart-band)"} isAnimationActive={false} activeDot={false} />
              ))}
              {series.map((s, i) => (
                <Line key={s.id} data={s.points.map((p) => ({ x: p.x, [s.id]: p.y }))} dataKey={s.id} name={s.name} stroke={SERIES_COLOR(s.color ?? i)} strokeWidth={2} dot={s.dots ? { r: 2.5, strokeWidth: 0, fill: SERIES_COLOR(s.color ?? i) } : false}
                  strokeDasharray={s.dashed || s.kind === "predicted" ? "6 4" : undefined} isAnimationActive={false} activeDot={{ r: 4, stroke: "var(--surface-raised)", strokeWidth: 2 }} />
              ))}
              {refLines?.map((r) => <ReferenceLine key={r.label} x={r.x} stroke="var(--warn)" strokeDasharray="3 3" label={{ value: r.label, position: "top", fill: "var(--ink-muted)", fontSize: 10, fontFamily: "var(--font-mono)" }} />)}
              {cursorX != null && <ReferenceLine x={cursorX} stroke="var(--ink)" strokeWidth={1} />}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )} />
  );
}

export interface CvPoint { id: string; observed: number; median: number; q10: number; q90: number; event: boolean; group?: string }

/** Held-out predicted median (with 10–90 % interval) against observed lifetime, log–log, with the y = x line. */
export function PredVsObsChart({ points, height = 340 }: { points: CvPoint[]; height?: number }) {
  const withErr = points.map((p) => ({ ...p, err: [p.median - p.q10, p.q90 - p.median] as [number, number] }));
  const events = withErr.filter((p) => p.event), censored = withErr.filter((p) => !p.event);
  const all = points.flatMap((p) => [p.observed, p.q10, p.q90]).filter((v) => v > 0);
  const lo = Math.max(0.1, Math.min(...all) * 0.8), hi = Math.max(...all) * 1.2;
  const tip = ({ active, payload }: TooltipProps<number, string>) => {
    if (!active || !payload?.length) return null;
    const p = payload[0].payload as CvPoint;
    return <TipBox title={`${p.id}${p.group ? ` · day ${p.group}` : ""}`} rows={[
      { name: p.event ? "Observed lifetime" : "Still burning at (lower bound)", value: `${fmt(p.observed, 1)} s` },
      { name: "Predicted median", value: `${fmt(p.median, 1)} s` }, { name: "80 % interval", value: `${fmt(p.q10, 1)}–${fmt(p.q90, 1)} s` },
    ]} />;
  };
  const columns: Column<Record<string, unknown>>[] = [
    { key: "id", label: "Test point" }, { key: "group", label: "Day" },
    { key: "observed", label: "Observed (s)", numeric: true, render: (r) => fmt(r.observed as number, 2) },
    { key: "event", label: "Outcome", render: (r) => (r.event ? "extinguished" : "censored") },
    { key: "median", label: "Pred. median (s)", numeric: true, render: (r) => fmt(r.median as number, 2) },
    { key: "q10", label: "Q10", numeric: true, render: (r) => fmt(r.q10 as number, 2) }, { key: "q90", label: "Q90", numeric: true, render: (r) => fmt(r.q90 as number, 2) },
  ];
  return (
    <ChartFrame
      legend={<div className="legend"><span><span className="swatch" style={{ background: SERIES_COLOR(0), borderRadius: 99 }} />Extinguished (observed lifetime)</span>
        <span><span className="swatch" style={{ border: `2px solid ${SERIES_COLOR(1)}`, borderRadius: 99 }} />Censored (burning at end; true lifetime is longer)</span>
        <span><i className="dashed" style={{ color: "var(--ink-subtle)" }} />y = x</span></div>}
      table={<DataTable columns={columns} rows={points as unknown as Record<string, unknown>[]} rowKey={(r) => String(r.id)} maxHeight={height} caption="Held-out predictions" />}
      chart={
        <div style={{ width: "100%", height }} role="img" aria-label="Held-out predicted lifetime against observed lifetime">
          <ResponsiveContainer>
            <ScatterChart margin={{ top: 8, right: 16, bottom: 22, left: 4 }}>
              <CartesianGrid stroke="var(--chart-grid)" />
              <XAxis type="number" dataKey="observed" scale="log" domain={[lo, hi]} tick={AXIS} stroke="var(--chart-grid)" tickFormatter={(v) => fmt(v, 0)} allowDataOverflow
                label={{ value: "observed lifetime (s)", position: "insideBottom", offset: -12, fill: "var(--chart-axis)", fontSize: 11 }} />
              <YAxis type="number" dataKey="median" scale="log" domain={[lo, hi]} tick={AXIS} stroke="var(--chart-grid)" width={56} tickFormatter={(v) => fmt(v, 0)} allowDataOverflow
                label={{ value: "predicted median (s)", angle: -90, position: "insideLeft", fill: "var(--chart-axis)", fontSize: 11, style: { textAnchor: "middle" } }} />
              <ReferenceLine segment={[{ x: lo, y: lo }, { x: hi, y: hi }]} stroke="var(--ink-subtle)" strokeDasharray="5 4" ifOverflow="hidden" />
              <Tooltip content={tip} />
              <Scatter data={events} fill={SERIES_COLOR(0)} isAnimationActive={false}>
                <ErrorBar dataKey="err" direction="y" stroke={SERIES_COLOR(0)} strokeOpacity={0.35} width={0} />
              </Scatter>
              <Scatter data={censored} fill="var(--surface-raised)" stroke={SERIES_COLOR(1)} strokeWidth={2} isAnimationActive={false} />
            </ScatterChart>
          </ResponsiveContainer>
        </div>
      } />
  );
}

/** Histogram from server-side counts and bin edges. */
export function Histogram({ counts, edges, label, unit, height = 180 }: { counts: number[]; edges: number[]; label: string; unit?: string | null; height?: number }) {
  const data = counts.map((c, i) => ({ bin: `${fmt(edges[i], 2)}–${fmt(edges[i + 1], 2)}`, mid: (edges[i] + edges[i + 1]) / 2, count: c }));
  const tip = ({ active, payload }: TooltipProps<number, string>) => active && payload?.length
    ? <TipBox title={`${label} ${(payload[0].payload as { bin: string }).bin}${unit ? ` ${unit}` : ""}`} rows={[{ name: "rows", value: String(payload[0].value) }]} /> : null;
  return (
    <ChartFrame title={`${label}${unit ? ` (${unit})` : ""}`}
      table={<DataTable columns={[{ key: "bin", label: "Bin" }, { key: "count", label: "Rows", numeric: true }]} rows={data} rowKey={(r) => r.bin} maxHeight={height + 40} />}
      chart={
        <div style={{ width: "100%", height }} role="img" aria-label={`Distribution of ${label}`}>
          <ResponsiveContainer>
            <BarChart data={data} margin={{ top: 4, right: 8, bottom: 4, left: 0 }} barCategoryGap={2}>
              <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
              <XAxis dataKey="mid" tick={AXIS} stroke="var(--chart-grid)" tickFormatter={(v) => fmt(v, 1)} />
              <YAxis tick={AXIS} stroke="var(--chart-grid)" width={36} allowDecimals={false} />
              <Tooltip content={tip} cursor={{ fill: "var(--surface-sunken)" }} />
              <Bar dataKey="count" fill={SERIES_COLOR(0)} radius={[4, 4, 0, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      } />
  );
}

/** Diverging horizontal bars around zero (e.g. contributions to log-lifetime). Sign is also written, never colour alone. */
export function DivergingBars({ rows, unit, positiveLabel, negativeLabel }: { rows: { label: string; value: number; detail?: string }[]; unit?: string; positiveLabel: string; negativeLabel: string }) {
  const max = Math.max(1e-9, ...rows.map((r) => Math.abs(r.value)));
  return (
    <div className="stack-s" role="list">
      <div className="row-between data-s subtle"><span>← {negativeLabel}</span><span>{positiveLabel} →</span></div>
      {rows.map((r) => {
        const w = (Math.abs(r.value) / max) * 50;
        const pos = r.value >= 0;
        return (
          <div key={r.label} role="listitem" style={{ display: "grid", gridTemplateColumns: "minmax(110px, 30%) 1fr 84px", gap: 10, alignItems: "center" }}>
            <span className="data-s" title={r.detail}>{r.label}</span>
            <div style={{ position: "relative", height: 14, background: "var(--surface-sunken)", borderRadius: 4 }}>
              <div style={{ position: "absolute", left: "50%", top: -2, bottom: -2, width: 1, background: "var(--line-strong)" }} />
              <div style={{ position: "absolute", top: 2, bottom: 2, borderRadius: 3, background: pos ? SERIES_COLOR(0) : SERIES_COLOR(1), left: pos ? "50%" : `${50 - w}%`, width: `${w}%` }} />
            </div>
            <span className="data-s" style={{ textAlign: "right" }}>{r.value >= 0 ? "+" : "−"}{fmt(Math.abs(r.value), 3)}{unit ? ` ${unit}` : ""}</span>
          </div>
        );
      })}
    </div>
  );
}
