// Mission Control: the state of the workspace at a glance, from live API data only.
import { Link, useNavigate } from "react-router-dom";
import { Button, DataTable, EmptyState, Kv, LoadingBlock, MetricCard, Panel, Progress, StatusPill, type Column } from "../design-system";
import { api } from "../services/api";
import { useAsync, usePolling } from "../hooks";
import { useApp } from "../store/app";
import { ActivityTimeline } from "../components/Activity";
import { DataClassPill, ErrorState, SummaryCards, useExperimentBundle } from "../components/common";
import { ago, bytes, DATA_CLASS_LABEL, fmt } from "../lib/format";
import type { Experiment } from "../types/api";

function Arcs() {
  return (
    <svg className="hero-arcs" viewBox="0 0 460 460" aria-hidden>
      {[60, 110, 160, 210].map((r, i) => <circle key={r} cx="230" cy="230" r={r} fill="none" stroke="#fff" strokeOpacity={0.5 - i * 0.1} strokeWidth={1.5} strokeDasharray={i % 2 ? "4 8" : undefined} />)}
      <circle cx="230" cy="230" r="18" fill="#d4f25a" />
    </svg>
  );
}

export default function Dashboard() {
  const nav = useNavigate();
  const { experimentId, setExperiment } = useApp();
  const status = usePolling(() => api.systemStatus(), 8000);
  const exps = usePolling(() => api.experiments({ limit: 8 }), 8000);
  const activity = usePolling(() => api.activity(12), 8000);
  const jobs = usePolling(() => api.jobs(undefined, 20), 3000);
  const models = useAsync(() => api.models(), []);
  const current = useExperimentBundle(experimentId);
  const model = models.data?.models[0];
  const s = status.data;
  const active = jobs.data?.filter((j) => j.status === "processing" || j.status === "queued") ?? [];

  const cols: Column<Experiment & Record<string, unknown>>[] = [
    { key: "name", label: "Experiment", render: (e) => <Link to={`/experiments/${e.id}`}>{e.name}</Link> },
    { key: "data_class", label: "Source", render: (e) => <DataClassPill exp={e} /> },
    { key: "status", label: "Status", render: (e) => <StatusPill state={e.status} /> },
    { key: "updated_at", label: "Updated", render: (e) => ago(e.updated_at) },
  ];

  return (
    <div className="page">
      <section className="hero" aria-labelledby="hero-title">
        <Arcs />
        <div style={{ position: "relative" }}>
          <span className="fif-label fif-eyebrow">Mission control</span>
          <h1 id="hero-title">Measure flames that have no up.</h1>
          <p className="lede">Track spherical microgravity flames frame by frame, quantify growth and extinction with propagated uncertainty, and estimate burning lifetime from conditions with a cross-validated survival model trained on NASA s-Flame test points.</p>
          <div className="hero-actions">
            <Button variant="lime" onClick={() => nav("/video-analysis")}>Analyse a flame</Button>
            <Button variant="outline" onClick={() => nav("/present")}>Guided demo</Button>
          </div>
        </div>
        <div className="hero-card">
          {model ? (<>
            <span className="fif-label">Lifetime model · {model.model_version}</span>
            <div className="big">{fmt(model.validation.selected.c_index, 2)}<span style={{ fontSize: 15, marginLeft: 6 }}>C-index, held-out days</span></div>
            <span className="body-s" style={{ color: "#3a414b" }}>Ranks which conditions burn longer (baseline 0.50). Absolute lifetime error is large: median {fmt(model.validation.selected.events_median_abs_error_s, 1)} s. Trained on {model.training_data.n} runs, {model.training_data.n_events} extinctions.</span>
            <div><Link to="/models" style={{ color: "#0a63b8" }}>Model evidence →</Link></div>
          </>) : models.loading ? <LoadingBlock rows={3} /> : (
            <><span className="fif-label">Lifetime model</span><span className="body-s" style={{ color: "#3a414b" }}>{models.data?.error ?? models.error ?? "No trained model is loaded on this server."}</span></>
          )}
        </div>
      </section>

      {status.error && !s && <ErrorState error={status.error} onRetry={status.reload} title="System status unavailable" />}
      <div className="grid g-4">
        <MetricCard label="Experiments" loading={!s && status.loading} value={s?.experiments.total} footnote={s ? Object.entries(s.experiments.by_status).map(([k, v]) => `${v} ${k}`).join(" · ") || "none yet" : undefined} />
        <MetricCard label="Analyses running" loading={!s && status.loading} value={s?.jobs.active} tone={s && s.jobs.active > 0 ? "ink" : "surface"} footnote={s ? `${s.jobs.workers} worker${s.jobs.workers === 1 ? "" : "s"} · ${s.processing.throughput_frames_per_s ? `${fmt(s.processing.throughput_frames_per_s, 1)} frames/s average` : "no timed jobs yet"}` : undefined} />
        <MetricCard label="NASA s-Flame test points" quantity="measured" loading={!s && status.loading} value={s?.datasets.sflame_test_points ?? undefined} footnote={<Link to="/datasets">Dataset quality and provenance</Link>} />
        <MetricCard label="Storage used" loading={!s && status.loading} value={s ? bytes(s.storage.used_by_app_bytes) : undefined} footnote={s ? `${bytes(s.storage.disk_free_bytes)} free · samples ${s.samples.available}/${s.samples.total} on disk` : undefined} />
      </div>

      {active.length > 0 && (
        <Panel title="Running now" eyebrow="Processing queue" actions={<Link to="/system"><Button size="sm">Queue</Button></Link>}>
          {active.map((j) => (
            <div key={j.id} className="stack-s">
              <div className="row-between"><Link to={`/experiments/${j.experiment_id}`}>{exps.data?.find((e) => e.id === j.experiment_id)?.name ?? j.experiment_id}</Link><StatusPill state={j.status} /></div>
              <Progress value={j.progress} label={`${j.frames_processed} frames`} state={j.status} />
            </div>
          ))}
        </Panel>
      )}

      <div className="grid g-main-side">
        <div className="stack">
          <Panel title={current.exp.data ? current.exp.data.name : "Current experiment"} eyebrow="In context"
            actions={current.exp.data && <><Link to={`/experiments/${current.exp.data.id}`}><Button size="sm">Details</Button></Link><Link to="/analytics/flame"><Button size="sm" variant="ink">Analytics</Button></Link></>}>
            {!experimentId ? <EmptyState title="No experiment in context." body="Pick one from the list below or the selector above; its latest measurements appear here." />
              : current.exp.error ? <ErrorState error={current.exp.error} onRetry={current.reload} />
                : current.result.data ? <>
                  <div className="row"><DataClassPill exp={current.exp.data!} />{current.exp.data!.data_class === "synthetic" && <span className="body-s subtle">Generated test video with known truth; not a real flame.</span>}</div>
                  <SummaryCards result={current.result.data} />
                </>
                  : current.running ? <Progress value={current.running.progress} label="Analysis in progress" state={current.running.status} />
                    : current.exp.loading || current.jobs.loading || current.result.loading ? <LoadingBlock rows={3} />
                      : <EmptyState title="This experiment has no completed analysis." body="Run one from Video Intelligence." action={<Link to="/video-analysis"><Button variant="ink" arrow>Video Intelligence</Button></Link>} />}
          </Panel>
          <Panel title="Recent experiments" eyebrow="Workspace" actions={<Link to="/experiments"><Button size="sm">All experiments</Button></Link>}>
            {exps.error && !exps.data ? <ErrorState error={exps.error} onRetry={exps.reload} />
              : !exps.data ? <LoadingBlock rows={4} />
                : <DataTable columns={cols} rows={exps.data as (Experiment & Record<string, unknown>)[]} rowKey={(e) => e.id} selectedKey={experimentId}
                  onRowClick={(e) => setExperiment(e.id)} emptyText="No experiments yet. Create one, or run the guided demo." caption="Recent experiments" />}
          </Panel>
        </div>
        <div className="stack">
          <Panel title="Activity" eyebrow="Timeline">
            {activity.error && !activity.data ? <ErrorState error={activity.error} onRetry={activity.reload} /> : !activity.data ? <LoadingBlock rows={5} /> : <ActivityTimeline events={activity.data} />}
          </Panel>
          <Panel title="System" eyebrow="Health" actions={<Link to="/system"><Button size="sm">Details</Button></Link>}>
            {s ? <Kv rows={[
              ["Database", <StatusPill key="d" state={s.database.ok ? "operational" : "unavailable"}>{s.database.backend}</StatusPill>],
              ["Prediction model", <StatusPill key="m" state={s.model.loaded ? "ready" : "unavailable"}>{s.model.version ?? "not loaded"}</StatusPill>],
              ["Video decoding", s.runtime.ffmpeg ? `FFmpeg + OpenCV ${s.runtime.opencv}` : `OpenCV ${s.runtime.opencv} (FFmpeg missing)`],
              ["Data classes", Object.values(DATA_CLASS_LABEL).join(" · ")],
            ]} /> : <LoadingBlock rows={4} />}
          </Panel>
        </div>
      </div>
    </div>
  );
}
