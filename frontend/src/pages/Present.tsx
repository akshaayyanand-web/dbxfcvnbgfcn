// Guided demonstration: a 15-step walk through the real product using the synthetic demo and the NASA samples.
// Steps that create data call the same API as the rest of the app; nothing is pre-seeded or edited in the database.
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, Button, LoadingBlock, Panel, StatusPill } from "../design-system";
import { api, errorMessage } from "../services/api";
import { useAsync } from "../hooks";
import { useApp } from "../store/app";
import { PageHead } from "../components/common";
import type { Experiment } from "../types/api";

interface Step { title: string; say: string; show: string; to?: string; sample?: string; compare?: boolean; tp?: string }

const STEPS: Step[] = [
  { title: "Mission Control", to: "/dashboard", say: "One screen for the state of the workspace: experiments, running analyses, the lifetime model's held-out score, and recent activity.", show: "The hero card quotes the model's held-out C-index and its large absolute error side by side." },
  { title: "Where the data comes from", to: "/datasets", say: "Every s-Flame test-point run, built from NASA PSI raw files (CC0). Flame on/off comes from the OH* photomultiplier, not from video.", show: "Quality tab: outcomes, flags, and the corrections applied to NASA's experimental table." },
  { title: "Create the demo experiment", sample: "SYNTHETIC/demo", say: "Analyse the synthetic video: a generated flame with a known radius law. It is labelled synthetic everywhere so it cannot be mistaken for a measurement.", show: "Press the button; the experiment is created through the normal API and queued." },
  { title: "Watch it analyse", to: "/video-analysis", say: "Frames stream over a WebSocket as they are measured, with the contour, centroid and radius drawn on the frame the server decoded.", show: "Processing panel: progress, frame rate, transport (WebSocket or polling fallback)." },
  { title: "Scrub and inspect frames", to: "/video-analysis", say: "Step frame by frame with the arrow keys. Each analysed frame shows its status, confidence and per-frame uncertainty.", show: "Toggle overlay layers; click the chart to jump to a moment." },
  { title: "Calibration", to: "/video-analysis", say: "Sizes become millimetres only through a calibration: a known length clicked on the frame or entered. Its uncertainty is carried as a systematic term.", show: "Calibration panel; without it everything stays in pixels." },
  { title: "Flame analytics", to: "/analytics/flame", say: "Radius, dr/dt, area, volume, shape and drift as small multiples, each on its own axis, with ±1σ bands.", show: "Quantity tags: image-derived vs calculated. The uncertainty budget splits random and systematic parts." },
  { title: "Check against known truth", to: "/analytics/flame", say: "The synthetic video's true radius is known, so the measured curve is a direct accuracy check of the pipeline (about 0.01 px radius bias in the test suite).", show: "Statistics table: compare the measured growth with the generator's law in SCIENTIFIC_ASSUMPTIONS.md." },
  { title: "A real ISS flame", sample: "PSI-23/19254C1", say: "Now NASA test point 19254C1, a hollow spherical ethylene flame. The burner sphere (6.35 mm) in the image provides the calibration.", show: "Needs the raw NASA images on the server; if they are not downloaded the button says so." },
  { title: "Shell limb vs. area radius", to: "/analytics/flame", say: "For hollow shells the area-equivalent radius under-measures by about 12 %; the limb fit follows the visible shell edge.", show: "Radius panel: both curves; extinction marked from the camera, 0.17 s from the PMT time." },
  { title: "Compare", to: "/comparison", compare: true, say: "Overlay the synthetic and the real flame, aligned at first detection.", show: "Colours follow each experiment; units fall back to pixels if either is uncalibrated." },
  { title: "Predict a lifetime", to: "/prediction", tp: "19254C1", say: "From conditions known before ignition, the survival model gives a median lifetime and a calibrated 80 % interval, flagged when inputs leave the training range.", show: "The observed NASA lifetime is shown next to the prediction, with the drivers of the estimate." },
  { title: "How good is the model?", to: "/models", say: "The held-out C-index says how well it ranks conditions; R² on ln(lifetime) says how well it predicts absolute values, and it is shown even though it is negative.", show: "Predicted vs observed, censored runs marked as lower bounds." },
  { title: "Write it up", to: "/reports", say: "Generate a report from stored results: methodology, measurements, uncertainty, model evaluation and limitations, as PDF, JSON and CSV.", show: "Preview renders the same content the PDF contains." },
  { title: "Operations", to: "/system", say: "Health, resources, the job queue and the server log, so a failure is visible and explainable.", show: "Everything shown in the demo came from these services." },
];

export default function Present() {
  const nav = useNavigate();
  const { setExperiment, setComparison, notify } = useApp();
  const [i, setI] = useState(0);
  const [busy, setBusy] = useState(false);
  const samples = useAsync(() => api.samples(), []);
  const exps = useAsync(() => api.experiments(), []);
  const step = STEPS[i];
  const existing = (sid: string): Experiment | undefined => exps.data?.find((e) => e.dataset_ref === sid);
  const sample = step.sample ? samples.data?.find((s) => s.id === step.sample) : undefined;

  const runSample = async (sid: string) => {
    setBusy(true);
    try { const j = await api.analyzeSample(sid); setExperiment(j.experiment_id); notify("info", "Analysis queued", sid); exps.reload(); nav("/video-analysis"); }
    catch (e) { notify("bad", "Could not start", errorMessage(e)); } finally { setBusy(false); }
  };
  const go = () => {
    if (step.compare) {
      const ids = ["SYNTHETIC/demo", "PSI-23/19254C1"].map((s) => existing(s)?.id).filter(Boolean) as string[];
      if (ids.length) setComparison(ids);
    }
    if (step.to) nav(step.tp ? `${step.to}?tp=${step.tp}` : step.to);
  };

  return (
    <div className="page">
      <PageHead eyebrow="Guided demonstration" title="From a frame to a forecast"
        lede="Fifteen steps through the live product. Each step opens the real page; the two data steps run real analyses through the API. Synthetic data is labelled as such throughout." />
      <div className="present">
        <Panel>
          <ol aria-label="Demo steps">
            {STEPS.map((s, k) => <li key={s.title}><button aria-current={k === i ? "step" : undefined} onClick={() => setI(k)}><span className="n">{String(k + 1).padStart(2, "0")}</span><span>{s.title}</span></button></li>)}
          </ol>
        </Panel>
        <Panel title={step.title} eyebrow={`Step ${i + 1} of ${STEPS.length}`}>
          <p className="body" style={{ fontSize: 19, lineHeight: "28px", maxWidth: 720 }}>{step.say}</p>
          <p className="body-s muted">{step.show}</p>
          {step.sample && (samples.loading || exps.loading ? <LoadingBlock rows={2} /> : (
            <div className="stack-s">
              {existing(step.sample) && <Alert tone="info" title="Already in this workspace">{existing(step.sample)!.name} · <StatusPill state={existing(step.sample)!.status} /></Alert>}
              {sample && !sample.available && <Alert tone="warn" title="Raw files not on this server">{sample.download_hint ?? "Download the NASA files to enable this step."}</Alert>}
              {!sample && <Alert tone="warn" title="Sample not registered">{step.sample} is not in data/presets/samples.json.</Alert>}
            </div>
          ))}
          <div className="row">
            {step.sample && existing(step.sample) && <Button variant="ink" onClick={() => { setExperiment(existing(step.sample!)!.id); nav("/video-analysis"); }}>Open existing</Button>}
            {step.sample && <Button variant="lime" busy={busy} disabled={!sample?.available} onClick={() => runSample(step.sample!)}>{existing(step.sample) ? "Analyse again" : "Run analysis"}</Button>}
            {step.to && <Button variant={step.sample ? "outline" : "lime"} onClick={go}>Open {step.to.replace("/", "").replace("-", " ")}</Button>}
          </div>
          <hr className="divider" />
          <div className="row-between">
            <Button variant="ghost" disabled={i === 0} onClick={() => setI(i - 1)}>Previous</Button>
            <Button variant="ink" disabled={i === STEPS.length - 1} onClick={() => setI(i + 1)}>Next step</Button>
          </div>
        </Panel>
      </div>
    </div>
  );
}
