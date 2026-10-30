// Model evidence: what the lifetime model was trained on, how it was validated, and where it is weak.
import { Alert, DataTable, Kv, LoadingBlock, MetricCard, Panel, type Column } from "../design-system";
import { api } from "../services/api";
import { useAsync } from "../hooks";
import { PredVsObsChart } from "../charts";
import { ErrorState, PageHead } from "../components/common";
import { date, fmt, pct } from "../lib/format";
import type { CandidateMetrics, CoefficientRow } from "../types/api";

export default function Models() {
  const models = useAsync(() => api.models(), []);
  const cv = useAsync(() => api.cvPredictions(), []);
  const m = models.data?.models[0];
  if (models.error || models.data?.error) return <div className="page"><PageHead eyebrow="Models" title="Model registry" /><ErrorState error={models.error ?? models.data!.error!} onRetry={models.reload} /></div>;
  if (!m) return <div className="page"><PageHead eyebrow="Models" title="Model registry" /><LoadingBlock rows={8} /></div>;
  const sel = m.validation.selected, base = m.validation.baseline_intercept_only;
  const met = cv.data?.metrics;

  const candCols: Column<CandidateMetrics & Record<string, unknown>>[] = [
    { key: "candidate", label: "Candidate", render: (c) => <span>{c.candidate}{c.candidate === sel.candidate && <span className="fif-chip" style={{ marginLeft: 8 }}>selected</span>}</span> },
    { key: "distribution", label: "Dist." }, { key: "features", label: "Features", sortable: false, render: (c) => <span className="data-s">{c.features.join(", ") || "none"}</span> },
    { key: "c_index", label: "C-index", numeric: true, render: (c) => fmt(c.c_index, 3) },
    { key: "c_index_within_day", label: "C within day", numeric: true, render: (c) => fmt(c.c_index_within_day, 3) },
    { key: "events_median_abs_error_s", label: "Median |err| (s)", numeric: true, render: (c) => fmt(c.events_median_abs_error_s, 2) },
    { key: "events_80pct_interval_coverage", label: "80 % coverage", numeric: true, render: (c) => pct(c.events_80pct_interval_coverage) },
    { key: "fold_failures", label: "Failed folds", numeric: true },
  ];
  const coefCols: Column<CoefficientRow & Record<string, unknown>>[] = [
    { key: "term", label: "Term" }, { key: "coef", label: "β (std.)", numeric: true, render: (c) => fmt(c.coef, 3) }, { key: "se", label: "SE", numeric: true, render: (c) => fmt(c.se, 3) },
    { key: "time_ratio", label: "Time ratio", numeric: true, render: (c) => fmt(c.time_ratio, 3) },
    { key: "ci", label: "95 % CI", numeric: true, sortable: false, render: (c) => `${fmt(c.time_ratio_ci95[0], 2)}–${fmt(c.time_ratio_ci95[1], 2)}` },
    { key: "p_value", label: "p", numeric: true, render: (c) => fmt(c.p_value, 3) },
  ];

  return (
    <div className="page">
      <PageHead eyebrow="Models" title={`Lifetime model ${m.model_version}`}
        lede={`${m.distribution === "lognormal" ? "Log-normal" : "Weibull"} accelerated-failure-time survival model with right-censoring, L2 ${m.l2}. Trained ${date(m.created_at)}; validated by ${m.validation.scheme}. ${m.converged ? "Optimiser converged." : "Optimiser did NOT converge."}`} />
      <div className="grid g-4">
        <MetricCard label="C-index, held-out days" quantity="calculated" tone="lime" value={fmt(sel.c_index, 2)} footnote={`baseline ${fmt(0.5, 2)} (no information); within-day ${fmt(sel.c_index_within_day, 2)}`} />
        <MetricCard label="Median absolute error" quantity="calculated" tone="raised" value={fmt(sel.events_median_abs_error_s, 1)} unit="s" footnote={`intercept-only baseline ${fmt(base.events_median_abs_error_s, 1)} s`} />
        <MetricCard label="R² on ln(lifetime)" quantity="calculated" tone="raised" value={met ? fmt(met.r2_log, 2) : undefined} loading={cv.loading}
          footnote={met ? `Negative: worse than predicting the mean, for absolute values. RMSE ${fmt(met.rmse_log, 2)} in ln units.` : undefined} />
        <MetricCard label="80 % interval coverage" quantity="calculated" tone="raised" value={pct(m.interval_inflation.coverage_after)}
          footnote={`${pct(m.interval_inflation.coverage_before)} before widening σ ×${fmt(m.interval_inflation.factor, 2)}`} />
      </div>
      <Alert tone="warn" title="Read this before using a prediction">The model orders conditions by expected lifetime better than chance, but it does not predict absolute lifetimes better than the training average. Intervals are calibrated on the same held-out predictions used to select the model (mildly optimistic).</Alert>
      <div className="grid g-main-side">
        <Panel title="Held-out predictions vs. observed" eyebrow={met ? `${met.n_events} extinguished · ${met.n_censored} censored` : "Leave-one-test-day-out"}>
          {cv.error ? <ErrorState error={cv.error} onRetry={cv.reload} /> : !cv.data ? <LoadingBlock rows={6} />
            : <PredVsObsChart points={cv.data.rows.map((r) => ({ id: r.test_point, group: r.group, observed: r.time_s, median: r.pred_median_s, q10: r.pred_q10_s, q90: r.pred_q90_s, event: r.event }))} />}
          {met && <span className="body-s subtle">{met.note}</span>}
        </Panel>
        <div className="stack">
          <Panel title="Target" eyebrow="What is predicted">
            <Kv rows={[["Name", m.target.name], ["Definition", m.target.definition], ["Censoring", m.target.censoring], ["Population", m.population]]} />
          </Panel>
          <Panel title="Training data" eyebrow="Provenance">
            <Kv rows={[["File", m.training_data.file], ["SHA-256", <span key="h" className="data-s">{m.training_data.sha256.slice(0, 16)}…</span>], ["Runs", m.training_data.n], ["Extinctions", m.training_data.n_events],
              ["Test days", m.training_data.test_days.length], ["Source", m.training_data.source]]} />
          </Panel>
        </div>
      </div>
      <Panel title="Model selection" eyebrow="All candidates, same folds">
        <DataTable columns={candCols} rows={[...m.validation.candidates, base] as (CandidateMetrics & Record<string, unknown>)[]} rowKey={(c) => `${c.candidate}-${c.distribution}`} selectedKey={`${sel.candidate}-${sel.distribution}`}
          initialSort={{ key: "c_index", dir: "desc" }} caption="Candidate models" />
        <span className="body-s subtle">{m.validation.baseline_note}</span>
      </Panel>
      <div className="grid g-2">
        <Panel title="Coefficients" eyebrow="Standardized inputs; time ratio = e^β">
          <DataTable columns={coefCols} rows={m.coefficient_table_standardized as (CoefficientRow & Record<string, unknown>)[]} rowKey={(c) => c.term} caption="Coefficients" />
        </Panel>
        <Panel title="Inputs and training ranges" eyebrow="Outside these, predictions are flagged">
          <Kv rows={m.features.map((f) => [f.name, <span key={f.name}>{f.description}<br /><span className="data-s subtle">{fmt(m.feature_ranges[f.name]?.min, 3)} to {fmt(m.feature_ranges[f.name]?.max, 3)} {f.unit !== "-" ? f.unit : ""}</span></span>])} />
        </Panel>
      </div>
      <Panel title="Limitations" eyebrow="Stated by the training pipeline">
        <ul className="body muted" style={{ margin: 0, paddingLeft: 20 }}>{m.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
      </Panel>
    </div>
  );
}
