// Flame Analytics: every measured and derived quantity over time for the experiment in context, as small multiples
// (one quantity per axis), with statistics over a chosen time window, extinction and an uncertainty budget.
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Alert, Button, DataTable, EmptyState, Field, Kv, LoadingBlock, MetricCard, Panel, QuantityTag, Segmented, type Column } from "../design-system";
import { api, downloadUrl, saveText } from "../services/api";
import { useApp } from "../store/app";
import { TimeSeriesChart, type Series } from "../charts";
import { ErrorState, NoExperiment, PageHead, SummaryCards, useCurrentExperimentBundle } from "../components/common";
import { effectiveUnits, hasValues, measurementsCsv, QUANTITIES, quantity, series, type Quantity } from "../lib/analysis";
import { fmt, pct } from "../lib/format";
import type { AnalysisResult } from "../types/api";

const PANELS: { id: string; title: string; q: string[]; y: (u: string) => string }[] = [
  { id: "radius", title: "Radius", q: ["eq_radius", "limb_radius"], y: (u) => `radius (${u})` },
  { id: "velocity", title: "Expansion velocity", q: ["velocity"], y: (u) => `dr/dt (${u}/s)` },
  { id: "area", title: "Projected area", q: ["area"], y: (u) => (u === "mm" ? "area (mm²)" : "area (px²)") },
  { id: "volume", title: "Equivalent spherical volume", q: ["volume"], y: () => "volume (mm³)" },
  { id: "shape", title: "Shape", q: ["circularity", "eccentricity"], y: () => "dimensionless" },
  { id: "drift", title: "Centroid drift", q: ["drift"], y: () => "displacement (mm)" },
  { id: "quality", title: "Detection quality", q: ["confidence", "contrast"], y: () => "0–1" },
];

function stats(xs: number[]) {
  if (!xs.length) return null;
  const n = xs.length, mean = xs.reduce((a, b) => a + b, 0) / n;
  const sd = n > 1 ? Math.sqrt(xs.reduce((a, b) => a + (b - mean) ** 2, 0) / (n - 1)) : 0;
  const sorted = [...xs].sort((a, b) => a - b);
  return { n, mean, sd, min: sorted[0], max: sorted[n - 1], median: sorted[Math.floor(n / 2)] };
}

function windowed(r: AnalysisResult, t0: number | null, t1: number | null): AnalysisResult {
  if (t0 == null && t1 == null) return r;
  return { ...r, measurements: r.measurements.filter((m) => (t0 == null || m.timestamp_s >= t0) && (t1 == null || m.timestamp_s <= t1)) };
}

export default function FlameAnalytics() {
  const { units, setUnits } = useApp();
  const b = useCurrentExperimentBundle();
  const [t0, setT0] = useState("");
  const [t1, setT1] = useState("");
  const [band, setBand] = useState(true);
  const full = b.result.data;
  const r = useMemo(() => full && windowed(full, t0 === "" ? null : Number(t0), t1 === "" ? null : Number(t1)), [full, t0, t1]);
  const u = effectiveUnits(full, units);

  if (!b.id) return <div className="page"><PageHead eyebrow="Analytics" title="Flame analytics" /><NoExperiment what="flame analytics" /></div>;
  if (b.exp.error) return <div className="page"><PageHead eyebrow="Analytics" title="Flame analytics" /><ErrorState error={b.exp.error} onRetry={b.reload} /></div>;
  if (b.exp.loading || b.jobs.loading || b.result.loading) return <div className="page"><PageHead eyebrow="Analytics" title={b.exp.data?.name ?? "Flame analytics"} /><LoadingBlock rows={8} /></div>;
  if (b.result.error) return <div className="page"><PageHead eyebrow="Analytics" title={b.exp.data?.name ?? ""} /><ErrorState error={b.result.error} onRetry={b.result.reload} /></div>;
  if (!full || !r) return (
    <div className="page"><PageHead eyebrow="Analytics" title={b.exp.data?.name ?? "Flame analytics"} />
      <EmptyState title="No completed analysis for this experiment." body={b.running ? "An analysis is running; results appear here when it completes." : "Run one in Video Intelligence."}
        action={<Link to="/video-analysis"><Button variant="ink" arrow>Video Intelligence</Button></Link>} /></div>
  );

  const s = full.summary;
  const statRows = QUANTITIES.filter((q) => hasValues(r, q, u) && (!q.needsCalibration || s.calibrated)).map((q) => {
    const xs = r.measurements.map((m) => q.value(m, u)).filter((x): x is number => x != null);
    const st = stats(xs);
    return { id: q.id, q, label: q.label, unit: q.unit(u), ...st } as Record<string, unknown> & { q: Quantity };
  });
  const cols: Column<Record<string, unknown> & { q: Quantity }>[] = [
    { key: "label", label: "Quantity", render: (x) => <span className="row">{x.label as string}<QuantityTag kind={x.q.kind} /></span> },
    { key: "unit", label: "Unit" }, { key: "n", label: "Frames", numeric: true },
    ...(["mean", "sd", "min", "median", "max"] as const).map((k) => ({ key: k, label: k === "sd" ? "Std dev" : k[0].toUpperCase() + k.slice(1), numeric: true, render: (x: Record<string, unknown>) => fmt(x[k] as number, 3) })),
  ];
  const randomSig = r.measurements.map((m) => m.radius_sigma_random_mm as number | null).filter((x): x is number => typeof x === "number");
  const scaleSig = r.measurements.map((m) => m.radius_sigma_scale_mm as number | null).filter((x): x is number => typeof x === "number");
  const med = (xs: number[]) => (xs.length ? [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)] : null);
  const ext = s.extinction;
  const cols2 = ["frame_index", "timestamp_s", "status", "confidence", "equivalent_radius_px", "radius_mm", "radius_sigma_mm", "limb_radius_mm", "limb_radius_sigma_mm", "limb_fit_ok",
    "expansion_velocity_mm_s", "expansion_velocity_sigma_mm_s", "area_mm2", "equivalent_volume_mm3", "circularity", "eccentricity", "centroid_displacement_mm"];

  return (
    <div className="page">
      <PageHead eyebrow="Analytics" title={b.exp.data!.name}
        lede={`${r.measurements.length} analysed frames in view · ${s.calibrated ? "calibrated" : "uncalibrated, pixels only"} · radius method: ${s.radius_method}. Image-derived quantities come straight from segmentation; calculated ones carry propagated 1σ uncertainty.`}
        actions={<>
          <Segmented label="Units" value={u} onChange={(v) => setUnits(v)} options={s.calibrated ? [{ value: "mm", label: "mm" }, { value: "px", label: "px" }] : [{ value: "px", label: "px (uncalibrated)" }]} />
          <Button onClick={() => saveText(measurementsCsv(r, cols2), `${b.exp.data!.name}-window.csv`, "text/csv")}>CSV (this window)</Button>
          <Button onClick={() => downloadUrl(api.jobResultCsvUrl(b.completed!.id), `${b.exp.data!.name}.csv`)}>Full CSV</Button>
        </>} />
      <SummaryCards result={full} />
      <Panel>
        <div className="row-between">
          <div className="row">
            <Field label="From" unit="s" value={t0} onChange={(e) => setT0(e.target.value)} inputMode="decimal" placeholder={fmt(full.measurements[0]?.timestamp_s, 2)} style={{ width: 90 }} />
            <Field label="To" unit="s" value={t1} onChange={(e) => setT1(e.target.value)} inputMode="decimal" placeholder={fmt(full.measurements[full.measurements.length - 1]?.timestamp_s, 2)} style={{ width: 90 }} />
            {(t0 || t1) && <Button size="sm" variant="ghost" onClick={() => { setT0(""); setT1(""); }}>Reset window</Button>}
          </div>
          <label className="fif-check"><input type="checkbox" checked={band} onChange={(e) => setBand(e.target.checked)} />Show ±1σ bands</label>
        </div>
      </Panel>
      <div className="grid g-2">
        {PANELS.map((p) => {
          const qs = p.q.map(quantity).filter((q) => hasValues(r, q, u) && (!q.needsCalibration || s.calibrated));
          if (!qs.length) return (
            <Panel key={p.id} title={p.title} eyebrow="Not available">
              <p className="body-s subtle">{p.q.map(quantity).some((q) => q.needsCalibration) && !s.calibrated ? "Needs a calibration; this analysis is in pixels." : p.id === "radius" ? "No accepted frames." : "No values for this analysis (e.g. limb fit not used)."}</p>
            </Panel>
          );
          const ser: Series[] = qs.map((q, i) => ({ ...series(r, q, u, { color: i }), band: band && !!q.sigma }));
          return (
            <Panel key={p.id} title={p.title} eyebrow={qs.map((q) => q.kind.replace("_", "-")).filter((v, i, a) => a.indexOf(v) === i).join(" · ")}>
              <TimeSeriesChart series={ser} xLabel="time (s)" yLabel={p.y(u)} height={220} digits={p.id === "volume" || p.id === "area" ? 1 : 3}
                refLines={ext.time_s != null && p.id !== "quality" ? [{ x: ext.time_s, label: "extinction" }] : undefined} />
            </Panel>
          );
        })}
        <Panel title="Extinction" eyebrow="Camera-based estimate">
          <Kv rows={[["Status", ext.status.replace(/_/g, " ")], ["Time", ext.time_s != null ? `${fmt(ext.time_s, 3)} ± ${fmt(ext.uncertainty_s, 3)} s` : "—"],
            ["Last detected", ext.last_detected_time_s != null ? `${fmt(ext.last_detected_time_s, 3)} s` : "—"], ["First missing", ext.first_missing_time_s != null ? `${fmt(ext.first_missing_time_s, 3)} s` : "—"]]} />
          <Alert tone="info" title="What this measures">{ext.message} Visible-light extinction can differ from the OH* chemiluminescence signal NASA uses; the gap was 0.17 s on 19254C1.</Alert>
        </Panel>
      </div>
      <div className="grid g-main-side">
        <Panel title="Statistics over the window" eyebrow="Accepted frames only">
          <DataTable columns={cols} rows={statRows} rowKey={(x) => x.id as string} caption="Statistics per quantity" />
        </Panel>
        <div className="stack">
          <Panel title="Uncertainty budget" eyebrow="Radius, median per frame">
            {s.calibrated && randomSig.length ? (<>
              <div className="grid g-2">
                <MetricCard label="Random (pixel)" quantity="calculated" value={fmt(med(randomSig), 3)} unit="mm" footnote="Edge localisation; independent frame to frame." />
                <MetricCard label="Systematic (scale)" quantity="calculated" value={fmt(med(scaleSig), 3)} unit="mm" footnote="Calibration; shifts every frame together." />
              </div>
              <p className="body-s muted">Velocities use the random part for frame-to-frame scatter and add the scale part in quadrature. See SCIENTIFIC_ASSUMPTIONS A-UQ.</p>
            </>) : <p className="body-s subtle">{s.calibrated ? "No per-frame uncertainty decomposition in this result." : "Uncalibrated: only the pixel (random) uncertainty applies."}</p>}
          </Panel>
          <Panel title="Frame outcomes" eyebrow="Segmentation">
            <Kv rows={Object.entries(s.status_counts).map(([k, v]) => [k.replace(/_/g, " "), `${v} (${pct(v / Math.max(1, s.frames_analyzed))})`])} />
            {(s.frames_volume_suppressed_non_spherical ?? 0) > 0 && <Alert tone="warn" title="Volume suppressed on some frames">{s.frames_volume_suppressed_non_spherical} frames were too non-spherical for a spherical-volume estimate.</Alert>}
          </Panel>
        </div>
      </div>
    </div>
  );
}

