# UBOgraph

Maps multi-layered corporate ownership structures so a commercial or M&A lawyer can
see who ultimately controls a company — including through free-zone and offshore
intermediaries — and what should be checked before signing.

It pulls from sanctions and corporate registry APIs, resolves records that describe
the same real-world entity, builds one graph, runs red-flag detectors over it, and
draws the result.

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

### Keys

Open `.env` and paste your keys after the `=` signs:

```
OPENSANCTIONS_API_KEY=your-key-here
OPENCORPORATES_API_TOKEN=your-token-here
ANTHROPIC_API_KEY=your-key-here     # optional
```

Then restart the server. The header chips tell you which sources are actually live.

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
./.venv/bin/python test_ubograph.py       # smoke tests, no pytest needed
```

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
way to kill namesake false positives. Nationality and date of birth show for
people, registration number for companies, plus a jurisdiction filter.

---

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

Each finding is a lead, not a conclusion — the wording in the UI says so. Company
formation agents legitimately host hundreds of clients at one address and act as
nominee directors for many companies; the value is in surfacing the pattern for a
human to weigh, not in scoring anyone guilty.

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
pipeline.py          command line entry point
test_ubograph.py     smoke tests
sources/
  opensanctions.py   /match + nested /entities, FollowTheMoney relationship walker
  opencorporates.py  company search, company detail, officer search
  adverse_media.py   open-web fallback via the Claude API
  demo.py            synthetic network used when no keys are configured
frontend/index.html  the whole UI: form, force-directed graph, findings, detail
```

Adding a source means writing one adapter that emits `Node`s and `Edge`s. Nothing
downstream knows which API a record came from.

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/status` | Which sources are configured (drives the header chips) |
| `GET|POST /api/search` | `name`, `entity_type`, `nationality`, `birth_date`, `reg_number`, `jurisdiction`, `hops` → graph payload |
| `GET /api/export` | Same payload as a downloadable JSON file |

The frontend only ever calls `/api/search`, so the visual layer can be reworked
freely without touching the backend.

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
