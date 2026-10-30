// Comparison: up to four experiments on shared axes (one quantity per chart), with a summary table and a
// comparison report. Units fall back to pixels for everyone if any selected analysis is uncalibrated.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { X } from "lucide-react";
import { Alert, Button, DataTable, EmptyState, LoadingBlock, Panel, SelectField, type Column } from "../design-system";
import { api, errorMessage } from "../services/api";
import { useAsync } from "../hooks";
import { useApp } from "../store/app";
import { SERIES_COLOR, TimeSeriesChart, type Series } from "../charts";
import { DataClassPill, PageHead } from "../components/common";
import { primaryRadius, quantity, series } from "../lib/analysis";
import { fmt, pct } from "../lib/format";
import type { AnalysisResult, Experiment } from "../types/api";

const MAX = 4;
interface Loaded { exp: Experiment; result: AnalysisResult | null; error: string | null }

function useResults(ids: string[]) {
  const [data, setData] = useState<Record<string, Loaded>>({});
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    let alive = true;
    const missing = ids.filter((id) => !data[id]);
    if (!missing.length) return;
    setLoading(true);
    Promise.all(missing.map(async (id): Promise<[string, Loaded | null]> => {
      try {
        const exp = await api.experiment(id);
        const job = (await api.experimentJobs(id)).find((j) => j.status === "completed");
        return [id, { exp, result: job ? await api.jobResult(job.id) : null, error: job ? null : "No completed analysis" }];
      } catch { return [id, null]; }
    })).then((pairs) => {
      if (!alive) return;
      setData((d) => { const n = { ...d }; for (const [id, v] of pairs) if (v) n[id] = v; return n; });
      setLoading(false);
    });
    return () => { alive = false; };
  }, [ids.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps
  return { data, loading };
}

function shift(r: AnalysisResult, align: boolean): AnalysisResult {
  if (!align) return r;
  const t0 = r.measurements.find((m) => m.status === "detected")?.timestamp_s ?? 0;
  return { ...r, measurements: r.measurements.map((m) => ({ ...m, timestamp_s: m.timestamp_s - t0 })) };
}

export default function Comparison() {
  const { comparison, setComparison, notify } = useApp();
  const ids = comparison.slice(0, MAX);
  const all = useAsync(() => api.experiments({ status: "completed" }), []);
  const { data, loading } = useResults(ids);
  const [align, setAlign] = useState(true);
  const [busy, setBusy] = useState(false);
  const rows = ids.map((id) => data[id]).filter(Boolean) as Loaded[];
  const ready = rows.filter((x) => x.result) as (Loaded & { result: AnalysisResult })[];
  const mm = ready.length > 0 && ready.every((x) => x.result.summary.calibrated);
  const u = mm ? "mm" : "px";

  const radius: Series[] = ready.map((x) => ({ ...series(shift(x.result, align), primaryRadius(x.result), u, { name: x.exp.name, color: ids.indexOf(x.exp.id) }), id: `r-${x.exp.id}`, band: false }));
  const vel: Series[] = ready.map((x) => ({ ...series(shift(x.result, align), quantity("velocity"), u, { name: x.exp.name, color: ids.indexOf(x.exp.id) }), id: `v-${x.exp.id}`, band: false }));

  const cols: Column<Record<string, unknown> & { x: Loaded }>[] = [
    { key: "name", label: "Experiment", render: (r) => <span className="row"><span className="swatch" style={{ background: SERIES_COLOR(r.i as number) }} /><Link to={`/experiments/${r.x.exp.id}`}>{r.x.exp.name}</Link></span> },
    { key: "src", label: "Source", sortable: false, render: (r) => <DataClassPill exp={r.x.exp} /> },
    { key: "fuel", label: "Fuel", render: (r) => r.x.exp.fuel_type ?? "—" },
    { key: "o2", label: "X(O₂)", numeric: true, render: (r) => fmt(r.x.exp.oxygen_fraction, 3) },
    { key: "method", label: "Radius", render: (r) => r.x.result?.summary.radius_method ?? "—" },
    { key: "rmax", label: `Max radius (${u})`, numeric: true, render: (r) => { const s = r.x.result?.summary; if (!s) return "—"; const st = s.radius_method === "limb" ? (mm ? s.limb_radius_mm : s.limb_radius_px) : (mm ? s.radius_mm : s.equivalent_radius_px); return fmt(st?.max, 2); } },
    { key: "vel", label: `Mean dr/dt (${u}/s)`, numeric: true, render: (r) => fmt((mm ? r.x.result?.summary.expansion_velocity_mm_s : r.x.result?.summary.expansion_velocity_px_s)?.mean, 2) },
    { key: "ext", label: "Extinction (s)", numeric: true, render: (r) => { const e = r.x.result?.summary.extinction; return e?.time_s != null ? `${fmt(e.time_s, 2)} ± ${fmt(e.uncertainty_s, 2)}` : e ? e.status.replace(/_/g, " ") : "—"; } },
    { key: "det", label: "Detected", numeric: true, render: (r) => pct(r.x.result?.summary.detection_rate) },
  ];

  const report = async () => {
    setBusy(true);
    try { await api.createReport({ comparison_ids: ready.map((x) => x.exp.id), title: `Comparison of ${ready.length} experiments` }); notify("ok", "Comparison report generated", "Open Reports to download it."); }
    catch (e) { notify("bad", "Report failed", errorMessage(e)); } finally { setBusy(false); }
  };

  return (
    <div className="page">
      <PageHead eyebrow="Analytics" title="Compare experiments"
        lede="Overlay up to four analysed experiments. Curves are aligned at each flame's first detected frame by default, so growth histories line up regardless of when recording started."
        actions={<>{ready.length >= 2 && <Button variant="lime" busy={busy} onClick={report}>Comparison report</Button>}</>} />
      <Panel>
        <div className="row-between">
          <div className="row">
            {ids.map((id, i) => (
              <span key={id} className="fif-chip"><span className="swatch" style={{ background: SERIES_COLOR(i) }} />{data[id]?.exp.name ?? id}
                <button className="fif-icon-btn" style={{ width: 20, height: 20, border: 0, background: "transparent" }} aria-label="Remove from comparison" onClick={() => setComparison(comparison.filter((x) => x !== id))}><X size={12} /></button></span>
            ))}
            {ids.length < MAX && (
              <SelectField label="Add experiment" value="" onChange={(e) => e.target.value && setComparison([...ids, e.target.value])}>
                <option value="">Choose…</option>
                {all.data?.filter((e) => !ids.includes(e.id)).map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
              </SelectField>
            )}
          </div>
          <label className="fif-check"><input type="checkbox" checked={align} onChange={(e) => setAlign(e.target.checked)} />Align at first detection</label>
        </div>
      </Panel>
      {ids.length < 2 ? <EmptyState eyebrow="Comparison" title="Choose at least two experiments." body="Add them here or tick rows in the experiment list. Only experiments with a completed analysis can be plotted." action={<Link to="/experiments"><Button variant="ink" arrow>Experiments</Button></Link>} />
        : loading && !ready.length ? <LoadingBlock rows={6} /> : (<>
          {rows.filter((x) => !x.result).map((x) => <Alert key={x.exp.id} tone="warn" title={`${x.exp.name}: not plotted`}>{x.error}</Alert>)}
          {!mm && ready.length > 0 && <Alert tone="info" title="Shown in pixels">At least one selected analysis is uncalibrated, so all are shown in pixels. Pixel sizes are only comparable between videos with the same optics.</Alert>}
          {ready.some((x) => x.exp.data_class === "synthetic") && <Alert tone="info" title="Includes synthetic data">The synthetic demo is a generated test video, not a flame.</Alert>}
          <div className="grid g-2">
            <Panel title="Radius" eyebrow={align ? "time since first detection" : "time since recording start"}>
              <TimeSeriesChart series={radius} xLabel={align ? "t − t₀ (s)" : "time (s)"} yLabel={`radius (${u})`} height={280} />
            </Panel>
            <Panel title="Expansion velocity" eyebrow="dr/dt, local polynomial">
              <TimeSeriesChart series={vel} xLabel={align ? "t − t₀ (s)" : "time (s)"} yLabel={`dr/dt (${u}/s)`} height={280} />
            </Panel>
          </div>
          <Panel title="Summary" eyebrow="Latest completed analysis of each">
            <DataTable columns={cols} rows={rows.map((x) => ({ id: x.exp.id, i: ids.indexOf(x.exp.id), x }))} rowKey={(r) => r.id as string} caption="Comparison summary" />
          </Panel>
        </>)}
    </div>
  );
}
