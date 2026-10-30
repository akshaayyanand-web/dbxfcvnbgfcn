# NASA ACME Data Availability Matrix

**Status as of 2026-10-30: NOT VERIFIED.** The build environment's network policy
blocked the NASA hosts (`psi.nasa.gov`, `www1.grc.nasa.gov`, `gipoc.grc.nasa.gov`,
`ntrs.nasa.gov`; the proxy refused each connection). Nothing below has been downloaded or inspected.
This matrix records what public descriptions suggest, and what must be confirmed
before any variable is used for modelling.

## 1. What is publicly stated (secondary sources, web search)

* ACME (Advanced Combustion via Microgravity Experiments) was a set of six
  investigations of laminar, non-premixed gaseous flames. They ran in the
  Combustion Integrated Rack (CIR) on the ISS from 2017 using one set of modular
  hardware. About 1,500 flames were ignited. The hardware was later removed for
  SoFIE (launched Feb 2022).
* NASA's **Physical Sciences Informatics (PSI)** system is described as an
  open-access repository of raw and processed reduced-gravity experiment data,
  including combustion. NASA has funded at least one proposal to analyse ACME
  **s-Flame** data from PSI.
* The GIPOC ACME page links to "ACME data" marked **"Authorized users only"**.
  Access conditions may differ by dataset, and PSI may require registration.
* **s-Flame** (C.K. Law, Princeton; S. Tse, Rutgers) studied spherical diffusion
  flames that were ignited and allowed to evolve naturally towards extinction,
  including radiative and convective extinction limits.
* **BRE** (Burning Rate Emulator) used a porous burner. Transient flame growth on
  BRE has been modelled in the literature (Markan, Baum & Sunderland, *Combust.
  Flame* 2020).
* Other ACME investigations named in NASA material: **CLD Flame** (coflow
  laminar diffusion), **E-FIELD Flames** (electric-field effects) and **Flame
  Design**. The sixth investigation's name and every investigation's exact
  geometry must be confirmed from primary NASA records.

Sources: NASA science.nasa.gov s-Flame page; NTRS 20210022542 / 20210021781
(ACME JASMAC papers); GIPOC ACME page; re3data PSI entry; Universe Today / Space.com
summaries. These are secondary descriptions, not dataset documentation.

## 2. Relevance to the CV engine

| Investigation | Expected flame geometry | Equivalent spherical volume valid? | Radius-vs-time analysis valid? |
|---|---|---|---|
| s-Flame | spherical (porous spherical burner) | plausibly, after confirming symmetry | yes |
| Flame Design | believed spherical: **verify** | verify | verify |
| BRE | porous burner, flame shape to verify | verify | verify |
| CLD Flame | coflow / jet | **no** | no (use height/width instead) |
| E-FIELD Flames | coflow with applied field | **no** | no |

## 3. Target-availability matrix (to be filled from primary data)

Legend: **U** = unverified, **A** = available and checked, **N** = confirmed not available.

| Variable | Role | Expected unit | Likely source | Status | Coverage | Quality | Notes |
|---|---|---|---|---|---|---|---|
| Investigation / test-point ID | key | – | PSI metadata | U | – | – | Needed for experiment-group-aware splits |
| Fuel / diluent composition | condition | mole fraction | PSI metadata | U | – | – | |
| Oxidizer O₂ fraction | condition | mole fraction | PSI metadata | U | – | – | |
| Chamber pressure | condition | kPa / atm | CIR telemetry | U | – | – | |
| Fuel flow rate | condition | sccm / mg s⁻¹ | PSI metadata | U | – | – | |
| Burner diameter | condition / calibration reference | mm | hardware docs | U | – | – | Candidate in-plane reference length (A-CAL-2) |
| Flame video / image sequences | observation | px, s | PSI raw data | U | – | – | Required for real-footage CV validation |
| Camera spec (resolution, fps, optics) | metadata | – | hardware docs | U | – | – | Required for calibration validity |
| Flame radius vs time | outcome | mm | derived by investigators or by us | U | – | – | Can be produced by this platform once video is available |
| Extinction time | outcome | s | investigator records / video | U | – | – | Visible vs chemical extinction differ (A-PH-4) |
| Flame temperature | outcome | K | thermocouple or radiometer, if any | U | – | – | **Do not train** until a measured source is confirmed |
| Soot volume fraction | outcome | ppm | Flame Design / soot diagnostics, if any | U | – | – | |
| Radiative emission | outcome | W | radiometer, if any | U | – | – | |

## 4. Rules that follow from this matrix

1. No predictive target is trained until its row is **A**, with a provenance record
   in `backend/data/` (source URL, file checksum, retrieval date).
2. Until then the demo uses SYNTHETIC data only, labelled per A-DATA-2.
3. **Action for the team:** allow `psi.nasa.gov`, `ntrs.nasa.gov` and `www1.grc.nasa.gov` in the
   environment's network settings, or download PSI files manually into `data/raw/`.
   Then re-run the data-discovery step and replace every **U** above.
