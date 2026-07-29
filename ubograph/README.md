# UBOgraph

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
ANTHROPIC_API_KEY=your-key-here     # optional
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
countries; date of birth is day / month / year selects where the year alone is enough
(often all a registry publishes); jurisdiction is a grouped dropdown covering every
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
pipeline.py          command line entry point
test_ubograph.py     smoke tests
sources/
  opensanctions.py   /match + nested /entities, FollowTheMoney relationship walker
  opencorporates.py  company search, company detail, officer search
  adverse_media.py   open-web fallback via the Claude API
  dossier.py         raw OpenSanctions entity -> structured dossier, and merging
  demo.py            synthetic network + sample dossier for keyless demos
frontend/index.html  markup: form, tabs, table, report
frontend/app.js      search, graph rendering, table filtering, report + PDF
frontend/styles.css  the whole visual layer
frontend/data/       generated ISO country/jurisdiction lists + sourced country_risk.json
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
| `POST /api/report.pdf` | Same input → a PDF file |

The report endpoints take the result set the browser already holds, so opening a
report and downloading a PDF cost no extra API quota.

The frontend only ever calls `/api/search`, so the visual layer can be reworked
freely without touching the backend.

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
  included, ready to file or attach.

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
