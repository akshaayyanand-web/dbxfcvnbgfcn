// Reports: generate experiment or comparison reports from chosen sections, preview their content, download PDF/JSON/CSV.
import { useEffect, useState } from "react";
import { Alert, Button, DataTable, EmptyState, Field, Kv, LoadingBlock, Panel, Segmented, SelectField, StatusPill, type Column } from "../design-system";
import { api, downloadUrl, errorMessage } from "../services/api";
import { useAsync } from "../hooks";
import { useApp } from "../store/app";
import { TimeSeriesChart } from "../charts";
import { ErrorState, PageHead } from "../components/common";
import { date } from "../lib/format";
import type { ReportBlock, ScientificReport } from "../types/api";

export const SECTIONS: [string, string][] = [
  ["overview", "Experiment overview"], ["conditions", "Experimental conditions"], ["provenance", "Dataset provenance"], ["video", "Video specifications"],
  ["calibration", "Calibration"], ["cv_methodology", "Computer-vision methodology"], ["measurements", "Flame measurements"], ["temporal", "Temporal analysis"],
  ["model", "Predictive model"], ["model_evaluation", "Model evaluation"], ["uncertainty", "Uncertainty"], ["limitations", "Scientific limitations"], ["conclusions", "Conclusions"],
];

function Block({ b }: { b: ReportBlock }) {
  switch (b.type) {
    case "p": return <p className="body muted" style={{ maxWidth: 820 }}>{b.text}</p>;
    case "list": return <ul className="body muted" style={{ margin: 0, paddingLeft: 20 }}>{b.items.map((i) => <li key={i}>{i}</li>)}</ul>;
    case "kv": return <Kv rows={b.rows.map(([k, v]) => [k, typeof v === "object" && v !== null ? JSON.stringify(v) : String(v ?? "—")])} />;
    case "table": return (<div className="stack-s">{b.title && <span className="fif-label">{b.title}</span>}
      <DataTable columns={b.columns.map((c, i) => ({ key: String(i), label: c }))} rows={b.rows.map((r, k) => Object.fromEntries([["_k", k], ...r.map((v, i) => [String(i), v])]))} rowKey={(r) => String(r._k)} maxHeight={360} /></div>);
    case "figure": return <TimeSeriesChart title={b.title} xLabel={b.x} yLabel={b.y} height={240}
      series={b.series.map((s, i) => ({ id: `${b.id}-${i}`, name: s.name, kind: s.class, color: i, points: s.points.map(([x, y]) => ({ x, y })) }))} />;
    default: return null;
  }
}

export default function Reports() {
  const { experimentId, comparison, notify } = useApp();
  const list = useAsync(() => api.reports(), []);
  const exps = useAsync(() => api.experiments(), []);
  const [kind, setKind] = useState<"experiment" | "comparison">("experiment");
  const [exp, setExp] = useState(experimentId ?? "");
  const [sections, setSections] = useState<string[]>(SECTIONS.map(([s]) => s));
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const detail = useAsync(() => api.report(selected!), [selected], !!selected);
  useEffect(() => { if (!selected && list.data?.length) setSelected(list.data[0].id); }, [list.data, selected]);

  const create = async () => {
    setBusy(true);
    try {
      const r = kind === "experiment"
        ? await api.createReport({ experiment_id: exp, sections, title: title || undefined })
        : await api.createReport({ comparison_ids: comparison, title: title || undefined });
      if (r.status === "failed") notify("bad", "Report rendering failed", r.error ?? undefined); else notify("ok", "Report generated", r.title);
      list.reload(); setSelected(r.id);
    } catch (e) { notify("bad", "Report not generated", errorMessage(e)); } finally { setBusy(false); }
  };

  const cols: Column<ScientificReport & Record<string, unknown>>[] = [
    { key: "title", label: "Title" }, { key: "report_type", label: "Type" }, { key: "created_at", label: "Created", render: (r) => date(r.created_at) },
    { key: "status", label: "Status", render: (r) => <StatusPill state={r.status} /> },
    { key: "dl", label: "Download", sortable: false, render: (r) => <span className="row" onClick={(e) => e.stopPropagation()}>{r.formats.map((f) => <Button key={f} size="sm" variant="ghost" onClick={() => downloadUrl(api.reportDownloadUrl(r.id, f), `${r.title}.${f}`).catch((e) => notify("bad", "Download failed", errorMessage(e)))}>{f.toUpperCase()}</Button>)}</span> },
  ];
  const content = detail.data?.content;

  return (
    <div className="page">
      <PageHead eyebrow="Reports" title="Scientific reports" lede="Reports are assembled on the server from stored results only. Sections without data say so rather than being filled in. PDFs include the figures; JSON carries the full content; CSV carries per-frame measurements." />
      <div className="grid g-side-main">
        <Panel title="New report" eyebrow="Generate">
          <Segmented label="Report type" value={kind} onChange={setKind} options={[{ value: "experiment", label: "Experiment" }, { value: "comparison", label: "Comparison" }]} />
          {kind === "experiment" ? (<>
            <SelectField label="Experiment" value={exp} onChange={(e) => setExp(e.target.value)}>
              <option value="">Choose…</option>{exps.data?.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
            </SelectField>
            <fieldset style={{ border: 0, padding: 0, margin: 0 }} className="stack-s">
              <legend className="fif-label" style={{ marginBottom: 6 }}>Sections</legend>
              <div className="row"><Button size="sm" variant="ghost" onClick={() => setSections(SECTIONS.map(([s]) => s))}>All</Button><Button size="sm" variant="ghost" onClick={() => setSections([])}>None</Button></div>
              {SECTIONS.map(([id, label]) => <label key={id} className="fif-check"><input type="checkbox" checked={sections.includes(id)} onChange={() => setSections((s) => (s.includes(id) ? s.filter((x) => x !== id) : SECTIONS.map(([x]) => x).filter((x) => s.includes(x) || x === id)))} />{label}</label>)}
            </fieldset>
          </>) : comparison.length >= 2 ? <Alert tone="info" title={`${comparison.length} experiments selected`}>From the Comparison page or the experiment list.</Alert>
            : <Alert tone="warn" title="Select at least two experiments">Tick them in the experiment list or add them on the Comparison page.</Alert>}
          <Field label="Title (optional)" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={200} />
          <Button variant="lime" busy={busy} onClick={create} disabled={kind === "experiment" ? !exp || !sections.length : comparison.length < 2}>Generate report</Button>
        </Panel>
        <Panel title="Library" eyebrow={list.data ? `${list.data.length} reports` : "Generated reports"}>
          {list.error ? <ErrorState error={list.error} onRetry={list.reload} /> : !list.data ? <LoadingBlock rows={4} />
            : <DataTable columns={cols} rows={list.data as (ScientificReport & Record<string, unknown>)[]} rowKey={(r) => r.id} selectedKey={selected} onRowClick={(r) => setSelected(r.id)}
              initialSort={{ key: "created_at", dir: "desc" }} emptyText="No reports yet." caption="Reports" />}
        </Panel>
      </div>
      <Panel title={content?.title ?? "Preview"} eyebrow={detail.data ? `Generated ${date(content?.generated_at ?? detail.data.created_at)}` : "Select a report"}>
        {!selected ? <EmptyState title="Nothing to preview yet." body="Generate a report or select one from the library." />
          : detail.error ? <ErrorState error={detail.error} onRetry={detail.reload} /> : detail.loading ? <LoadingBlock rows={8} />
            : detail.data?.status === "failed" ? <Alert tone="bad" title="This report failed to render">{detail.data.error}</Alert>
              : content ? content.sections.map((s) => (
                <section key={s.id} className="stack" style={{ paddingBottom: 16, borderBottom: "1px solid var(--line)" }}>
                  <h3 className="title-l">{s.title}</h3>
                  {s.blocks.map((b, i) => <Block key={i} b={b} />)}
                </section>
              )) : <p className="body-s subtle">No content stored for this report.</p>}
      </Panel>
    </div>
  );
}
