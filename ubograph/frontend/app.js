/* UBOgraph frontend: search form, force-directed graph, entity table, report. */
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

const state = {
  payload: {nodes: [], edges: [], findings: [], ubos: []},
  report: null,
  filters: {bands: new Set(['red', 'orange', 'green']), type: '', flag: '', q: ''},
  sort: {key: 'risk_score', dir: -1},
  mediaFilter: '',
  countries: [],
  riskRatingOptions: null,
};

const canvas = $('#canvas'), ctx = canvas.getContext('2d');
let sim = {nodes: [], edges: []}, view = {x: 0, y: 0, k: 1};
let selected = null, highlight = new Set(), dragNode = null, panning = null, raf = null;

const css = (name) => getComputedStyle(document.body).getPropertyValue(name).trim();
const BAND_LABEL = {red: 'High risk', orange: 'Elevated risk', green: 'No flags found'};
const FLAG_LABEL = {
  sanctioned: 'sanctioned',
  sanction_linked: 'sanction-linked',
  pep: 'PEP',
  pep_associate: 'PEP associate',
  crime: 'crime',
  debarred: 'debarred',
  wanted: 'wanted',
  leak: 'leak',
};
const flagLabel = (flag) => FLAG_LABEL[flag] || flag.replace(/_/g, ' ');

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g,
    (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
}

/* ------------------------------------------------------------------ *
 * Reference data for the dropdowns
 * ------------------------------------------------------------------ */
async function loadReference() {
  const response = await fetch('/api/reference');
  const {countries, jurisdictions} = await response.json();
  state.countries = countries;
  fetch('/api/risk_rating/options').then((r) => r.json()).then((o) => { state.riskRatingOptions = o; });

  const nationality = $('#nationality');
  countries.forEach((c) => nationality.add(new Option(`${c.name} (${c.code.toUpperCase()})`, c.code)));

  const jurisdiction = $('#jurisdiction');
  const groups = new Map();
  jurisdictions.forEach((j) => {
    const key = j.group === 'Country' ? 'Countries' : j.group;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(j);
  });
  for (const [label, items] of groups) {
    const optgroup = document.createElement('optgroup');
    optgroup.label = label;
    items.forEach((j) => optgroup.appendChild(new Option(`${j.name} (${j.code})`, j.code)));
    jurisdiction.appendChild(optgroup);
  }

  const day = $('#dob_day'), month = $('#dob_month'), year = $('#dob_year');
  for (let d = 1; d <= 31; d++) day.add(new Option(String(d), String(d).padStart(2, '0')));
  ['January', 'February', 'March', 'April', 'May', 'June', 'July',
   'August', 'September', 'October', 'November', 'December']
    .forEach((name, index) => month.add(new Option(name, String(index + 1).padStart(2, '0'))));
  const thisYear = new Date().getFullYear();
  for (let y = thisYear; y >= 1900; y--) year.add(new Option(String(y), String(y)));
}

function birthDateValue() {
  const year = $('#dob_year').value, month = $('#dob_month').value, day = $('#dob_day').value;
  if (!year) return '';                       // year is the anchor; without it, send nothing
  if (!month) return year;                    // year alone is a valid partial date
  return day ? `${year}-${month}-${day}` : `${year}-${month}`;
}

/* ------------------------------------------------------------------ *
 * Status chips + search
 * ------------------------------------------------------------------ */
fetch('/api/status').then((r) => r.json()).then((s) => {
  const chips = [['OpenSanctions', s.opensanctions], ['OpenCorporates', s.opencorporates],
                 ['Adverse media', s.adverse_media]]
    .map(([label, on]) => `<span class="chip ${on ? 'on' : ''}">${label} ${on ? 'live' : 'off'}</span>`)
    .join('');
  $('#chips').innerHTML = chips + (s.demo_mode ? '<span class="chip demo">demo data</span>' : '');
});

function syncOptional() {
  const type = $('#entity_type').value;
  $$('[data-for]').forEach((block) => {
    block.style.display = (type === 'any' || block.dataset.for === type) ? '' : 'none';
  });
}
$('#entity_type').addEventListener('change', syncOptional);

$('#form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const params = new URLSearchParams();
  ['name', 'entity_type', 'nationality', 'reg_number', 'jurisdiction', 'hops']
    .forEach((id) => { const value = $('#' + id).value; if (value) params.set(id, value); });
  const dob = birthDateValue();
  if (dob) params.set('birth_date', dob);

  $('#go').disabled = true;
  $('#status').textContent = 'searching…';
  try {
    const response = await fetch('/api/search?' + params.toString());
    const payload = await response.json();
    if (payload.error) throw new Error(payload.error);
    render(payload);
  } catch (error) {
    $('#errors').innerHTML = `<div class="err">${escapeHtml(error.message)}</div>`;
    $('#status').textContent = 'error';
  } finally {
    $('#go').disabled = false;
  }
});

/* ------------------------------------------------------------------ *
 * Tabs
 * ------------------------------------------------------------------ */
function showTab(name) {
  ['graph', 'table', 'report'].forEach((tab) => {
    $('#tab-' + tab).setAttribute('aria-selected', String(tab === name));
    $('#pane-' + tab).classList.toggle('active', tab === name);
  });
  if (name === 'graph') resize();
}
['graph', 'table', 'report'].forEach((tab) => {
  $('#tab-' + tab).addEventListener('click', () => showTab(tab));
});

/* ------------------------------------------------------------------ *
 * Render a search result
 * ------------------------------------------------------------------ */
function render(payload) {
  state.payload = payload;
  state.report = null;
  selected = null;
  highlight = new Set();
  $('#errors').innerHTML = (payload.errors || [])
    .map((e) => `<div class="err"><b>${escapeHtml(e.source)}</b>: ${escapeHtml(e.message)}</div>`)
    .join('');
  $('#status').textContent = payload.matched
    ? `${payload.stats.node_count} entities · ${payload.stats.edge_count} relationships`
    : 'no match';
  renderEmptyState(payload);
  $('#report').innerHTML = '<p class="empty">Pick a name from the Table tab, or click a node on the graph.</p>';
  layout(payload);
  renderTable();
  renderSidebar(payload);
  showTab($('#tab-report').getAttribute('aria-selected') === 'true' ? 'table' : 'graph');
}

function renderEmptyState(payload) {
  const banner = $('#empty-state');
  if (payload.matched) { banner.style.display = 'none'; return; }
  const live = (payload.sources_used || []).filter((s) => s !== 'demo');
  banner.style.display = 'block';
  banner.innerHTML = live.length
    ? `<h3>No match for “${escapeHtml(payload.query.name || '')}”</h3>
       <p>Searched: ${escapeHtml(live.join(', '))}. Nothing in those sources matched this
       name with the identifiers given.</p>
       <p class="empty">Try removing an optional field (an exact birth date or jurisdiction
       will exclude a record that has the year only), or check the spelling used by the
       registry rather than the common transliteration.</p>`
    : `<h3>No sources configured</h3>
       <p>Add an API key to <code>.env</code> and restart the server to search live data.</p>`;
}

/* ------------------------------------------------------------------ *
 * Table
 * ------------------------------------------------------------------ */
const EDGE_PHRASE = {
  owns: 'Owner of',
  shareholder_of: 'Shareholder in',
  directs: 'Director of',
  registered_at: 'Registered at',
  linked_to: 'Linked to',
};
const REVERSE_PHRASE = {
  owns: 'Owned by',
  shareholder_of: 'Shares held by',
  directs: 'Directed by',
  registered_at: 'Registered office of',
  linked_to: 'Linked to',
};

function nameOf(id) {
  const node = (state.payload.nodes || []).find((n) => n.id === id);
  return node ? node.name : '';
}

function relationshipOf(node) {
  if (node.is_root) return 'Search match';
  const edges = (state.payload.edges || []).filter((e) => e.type !== 'possibly_same_as');

  const outgoing = edges.filter((e) => e.source === node.id);
  if (outgoing.length) {
    // Group by relationship type so a nominee reads "Director of 8 entities"
    // rather than naming whichever company happened to come first.
    const byType = {};
    outgoing.forEach((e) => { (byType[e.type] = byType[e.type] || []).push(e); });
    return Object.entries(byType).map(([type, group]) => {
      const phrase = EDGE_PHRASE[type] || type.replace(/_/g, ' ');
      if (group.length === 1) {
        const share = group[0].share_pct ? ` (${group[0].share_pct}%)` : '';
        return `${phrase} ${nameOf(group[0].target)}${share}`;
      }
      return `${phrase} ${group.length} entities`;
    }).join(' · ');
  }

  const incoming = edges.filter((e) => e.target === node.id);
  if (incoming.length) {
    const first = incoming[0];
    const phrase = REVERSE_PHRASE[first.type] || first.type.replace(/_/g, ' ');
    return incoming.length === 1
      ? `${phrase} ${nameOf(first.source)}`
      : `${phrase} ${incoming.length} entities`;
  }
  return '—';
}

function visibleRows() {
  const {bands, type, flag, q} = state.filters;
  const query = q.trim().toLowerCase();
  return (state.payload.nodes || [])
    .filter((n) => bands.has(n.risk_band))
    .filter((n) => !type || n.type === type)
    .filter((n) => {
      if (!flag) return true;
      const flags = n.risk_flags || [];
      return flag === 'none' ? flags.length === 0 : flags.includes(flag);
    })
    .filter((n) => !query || (n.name || '').toLowerCase().includes(query))
    .map((n) => ({...n, role: relationshipOf(n)}))
    .sort((a, b) => {
      const {key, dir} = state.sort;
      const av = key === 'flags' ? (a.risk_flags || []).join() : (a[key] ?? '');
      const bv = key === 'flags' ? (b.risk_flags || []).join() : (b[key] ?? '');
      if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * dir;
      return String(av).localeCompare(String(bv)) * dir;
    });
}

function renderTable() {
  const rows = visibleRows();
  $('#table-count').textContent =
    `${rows.length} of ${(state.payload.nodes || []).length} shown`;
  $('#table-body').innerHTML = rows.map((n) => `
    <tr>
      <td class="band ${n.risk_band}"></td>
      <td><button class="namebtn" data-node="${escapeHtml(n.id)}">${escapeHtml(n.name)}</button>
        ${n.is_root ? '<div class="empty" style="font-size:11px">search match</div>' : ''}</td>
      <td>${escapeHtml((n.type || '').replace(/^\w/, (c) => c.toUpperCase()))}</td>
      <td>${escapeHtml(n.role)}</td>
      <td>${escapeHtml(n.jurisdiction_label || n.country_label || n.jurisdiction || '')}</td>
      <td>${(n.risk_flags || []).map((f) =>
        `<span class="tag-flag ${f}">${escapeHtml(flagLabel(f))}</span>`).join('') || '<span class="empty">—</span>'}</td>
      <td class="num">${n.risk_score}</td>
    </tr>`).join('');
  $$('#table-body .namebtn').forEach((button) => {
    button.addEventListener('click', () => openReport(button.dataset.node));
  });
}

$$('.pill[data-band]').forEach((pill) => {
  pill.addEventListener('click', () => {
    const band = pill.dataset.band;
    const pressed = pill.getAttribute('aria-pressed') === 'true';
    pill.setAttribute('aria-pressed', String(!pressed));
    if (pressed) state.filters.bands.delete(band); else state.filters.bands.add(band);
    renderTable();
  });
});
$('#filter-type').addEventListener('change', (e) => { state.filters.type = e.target.value; renderTable(); });
$('#filter-flag').addEventListener('change', (e) => { state.filters.flag = e.target.value; renderTable(); });
$('#filter-q').addEventListener('input', (e) => { state.filters.q = e.target.value; renderTable(); });
$$('th[data-sort]').forEach((th) => {
  th.addEventListener('click', () => {
    const key = th.dataset.sort;
    state.sort = {key, dir: state.sort.key === key ? -state.sort.dir : (key === 'risk_score' ? -1 : 1)};
    $$('th[data-sort]').forEach((other) => other.removeAttribute('aria-sort'));
    th.setAttribute('aria-sort', state.sort.dir === 1 ? 'ascending' : 'descending');
    renderTable();
  });
});

/* ------------------------------------------------------------------ *
 * Report
 * ------------------------------------------------------------------ */
async function openReport(nodeId) {
  showTab('report');
  $('#report').innerHTML = '<p class="empty">Building report…</p>';
  const response = await fetch('/api/report', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({payload: state.payload, node_id: nodeId}),
  });
  const report = await response.json();
  if (report.error) {
    $('#report').innerHTML = `<p class="err">${escapeHtml(report.error)}</p>`;
    return;
  }
  state.report = report;
  renderReport(report);
  selected = nodeId;
  highlight = new Set([nodeId]);
  draw();
}

function affiliationTable(entries, emptyText) {
  if (!entries.length) return `<p class="empty">${emptyText}</p>`;
  return `<table><thead><tr>
      <th class="band"></th><th>Entity</th><th>Role</th><th>Stake</th>
      <th>Jurisdiction</th><th>Period</th></tr></thead><tbody>
    ${entries.map((a) => `<tr>
      <td class="band ${a.band}"></td>
      <td><button class="namebtn" data-node="${escapeHtml(a.id)}">${escapeHtml(a.name)}</button>
        ${(a.flags || []).map((f) => `<span class="tag-flag ${f}">${escapeHtml(flagLabel(f))}</span>`).join('')}</td>
      <td>${escapeHtml(a.detail_role || a.role)}</td>
      <td class="num">${escapeHtml(a.share || '—')}</td>
      <td>${escapeHtml(a.jurisdiction || '—')}</td>
      <td>${escapeHtml([a.start_date, a.end_date].filter(Boolean).join(' – ') || 'no dates recorded')}</td>
    </tr>`).join('')}</tbody></table>`;
}

const RATING_BAND_LABEL = {low: 'Low', medium: 'Medium', high: 'High'};

function countrySelect(id, label) {
  const opts = state.countries.map((c) =>
    `<option value="${escapeHtml(c.code)}">${escapeHtml(c.name)}</option>`).join('');
  return `<label for="${id}">${escapeHtml(label)}</label>
    <select id="${id}"><option value="">Select…</option>${opts}</select>`;
}

function optionSelect(id, label, choices) {
  const opts = (choices || []).map((c) =>
    `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');
  return `<label for="${id}">${escapeHtml(label)}</label>
    <select id="${id}"><option value="">Select…</option>${opts}</select>`;
}

function riskRatingHtml(report) {
  if (report.subject.type !== 'person' || !state.riskRatingOptions) return '';
  const o = state.riskRatingOptions;
  return `
    <h3>Client risk rating</h3>
    <p class="note">A separate, manual worksheet — the same weighted scoring rubric a
      real MLRO runs in a KYC risk-rating spreadsheet, not the graph-based score above.
      Nationality and the screening outcome come from this entity's own record;
      employment, payment and source of funds are KYC facts no public source carries,
      so fill them in from the client's file. Source: ${escapeHtml(o.source)}.</p>
    <div class="rating-form">
      ${countrySelect('rr-birth', 'Country of birth')}
      ${countrySelect('rr-residence', 'Country of residence')}
      ${countrySelect('rr-work', 'Business / work location')}
      ${optionSelect('rr-employment-type', 'Employment type', o.employment_type)}
      ${optionSelect('rr-employment-industry', 'Employment industry', o.employment_industry)}
      ${optionSelect('rr-payment', 'Mode of payment', o.mode_of_payment)}
      ${optionSelect('rr-funds', 'Source of funds / wealth', o.source_of_funds)}
    </div>
    <button class="ghost" id="rr-calculate" type="button">Calculate rating</button>
    <div id="rr-result"></div>`;
}

function renderRiskRating(result) {
  const rows = result.rows.map((r) => `<tr>
      <td>${escapeHtml(r.criterion)}</td>
      <td>${escapeHtml(r.selected || '—')}</td>
      <td class="num">${r.score ?? '—'}</td>
      <td class="num">${r.weight ?? '—'}</td>
      <td class="num">${r.weighted_score ?? '—'}</td>
    </tr>`).join('');
  const bandChip = result.band
    ? `<span class="band-chip ${result.band === 'low' ? 'green' : result.band === 'medium' ? 'orange' : 'red'}">
        ${RATING_BAND_LABEL[result.band]} risk — ${result.score} / 100</span>`
    : '<p class="empty">Select every field to compute a score.</p>';
  const missing = result.missing.length
    ? `<p class="note">Not yet scored: ${escapeHtml(result.missing.join(', '))}.</p>` : '';
  return `${bandChip}${missing}
    <table><thead><tr><th>Criterion</th><th>Selected</th><th>Score</th><th>Weight</th><th>Weighted</th></tr></thead>
      <tbody>${rows}</tbody></table>`;
}

function renderReport(report) {
  const s = report.subject;
  const facts = [
    ['Type', (s.type || '').replace(/^\w/, (c) => c.toUpperCase())],
    ['Nationality / country', s.country_label],
    ['Date of birth', s.birth_date],
    ['Jurisdiction', s.jurisdiction_label],
    ['Registration number', s.reg_number],
    ['Status', s.status],
    ['Risk flags', (s.flags || []).join(', ')],
    ['Risk score', `${s.risk_score} / 100`],
    ['Sources', (s.sources || []).join(', ')],
  ].filter(([, value]) => value);

  const media = report.media;
  const mediaCategories = media && media.findings
    ? [...new Set(media.findings.map((f) => f.category).filter(Boolean))] : [];

  $('#report').innerHTML = `
    <h2>${escapeHtml(s.name)}</h2>
    <p class="meta">Beneficial ownership &amp; risk report · generated ${escapeHtml(report.generated_at)}
      ${report.demo_mode ? ' · <b>sample data, not a real record</b>' : ''}</p>
    <span class="band-chip ${s.risk_band}">${BAND_LABEL[s.risk_band] || s.risk_band}</span>
    <div class="actions">
      <button class="ghost" id="download-pdf" type="button">Download PDF</button>
      <button class="ghost" id="back-to-table" type="button">Back to table</button>
    </div>
    <p>${escapeHtml(s.band_reason)}</p>

    <h3>Identifying details</h3>
    <dl class="facts">${facts.map(([k, v]) =>
      `<dt>${escapeHtml(k)}</dt><dd>${escapeHtml(String(v))}</dd>`).join('')}</dl>
    ${(s.source_urls || []).length ? `<dl class="facts">${s.source_urls.map((u) =>
      `<dt>Source</dt><dd><a href="${escapeHtml(u)}" target="_blank" rel="noopener">${escapeHtml(u)}</a></dd>`
    ).join('')}</dl>` : ''}

    ${dossierHtml(report)}

    <h3>Assessment</h3>
    ${(report.narrative || []).map((p) => `<p>${escapeHtml(p)}</p>`).join('')}

    ${(report.findings || []).length ? `<h3>Findings</h3>${report.findings.map((f) => `
      <div class="finding ${f.severity}">
        <div class="t"><span class="sev ${f.severity}">${escapeHtml(f.severity)}</span>${escapeHtml(f.title)}</div>
        <div class="d">${escapeHtml(f.detail)}</div>
      </div>`).join('')}` : ''}

    ${riskRatingHtml(report)}

    <h3>Current affiliations</h3>
    ${affiliationTable(report.affiliations.current, 'No current controlling roles in this network.')}
    <h3>Previous affiliations</h3>
    ${affiliationTable(report.affiliations.previous, 'None recorded as ended.')}
    <p class="note">${escapeHtml(report.end_date_note)}</p>

    ${(report.controllers || []).length ? `<h3>Controlled by</h3>
      ${report.controllers.map((c) => `<p>
        <button class="namebtn" data-node="${escapeHtml(c.id)}">${escapeHtml(c.name)}</button>
        — ${escapeHtml(c.role)}${c.share ? ` (${escapeHtml(c.share)})` : ''}</p>`).join('')}` : ''}

    ${(report.ownership_paths || []).length ? `<h3>Ownership route</h3>
      ${report.ownership_paths.map((p) =>
        `<p>${escapeHtml((p.path || []).join(' → '))}</p>`).join('')}` : ''}

    ${media && media.available ? `<h3>Open-web research (unverified)</h3>
      <div class="amber">
        <p class="warn">Retrieved by web search, not from a registry. Check every claim
          against its source before use.</p>
        ${media.error ? `<p>${escapeHtml(media.error)}</p>` : ''}
        <p>${escapeHtml(media.summary || '')}</p>
        ${mediaCategories.length ? `<label for="media-filter">Filter by category</label>
          <select id="media-filter">
            <option value="">All categories</option>
            ${mediaCategories.map((c) =>
              `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('')}
          </select>` : ''}
        <ul id="media-list">${mediaItems(media)}</ul>
      </div>` : ''}

    <p class="disclaimer">${escapeHtml(report.disclaimer)}</p>`;

  $('#download-pdf').addEventListener('click', downloadPdf);
  $('#back-to-table').addEventListener('click', () => showTab('table'));
  $$('#report .namebtn').forEach((button) => {
    button.addEventListener('click', () => openReport(button.dataset.node));
  });
  state.riskRatingInputs = null;
  const rrButton = $('#rr-calculate');
  if (rrButton) {
    rrButton.addEventListener('click', async () => {
      $('#rr-result').innerHTML = '<p class="empty">Calculating…</p>';
      const inputs = {
        country_of_birth: $('#rr-birth').value,
        country_of_residence: $('#rr-residence').value,
        business_work_location: $('#rr-work').value,
        employment_type: $('#rr-employment-type').value,
        employment_industry: $('#rr-employment-industry').value,
        mode_of_payment: $('#rr-payment').value,
        source_of_funds: $('#rr-funds').value,
      };
      const response = await fetch('/api/risk_rating', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({payload: state.payload, node_id: report.subject.id, ...inputs}),
      });
      const result = await response.json();
      $('#rr-result').innerHTML = result.error
        ? `<p class="err">${escapeHtml(result.error)}</p>` : renderRiskRating(result);
      if (!result.error) state.riskRatingInputs = inputs;
    });
  }
  const mediaFilter = $('#media-filter');
  if (mediaFilter) {
    mediaFilter.addEventListener('change', (event) => {
      state.mediaFilter = event.target.value;
      $('#media-list').innerHTML = mediaItems(report.media);
    });
  }
}

function dossierHtml(report) {
  const d = report.dossier;
  if (!d) {
    return report.dossier_error
      ? `<h3>Source detail</h3><p class="empty">${escapeHtml(report.dossier_error)}</p>`
      : '';
  }
  const lists = (d.datasets || []).map((x) =>
    x.url ? `<a href="${escapeHtml(x.url)}" target="_blank" rel="noopener">${escapeHtml(x.title)}</a>`
          : escapeHtml(x.title)).join(' · ');

  const merged = d.record_count > 1
    ? `<p class="note">Combined from ${d.record_count} source records
       (${(d.record_ids || []).map((i) => `<code>${escapeHtml(i)}</code>`).join(', ')}).
       Values appearing on more than one list are stated once.</p>`
    : '';

  const groups = (d.groups || []).map((g) => `
    <h3>${escapeHtml(g.title)}</h3>
    <dl class="facts">${g.rows.map((r) => `
      <dt>${escapeHtml(r.label)}</dt>
      <dd>${r.values.map((v) => escapeHtml(v)).join('<br>')}</dd>`).join('')}</dl>`).join('');

  const sanctions = (d.sanctions || []).map((s) => `
    <div class="sanction">
      <div class="t">${escapeHtml(s.program || s.authority || 'Sanction record')}</div>
      <dl class="facts">
        ${s.authority ? `<dt>Authority</dt><dd>${escapeHtml(s.authority)}</dd>` : ''}
        ${s.reason ? `<dt>Reason</dt><dd class="prose">${escapeHtml(s.reason)}</dd>` : ''}
        ${(s.provisions || []).length ? `<dt>Provisions</dt><dd>${s.provisions.map(escapeHtml).join('<br>')}</dd>` : ''}
        ${s.status ? `<dt>Status</dt><dd>${escapeHtml(s.status)}</dd>` : ''}
        ${s.listing_date ? `<dt>Listed</dt><dd>${escapeHtml(s.listing_date)}</dd>` : ''}
        ${s.start_date ? `<dt>Start date</dt><dd>${escapeHtml(s.start_date)}</dd>` : ''}
        ${s.end_date ? `<dt>End date</dt><dd>${escapeHtml(s.end_date)}</dd>` : ''}
        ${s.authority_id ? `<dt>Authority ref.</dt><dd>${escapeHtml(s.authority_id)}</dd>` : ''}
        ${s.unsc_id ? `<dt>UNSC ID</dt><dd>${escapeHtml(s.unsc_id)}</dd>` : ''}
        ${(s.datasets || []).length ? `<dt>List</dt><dd>${s.datasets.map((x) => escapeHtml(x.title)).join('<br>')}</dd>` : ''}
        ${s.source_url ? `<dt>Source</dt><dd><a href="${escapeHtml(s.source_url)}" target="_blank" rel="noopener">${escapeHtml(s.source_url)}</a></dd>` : ''}
      </dl>
    </div>`).join('');

  const relationships = (d.relationships || []).map((r) => `
    <tr><td>${escapeHtml(r.kind)}</td><td>${escapeHtml(r.role || '—')}</td>
    <td>${escapeHtml(r.name)}</td>
    <td>${escapeHtml([r.start_date, r.end_date].filter(Boolean).join(' – ') || '—')}</td></tr>`).join('');

  return `
    <h3>Source detail</h3>
    <p><b>Listed on:</b> ${lists || '<span class="empty">no dataset recorded</span>'}</p>
    ${merged}
    ${d.last_change ? `<p class="note">Source last changed ${escapeHtml(d.last_change)}
      · first seen ${escapeHtml(d.first_seen || 'unknown')}
      ${d.url ? `· <a href="${escapeHtml(d.url)}" target="_blank" rel="noopener">view on OpenSanctions</a>` : ''}</p>` : ''}
    ${groups}
    ${sanctions ? `<h3>Sanction records</h3>${sanctions}` : ''}
    ${relationships ? `<h3>Recorded relationships</h3>
      <table><thead><tr><th>Type</th><th>Role</th><th>Party</th><th>Period</th></tr></thead>
      <tbody>${relationships}</tbody></table>` : ''}`;
}

function mediaItems(media) {
  return (media.findings || [])
    .filter((f) => !state.mediaFilter || f.category === state.mediaFilter)
    .map((f) => `<li>${escapeHtml(f.claim || '')}
      ${f.source_url ? ` <a href="${escapeHtml(f.source_url)}" target="_blank" rel="noopener">${escapeHtml(f.source_title || 'source')}</a>` : ''}
      ${f.date ? ` <span class="empty">${escapeHtml(f.date)}</span>` : ''}</li>`).join('')
    || '<li class="empty">Nothing in this category.</li>';
}

async function downloadPdf() {
  const button = $('#download-pdf');
  button.disabled = true;
  button.textContent = 'Building PDF…';
  try {
    const response = await fetch('/api/report.pdf', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        payload: state.payload,
        node_id: state.report.subject.id,
        ...(state.riskRatingInputs || {}),
      }),
    });
    if (!response.ok) throw new Error('The server could not build the PDF.');
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `UBOgraph_${(state.report.subject.name || 'report').replace(/[^A-Za-z0-9]+/g, '_')}.pdf`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
  } catch (error) {
    alert(error.message);
  } finally {
    button.disabled = false;
    button.textContent = 'Download PDF';
  }
}

/* ------------------------------------------------------------------ *
 * Sidebar: findings + UBOs
 * ------------------------------------------------------------------ */
function renderSidebar(payload) {
  const parts = [];
  parts.push(`<div class="section"><h4>Red flags</h4>` + (
    (payload.findings || []).length
      ? payload.findings.map((f, i) => `<div class="finding ${f.severity}" data-finding="${i}">
          <div class="t"><span class="sev ${f.severity}">${escapeHtml(f.severity)}</span>${escapeHtml(f.title)}</div>
          <div class="d">${escapeHtml(f.detail)}</div></div>`).join('')
      : '<p class="empty">Nothing flagged in this subgraph.</p>') + '</div>');

  parts.push(`<div class="section"><h4>Candidate UBOs</h4>` + (
    (payload.ubos || []).length
      ? payload.ubos.map((u) => `<div class="ubo" data-node="${escapeHtml(u.id)}">
          <div class="n">${escapeHtml(u.name || '')}
            ${(u.risk_flags || []).map((f) => `<span class="tag-flag ${f}">${escapeHtml(flagLabel(f))}</span>`).join('')}</div>
          <div class="p">${u.tiers} tier${u.tiers === 1 ? '' : 's'} up ·
            ${escapeHtml((u.path || []).join(' → '))}</div></div>`).join('')
      : '<p class="empty">No natural person reachable through ownership edges. That absence is itself worth noting.</p>')
    + '</div>');

  $('#right').innerHTML = parts.join('');
  $$('#right [data-finding]').forEach((el) => {
    el.addEventListener('click', () => {
      const finding = payload.findings[+el.dataset.finding];
      highlight = new Set(finding.nodes || []);
      showTab('graph');
      draw();
    });
  });
  $$('#right [data-node]').forEach((el) => {
    el.addEventListener('click', () => openReport(el.dataset.node));
  });
}

/* ------------------------------------------------------------------ *
 * Force-directed graph
 * ------------------------------------------------------------------ */
function layout(payload) {
  const degree = {};
  payload.edges.forEach((e) => {
    degree[e.source] = (degree[e.source] || 0) + 1;
    degree[e.target] = (degree[e.target] || 0) + 1;
  });
  const width = canvas.clientWidth || 800, height = canvas.clientHeight || 600;
  sim.nodes = payload.nodes.map((n, i) => ({
    ...n,
    x: width / 2 + Math.cos(i) * (80 + i * 9),
    y: height / 2 + Math.sin(i) * (80 + i * 9),
    vx: 0, vy: 0,
    r: 6 + Math.min(12, Math.sqrt(degree[n.id] || 1) * 3.2) + (n.is_root ? 3 : 0),
  }));
  const index = Object.fromEntries(sim.nodes.map((n) => [n.id, n]));
  sim.edges = payload.edges
    .map((e) => ({...e, s: index[e.source], t: index[e.target]}))
    .filter((e) => e.s && e.t);
  view = {x: 0, y: 0, k: 1};
  tick(220);
}

function tick(steps) {
  cancelAnimationFrame(raf);
  let remaining = steps;
  const step = () => {
    for (let pass = 0; pass < 2; pass++) physics();
    draw();
    if (--remaining > 0) raf = requestAnimationFrame(step);
  };
  step();
}

function physics() {
  const width = canvas.clientWidth, height = canvas.clientHeight;
  const nodes = sim.nodes;
  for (let i = 0; i < nodes.length; i++) {
    const a = nodes[i];
    for (let j = i + 1; j < nodes.length; j++) {
      const b = nodes[j];
      const dx = b.x - a.x, dy = b.y - a.y;
      const dist2 = dx * dx + dy * dy || 0.01;
      if (dist2 > 90000) continue;
      const dist = Math.sqrt(dist2), force = 2600 / dist2;
      const fx = (dx / dist) * force, fy = (dy / dist) * force;
      a.vx -= fx; a.vy -= fy; b.vx += fx; b.vy += fy;
    }
  }
  sim.edges.forEach((e) => {
    const dx = e.t.x - e.s.x, dy = e.t.y - e.s.y;
    const dist = Math.hypot(dx, dy) || 0.01;
    const force = (dist - 110) * 0.012;
    const fx = (dx / dist) * force, fy = (dy / dist) * force;
    e.s.vx += fx; e.s.vy += fy; e.t.vx -= fx; e.t.vy -= fy;
  });
  sim.nodes.forEach((n) => {
    n.vx += (width / 2 - n.x) * 0.0016;
    n.vy += (height / 2 - n.y) * 0.0016;
    if (n === dragNode) { n.vx = n.vy = 0; return; }
    n.vx *= 0.82; n.vy *= 0.82;
    n.x += Math.max(-18, Math.min(18, n.vx));
    n.y += Math.max(-18, Math.min(18, n.vy));
  });
}

function resize() {
  const ratio = window.devicePixelRatio || 1;
  canvas.width = canvas.clientWidth * ratio;
  canvas.height = canvas.clientHeight * ratio;
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  draw();
}
window.addEventListener('resize', resize);

function draw() {
  const width = canvas.clientWidth, height = canvas.clientHeight;
  const ratio = window.devicePixelRatio || 1;
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);
  ctx.save();
  ctx.translate(view.x, view.y);
  ctx.scale(view.k, view.k);

  const dim = highlight.size > 0;
  sim.edges.forEach((e) => {
    const lit = !dim || (highlight.has(e.source) && highlight.has(e.target));
    ctx.globalAlpha = lit ? 1 : 0.14;
    ctx.strokeStyle = e.asserted ? css('--edge') : css('--link');
    ctx.lineWidth = e.asserted ? (e.share_pct ? 1.2 + e.share_pct / 60 : 1.3) : 1.4;
    ctx.setLineDash(e.asserted ? [] : [5, 4]);
    ctx.beginPath();
    ctx.moveTo(e.s.x, e.s.y);
    ctx.lineTo(e.t.x, e.t.y);
    ctx.stroke();
    if (e.asserted) arrow(e.s, e.t);
    ctx.setLineDash([]);
  });

  sim.nodes.forEach((n) => {
    const lit = !dim || highlight.has(n.id);
    ctx.globalAlpha = lit ? 1 : 0.16;
    ctx.beginPath();
    if (n.type === 'company') {
      ctx.rect(n.x - n.r, n.y - n.r, n.r * 2, n.r * 2);
    } else if (n.type === 'address') {
      ctx.moveTo(n.x, n.y - n.r); ctx.lineTo(n.x + n.r, n.y);
      ctx.lineTo(n.x, n.y + n.r); ctx.lineTo(n.x - n.r, n.y); ctx.closePath();
    } else {
      ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
    }
    ctx.fillStyle = css('--' + (n.risk_band || 'green'));
    ctx.fill();
    if (n.id === selected || n.is_root) {
      ctx.strokeStyle = css('--ink');
      ctx.lineWidth = n.id === selected ? 2.5 : 1.5;
      ctx.stroke();
    }
    if (n.r > 9 || lit) {
      ctx.fillStyle = css('--ink');
      ctx.font = '12px ui-sans-serif, system-ui, sans-serif';
      ctx.textAlign = 'center';
      const label = (n.name || '').length > 26 ? n.name.slice(0, 24) + '…' : (n.name || '');
      ctx.fillText(label, n.x, n.y + n.r + 13);
    }
  });
  ctx.globalAlpha = 1;
  ctx.restore();
}

function arrow(from, to) {
  const angle = Math.atan2(to.y - from.y, to.x - from.x);
  const tipX = to.x - Math.cos(angle) * (to.r + 3);
  const tipY = to.y - Math.sin(angle) * (to.r + 3);
  ctx.beginPath();
  ctx.moveTo(tipX, tipY);
  ctx.lineTo(tipX - Math.cos(angle - 0.4) * 7, tipY - Math.sin(angle - 0.4) * 7);
  ctx.lineTo(tipX - Math.cos(angle + 0.4) * 7, tipY - Math.sin(angle + 0.4) * 7);
  ctx.closePath();
  ctx.fillStyle = ctx.strokeStyle;
  ctx.fill();
}

function toWorld(event) {
  const rect = canvas.getBoundingClientRect();
  return {
    x: (event.clientX - rect.left - view.x) / view.k,
    y: (event.clientY - rect.top - view.y) / view.k,
  };
}
const nodeAt = (point) =>
  sim.nodes.find((n) => Math.hypot(n.x - point.x, n.y - point.y) <= n.r + 4);

canvas.addEventListener('mousedown', (event) => {
  const node = nodeAt(toWorld(event));
  if (node) dragNode = node;
  else panning = {x: event.clientX - view.x, y: event.clientY - view.y};
  canvas.classList.add('dragging');
});
canvas.addEventListener('mousemove', (event) => {
  const point = toWorld(event);
  if (dragNode) { dragNode.x = point.x; dragNode.y = point.y; tick(30); return; }
  if (panning) { view.x = event.clientX - panning.x; view.y = event.clientY - panning.y; draw(); return; }
  const node = nodeAt(point);
  canvas.title = node ? `${node.name} — ${BAND_LABEL[node.risk_band] || ''}` : '';
});
window.addEventListener('mouseup', () => {
  if (dragNode) tick(60);
  dragNode = null;
  panning = null;
  canvas.classList.remove('dragging');
});
canvas.addEventListener('click', (event) => {
  const node = nodeAt(toWorld(event));
  if (node) openReport(node.id);
  else { highlight = new Set(); selected = null; draw(); }
});
canvas.addEventListener('wheel', (event) => {
  event.preventDefault();
  const factor = event.deltaY < 0 ? 1.12 : 0.89;
  const rect = canvas.getBoundingClientRect();
  const mx = event.clientX - rect.left, my = event.clientY - rect.top;
  view.x = mx - (mx - view.x) * factor;
  view.y = my - (my - view.y) * factor;
  view.k = Math.max(0.25, Math.min(3.5, view.k * factor));
  draw();
}, {passive: false});

/* ------------------------------------------------------------------ */
syncOptional();
resize();
loadReference()
  .catch(() => { /* dropdowns stay empty; the search still works */ })
  .finally(() => $('#form').dispatchEvent(new Event('submit')));
