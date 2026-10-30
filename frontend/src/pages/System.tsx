// System health: services, runtime, resources, the processing queue and recent server logs.
import { useState } from "react";
import { Link } from "react-router-dom";
import { Alert, Button, DataTable, Field, Kv, LoadingBlock, MetricCard, Panel, Progress, SelectField, StatusPill, type Column } from "../design-system";
import { api, errorMessage } from "../services/api";
import { usePolling } from "../hooks";
import { useApp } from "../store/app";
import { ErrorState, PageHead } from "../components/common";
import { bytes, date, duration, fmt, pct } from "../lib/format";
import type { LogRecord, ProcessingJob } from "../types/api";

export default function SystemPage() {
  const { notify } = useApp();
  const st = usePolling(() => api.systemStatus(), 5000);
  const [jobFilter, setJobFilter] = useState("");
  const jobs = usePolling(() => api.jobs(jobFilter || undefined, 200), 3000, true, [jobFilter]);
  const [q, setQ] = useState("");
  const [level, setLevel] = useState("");
  const logs = usePolling(() => api.logs(q), 5000, true, [q]);
  const s = st.data;

  const jobCols: Column<ProcessingJob & Record<string, unknown>>[] = [
    { key: "created_at", label: "Created", render: (j) => date(j.created_at) },
    { key: "experiment_id", label: "Experiment", render: (j) => <Link to={`/experiments/${j.experiment_id}`}>{j.experiment_id}</Link> },
    { key: "input_ref", label: "Input", render: (j) => <span className="data-s">{j.input_ref}</span> },
    { key: "status", label: "Status", render: (j) => <StatusPill state={j.status} /> },
    { key: "progress", label: "Progress", numeric: true, render: (j) => (j.status === "processing" ? <div style={{ minWidth: 120 }}><Progress value={j.progress} label={`${j.frames_processed} fr`} /></div> : pct(j.progress)) },
    { key: "duration_s", label: "Duration", numeric: true, render: (j) => duration(j.duration_s ?? null) },
    { key: "error", label: "Error", render: (j) => <span className="body-s">{j.error ?? "—"}</span> },
    { key: "act", label: "", sortable: false, render: (j) => (j.status === "processing" || j.status === "queued")
      ? <Button size="sm" variant="danger" onClick={() => api.cancelJob(j.id).then(() => { notify("info", "Cancellation requested"); jobs.reload(); }).catch((e) => notify("bad", "Cancel failed", errorMessage(e)))}>Cancel</Button> : null },
  ];
  const logCols: Column<LogRecord & Record<string, unknown>>[] = [
    { key: "time", label: "Time", render: (l) => <span className="data-s">{date(l.time)}</span> },
    { key: "level", label: "Level", render: (l) => <StatusPill state={l.level === "ERROR" ? "error" : l.level === "WARNING" ? "warning" : "queued"}>{l.level}</StatusPill> },
    { key: "logger", label: "Source", render: (l) => <span className="data-s">{l.logger}</span> },
    { key: "message", label: "Message", render: (l) => <span className="data-s" style={{ whiteSpace: "pre-wrap" }}>{l.message}</span> },
  ];
  const logRows = (logs.data ?? []).filter((l) => !level || l.level === level);

  return (
    <div className="page">
      <PageHead eyebrow="System" title="System health" lede="Live state of this server, refreshed every few seconds." />
      {st.error && !s ? <ErrorState error={st.error} onRetry={st.reload} title="Status unavailable" /> : !s ? <LoadingBlock rows={6} /> : (<>
        <div className="grid g-4">
          <MetricCard label="API" value={s.api_version} footnote={`engine ${s.engine_version}`} tone="raised" />
          <MetricCard label="Database" value={s.database.ok ? "OK" : "Down"} tone={s.database.ok ? "raised" : "ink"} footnote={s.database.backend} />
          <MetricCard label="Queue" value={s.jobs.active} footnote={`${s.jobs.workers} workers · ${Object.entries(s.jobs.by_status).map(([k, v]) => `${v} ${k}`).join(" · ")}`} tone={s.jobs.active ? "lime" : "raised"} />
          <MetricCard label="Throughput" quantity="calculated" value={fmt(s.processing.throughput_frames_per_s, 1)} unit="frames/s" footnote={`${s.processing.completed_jobs_timed} timed jobs · mean ${duration(s.processing.average_duration_s)}`} tone="raised" />
        </div>
        <div className="grid g-3">
          <Panel title="Resources" eyebrow="Host">
            {s.resources.memory && <Progress value={s.resources.memory.used_fraction} label="Memory" detail={`${bytes(s.resources.memory.total_bytes - s.resources.memory.available_bytes)} / ${bytes(s.resources.memory.total_bytes)}`} />}
            {s.resources.cpu_load_fraction_1m != null && <Progress value={s.resources.cpu_load_fraction_1m} label="CPU load (1 min)" detail={`${fmt(s.resources.load_average?.["1m"], 2)} on ${s.resources.cpu_count} cores`} />}
            <Progress value={s.storage.used_by_app_bytes / Math.max(1, s.storage.used_by_app_bytes + s.storage.disk_free_bytes)} label="Disk used by app" detail={`${bytes(s.storage.used_by_app_bytes)} · ${bytes(s.storage.disk_free_bytes)} free`} />
            <Kv rows={[["Process peak RSS", bytes(s.resources.process_max_rss_bytes)], ["GPU", s.resources.gpu_note]]} />
          </Panel>
          <Panel title="Services" eyebrow="Dependencies">
            <Kv rows={[["Prediction model", <StatusPill key="m" state={s.model.loaded ? "ready" : "unavailable"}>{s.model.version ?? s.model.error ?? "not loaded"}</StatusPill>],
              ["s-Flame dataset", s.datasets.sflame_test_points != null ? `${s.datasets.sflame_test_points} rows` : "not built"], ["Samples on disk", `${s.samples.available} of ${s.samples.total}`],
              ["FFmpeg", <StatusPill key="f" state={s.runtime.ffmpeg ? "ready" : "degraded"}>{s.runtime.ffmpeg ? "available" : "missing: OpenCV fallback"}</StatusPill>],
              ["Write protection", s.auth_required_for_writes ? "API key required" : "open (local use)"]]} />
          </Panel>
          <Panel title="Runtime" eyebrow="Versions">
            <Kv rows={[["Python", s.runtime.python], ["OpenCV", s.runtime.opencv], ["Platform", s.runtime.platform],
              ["Startup recovery", `${s.recovery_on_startup.failed_interrupted} interrupted jobs failed · ${s.recovery_on_startup.requeued} requeued`]]} />
          </Panel>
        </div>
        {!s.model.loaded && <Alert tone="warn" title="Prediction is unavailable">{s.model.error ?? "No model artifact was found."}</Alert>}
      </>)}

      <Panel title="Processing queue" eyebrow="All analysis jobs" actions={
        <SelectField label="Status" value={jobFilter} onChange={(e) => setJobFilter(e.target.value)}>
          <option value="">Any</option>{["queued", "processing", "completed", "failed", "cancelled"].map((x) => <option key={x}>{x}</option>)}
        </SelectField>}>
        {jobs.error && !jobs.data ? <ErrorState error={jobs.error} onRetry={jobs.reload} /> : !jobs.data ? <LoadingBlock rows={4} />
          : <DataTable columns={jobCols} rows={jobs.data as (ProcessingJob & Record<string, unknown>)[]} rowKey={(j) => j.id} maxHeight={420} emptyText="No jobs." caption="Jobs" />}
      </Panel>

      <Panel title="Server log" eyebrow="Newest first: in-memory records and failed jobs" actions={<>
        <Field label="Search" value={q} onChange={(e) => setQ(e.target.value)} type="search" />
        <SelectField label="Level" value={level} onChange={(e) => setLevel(e.target.value)}><option value="">Any</option><option>INFO</option><option>WARNING</option><option>ERROR</option></SelectField>
      </>}>
        {logs.error && !logs.data ? <ErrorState error={logs.error} onRetry={logs.reload} /> : !logs.data ? <LoadingBlock rows={4} />
          : <DataTable columns={logCols} rows={logRows.map((l, i) => ({ ...l, _i: i })) as (LogRecord & Record<string, unknown>)[]} rowKey={(l) => String(l._i)} maxHeight={420} emptyText="No log records match." caption="Server log" />}
      </Panel>
    </div>
  );
}
