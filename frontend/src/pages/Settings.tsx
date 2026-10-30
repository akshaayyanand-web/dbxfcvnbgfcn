// Settings: workspace preferences stored on the server, browser-only preferences, the API key, and project docs.
import { useEffect, useState } from "react";
import { Alert, Button, Field, Kv, LoadingBlock, Panel, Segmented, SelectField, SubNav, TextArea } from "../design-system";
import { api, API_KEY_STORAGE, errorMessage } from "../services/api";
import { useAsync } from "../hooks";
import { useApp, type ThemePref } from "../store/app";
import Markdown from "../components/Markdown";
import { ErrorState, PageHead } from "../components/common";
import { bytes } from "../lib/format";
import type { WorkspaceSettings } from "../types/api";

function readKey() { try { return window.localStorage.getItem(API_KEY_STORAGE) ?? ""; } catch { return ""; } }

export default function Settings() {
  const { theme, setTheme, setUnits, notify } = useApp();
  const [tab, setTab] = useState("workspace");
  const st = useAsync(() => api.settings(), []);
  const models = useAsync(() => api.models(), []);
  const docs = useAsync(() => api.docs(), [], tab === "docs");
  const [docId, setDocId] = useState("readme");
  const doc = useAsync(() => api.doc(docId), [docId], tab === "docs");
  const [f, setF] = useState<WorkspaceSettings | null>(null);
  const [cfgText, setCfgText] = useState("");
  const [cfgErr, setCfgErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [key, setKey] = useState(readKey);

  useEffect(() => {
    if (st.data) { setF(st.data.settings); setCfgText(JSON.stringify(st.data.settings.default_analysis_config ?? {}, null, 2)); }
  }, [st.data]);

  const save = async () => {
    if (!f) return;
    let cfg;
    try { cfg = JSON.parse(cfgText || "{}"); setCfgErr(null); } catch (e) { setCfgErr(`Not valid JSON: ${(e as Error).message}`); return; }
    setBusy(true);
    try {
      await api.saveSettings({ ...f, default_analysis_config: cfg });
      setUnits(f.units); notify("ok", "Settings saved"); st.reload();
    } catch (e) { notify("bad", "Settings not saved", errorMessage(e)); } finally { setBusy(false); }
  };
  const saveKey = () => {
    try { if (key) window.localStorage.setItem(API_KEY_STORAGE, key); else window.localStorage.removeItem(API_KEY_STORAGE); notify("ok", key ? "API key stored in this browser" : "API key removed"); }
    catch { notify("bad", "This browser blocks local storage; the key cannot be kept."); }
  };

  return (
    <div className="page">
      <PageHead eyebrow="System" title="Settings" lede="Workspace settings are stored on the server and apply to everyone using it. Theme and API key are kept in this browser only." />
      <SubNav items={[{ id: "workspace", label: "Workspace" }, { id: "analysis", label: "Analysis defaults" }, { id: "access", label: "Access & appearance" }, { id: "docs", label: "Documentation" }]} active={tab} onChange={setTab} />
      {st.error ? <ErrorState error={st.error} onRetry={st.reload} /> : !f || !st.data ? <LoadingBlock rows={6} /> : (<>
        {tab === "workspace" && (
          <div className="grid g-2">
            <Panel title="Workspace" eyebrow="Shared">
              <Field label="Workspace name" value={f.workspace_name} onChange={(e) => setF({ ...f, workspace_name: e.target.value })} maxLength={80} />
              <div className="fif-field"><span className="fif-label">Default units</span><Segmented label="Default units" value={f.units} onChange={(u) => setF({ ...f, units: u })} options={[{ value: "mm", label: "Millimetres" }, { value: "px", label: "Pixels" }]} />
                <span className="fif-help">Millimetres are used only where an analysis is calibrated.</span></div>
              <div className="fif-field"><span className="fif-label">Dates</span><Segmented label="Date format" value={f.date_format} onChange={(d) => setF({ ...f, date_format: d })} options={[{ value: "local", label: "Local" }, { value: "iso", label: "ISO 8601 UTC" }]} /></div>
              <div className="fif-field"><span className="fif-label">Default export</span><Segmented label="Export format" value={f.export_format} onChange={(x) => setF({ ...f, export_format: x })} options={[{ value: "csv", label: "CSV" }, { value: "json", label: "JSON" }]} /></div>
              <SelectField label="Default prediction model" value={f.default_model} onChange={(e) => setF({ ...f, default_model: e.target.value })}>
                <option value={f.default_model}>{f.default_model}</option>
                {models.data?.models.filter((m) => m.model_version !== f.default_model).map((m) => <option key={m.model_version} value={m.model_version}>{m.model_version}</option>)}
              </SelectField>
              <div><Button variant="ink" busy={busy} onClick={save}>Save workspace settings</Button></div>
            </Panel>
            <Panel title="Server limits" eyebrow="Read-only (environment variables)">
              <Kv rows={[["Max upload", bytes(st.data.server.max_upload_mb * 1024 * 1024)], ["Analysis workers", st.data.server.max_workers], ["Rate limit", `${st.data.server.rate_limit_per_minute} requests/min per client`],
                ["Database", st.data.server.database_backend], ["Telemetry buffer", `${st.data.server.telemetry_buffer} events per job`], ["Writes need API key", st.data.server.auth_required_for_writes ? "yes" : "no"]]} />
            </Panel>
          </div>
        )}
        {tab === "analysis" && (
          <Panel title="Default analysis configuration" eyebrow="Applied to new experiments without their own configuration">
            <TextArea label="Configuration (JSON)" value={cfgText} onChange={(e) => setCfgText(e.target.value)} rows={16} spellCheck={false} style={{ fontFamily: "var(--font-mono)", fontSize: 13 }} />
            {cfgErr && <Alert tone="bad" title="Not saved">{cfgErr}</Alert>}
            <span className="body-s subtle">Keys follow AnalysisConfig (backend/vision/cv_engine.py), e.g. {"{"}"segmentation": {"{"}"method": "otsu"{"}"}, "frame_step": 2, "radius_method": "limb"{"}"}. The server validates them on save.</span>
            <div className="row"><Button variant="ink" busy={busy} onClick={save}>Save defaults</Button><Button variant="ghost" onClick={() => setCfgText("{}")}>Clear</Button></div>
          </Panel>
        )}
        {tab === "access" && (
          <div className="grid g-2">
            <Panel title="API key" eyebrow="This browser only">
              <Alert tone={st.data.server.auth_required_for_writes ? "warn" : "info"} title={st.data.server.auth_required_for_writes ? "This server requires a key for changes" : "This server accepts changes without a key"}>
                The key is sent as X-API-Key on write requests and stored in this browser's local storage. There are no user accounts.
              </Alert>
              <Field label="API key" type="password" value={key} onChange={(e) => setKey(e.target.value)} autoComplete="off" />
              <div className="row"><Button variant="ink" onClick={saveKey}>Save key</Button>{key && <Button variant="ghost" onClick={() => { setKey(""); try { window.localStorage.removeItem(API_KEY_STORAGE); } catch { /* blocked */ } notify("ok", "API key removed"); }}>Remove</Button>}</div>
            </Panel>
            <Panel title="Appearance" eyebrow="This browser only">
              <div className="fif-field"><span className="fif-label">Theme</span>
                <Segmented<ThemePref> label="Theme" value={theme} onChange={setTheme} options={[{ value: "system", label: "System" }, { value: "light", label: "Light" }, { value: "dark", label: "Dark" }]} /></div>
            </Panel>
          </div>
        )}
      </>)}
      {tab === "docs" && (
        <div className="grid g-side-main">
          <Panel title="Documents" eyebrow="From the repository">
            {docs.error ? <ErrorState error={docs.error} onRetry={docs.reload} /> : !docs.data ? <LoadingBlock rows={6} /> : (
              <div className="stack-s" role="tablist" aria-label="Documents">
                {docs.data.map((d) => <button key={d.id} role="tab" aria-selected={d.id === docId} className="fif-subnav-item" style={{ justifyContent: "flex-start" }} onClick={() => setDocId(d.id)}>{d.file}</button>)}
              </div>
            )}
          </Panel>
          <Panel>{doc.error ? <ErrorState error={doc.error} onRetry={doc.reload} /> : doc.loading || !doc.data ? <LoadingBlock rows={10} /> : <Markdown source={doc.data} />}</Panel>
        </div>
      )}
    </div>
  );
}
