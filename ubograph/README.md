# Sanctions+

Maps multi-layered corporate ownership structures so a commercial or M&A lawyer can
see who ultimately controls a company — including through free-zone and offshore
intermediaries — and what should be checked before signing.

It pulls from sanctions and corporate registry APIs, resolves records that describe
the same real-world entity, builds one graph, runs red-flag detectors over it, and
presents the result three ways: an interactive **graph**, a filterable **table**, and
a per-entity **written report** you can download as a PDF.

---

## Run it

```bash
cd ubograph
./setup.sh                       # virtualenv + dependencies + a .env to fill in
./.venv/bin/python server.py     # then open http://localhost:5000
```

If `./setup.sh` won't run (Windows, or no bash), do the same three steps by hand:

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt      # Windows: .venv\Scripts\pip
cp .env.example .env                             # Windows: copy .env.example .env
./.venv/bin/python server.py                     # Windows: .venv\Scripts\python
```

**It runs with no keys at all** — you get the built-in synthetic network, which is
enough to demo the whole interface. Add keys when you want live data.

The synthetic network appears **only** when no key is configured. Once a key is
present, a search that finds nothing reports nothing found — an invented network
shown for a real name would be the worst failure this tool could have.

### Keys

Open `.env` and paste your keys after the `=` signs:

```
OPENSANCTIONS_API_KEY=your-key-here
OPENCORPORATES_API_TOKEN=your-token-here
ANTHROPIC_API_KEY=your-key-here     # optional — adverse media (see below)
GEMINI_API_KEY=your-key-here        # optional — adverse media, alternative to Anthropic
```

Then restart the server. The header chips tell you which sources are actually live,
and `pipeline.py --check-keys` probes each one and prints the exact API error if a
key is rejected — worth running before you blame the app for a thin result.

Two things that trip people up: a text editor may save the file as `.env.txt`
(the chips will still say "off"), and the server has to stay running in its
terminal while you use the browser.

> **Rotate any key you have pasted into a chat window, including to me.** Regenerate
> both from your provider dashboards and put the new ones in `.env`. That file is
> git-ignored, so the real keys never enter the repository.

### Command line

```bash
./.venv/bin/python pipeline.py "falcon capital"
./.venv/bin/python pipeline.py "Elena Kovacs" --type person --nationality cy
./.venv/bin/python pipeline.py "Falcon Capital" --json graph.json
./.venv/bin/python pipeline.py --check-keys   # test each API key and exit
./.venv/bin/python test_ubograph.py       # smoke tests, no pytest needed
./.venv/bin/python test_dossier.py        # dossier parsing + merge rules
```

### Putting it on a public URL

See [DEPLOY.md](DEPLOY.md). Render's free tier is the shortest path — it reads
`render.yaml` from the repository root, gives you `https://yourname.onrender.com`, and takes the API keys
as environment variables. A `Dockerfile` is included for Hugging Face Spaces,
Fly.io, Koyeb or Cloud Run.

Set `APP_PASSWORD` on any deployment. A public instance searches on your API keys,
and without a password anyone who finds the URL spends your quota.

---

## How a search flows

1. **OpenSanctions `/match`** finds candidate entities. The top candidates are then
   expanded through `/entities?nested=true`, which returns their ownership and
   directorship network rather than just the listing.
2. **OpenCorporates** adds registry records: company search gives officers and
   registered addresses; officer search runs the other direction, which is how one
   person holding thirty directorships becomes visible.
3. **The resolver** merges records that are certainly the same entity and *links*
   ones that merely look similar.
4. **Detectors** run over the merged graph, each node gets a 0–100 risk score, and
   the subgraph around the match is returned to the browser.
5. If nothing matched at all and an Anthropic key is set, an **open-web research
   call** runs and renders in a separate amber panel labelled unverified.

### The optional identifier fields

They are the most valuable part of the form, which is why the UI explains them
rather than hiding them. OpenSanctions scores a multi-attribute match far higher
than a name-only one, so a birth year or nationality is the single most effective
way to kill namesake false positives. Nationality is a dropdown of all 249 ISO
countries; date of birth is a single year select — that's what a registry usually
publishes anyway, and a day/month a searcher rarely knows added friction without
adding much match accuracy; jurisdiction is a grouped dropdown covering every
country plus the sub-national registries that matter — US states, UAE emirates,
Canadian provinces, Australian states — in the `us_de` / `ae_du` form the APIs expect.
Registration number shows for companies.

---

## Duplicate records for one person

A search for a common name often returns the same individual several times, once
per list they appear on. Those records are collapsed into one entity when a
`/match` result scores 100% **and** nothing in the two records contradicts the
identification — different birth years, passport numbers, national ID numbers or
nationalities each block the merge. Records OpenSanctions itself marks as the
same thing (via `referents`) are merged regardless.

This guard matters more than it looks. A `/match` score measures the record
against **your query**, not against another record: search a bare "Imran Khan"
and every same-named record scores 1.0, including men who are plainly not each
other. Collapsing on score alone would manufacture a single person holding
another man's sanctions listing.

When records are merged the report says so, lists the source record IDs, and
states each fact once — a passport number appearing on four lists is one fact,
not four findings. Anything below 100% is never collapsed; it stays a separate
entity with a dashed "possible match" link.

## Entity resolution — why it merges cautiously

A false merge invents a claim about a real person. A "possible match" edge just
shows the lawyer something to check. So resolution runs in three layers:

| Layer | Signal | Action |
|---|---|---|
| 1 | Same registration number + jurisdiction | **merge** |
| 2 | Normalised name ≥ 92% **and** a corroborating attribute (same birth year, or same registration number, or same country for companies) | **merge** |
| 3 | Normalised name ≥ 84%, nothing corroborating | **link** with a dashed `possibly_same_as` edge |

Name normalisation lowercases, strips punctuation, collapses dotted acronyms, and
drops legal-form suffixes (`Ltd`, `LLC`, `FZE`, `DMCC`, …) and honorifics, so
"Falcon Capital Holdings FZE" and "FALCON CAPITAL HLDGS" reach the same key.

Conflicting birth years block a merge outright: two John Smiths born fifteen years
apart stay two people.

---

## Detectors

| Detector | What it looks for | Severity |
|---|---|---|
| `sanctioned` / `pep` | Sanctions listing or political exposure on any node | high / medium |
| `circular_ownership` | Ownership or control that returns to its starting point | high |
| `nominee_hub` | One person holding a controlling role in ≥ 5 entities | medium |
| `shared_address` | ≥ 4 entities at one registered address (brass plate) | medium |
| `deep_layering` | An ownership chain ≥ 3 tiers above the target | medium |
| `high_risk_jurisdiction` | Registration in a limited-disclosure jurisdiction | low |
| `fatf_jurisdiction` | Registration under a live FATF or UN sanctions-regime listing | high / medium |

Each finding is a lead, not a conclusion — the wording in the UI says so. Company
formation agents legitimately host hundreds of clients at one address and act as
nominee directors for many companies; the value is in surfacing the pattern for a
human to weigh, not in scoring anyone guilty.

`fatf_jurisdiction` is separate from `high_risk_jurisdiction`: the latter is a fixed
list of jurisdictions known for limited beneficial-ownership disclosure (BVI, Cayman,
Panama, …), the former reads a dated, sourced country-risk table — FATF's Call for
Action and Increased Monitoring ("grey") lists plus the UAE's UN targeted-financial-
sanctions jurisdiction list — supplied via a real client AML risk-rating workbook
(`frontend/data/country_risk.json`; see `reference.risk_data_meta()` for the exact
source and the date FATF/UN lists were last updated). A UN-sanctioned-regime or
FATF-blacklisted jurisdiction scores high, same weight as a direct sanctions hit;
FATF's grey list scores medium. Like every other detector here, it flags the
*registration jurisdiction* for enhanced diligence — it is not a finding against the
entity itself.

FATF's Call for Action and Increased Monitoring lists get their own **black
list** / **grey list** marking — a literal black or grey badge, distinct
from the red/orange severity pill used everywhere else — so a reader can
tell "this jurisdiction is on FATF's black list" apart from "this entity is
sanctioned" at a glance instead of both looking like the same red flag.
FATF-suspended-cooperation cases stay on the plain severity colour, since
that's not literally either FATF list.

A UN Security Council targeted financial sanctions regime gets its own
**UN Sanctions** marking too (`reference.un_sanctioned()`), checked
independently of FATF status rather than as a fallback — a jurisdiction
can be on a FATF list *and* under UN sanctions at once (Iran, North Korea
and several others are both), and both badges show together rather than
whichever check happens to fire first. This is written up everywhere a
jurisdiction is shown during risk assessment, not only in the graph:

- The `fatf_jurisdiction` detector raises its own UN Sanctions finding,
  separate from any FATF black/grey-list finding on the same entity.
- Every country field in the client risk-rating worksheet (nationality,
  country of birth/residence, business/work location) carries an
  independent `un_sanctioned` flag alongside its FATF marking, shown as
  its own badge in both the on-screen table and the PDF.
- Every "Screen this name" match carries the same `un_sanctioned` flag
  next to its FATF marking.

**UBO traversal follows ownership edges only.** A director sits in the control
graph but is not a beneficial owner, and listing a hired director as the UBO is
precisely the outcome a nominee arrangement is designed to produce.

---

## Layout

```
config.py            environment + .env loading, high-risk jurisdiction list
schema.py            Node / Edge — the one shape every source normalises into
resolve.py           entity resolution: merge vs link
graph.py             NetworkX build, detectors, risk scoring, UBO paths, export
search.py            orchestration across every configured source
server.py            Flask: static frontend + /api/status, /api/search, /api/export
report.py            per-entity report structure (screen and PDF share it)
pdf.py               ReportLab rendering of that structure
reference.py         ISO country / jurisdiction lookup
risk_rating.py       client risk-rating rubric (client-supplied workbook, digitized)
geocode.py           free, keyless address geocoding + satellite-image URLs
edd.py               Enhanced Due Diligence checklist, sourced from the graph
goaml.py             goAML XML draft export (starting point, not schema-validated)
package.py           "Download All" — bundles every document into one ZIP
reasons.py           "reason for reporting" reference library (STR/SAR red-flag codes)
db.py                SQLite: saved cases, the watchlist, the activity log
pipeline.py          command line entry point
test_ubograph.py     smoke tests
sources/
  opensanctions.py   /match + nested /entities, FollowTheMoney relationship walker
  opencorporates.py  company search, company detail, officer search
  adverse_media.py   open-web fallback via Claude or Gemini (whichever key is set)
  dossier.py         raw OpenSanctions entity -> structured dossier, and merging
  demo.py            synthetic network + sample dossier for keyless demos
frontend/index.html  markup: form, tabs, table, report
frontend/app.js      search, graph rendering, table filtering, report + PDF
frontend/styles.css  the whole visual layer
frontend/data/       generated ISO lists + sourced country_risk.json / client_risk_rubric.json
```

Adding a source means writing one adapter that emits `Node`s and `Edge`s. Nothing
downstream knows which API a record came from.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/status` | Which sources are configured (drives the header chips) |
| `GET|POST /api/search` | `name`, `entity_type`, `nationality`, `birth_date`, `reg_number`, `jurisdiction`, `hops` → graph payload |
| `GET /api/export` | Same payload as a downloadable JSON file |
| `GET /api/reference` | Country and jurisdiction lists for the dropdowns |
| `POST /api/report` | `{payload, node_id}` → the report structure for one entity |
| `POST /api/report.pdf` | Same input, plus an optional `analyst_comments` string → a PDF file. Always includes an automatic Risk Assessment section and a signature block. |
| `GET /api/risk_rating/options` | Dropdown option lists and weights for the client risk-rating panel |
| `POST /api/risk_rating` | `{nationality, country_of_birth, country_of_residence, business_work_location, screening_outcome, employment_type, employment_industry, mode_of_payment, source_of_funds, subject_name, screening_reference, compliance_notes, prepared_by, review_status}` → a weighted score plus a risk matrix, reasoning and mitigation recommendations. Standalone — no payload or node_id; every field past `source_of_funds` is optional record-keeping metadata for the PDF. |
| `POST /api/risk_rating.pdf` | Same input → the worksheet as its own PDF, with a signature block |
| `POST /api/screen` | `{name, entity_type, ...expanded identification fields}` → a suggested screening outcome plus the raw matches found. See `server.SCREENING_DETAIL_FIELDS` for every optional field accepted. |
| `POST /api/geocode` | `{address}` → coordinates, a satellite-image URL, and an OpenStreetMap link |
| `POST /api/edd.pdf` | `{payload, node_id}` → the Enhanced Due Diligence checklist as a PDF |
| `POST /api/mou.pdf` | `{payload, node_id, role}` → an MOU draft with the entity pre-filled as `"purchaser"` or `"seller"` |
| `GET /api/reasons` | `?q=` → the "reason for reporting" reference library (code + description), optionally filtered |
| `POST /api/goaml.xml` | `{payload, node_id, reason, reason_code, report_type}` → a starting-point goAML XML draft (`report_type` is `"STR"` or `"SAR"`) |
| `POST /api/goaml_match.xml` | `{name, match, report_type}` → a goAML draft for one screening hit (`report_type` is `"CNMR"` or `"PNMR"`) |
| `POST /api/download_all.zip` | `{payload, node_id, analyst_comments}` → one ZIP with the full report, a standalone Risk Assessment PDF, the EDD checklist, an evidence/sources list, and an audit trail extract |
| `POST /api/batch_screen` | `{names: [...], entity_type}` or a multipart `file` upload → a risk read on every name |
| `GET /api/batch_screen.csv` | Same, as a downloadable CSV — repeated `?name=` query params |
| `POST /api/cases` · `GET /api/cases` · `GET /api/cases/<id>` · `POST /api/cases/<id>/notes` · `DELETE /api/cases/<id>` | Save / list / open / annotate / delete a case (a named snapshot of one entity's result set) |
| `POST /api/watchlist` · `GET /api/watchlist` · `DELETE /api/watchlist/<id>` | Add / list / remove a name from ongoing-monitoring |
| `POST /api/watchlist/<id>/check` · `POST /api/watchlist/check_all` | Re-screen one watched name, or all of them — point an external cron at `check_all` for real automatic monitoring |
| `GET /api/activity` | Recent activity log (searches, report views, exports, case/watchlist changes) |
| `POST /api/geocode` | `{address}` → coordinates, a satellite-image URL, and an OpenStreetMap link |

The report endpoints take the result set the browser already holds, so opening a
report and downloading a PDF cost no extra API quota.

### Client risk rating

Its own "Risk Assessment" tab, entirely independent of the graph, a search, or
any entity: the exact weighted rubric from a real client's AML risk-rating
workbook (nationality, country of birth/residence, business/work-location
country, the sanctions/PEP screening outcome, employment type and industry,
mode of payment, source of funds — each scored 0-10 and weighted, summed, then
rescaled to 0-100). Every field, including nationality and the screening
outcome, is a manual selection — nothing here is looked up against a searched
name or a PEP/sanctions hit, so it works identically whether or not anything
has ever been searched for. See `risk_rating.py` for the scoring rule and
`frontend/data/client_risk_rubric.json` for where the numbers came from. A
"Screen this name" button runs a standalone sanctions/PEP lookup and suggests
a screening outcome (still editable), and "Download PDF" produces the
worksheet as its own document — no entity or report required for either.

Behind "More identifying details" is a full identification form — alias,
nationality, date/place of birth, gender, country of residence, address,
passport/national ID/visa numbers, employment (occupation, employer,
position, industry), business details (company name, registration number,
country of registration, company address), and additional fields (email,
phone, website, tax ID, known associates, a PEP indicator, a sanctions
search reference, notes). Every field that OpenSanctions' matching engine
actually understands (alias, nationality, birth date/place, gender,
address, passport/national ID, email, phone, website, tax ID, position,
registration number) is sent straight into the live search and genuinely
narrows it — the more that's filled in, the less likely a search returns an
unrelated namesake instead of "not found". Fields with no equivalent there
(occupation, employer, visa number, known associates, the PEP indicator, a
free-text reference) are kept on the returned screening record for the
audit trail rather than discarded. See `search._extra_match_properties` for
the exact field mapping.

The downloadable PDF is a full compliance record, not just the scoring
table: subject details (name, an optional screening reference), a risk
matrix showing where the score landed against the full Low/Medium/High
scale, plain-language reasoning naming what actually drove the score,
band-appropriate mitigation recommendations, free-text compliance notes,
who prepared it and its review status (Draft/Under review/Approved/
Rejected), and a Prepared By / Reviewed By / Approved By sign-off block —
none of the identity fields are ever pre-filled with a real name; each is
either what you typed in or left an explicit blank.

### Adverse media (open-web research)

Runs on every search now, not only when the structured sources find nothing —
a weak or wrong structured match shouldn't silently suppress the one check
that could catch it. See `sources/adverse_media.py` for the Anthropic/Gemini
provider split. Two things work together to keep the searched name and the
open-web findings from talking past each other:

- **Searching with "Any" entity type no longer falls back to a vague schema.**
  OpenSanctions' `/match` used to query the abstract `LegalEntity` schema
  whenever the entity type wasn't specified — which strips out every
  person/company-specific identifying property (nationality, birth date,
  registration number) and leaves a name-only query against the loosest
  schema OpenSanctions has, exactly the shape of query that ranks a
  same-surname stranger above "not found". "Any" now queries `Person` and
  `Company` as two separate concrete schemas and merges the results by best
  score instead. See `opensanctions.match`.
- **Weak OpenSanctions matches are filtered out before they can pose as "the"
  result.** A bare name search scores every same-ish-sounding record; without
  a floor, an unrelated namesake with a low score becomes the reported entity
  just by being first in a short list — the actual person, who may simply not
  be in that database, never gets reported as genuinely not found. Candidates
  scoring below `MATCH_SCORE_THRESHOLD` (env var, default `0.5`) are dropped
  before they can become a root. See `opensanctions._filter_weak_matches`.
- **Every OpenSanctions result carries its match confidence as a visible
  note**, not just an internal score thrown away after filtering. A `/match`
  score reflects how well a record's text fits the query, not whether it's
  actually the same person — a name-only search can still surface a real,
  unrelated namesake above the threshold. Each report (and its PDF) shows
  "Matched the search '...' at N% confidence", flagged as an explicit weak
  match below 70% (`opensanctions.LOW_CONFIDENCE_MATCH`) — so a shaky result
  is never presented with the same unqualified confidence as a strong one.
  Add a birth year, nationality or jurisdiction to the search — the
  single most effective way to push a true match's score up and a
  namesake's down.
- **The open-web findings are folded into the same report**, not left in a
  separate box nobody reads — a report's Findings section carries both the
  structured detector hits and the adverse-media claims together, each
  claim still clearly labelled "Open-web (unverified)" and capped at
  "medium" severity so scraped narrative can never outrank a verified
  finding. Only the entity actually searched for gets this treatment
  (`is_root`) — findings never leak onto an unrelated owner or director
  pulled into the same graph.
- **An ordinary person or business with no sanctions/PEP/registry hit but
  real web coverage gets its own entry**, not just a paragraph on a "no
  match" screen. When the structured sources (live, not demo) find nothing
  and the open-web search actually turned something up, that becomes a
  proper node — a Table row, a Graph node, a full report and PDF — sourced
  entirely from the open web and clearly labelled as such: no risk flags or
  score are fabricated from unverified narrative (it always bands green),
  and every note and finding says outright that this isn't a registry hit.
  Search "Definitely No Web Coverage Of This" and it still correctly comes
  back "no match" — this only fires when the web search found something
  real. See `search._add_adverse_media_node`.

Batch screening (`batch_screen`) opts out of this — screening a whole
portfolio would otherwise turn one API key into hundreds of web-search calls
per run. Run a name individually from the Table tab to get the open-web
check.

### Satellite view

Opening the report for an address entity (the diamond nodes — a registered
address, most often surfaced via the `shared_address` finding) adds a
"Location" section: the address is geocoded via OpenStreetMap's Nominatim
(free, no key) and shown as a static satellite image from Esri's World
Imagery service (also free, no key), with a link to the same point on the
full interactive OpenStreetMap. Good for a quick "is this a real building or
a brass-plate address" check, not for anything needing survey accuracy. See
`geocode.py`. Both services are unauthenticated and rate-limited for
reasonable individual use — not meant for bulk lookups.

### Documents for the file: EDD checklist, MOU draft, goAML export

Three more buttons on a report, each producing a document a lawyer or MLRO
would otherwise assemble by hand:

- **EDD checklist** — walks through the same enhanced-due-diligence triggers
  a real AML policy runs (sanctioned? PEP? high-risk jurisdiction? complex
  ownership structure?), each answered from this entity's own record. Where
  this tool genuinely has no source for a fact (business type, residency,
  transaction history), it says "not available" rather than guessing "no" —
  see `edd.py`.
- **MOU draft** — a resale Memorandum of Understanding with the searched
  entity pre-filled as buyer or seller and every other field (price,
  property, dates) left as a placeholder. A starting point for the acting
  lawyer to complete and review, not a substitute for the firm's own
  approved template.
- **goAML export** — a draft XML with the entity's name, DOB/registration,
  identifiers, address and findings filled in, as either a Suspicious
  Transaction Report (STR) or a Suspicious Activity Report (SAR) — pick
  which when downloading. An optional "reason for reporting" field is backed
  by `reasons.py`, a 280+ code reference library of standard red-flag
  typologies (funnel accounts, structuring, shell-company indicators, TFS
  matches and the like); typing a keyword and picking a code carries its own
  wording straight into the draft instead of writing the reason from
  scratch. **Not validated against the actual goAML XSD** (that schema isn't
  published anywhere this tool can read it from) — treat it as a head start
  to complete inside goAML, not a ready-to-submit file. See `goaml.py` for
  exactly what it does and doesn't claim.
- **goAML match report (CNMR/PNMR)** — a lightweight goAML draft generated
  straight from a "Screen this name" hit (Risk Assessment tab), for the
  Confirmed or Partial Name Match Report a DNFBP files against the UAE's
  Targeted Financial Sanctions regime once a name match turns up — separate
  from the full entity STR/SAR above, and carrying the standard reminder
  that a confirmed or partial match should be reported through goAML within
  five days, alongside any funds-freeze action taken.

### Download All — one complete investigation package

"Download All" sits right next to "Download PDF" on a report and produces a
single ZIP with everything otherwise downloaded one document at a time:

1. The full screening report PDF (with its automatic Risk Assessment
   section and Prepared By / Reviewed By / Approved By signature block).
2. A standalone Risk Assessment PDF (the same automatic assessment, broken
   out as its own file).
3. The EDD checklist PDF.
4. A plain-text evidence/source list — every source URL on record plus any
   open-web research findings, each with its attribution.
5. An audit trail CSV — every activity-log entry that mentions this
   subject by name (search, report view, exports, workspace changes).

Everything is generated fresh from the same report structure the on-screen
view uses, so nothing in the bundle can say something different from what
was actually screened. See `package.py`.

### Workspace: cases, watchlist, batch screening, activity log

A fourth tab, backed by a small SQLite database (`db.py`, stored at
`data/sanctionsplus.db`, gitignored):

- **Saved cases** — snapshot one entity's result set under a name, with a
  free-text note, so you can come back to it without re-running the search.
  "Save as case" is a button on the report; open or delete it from the
  Workspace tab.
- **Watchlist** — add a name to monitor, then "Check now" (or "Check all
  now") re-screens it and calls out any flag that's new since the last
  check. There's no scheduler built into a Render free-tier app, so real
  *ongoing* monitoring means pointing an external cron (Render's own paid
  Cron Jobs, or a free service like cron-job.org) at
  `POST /api/watchlist/check_all` on whatever cadence fits — daily or
  weekly, not more often, since it spends your OpenSanctions quota.
- **Batch screening** — upload a CSV or text file (one name per line, or the
  first column of a CSV) and get every name screened in one pass, with a
  downloadable CSV of the results. Capped at 200 names per batch and runs
  sequentially, to stay inside a live API's rate limit rather than burst it.
- **Activity log** — every search, report view, export and case/watchlist
  change, with a timestamp, so there's a record of what was checked and when.

**The honest limit on all of it:** Render's free tier resets its filesystem
on every redeploy and on the spin-down that follows ~15 minutes of no
traffic, so cases, the watchlist and the activity log do not persist
indefinitely — this is a working-session convenience, not a system of
record. A real deployment that needs cases and an audit trail to survive
would need a managed database (e.g. Render's paid Postgres) behind `db.py`.

## The three views

**Graph** — the network. Circle = person, square = company, diamond = address.

**Table** — every entity as a row: name, type, how it relates to the network,
jurisdiction, flags and risk score. Sort by any column. Filter by risk band (the
three coloured pills), entity type, specific flag, or name. Click any name to open
its report.

**Report** — the written assessment for one entity:

- Risk band chip (red / orange / green) and a plain sentence saying why that band.
- Identifying details: nationality, date of birth, registration number, jurisdiction,
  aliases, sources.
- **Assessment** — several paragraphs in plain English explaining what makes this
  entity a risk: sanctions or PEP status, how many entities it controls and where,
  which of those are themselves red, the ownership route to the company you searched,
  and which structural findings it is caught up in.
- **Current** and **previous affiliations** as tables, each row colour-banded by that
  company's own risk, with role, stake, jurisdiction and dates.
- **Source detail** — everything OpenSanctions publishes about the subject:
  patronymic, place of birth, gender, position held, nationality, passport and
  national ID numbers, tax numbers, addresses, plus the named lists it appears on
  ("NACTA List of Proscribed Persons", not `pk_nacta_proscribed`).
- **Sanction records** — one block per listing: issuing authority, programme,
  the stated reason, provisions (asset freeze, travel ban), status, listing and
  start dates, the authority's own reference and a link to the source document.
- **Recorded relationships** — family, associates, directorships and ownership
  as the source states them, with roles and dates.
- Unresolved identity matches, flagged for verification and never silently merged.
- Open-web research, if enabled, in a separate amber panel with a category filter.
- **Download PDF** produces a formatted document with the same content, colour bands
  included, ready to file or attach — opening with its own cover page
  (classification marker, subject, overall risk rating, generation date, a
  "Prepared for" placeholder) and an executive summary (what was screened,
  the headline rating and score, how many findings, the first recommended
  action) before the detailed sections, so it reads as a complete
  regulator-ready compliance report from the first page rather than a
  printout of the on-screen view.

Every name in the report is clickable, so you can walk the chain from a subsidiary up
to its beneficial owner one report at a time.

### Risk bands

| Band | Meaning |
|---|---|
| **Red** | A sanctions, criminal or wanted flag, or a risk score of 50+ |
| **Orange** | Politically exposed, or a risk score of 25–49 |
| **Green** | Score under 25 and no adverse flag in the sources searched |

Flags override the score: a sanctioned party is red even in an otherwise empty
network. Scoring is calibrated so the bands and the findings cannot contradict each
other — one high finding alone reaches red, one medium alone reaches orange. An
entity that merely appears in someone else's finding carries a fraction of the
weight, because being one of eight companies a nominee runs is context, not the same
fact as being the nominee.

Green means nothing was found, which is not the same as clearance — the report says
so explicitly.

## Reading the graph

- Circle = person, square = company, diamond = address.
- Colour is risk: red high, amber medium, green low, grey none.
- Node size is network centrality.
- **Solid line** = a relationship a source actually asserts.
- **Dashed amber line** = the resolver thinks these might be the same entity. Verify
  before treating them as one.
- Click a red flag to isolate the entities involved; click a node for its record,
  including source links.

## Notes for demo day

Rehearse on demo data even if your keys work — live APIs can be slow or rate-limited
on bad wifi, and a frozen spinner in front of judges is worse than obviously-labelled
sample data. Check your OpenSanctions tier in advance too: each search makes a match
call plus entity expansions, so a nervous rehearsal can eat a trial quota. If you do
hit a limit mid-demo the app degrades gracefully — the error shows in red and the
graph comes back thin rather than blank.
