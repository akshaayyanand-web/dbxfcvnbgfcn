// One experiment end to end: metadata, latest results, the analysis timeline, jobs, predictions and reports.
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Button, DataTable, Dialog, EmptyState, Field, Kv, LoadingBlock, Panel, Progress, StatusPill, SubNav, TextArea, type Column } from "../design-system";
import { api, downloadUrl, errorMessage, saveBlob } from "../services/api";
import { useAsync } from "../hooks";
import { useApp } from "../store/app";
import { TimeSeriesChart } from "../charts";
import { ActivityTimeline } from "../components/Activity";
import { DataClassPill, ErrorState, IssueList, PageHead, SummaryCards, useExperimentBundle } from "../components/common";
import { effectiveUnits, primaryRadius, quantity, series } from "../lib/analysis";
import { bytes, date, duration, fmt } from "../lib/format";
import type { Experiment, FlameMeasurement, PredictionRecord, ProcessingJob, ScientificReport } from "../types/api";

const TABS = [{ id: "overview", label: "Overview" }, { id: "measurements", label: "Measurements" }, { id: "config", label: "Configuration" },
  { id: "jobs", label: "Analysis runs" }, { id: "predictions", label: "Predictions" }, { id: "reports", label: "Reports" }];

function EditDialog({ exp, open, onClose, onSaved }: { exp: Experiment; open: boolean; onClose: () => void; onSaved: () => void }) {
  const [f, setF] = useState({ name: exp.name, description: exp.description, fuel_type: exp.fuel_type ?? "", oxygen_fraction: exp.oxygen_fraction?.toString() ?? "", chamber_pressure_kpa: exp.chamber_pressure_kpa?.toString() ?? "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const n = (s: string) => (s.trim() === "" ? null : Number(s));
  const save = async () => {
    setBusy(true); setErr(null);
    try {
      await api.updateExperiment(exp.id, { name: f.name, description: f.description, fuel_type: f.fuel_type || null, oxygen_fraction: n(f.oxygen_fraction), chamber_pressure_kpa: n(f.chamber_pressure_kpa) });
      onSaved(); onClose();
    } catch (e) { setErr(errorMessage(e)); } finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onClose={onClose} title="Edit experiment" footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="ink" busy={busy} onClick={save} disabled={!f.name.trim()}>Save</Button></>}>
      <Field label="Name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} error={f.name.trim() ? null : "Required"} />
      <TextArea label="Description" value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} />
      <div className="form-grid">
        <Field label="Fuel" value={f.fuel_type} onChange={(e) => setF({ ...f, fuel_type: e.target.value })} />
        <Field label="Oxygen mole fraction" value={f.oxygen_fraction} onChange={(e) => setF({ ...f, oxygen_fraction: e.target.value })} inputMode="decimal" />
        <Field label="Chamber pressure" unit="kPa" value={f.chamber_pressure_kpa} onChange={(e) => setF({ ...f, chamber_pressure_kpa: e.target.value })} inputMode="decimal" />
      </div>
      {err && <ErrorState error={err} title="Not saved" />}
    </Dialog>
  );
}

export default function ExperimentDetail() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const { setExperiment, experimentId, notify, units } = useApp();
  const [tab, setTab] = useState("overview");
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const b = useExperimentBundle(id);
  const activity = useAsync(() => api.activity(200), [id]);
  const preds = useAsync(() => api.predictions(id), [id], tab === "predictions");
  const reports = useAsync(() => api.reports(id), [id], tab === "reports");
  const exp = b.exp.data;
  const r = b.result.data;
  const u = effectiveUnits(r, units);

  const run = async (label: string, fn: () => Promise<unknown>, ok: string, then?: () => void) => {
    setBusy(label);
    try { await fn(); notify("ok", ok); b.reload(); then?.(); } catch (e) { notify("bad", `${label} failed`, errorMessage(e)); } finally { setBusy(null); }
  };

  if (b.exp.error) return <div className="page"><PageHead eyebrow="Experiment" title="Experiment not available" /><ErrorState error={b.exp.error} onRetry={b.reload} /><Link to="/experiments">Back to experiments</Link></div>;
  if (!exp) return <div className="page"><LoadingBlock rows={6} label="Loading experiment" /></div>;

  const jobCols: Column<ProcessingJob & Record<string, unknown>>[] = [
    { key: "created_at", label: "Started", render: (j) => date(j.created_at) },
    { key: "status", label: "Status", render: (j) => <StatusPill state={j.status} /> },
    { key: "frames_processed", label: "Frames", numeric: true },
    { key: "duration_s", label: "Duration", numeric: true, render: (j) => duration(j.duration_s ?? (j.started_at && j.finished_at ? (Date.parse(`${j.finished_at}Z`) - Date.parse(`${j.started_at}Z`)) / 1000 : null)) },
    { key: "message", label: "Message", render: (j) => <span className="body-s">{j.error ?? j.message}</span> },
    { key: "act", label: "", sortable: false, render: (j) => j.status === "completed"
      ? <Button size="sm" variant="ghost" onClick={() => downloadUrl(api.jobResultCsvUrl(j.id), `${exp.name}-${j.id}.csv`)}>CSV</Button>
      : (j.status === "processing" || j.status === "queued") ? <Button size="sm" variant="danger" onClick={() => run("Cancel", () => api.cancelJob(j.id), "Cancellation requested")}>Cancel</Button> : null },
  ];
  const mCols: Column<FlameMeasurement>[] = [
    { key: "frame_index", label: "Frame", numeric: true }, { key: "timestamp_s", label: "t (s)", numeric: true, render: (m) => fmt(m.timestamp_s, 4) },
    { key: "status", label: "Status", render: (m) => <StatusPill state={m.status} /> },
    { key: "confidence", label: "Conf.", numeric: true, render: (m) => fmt(m.confidence, 2) },
    { key: "equivalent_radius_px", label: "R eq (px)", numeric: true, render: (m) => fmt(m.equivalent_radius_px, 2) },
    { key: "radius_mm", label: "R eq (mm)", numeric: true, render: (m) => fmt(m.radius_mm, 3) },
    { key: "limb_radius_mm", label: "R limb (mm)", numeric: true, render: (m) => (m.limb_fit_ok ? fmt(m.limb_radius_mm, 3) : "—") },
    { key: "expansion_velocity_mm_s", label: "dr/dt (mm/s)", numeric: true, render: (m) => fmt(m.expansion_velocity_mm_s, 3) },
    { key: "circularity", label: "Circ.", numeric: true, render: (m) => fmt(m.circularity, 3) },
    { key: "warnings", label: "Warnings", sortable: false, render: (m) => <span className="data-s">{m.warnings.join("; ") || "—"}</span> },
  ];
  const predCols: Column<PredictionRecord & Record<string, unknown>>[] = [
    { key: "created_at", label: "When", render: (p) => date(p.created_at) },
    { key: "median", label: "Median lifetime (s)", numeric: true, sortValue: (p) => p.result.median_lifetime_s, render: (p) => fmt(p.result.median_lifetime_s, 2) },
    { key: "interval", label: "Interval (s)", numeric: true, sortable: false, render: (p) => `${fmt(p.result.interval.lower_s, 1)}–${fmt(p.result.interval.upper_s, 1)}` },
    { key: "model_version", label: "Model" },
    { key: "warnings", label: "Warnings", sortable: false, render: (p) => p.result.warnings.length ? `${p.result.warnings.length}` : "none" },
  ];
  const repCols: Column<ScientificReport & Record<string, unknown>>[] = [
    { key: "title", label: "Title" }, { key: "created_at", label: "Created", render: (x) => date(x.created_at) },
    { key: "status", label: "Status", render: (x) => <StatusPill state={x.status} /> },
    { key: "dl", label: "", sortable: false, render: (x) => x.status === "completed" ? <span className="row">{x.formats.map((f) => <Button key={f} size="sm" variant="ghost" onClick={() => downloadUrl(api.reportDownloadUrl(x.id, f), `${x.title}.${f}`)}>{f}</Button>)}</span> : x.error },
  ];
  const events = (activity.data ?? []).filter((e) => e.experiment_id === exp.id);

  return (
    <div className="page">
      <PageHead eyebrow="Experiment" title={exp.name}
        lede={<span className="row"><DataClassPill exp={exp} /><StatusPill state={exp.status} />{exp.archived && <span className="fif-chip">archived</span>}<span className="body-s subtle">created {date(exp.created_at)} · id {exp.id}</span></span>}
        actions={<>
          {experimentId !== exp.id && <Button onClick={() => setExperiment(exp.id)}>Set as context</Button>}
          <Button onClick={() => setEditing(true)}>Edit</Button>
          <Button onClick={() => { setExperiment(exp.id); nav("/video-analysis"); }}>Video</Button>
          {exp.video_ref && <Button busy={busy === "Re-analyse"} onClick={() => run("Re-analyse", () => api.reanalyze(exp.id), "Re-analysis queued")}>Re-analyse</Button>}
          {b.completed && <Button busy={busy === "Report"} onClick={() => run("Report", () => api.createReport({ experiment_id: exp.id }), "Report generated", () => setTab("reports"))}>Generate report</Button>}
          {b.completed && <Button variant="lime" onClick={() => api.exportExperiment(exp.id, "json").then((blob) => saveBlob(blob, `${exp.name}.json`)).catch((e) => notify("bad", "Export failed", errorMessage(e)))}>Export</Button>}
        </>} />
      {exp.description && <p className="body muted" style={{ maxWidth: 820 }}>{exp.description}</p>}
      {exp.data_class === "synthetic" && <div className="fif-alert fif-alert-info"><span className="fif-alert-mark">Info</span><span className="fif-alert-title">Synthetic demonstration experiment</span><span className="fif-alert-body">Generated video with a known radius law, used to check the measurement chain. It is not a combustion measurement.</span></div>}
      <SubNav items={TABS} active={tab} onChange={setTab} />

      {b.running && <Panel><Progress value={b.running.progress} label={`Analysis ${b.running.status}`} detail={`${b.running.frames_processed} frames · ${Math.round(b.running.progress * 100)} %`} state={b.running.status} /></Panel>}

      {tab === "overview" && (
        <div className="grid g-main-side">
          <div className="stack">
            {b.result.error ? <ErrorState error={b.result.error} onRetry={b.result.reload} />
              : r ? <>
                <SummaryCards result={r} />
                <Panel title="Growth" eyebrow={`${u === "mm" ? "Calibrated" : "Uncalibrated (pixels)"} · ${r.summary.radius_method} radius`}>
                  <TimeSeriesChart series={[series(r, primaryRadius(r), u)]} xLabel="time (s)" yLabel={`radius (${u})`}
                    refLines={r.summary.extinction.time_s != null ? [{ x: r.summary.extinction.time_s, label: "extinction" }] : undefined} />
                  <TimeSeriesChart series={[series(r, quantity("velocity"), u, { color: 1 })]} xLabel="time (s)" yLabel={`dr/dt (${u}/s)`} height={200} />
                </Panel>
                <Panel title="Validation" eyebrow="Issues raised by the engine"><IssueList issues={r.issues} /></Panel>
              </>
                : b.jobs.loading || b.result.loading ? <LoadingBlock rows={6} />
                  : <EmptyState title="No completed analysis yet." body={exp.video_ref ? "Re-analyse, or open Video Intelligence to tune segmentation first." : "Upload a video for this experiment in Video Intelligence."}
                    action={<Button variant="ink" arrow onClick={() => { setExperiment(exp.id); nav("/video-analysis"); }}>Video Intelligence</Button>} />}
          </div>
          <div className="stack">
            <Panel title="Conditions" eyebrow="Metadata">
              <Kv rows={[["Fuel", exp.fuel_type], ["Oxygen mole fraction", fmt(exp.oxygen_fraction, 3)], ["Chamber pressure", exp.chamber_pressure_kpa != null ? `${fmt(exp.chamber_pressure_kpa, 1)} kPa` : null],
                ["Burn duration", exp.burn_duration_s != null ? `${fmt(exp.burn_duration_s, 1)} s` : null], ["Input", exp.video_filename ?? exp.dataset_ref ?? "none"],
                ["Calibration", exp.calibration ? `${fmt(exp.calibration.mm_per_px ?? null, 5)} ± ${fmt(exp.calibration.mm_per_px_sigma ?? null, 5)} mm/px` : "not calibrated"]]} />
            </Panel>
            <Panel title="Timeline" eyebrow="Lifecycle">
              {activity.loading && !activity.data ? <LoadingBlock rows={4} /> : <ActivityTimeline events={events} empty="No recorded events for this experiment." />}
            </Panel>
          </div>
        </div>
      )}

      {tab === "measurements" && (
        <Panel title="Per-frame measurements" eyebrow={r ? `${r.measurements.length} frames · engine ${r.engine_version}` : "Latest completed run"}
          actions={b.completed && <Button size="sm" onClick={() => downloadUrl(api.jobResultCsvUrl(b.completed!.id), `${exp.name}.csv`)}>Download CSV</Button>}>
          {r ? <DataTable columns={mCols as unknown as Column<Record<string, unknown>>[]} rows={r.measurements as unknown as Record<string, unknown>[]} rowKey={(m) => String(m.frame_index)} maxHeight={560} caption="Per-frame measurements" />
            : b.result.loading ? <LoadingBlock rows={8} /> : <EmptyState title="No measurements yet." />}
        </Panel>
      )}

      {tab === "config" && (
        <div className="grid g-2">
          <Panel title="Video" eyebrow="Input">
            {r ? <Kv rows={[["File", r.video.filename], ["Kind", r.video.kind], ["Resolution", `${r.video.width} × ${r.video.height}`], ["Nominal rate", `${fmt(r.video.nominal_fps, 3)} fps`],
              ["Frames (reported)", r.video.reported_frame_count], ["Codec", r.video.codec_name ?? r.video.codec_fourcc], ["Size", bytes(r.video.file_size_bytes)], ["Timestamps", r.timestamp_source], ["Decoder", r.summary.decoder ?? "—"]]} />
              : <p className="body-s subtle">Available after an analysis completes.</p>}
          </Panel>
          <Panel title="Calibration" eyebrow="Scale">
            {exp.calibration ? <Kv rows={Object.entries(exp.calibration).map(([k, v]) => [k.replace(/_/g, " "), typeof v === "number" ? fmt(v, 5) : String(v ?? "—")])} /> : <p className="body-s subtle">No calibration. Sizes are in pixels; volumes and mm velocities are not computed.</p>}
          </Panel>
          <Panel title="Analysis configuration" eyebrow="As used by the latest run" className="span-all">
            <pre className="code">{JSON.stringify(r?.config ?? exp.analysis_config ?? {}, null, 2)}</pre>
          </Panel>
        </div>
      )}

      {tab === "jobs" && (
        <Panel title="Analysis runs" eyebrow="History">
          {b.jobs.error ? <ErrorState error={b.jobs.error} onRetry={b.jobs.reload} /> : !b.jobs.data ? <LoadingBlock rows={4} />
            : <DataTable columns={jobCols} rows={b.jobs.data as (ProcessingJob & Record<string, unknown>)[]} rowKey={(j) => j.id} emptyText="No analysis runs yet." caption="Analysis runs" />}
        </Panel>
      )}

      {tab === "predictions" && (
        <Panel title="Predictions" eyebrow="Linked to this experiment" actions={<Link to="/prediction"><Button size="sm" variant="ink">New prediction</Button></Link>}>
          {preds.error ? <ErrorState error={preds.error} onRetry={preds.reload} /> : !preds.data ? <LoadingBlock rows={3} />
            : <DataTable columns={predCols} rows={preds.data as (PredictionRecord & Record<string, unknown>)[]} rowKey={(p) => p.id} emptyText="No predictions linked to this experiment." />}
        </Panel>
      )}

      {tab === "reports" && (
        <Panel title="Reports" eyebrow="Generated documents" actions={<Link to="/reports"><Button size="sm">All reports</Button></Link>}>
          {reports.error ? <ErrorState error={reports.error} onRetry={reports.reload} /> : !reports.data ? <LoadingBlock rows={3} />
            : <DataTable columns={repCols} rows={reports.data as (ScientificReport & Record<string, unknown>)[]} rowKey={(x) => x.id} emptyText="No reports yet. Generate one from the header." />}
        </Panel>
      )}
      <EditDialog key={exp.updated_at} exp={exp} open={editing} onClose={() => setEditing(false)} onSaved={() => { notify("ok", "Experiment saved"); b.reload(); }} />
    </div>
  );
}
