// Datasets: provenance, quality and distributions of the NASA s-Flame test-point table, and a row browser.
import { useMemo, useState } from "react";
import { Alert, DataTable, Kv, LoadingBlock, MetricCard, Panel, SelectField, SubNav, type Column } from "../design-system";
import { api } from "../services/api";
import { useAsync } from "../hooks";
import { Histogram } from "../charts";
import { ErrorState, PageHead } from "../components/common";
import { date, fmt, pct } from "../lib/format";
import type { TestPointRow } from "../types/api";

const SHOW = ["test_point", "test_day", "round", "flow_programme", "atmosphere_inert", "initial_x_H2", "initial_x_CH4", "initial_x_C2H4", "initial_total_slpm", "outcome", "flame_duration_s", "nasa_stop_reason", "quality_flags"];

function Bars({ counts }: { counts: Record<string, number> }) {
  const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1;
  const max = Math.max(1, ...Object.values(counts));
  return (
    <div className="stack-s">
      {Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([k, v]) => (
        <div key={k} style={{ display: "grid", gridTemplateColumns: "minmax(120px, 34%) 1fr 92px", gap: 10, alignItems: "center" }}>
          <span className="data-s">{k.replace(/_/g, " ")}</span>
          <div style={{ height: 12, background: "var(--surface-sunken)", borderRadius: 4 }}><div style={{ height: "100%", width: `${(v / max) * 100}%`, background: "var(--chart-1)", borderRadius: 4 }} /></div>
          <span className="data-s" style={{ textAlign: "right" }}>{v} · {pct(v / total)}</span>
        </div>
      ))}
    </div>
  );
}

export default function Datasets() {
  const [tab, setTab] = useState("overview");
  const ds = useAsync(() => api.datasets(), []);
  const stats = useAsync(() => api.datasetStats(), []);
  const [variable, setVariable] = useState("flame_duration_s");
  const [outcome, setOutcome] = useState("");
  const [day, setDay] = useState("");
  const rows = useAsync(() => api.testPoints({ outcome: outcome || undefined, test_day: day || undefined }), [outcome, day], tab === "browse");
  const meta = ds.data?.datasets[0];
  const q = stats.data?.quality_report ?? meta?.quality_report ?? null;
  const v = stats.data?.variables.find((x) => x.name === variable);
  const days = useMemo(() => (stats.data?.variables.find((x) => x.name === "test_day")?.top_values ?? []).map(([d]) => d).sort(), [stats.data]);

  if (ds.error) return <div className="page"><PageHead eyebrow="Data" title="Datasets" /><ErrorState error={ds.error} onRetry={ds.reload} /></div>;
  if (!ds.data) return <div className="page"><PageHead eyebrow="Data" title="Datasets" /><LoadingBlock rows={8} /></div>;
  if (!meta) return (
    <div className="page"><PageHead eyebrow="Data" title="Datasets" />
      <Alert tone="warn" title="No processed dataset on this server">Download the NASA PSI-23 raw files with <code>python -m backend.data.psi_client</code> (see docs/DATA_AVAILABILITY_MATRIX.md), then build with <code>python -m backend.data.sflame_dataset</code>.</Alert></div>
  );

  const cols: Column<TestPointRow>[] = SHOW.filter((c) => meta.columns.includes(c)).map((c) => ({
    key: c, label: c.replace(/^initial_/, "").replace(/_/g, " "), numeric: typeof rows.data?.rows[0]?.[c] === "number",
    render: (r: TestPointRow) => { const x = r[c]; return typeof x === "number" ? fmt(x, c.startsWith("initial_x") ? 3 : 2) : x == null || x === "" ? "—" : String(x); },
  }));

  return (
    <div className="page">
      <PageHead eyebrow="Data" title={meta.title}
        lede={<>Built from NASA Physical Sciences Informatics (PSI) ACME s-Flame raw files. Flame on/off times come from the OH* photomultiplier, not from video. {meta.provenance.license}; no NASA endorsement is implied.</>} />
      <div className="grid g-4">
        <MetricCard label="Test-point runs" quantity="measured" value={meta.rows} footnote={`${meta.source_files} source files · ${meta.file_format}`} />
        <MetricCard label="Completeness" value={stats.data ? pct(stats.data.completeness, 1) : undefined} loading={stats.loading} footnote="Non-missing cells over all columns" />
        <MetricCard label="Duplicate rows" value={stats.data?.duplicate_rows} loading={stats.loading} footnote={stats.data ? `${stats.data.duplicate_test_points ?? 0} repeated test-point IDs (re-runs are kept as <id>_1)` : undefined} />
        <MetricCard label="Built" value={meta.built_at ? date(meta.built_at, false) : undefined} footnote={meta.provenance.doi} />
      </div>
      <SubNav items={[{ id: "overview", label: "Quality" }, { id: "variables", label: "Variables" }, { id: "browse", label: "Browse rows" }, { id: "provenance", label: "Provenance & import" }]} active={tab} onChange={setTab} />

      {tab === "overview" && (q ? (
        <div className="grid g-2">
          <Panel title="Outcomes" eyebrow="Classified from the PMT signal"><Bars counts={q.outcomes} /></Panel>
          <Panel title="Quality flags" eyebrow="Rows may carry several"><Bars counts={q.flag_counts} /></Panel>
          <Panel title="Outcome vs. NASA stop reason" eyebrow="Cross-check" className="span-all">
            <DataTable columns={[{ key: "outcome", label: "Outcome" }, ...Object.keys(Object.values(q.outcome_vs_nasa_stop_reason)[0] ?? {}).map((k) => ({ key: k, label: k, numeric: true }))]}
              rows={Object.entries(q.outcome_vs_nasa_stop_reason).map(([o, r]) => ({ outcome: o, ...r }))} rowKey={(r) => String(r.outcome)} caption="Outcome against NASA stop reason" />
          </Panel>
          <Panel title="Corrections and discrepancies" eyebrow="Applied or noted during the build">
            {q.experimental_table_corrections.map((c) => <Alert key={c["Test Day"]} tone="info" title={`Test day ${c["Test Day"]}`}>{c.corrections}</Alert>)}
            {q.known_source_discrepancies.map((d) => <Alert key={d} tone="warn" title="Source discrepancy">{d}</Alert>)}
            {!q.experimental_table_corrections.length && !q.known_source_discrepancies.length && <p className="body-s subtle">None.</p>}
          </Panel>
          <Panel title="Caveats" eyebrow="Read before analysis"><ul className="body-s muted" style={{ margin: 0, paddingLeft: 18 }}>{q.caveats.map((c) => <li key={c}>{c}</li>)}</ul></Panel>
        </div>
      ) : <p className="body-s subtle">No quality report was produced with this build.</p>)}

      {tab === "variables" && (stats.error ? <ErrorState error={stats.error} onRetry={stats.reload} /> : !stats.data ? <LoadingBlock rows={6} /> : (
        <div className="grid g-side-main">
          <Panel title="Variable" eyebrow={`${stats.data.columns} columns`}>
            <SelectField label="Column" value={variable} onChange={(e) => setVariable(e.target.value)}>
              {stats.data.variables.map((x) => <option key={x.name} value={x.name}>{x.name}</option>)}
            </SelectField>
            {v && <Kv rows={[["Kind", v.kind], ["Unit", v.unit ?? "—"], ["Missing", pct(v.missing_fraction, 1)],
              ...(v.kind === "numeric" ? [["Mean ± sd", `${fmt(v.mean, 3)} ± ${fmt(v.std, 3)}`], ["Median", fmt(v.median, 3)], ["Range", `${fmt(v.min, 3)} to ${fmt(v.max, 3)}`], ["IQR outliers", v.outliers_iqr ?? 0]] as [string, string | number][] : [])]} />}
          </Panel>
          <Panel title={variable} eyebrow="Distribution">
            {v?.kind === "numeric" && v.histogram ? <Histogram counts={v.histogram.counts} edges={v.histogram.edges} label={v.name} unit={v.unit} height={260} />
              : v?.top_values ? <Bars counts={Object.fromEntries(v.top_values)} /> : <p className="body-s subtle">No values.</p>}
          </Panel>
        </div>
      ))}

      {tab === "browse" && (
        <Panel title="Test points" eyebrow={rows.data ? `${rows.data.total} matching rows` : "Filter and sort"}>
          <div className="form-grid">
            <SelectField label="Outcome" value={outcome} onChange={(e) => setOutcome(e.target.value)}>
              <option value="">Any</option>{Object.keys(q?.outcomes ?? {}).map((o) => <option key={o}>{o}</option>)}
            </SelectField>
            <SelectField label="Test day" value={day} onChange={(e) => setDay(e.target.value)}>
              <option value="">Any</option>{days.map((d) => <option key={d}>{d}</option>)}
            </SelectField>
          </div>
          {rows.error ? <ErrorState error={rows.error} onRetry={rows.reload} /> : !rows.data ? <LoadingBlock rows={8} />
            : <DataTable columns={cols} rows={rows.data.rows} rowKey={(r) => String(r.test_point)} maxHeight={600} initialSort={{ key: "test_point", dir: "asc" }} emptyText="No rows match these filters." caption="Test points" />}
        </Panel>
      )}

      {tab === "provenance" && (
        <div className="grid g-2">
          <Panel title="Provenance" eyebrow="Source">
            <Kv rows={[["Source", meta.provenance.source], ["Licence", meta.provenance.license], ["DOI", meta.provenance.doi], ["Build", meta.provenance.build], ["Built at", date(meta.built_at)], ["Format", meta.file_format]]} />
          </Panel>
          <Panel title="Flame detection settings" eyebrow="Used to classify outcomes">
            <pre className="code">{JSON.stringify(meta.detection_config ?? {}, null, 2)}</pre>
          </Panel>
          <Panel title="Rebuild or import" eyebrow="Command line, on the server" className="span-all">
            <p className="body-s muted">Imports run on the server, not in the browser, so raw NASA files never pass through this page and every build is reproducible from the manifest of input file hashes.</p>
            <pre className="code">{`# 1. download PSI-23 raw files; repeat --match for _TP.txt, _data.csv and _mfcSetpoints.csv,
#    plus the experimental table (see docs/DATA_AVAILABILITY_MATRIX.md)
python -m backend.data.psi_client PSI-23 --match _TP.txt --dest data/raw
# 2. rebuild the test-point table and quality report
python -m backend.data.sflame_dataset --raw data/raw/PSI-23 --out data/processed
# 3. retrain and re-validate the lifetime model
python -m backend.ml.sflame_model train`}</pre>
            <span className="body-s subtle">Restart the API afterwards to load the new table and model.</span>
          </Panel>
        </div>
      )}
    </div>
  );
}
