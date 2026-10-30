// Predictive Intelligence: lifetime of an s-Flame test point from its pre-ignition conditions, with the
// cross-validated interval, extrapolation warnings, per-feature contributions, and a check against held-out NASA runs.
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Alert, Button, DataTable, EmptyState, Field, IntervalBar, Kv, LoadingBlock, MetricCard, Panel, SelectField, type Column } from "../design-system";
import { api, errorMessage } from "../services/api";
import { useAsync } from "../hooks";
import { useApp } from "../store/app";
import { DivergingBars } from "../charts";
import { ErrorState, PageHead } from "../components/common";
import { date, fmt } from "../lib/format";
import type { ModelMetadata, PredictionRecord, PredictionResult } from "../types/api";

type Inputs = { x_H2: string; x_CH4: string; x_C2H4: string; total_slpm: string; he_atmosphere: "0" | "1"; test_order_in_day: string };
const EMPTY: Inputs = { x_H2: "0", x_CH4: "0", x_C2H4: "0.17", total_slpm: "0.5", he_atmosphere: "0", test_order_in_day: "1" };

function toFeatures(f: Inputs): Record<string, number> {
  return { x_H2: Number(f.x_H2), x_CH4: Number(f.x_CH4), x_C2H4: Number(f.x_C2H4), log_total_slpm: Math.log(Number(f.total_slpm)), he_atmosphere: Number(f.he_atmosphere), test_order_in_day: Number(f.test_order_in_day) };
}
function fromFeatures(x: Record<string, number>): Inputs {
  return { x_H2: String(+x.x_H2.toFixed(4)), x_CH4: String(+x.x_CH4.toFixed(4)), x_C2H4: String(+x.x_C2H4.toFixed(4)), total_slpm: String(+Math.exp(x.log_total_slpm).toFixed(4)),
    he_atmosphere: x.he_atmosphere >= 0.5 ? "1" : "0", test_order_in_day: String(x.test_order_in_day) };
}

/** Contribution of each standardized feature to ln(lifetime), relative to the mean training condition. */
function contributions(model: ModelMetadata, x: Record<string, number>) {
  return model.features.map((f, j) => {
    const z = (x[f.name] - model.standardizer.mean[j]) / model.standardizer.std[j];
    return { label: f.name, value: model.coef[j + 1] * z, detail: f.description };
  });
}

export default function Prediction() {
  const { experimentId, notify } = useApp();
  const models = useAsync(() => api.models(), []);
  const cv = useAsync(() => api.cvPredictions(), []);
  const history = useAsync(() => api.predictions(), []);
  const [f, setF] = useState<Inputs>(EMPTY);
  const [level, setLevel] = useState("0.8");
  const [tp, setTp] = useState("");
  const [linkExp, setLinkExp] = useState(true);
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<PredictionResult | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const model = models.data?.models[0];
  const ref = cv.data?.rows.find((r) => r.test_point === tp);
  const [params] = useSearchParams();
  useEffect(() => {
    const want = params.get("tp");
    const row = want ? cv.data?.rows.find((r) => r.test_point === want) : undefined;
    if (row) { setTp(row.test_point); setF(fromFeatures(row as unknown as Record<string, number>)); }
  }, [cv.data, params]);

  useEffect(() => { setRes(null); }, [f]);
  const x = toFeatures(f);
  const errors: Partial<Record<keyof Inputs, string>> = {};
  for (const k of ["x_H2", "x_CH4", "x_C2H4"] as const) if (!(x[k] >= 0 && x[k] <= 1)) errors[k] = "0 to 1";
  if (!(Number(f.total_slpm) > 0)) errors.total_slpm = "Must be positive";
  if (!(x.test_order_in_day >= 1 && Number.isInteger(x.test_order_in_day))) errors.test_order_in_day = "A whole number ≥ 1";
  const fuelSum = x.x_H2 + x.x_CH4 + x.x_C2H4;
  if (fuelSum > 1 + 1e-9) errors.x_C2H4 = "Fuel fractions sum above 1";
  const valid = !Object.keys(errors).length;
  const contrib = useMemo(() => (model && valid ? contributions(model, x) : []), [model, valid, f]); // eslint-disable-line react-hooks/exhaustive-deps
  const range = (k: string) => model?.feature_ranges[k];

  const run = async () => {
    setBusy(true); setErr(null);
    try {
      const out = await api.predict(x, linkExp && experimentId ? experimentId : undefined, Number(level));
      setRes(out); history.reload();
      notify("ok", "Prediction saved", `median ${fmt(out.median_lifetime_s, 1)} s`);
    } catch (e) { setErr(errorMessage(e)); } finally { setBusy(false); }
  };

  const histCols: Column<PredictionRecord & Record<string, unknown>>[] = [
    { key: "created_at", label: "When", render: (p) => date(p.created_at) },
    { key: "inputs", label: "Inputs", sortable: false, render: (p) => <span className="data-s">H₂ {fmt(p.inputs.x_H2, 2)} · CH₄ {fmt(p.inputs.x_CH4, 2)} · C₂H₄ {fmt(p.inputs.x_C2H4, 2)} · {fmt(Math.exp(p.inputs.log_total_slpm), 2)} SLPM · {p.inputs.he_atmosphere ? "He" : "N₂"} · #{p.inputs.test_order_in_day}</span> },
    { key: "median", label: "Median (s)", numeric: true, sortValue: (p) => p.result.median_lifetime_s, render: (p) => fmt(p.result.median_lifetime_s, 2) },
    { key: "interval", label: "Interval (s)", numeric: true, sortable: false, render: (p) => `${fmt(p.result.interval.lower_s, 1)}–${fmt(p.result.interval.upper_s, 1)}` },
    { key: "warn", label: "Flags", numeric: true, sortValue: (p) => p.result.warnings.length, render: (p) => p.result.warnings.length || "—" },
  ];

  if (models.error || models.data?.error) return <div className="page"><PageHead eyebrow="Prediction" title="Predictive intelligence" /><ErrorState error={models.error ?? models.data!.error!} onRetry={models.reload} title="No prediction model available" /></div>;
  if (!model) return <div className="page"><PageHead eyebrow="Prediction" title="Predictive intelligence" /><LoadingBlock rows={6} /></div>;

  return (
    <div className="page">
      <PageHead eyebrow="Prediction" title="How long will it burn?"
        lede={<>Predicts the burning lifetime of an s-Flame constant-flow test point from conditions known before ignition. The model ranks conditions well (held-out C-index {fmt(model.validation.selected.c_index, 2)}) but absolute lifetimes are often off by about a factor of two; the interval is widened to the coverage measured on held-out days. <Link to="/models">Model evidence</Link>.</>} />
      <div className="grid g-side-main">
        <Panel title="Conditions" eyebrow="Pre-ignition inputs">
          <SelectField label="Start from a NASA test point (held out in CV)" value={tp} onChange={(e) => {
            setTp(e.target.value);
            const row = cv.data?.rows.find((r) => r.test_point === e.target.value);
            if (row) setF(fromFeatures(row as unknown as Record<string, number>));
          }} hint="Fills the inputs with that run's nominal conditions so you can compare with what happened.">
            <option value="">Manual entry</option>
            {cv.data?.rows.map((r) => <option key={r.test_point} value={r.test_point}>{r.test_point} · {r.event ? `extinguished at ${fmt(r.time_s, 1)} s` : `still burning at ${fmt(r.time_s, 1)} s`}</option>)}
          </SelectField>
          <div className="form-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
            {(["x_H2", "x_CH4", "x_C2H4"] as const).map((k) => (
              <Field key={k} label={`${k.slice(2)} mole fraction`} value={f[k]} onChange={(e) => { setF({ ...f, [k]: e.target.value }); setTp(""); }} inputMode="decimal" error={errors[k]}
                hint={range(k) ? `trained ${fmt(range(k)!.min, 2)}–${fmt(range(k)!.max, 2)}` : undefined} />
            ))}
            <Field label="Total fuel-line flow" unit="SLPM" value={f.total_slpm} onChange={(e) => { setF({ ...f, total_slpm: e.target.value }); setTp(""); }} inputMode="decimal" error={errors.total_slpm}
              hint={range("log_total_slpm") ? `trained ${fmt(Math.exp(range("log_total_slpm")!.min), 3)}–${fmt(Math.exp(range("log_total_slpm")!.max), 2)}; N₂-equivalent indicated` : undefined} />
            <SelectField label="Chamber inert" value={f.he_atmosphere} onChange={(e) => { setF({ ...f, he_atmosphere: e.target.value as "0" | "1" }); setTp(""); }}>
              <option value="0">Nitrogen (round 1)</option><option value="1">Helium (round 2)</option>
            </SelectField>
            <Field label="Order of test within the day" value={f.test_order_in_day} onChange={(e) => { setF({ ...f, test_order_in_day: e.target.value }); setTp(""); }} inputMode="numeric" error={errors.test_order_in_day} hint="vitiation proxy, 1–25 trained" />
          </div>
          <span className="body-s subtle">Remaining {fmt(Math.max(0, 1 - fuelSum), 3)} of the fuel line is diluent. Oxygen is not an input: it was not recorded per test on mixed-O₂ days.</span>
          <SelectField label="Interval" value={level} onChange={(e) => setLevel(e.target.value)} hint={`Only the ${Math.round(model.interval_inflation.level * 100)} % interval was calibrated on held-out data.`}>
            <option value="0.5">50 %</option><option value="0.8">80 % (calibrated)</option><option value="0.9">90 %</option>
          </SelectField>
          {experimentId && <label className="fif-check"><input type="checkbox" checked={linkExp} onChange={(e) => setLinkExp(e.target.checked)} />Link to the experiment in context</label>}
          <Button variant="lime" busy={busy} disabled={!valid} onClick={run}>Predict lifetime</Button>
          {err && <Alert tone="bad" title="Prediction failed">{err}</Alert>}
        </Panel>

        <div className="stack">
          {res ? (<>
            <div className="grid g-3">
              <MetricCard label="Median lifetime" quantity="predicted" tone="lime" value={fmt(res.median_lifetime_s, 1)} unit="s" footnote={`model ${res.model_version}`} />
              <MetricCard label={`${Math.round(res.interval.level * 100)} % interval`} quantity="predicted" tone="raised" value={`${fmt(res.interval.lower_s, 1)}–${fmt(res.interval.upper_s, 1)}`} unit="s"
                footnote={`σ widened ×${fmt(res.interval.sigma_inflation_cross_validated, 2)} from held-out coverage`} />
              <MetricCard label="Observed (NASA)" quantity="measured" tone="raised" value={ref ? fmt(ref.time_s, 1) : undefined} unit="s"
                footnote={ref ? `${ref.test_point}: ${ref.event ? "extinguished (OH* PMT)" : "still burning when stopped; lifetime is longer"} · held-out prediction ${fmt(ref.pred_median_s, 1)} s` : "Choose a NASA test point to compare."} />
            </div>
            <Panel title="Prediction interval" eyebrow="Predicted, not measured">
              <IntervalBar median={res.median_lifetime_s} lower={res.interval.lower_s} upper={res.interval.upper_s} min={0}
                max={Math.max(res.interval.upper_s, ref?.time_s ?? 0) * 1.1} observed={ref?.time_s ?? null} unit="s" label="Lifetime" />
              {ref && !ref.event && <span className="body-s subtle">The observed mark is a lower bound: this flame was still burning when the test ended.</span>}
              {res.warnings.map((w) => <Alert key={w} tone="warn" title="Extrapolation">{w}</Alert>)}
              {!res.warnings.length && <Alert tone="ok" title="All inputs are inside the training ranges." />}
            </Panel>
          </>) : (
            <Panel title="Result" eyebrow="Predicted">
              <EmptyState title="Set the conditions and run a prediction." body="Results are stored with their inputs and model version so they can be reviewed later." />
            </Panel>
          )}
          <Panel title="What drives this estimate" eyebrow="Contribution to ln(lifetime) vs. the average training condition">
            {valid ? <DivergingBars rows={contrib} positiveLabel="longer" negativeLabel="shorter" /> : <p className="body-s subtle">Fix the inputs to see contributions.</p>}
            <span className="body-s subtle">Each bar is coefficient × standardized input. A bar of +0.69 doubles the median lifetime; −0.69 halves it. Associational, not causal.</span>
          </Panel>
          <Panel title="Not predicted" eyebrow="Out of scope">
            <Kv rows={[["Flame temperature", "Not available: no temperature data in the s-Flame records used."], ["Flame radius / growth", "Measured from video in Flame Analytics, not predicted."],
              ["Soot, radiation", "Not modelled."], ["Population", model.population]]} />
          </Panel>
        </div>
      </div>
      <Panel title="Prediction history" eyebrow="Stored predictions" actions={<Button size="sm" variant="ghost" onClick={history.reload}>Refresh</Button>}>
        {history.error ? <ErrorState error={history.error} onRetry={history.reload} /> : !history.data ? <LoadingBlock rows={3} />
          : <DataTable columns={histCols} rows={history.data as (PredictionRecord & Record<string, unknown>)[]} rowKey={(p) => p.id} initialSort={{ key: "created_at", dir: "desc" }}
            onRowClick={(p) => { setF(fromFeatures(p.inputs)); setTp(""); setTimeout(() => setRes(p.result), 0); }} emptyText="No predictions yet." caption="Prediction history" />}
      </Panel>
    </div>
  );
}
