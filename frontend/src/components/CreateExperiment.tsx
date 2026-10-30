// Three-step experiment creation: details, conditions and calibration, then the input (upload, sample, or none).
import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, Button, Dialog, Field, Progress, SelectField, TextArea } from "../design-system";
import { api, errorMessage } from "../services/api";
import { useAsync } from "../hooks";
import { useApp } from "../store/app";
import type { Calibration, ExperimentCreate } from "../types/api";

const STEPS = ["Details", "Conditions", "Input"];
const num = (s: string) => (s.trim() === "" ? null : Number(s));

export default function CreateExperiment({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: () => void }) {
  const nav = useNavigate();
  const { notify, setExperiment } = useApp();
  const [step, setStep] = useState(0);
  const [f, setF] = useState({ name: "", description: "", fuel_type: "", oxygen_fraction: "", chamber_pressure_kpa: "", burn_duration_s: "", known_mm: "", measured_px: "", camera: "" });
  const [input, setInput] = useState<"none" | "upload" | "sample">("upload");
  const [file, setFile] = useState<File | null>(null);
  const [sampleId, setSampleId] = useState("");
  const [busy, setBusy] = useState(false);
  const [upload, setUpload] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const samples = useAsync(() => api.samples(), [], open);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });

  const ox = num(f.oxygen_fraction);
  const errors: Partial<Record<keyof typeof f, string>> = {};
  if (step >= 0 && f.name.trim() === "") errors.name = "A name is required.";
  if (ox != null && (Number.isNaN(ox) || ox < 0 || ox > 1)) errors.oxygen_fraction = "A mole fraction between 0 and 1.";
  for (const k of ["chamber_pressure_kpa", "burn_duration_s", "known_mm", "measured_px"] as const) {
    const v = num(f[k]);
    if (v != null && (Number.isNaN(v) || v <= 0)) errors[k] = "Must be a positive number.";
  }
  if ((f.known_mm === "") !== (f.measured_px === "")) errors.measured_px = "Give both the known length and its pixel length, or neither.";
  const stepValid = step === 0 ? !errors.name : step === 1 ? !errors.oxygen_fraction && !errors.chamber_pressure_kpa && !errors.burn_duration_s && !errors.known_mm && !errors.measured_px
    : input === "upload" ? !!file : input === "sample" ? !!sampleId : true;

  const reset = () => { setStep(0); setF({ name: "", description: "", fuel_type: "", oxygen_fraction: "", chamber_pressure_kpa: "", burn_duration_s: "", known_mm: "", measured_px: "", camera: "" }); setFile(null); setSampleId(""); setError(null); setUpload(null); };
  const close = () => { if (!busy) { reset(); onClose(); } };

  const submit = async () => {
    setBusy(true); setError(null);
    try {
      const calibration: Calibration | null = f.known_mm && f.measured_px ? { known_length_mm: Number(f.known_mm), measured_length_px: Number(f.measured_px), method: "manual entry" } : null;
      const body: ExperimentCreate = {
        name: f.name.trim(), description: f.description, fuel_type: f.fuel_type || null, oxygen_fraction: ox,
        chamber_pressure_kpa: num(f.chamber_pressure_kpa), burn_duration_s: num(f.burn_duration_s), calibration,
        camera: f.camera ? { description: f.camera } : null,
      };
      const exp = await api.createExperiment(body);
      if (input === "upload" && file) {
        setUpload(0);
        await api.analyzeVideo(file, { experimentId: exp.id, calibration }, setUpload);
        notify("info", "Upload complete, analysis queued", exp.name);
      } else if (input === "sample") {
        await api.analyzeSample(sampleId, exp.id);
        notify("info", "Sample analysis queued", exp.name);
      } else notify("ok", "Experiment created", `${exp.name} (draft, no input yet)`);
      setExperiment(exp.id);
      onCreated(); reset(); onClose();
      nav(input === "none" ? `/experiments/${exp.id}` : "/video-analysis");
    } catch (e) { setError(errorMessage(e)); } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onClose={close} title="New experiment" wide
      footer={<>
        {step > 0 && <Button variant="ghost" onClick={() => setStep(step - 1)} disabled={busy}>Back</Button>}
        {step < 2 ? <Button variant="ink" onClick={() => setStep(step + 1)} disabled={!stepValid}>Continue</Button>
          : <Button variant="lime" onClick={submit} busy={busy} disabled={!stepValid}>{input === "none" ? "Create draft" : "Create and analyse"}</Button>}
      </>}>
      <ol className="steps" style={{ margin: 0, padding: 0 }}>{STEPS.map((s, i) => <li key={s} className={i < step ? "done" : undefined} aria-current={i === step ? "step" : undefined}>{s}</li>)}</ol>
      {step === 0 && (
        <div className="stack">
          <Field label="Name" value={f.name} onChange={set("name")} error={f.name ? null : errors.name && "Required"} placeholder="e.g. Ethylene 21 % O2, run 3" autoFocus />
          <TextArea label="Description" value={f.description} onChange={set("description")} placeholder="Purpose, setup, anything a reviewer should know" />
          <Field label="Camera / optics (free text)" value={f.camera} onChange={set("camera")} placeholder="e.g. 1280×720 colour, 30 fps" />
        </div>
      )}
      {step === 1 && (
        <div className="stack">
          <div className="form-grid">
            <Field label="Fuel" value={f.fuel_type} onChange={set("fuel_type")} placeholder="e.g. C2H4" />
            <Field label="Oxygen mole fraction" value={f.oxygen_fraction} onChange={set("oxygen_fraction")} inputMode="decimal" error={errors.oxygen_fraction} placeholder="0.21" />
            <Field label="Chamber pressure" unit="kPa" value={f.chamber_pressure_kpa} onChange={set("chamber_pressure_kpa")} inputMode="decimal" error={errors.chamber_pressure_kpa} />
            <Field label="Burn duration" unit="s" value={f.burn_duration_s} onChange={set("burn_duration_s")} inputMode="decimal" error={errors.burn_duration_s} />
          </div>
          <Alert tone="info" title="Calibration (optional)">Without it, sizes are reported in pixels only. You can also calibrate later by clicking two points on a frame in Video Intelligence.</Alert>
          <div className="form-grid">
            <Field label="Known length" unit="mm" value={f.known_mm} onChange={set("known_mm")} inputMode="decimal" error={errors.known_mm} hint="e.g. burner diameter 6.35" />
            <Field label="Same length in image" unit="px" value={f.measured_px} onChange={set("measured_px")} inputMode="decimal" error={errors.measured_px} />
          </div>
        </div>
      )}
      {step === 2 && (
        <div className="stack">
          <SelectField label="Input" value={input} onChange={(e) => setInput(e.target.value as typeof input)}>
            <option value="upload">Upload a video</option>
            <option value="sample">Analyse a bundled sample</option>
            <option value="none">No input yet (draft)</option>
          </SelectField>
          {input === "upload" && (
            <div className="dropzone" role="button" tabIndex={0} onClick={() => fileRef.current?.click()} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") fileRef.current?.click(); }}
              onDragOver={(e) => { e.preventDefault(); e.currentTarget.classList.add("is-over"); }} onDragLeave={(e) => e.currentTarget.classList.remove("is-over")}
              onDrop={(e) => { e.preventDefault(); e.currentTarget.classList.remove("is-over"); if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]); }}>
              <span className="title">{file ? file.name : "Drop a video here or choose a file"}</span>
              <span className="body-s subtle">{file ? `${(file.size / 1e6).toFixed(1)} MB` : "MP4, MOV or AVI. The server checks the file contents, not just the extension. Image sequences (TIFF) are analysed with the command-line tool."}</span>
              <input ref={fileRef} type="file" hidden accept=".mp4,.avi,.mov" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </div>
          )}
          {input === "sample" && (
            <SelectField label="Sample" value={sampleId} onChange={(e) => setSampleId(e.target.value)} hint="NASA samples need their raw files downloaded on the server; unavailable ones are disabled.">
              <option value="">Choose…</option>
              {samples.data?.map((s) => <option key={s.id} value={s.id} disabled={!s.available}>{s.title}{s.available ? "" : " (not downloaded)"}</option>)}
            </SelectField>
          )}
          {upload != null && <Progress value={upload} label="Uploading" state={upload >= 1 ? "completed" : "processing"} />}
        </div>
      )}
      {error && <Alert tone="bad" title="Could not create the experiment">{error}</Alert>}
    </Dialog>
  );
}
