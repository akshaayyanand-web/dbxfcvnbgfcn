// Page-level building blocks shared by several pages.
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Alert, Button, EmptyState, Eyebrow, MetricCard, StatusPill } from "../design-system";
import { api } from "../services/api";
import { useAsync } from "../hooks";
import { useApp } from "../store/app";
import { fmt, fmtSigma, pct } from "../lib/format";
import type { AnalysisResult, Experiment, ProcessingJob, ValidationIssue } from "../types/api";

export function PageHead({ eyebrow, title, lede, actions }: { eyebrow: string; title: ReactNode; lede?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-head">
      <div><Eyebrow>{eyebrow}</Eyebrow><h1>{title}</h1>{lede && <p className="lede">{lede}</p>}</div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry, title = "Could not load this data" }: { error: string; onRetry?: () => void; title?: string }) {
  return (
    <div className="stack-s">
      <Alert tone="bad" title={title}>{error}</Alert>
      {onRetry && <div><Button size="sm" onClick={onRetry}>Retry</Button></div>}
    </div>
  );
}

export function NoExperiment({ what }: { what: string }) {
  return (
    <EmptyState eyebrow="No experiment selected" title={`Select an experiment to see ${what}.`}
      body="Use the experiment selector in the bar above, or start from the experiment list. The guided demo can create one from the synthetic sample."
      action={<div className="row"><Link to="/experiments"><Button variant="ink" arrow>Experiments</Button></Link><Link to="/present"><Button>Guided demo</Button></Link></div>} />
  );
}

/** Experiment, its jobs, and the result of its most recent completed job. */
export function useExperimentBundle(id: string | null | undefined, contours = false) {
  const exp = useAsync(() => api.experiment(id!), [id], !!id);
  const jobs = useAsync(() => api.experimentJobs(id!), [id], !!id);
  const completed = jobs.data?.find((j) => j.status === "completed");
  const running = jobs.data?.find((j) => j.status === "processing" || j.status === "queued");
  const result = useAsync(() => api.jobResult(completed!.id, contours), [completed?.id, contours], !!completed);
  const reload = () => { exp.reload(); jobs.reload(); };
  return { exp, jobs, completed, running, result, reload };
}

export function useCurrentExperimentBundle(contours = false) {
  const id = useApp((s) => s.experimentId);
  return { id, ...useExperimentBundle(id, contours) };
}

export function IssueList({ issues, limit = 12 }: { issues: ValidationIssue[]; limit?: number }) {
  if (!issues.length) return <Alert tone="ok" title="No validation issues were raised for this analysis." />;
  const order = { error: 0, warning: 1, info: 2 } as const;
  const sorted = [...issues].sort((a, b) => order[a.severity] - order[b.severity]);
  return (
    <div className="stack-s">
      {sorted.slice(0, limit).map((i, k) => (
        <Alert key={k} tone={i.severity === "error" ? "bad" : i.severity === "warning" ? "warn" : "info"} title={i.code.replace(/_/g, " ")}>
          {i.message}{i.frame_index != null ? ` (frame ${i.frame_index})` : ""}
        </Alert>
      ))}
      {sorted.length > limit && <span className="body-s subtle">{sorted.length - limit} more issues are in the exported result.</span>}
    </div>
  );
}

/** The headline measurement cards for an analysis. Uncalibrated analyses show px and say so. */
export function SummaryCards({ result }: { result: AnalysisResult }) {
  const s = result.summary;
  const mm = s.calibrated;
  const peak = s.peak_radius;
  const limb = s.radius_method === "limb";
  const r = limb ? (mm ? s.limb_radius_mm : s.limb_radius_px) : (mm ? s.radius_mm : s.equivalent_radius_px);
  const vel = mm ? s.expansion_velocity_mm_s : s.expansion_velocity_px_s;
  const [pr, ps] = fmtSigma(peak?.radius_mm ?? null, peak?.radius_sigma_mm ?? null);
  const ext = s.extinction;
  return (
    <div className="grid g-4">
      <MetricCard label={limb ? "Shell-limb radius, max" : "Peak equivalent radius"} quantity="image_derived" tone="raised"
        value={limb ? fmt(r?.max, 2) : mm ? pr : fmt(peak?.equivalent_radius_px, 1)} unit={mm ? "mm" : "px"} sigma={!limb && mm ? ps : undefined}
        footnote={limb ? `${s.limb_fits_ok ?? 0} accepted limb fits` : peak ? `at t = ${fmt(peak.timestamp_s, 2)} s` : "No accepted frames"} />
      <MetricCard label="Mean expansion velocity" quantity="calculated" tone="raised" value={fmt(vel?.mean, 2)} unit={mm ? "mm/s" : "px/s"}
        footnote={vel ? `range ${fmt(vel.min, 2)} to ${fmt(vel.max, 2)}` : "Too few accepted frames for derivatives"} />
      <MetricCard label="Extinction (camera)" quantity="image_derived" tone={ext.status === "observed" ? "lime" : "raised"}
        value={ext.time_s != null ? fmt(ext.time_s, 2) : undefined} unit="s" sigma={ext.uncertainty_s != null ? fmt(ext.uncertainty_s, 2) : undefined}
        footnote={ext.message} />
      <MetricCard label="Detection rate" quantity="calculated" tone="raised" value={pct(s.detection_rate)}
        footnote={`${s.frames_analyzed} of ${s.frames_decoded} decoded frames analysed · circularity ${fmt(s.circularity?.mean, 2)}`} />
    </div>
  );
}

export function JobStatusLine({ job }: { job: ProcessingJob }) {
  return <span className="row"><StatusPill state={job.status} /><span className="body-s muted">{job.message || job.error}</span></span>;
}

export function DataClassPill({ exp }: { exp: Pick<Experiment, "data_class"> }) {
  return exp.data_class === "synthetic" ? <span className="fif-qtag fif-qtag-simulated">Synthetic demo</span>
    : exp.data_class === "nasa_psi" ? <span className="fif-qtag fif-qtag-measured">NASA PSI data</span>
      : <span className="fif-qtag fif-qtag-calculated">User upload</span>;
}
