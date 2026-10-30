"""Parsers and unit conversions for NASA ACME s-Flame (PSI-23) non-imaging data.

Every conversion and code table here is transcribed from NASA documents that
ship with PSI-23, cited by section:

* [IDD]  ACME-DOC-010 Rev D, Software Interface Design Description,
         §10.1 Metadata Header (gas codes, Table 34) and §10.2 Data Conversions.
* [NIDD] "ACME non-imaging data file description" (2017-02-17), AIN channel tables.
* [DI]   "ACME/s-Flame Data Interpretation", 20 September 2021, §4.A and §4.B.4.

Important caveats from those documents, carried through as flags:

* MFC flows are *indicated* flows, ``V / 5 * full_scale`` in SLPM. Converting
  them to actual flows of the real gas mixtures needs gas conversion factors
  [DI §4.A.1], which are not applied here. Columns are named ``*_indicated_slpm``.
* The ACME pressure transducers "have not been calibrated in years"; CIR
  chamber pressure is more accurate [DI §4.A.1]. ``PTA3`` is converted but
  flagged as low-confidence.
* The MFCA1 gas code is the oxidiser bottle installed on the flow controller,
  not the chamber atmosphere. s-Flame burns into a pre-filled quiescent
  atmosphere; the chamber O2 level comes from the experimental table.
* Test-point log (``_TP.txt``) times have 1 s resolution. "Test Point Failure:
  EXTINCTION DETECTED" is the script's normal stop path when the flame goes out,
  not necessarily a failed test [procedure, extinctionDetectionStopsTest].
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

PSI_ACCESSION = "PSI-23"

# [IDD] Table 34 / §10.1. Compositions are mole fractions as labelled by NASA.
MFCA1_GAS = {  # oxidiser bottle on the static-mixer MFC
    0: {"O2": 0.21, "N2": 0.79}, 1: {"O2": 0.30, "N2": 0.70}, 2: {"O2": 0.40, "N2": 0.60},
    3: {"O2": 0.85, "N2": 0.15}, 4: {"O2": 0.30, "He": 0.70},
}
MFCA2_GAS = {0: {"N2": 1.0}, 1: {"He": 1.0}}  # bypass / diluent MFC
MFCA3_GAS = {  # fuel bottle
    0: {"CH4": 1.0}, 1: {"CH4": 0.30, "N2": 0.70}, 2: {"CH4": 0.40, "N2": 0.60}, 3: {"CH4": 0.45, "N2": 0.55},
    4: {"C2H4": 1.0}, 5: {"C2H4": 0.30, "N2": 0.70}, 6: {"C2H4": 0.50, "N2": 0.50}, 7: {"H2": 1.0},
    8: {"H2": 0.444, "CH4": 0.556}, 9: {"H2": 0.556, "CH4": 0.444}, 10: {"H2": 0.667, "CH4": 0.333},
    11: {"H2": 0.20, "CH4": 0.25, "He": 0.55}, 12: {"H2": 0.25, "CH4": 0.20, "He": 0.55},
    13: {"H2": 0.30, "CH4": 0.15, "He": 0.55}, 14: {"H2": 0.45, "He": 0.55}, 15: {"CH4": 0.45, "He": 0.55},
    16: {"C2H4": 0.20, "He": 0.80}, 17: {"C2H4": 0.25, "He": 0.75}, 18: {"C2H4": 0.30, "He": 0.70},
}
FUEL_SPECIES = ("H2", "CH4", "C2H4")
PSIA_TO_KPA = 6.894757


def mfc_flow_indicated_slpm(volts: np.ndarray | float, full_scale_slpm: float) -> np.ndarray | float:
    """[NIDD] AIN-0..2: ``Flow (SLPM) = Voltage / 5.0 * FULL_SCALE`` (indicated, no gas correction)."""
    return np.asarray(volts, dtype=float) / 5.0 * full_scale_slpm


def pressure_kpa(volts: np.ndarray | float) -> np.ndarray | float:
    """[NIDD] AIN-4..6: ``P (psia) = (V - 0.5) * 14.5038 * 10 / 4`` converted to kPa."""
    return (np.asarray(volts, dtype=float) - 0.5) * 14.5038 * 10.0 / 4.0 * PSIA_TO_KPA


def cold_junction_c(volts: np.ndarray | float) -> np.ndarray | float:
    """[NIDD] AIN-24 (AD590): ``T (C) = V / 0.00295 - 273.15``."""
    return np.asarray(volts, dtype=float) / 0.00295 - 273.15


# ------------------------------------------------------------------- header line


@dataclass
class DataHeader:
    timestamp: datetime
    experiment: int
    test_point: str
    mfca1_gas: int
    mfca1_full_scale: float
    mfca2_gas: int
    mfca2_full_scale: float
    mfca3_gas: int
    mfca3_full_scale: float
    flags: dict[str, float] = field(default_factory=dict)

    @property
    def fuel_bottle(self) -> dict[str, float] | None:
        return MFCA3_GAS.get(self.mfca3_gas)

    @property
    def diluent(self) -> dict[str, float] | None:
        return MFCA2_GAS.get(self.mfca2_gas)


_HEADER_TS = re.compile(r"^(\d{4}-\d{2}-\d{2}) \d{3} (\d{2}):(\d{2}):(\d{2}):(\d{3})")


def parse_header(line: str) -> DataHeader:
    """Parse the first line of ``_data.csv`` / ``_mfcSetpoints.csv`` [IDD §10.1]."""
    m = _HEADER_TS.match(line.strip())
    if not m:
        raise ValueError(f"Unrecognised header timestamp: {line[:40]!r}")
    date, hh, mm, ss, ms = m.groups()
    ts = datetime.fromisoformat(f"{date}T{hh}:{mm}:{ss}") + timedelta(milliseconds=int(ms))
    fields: dict[str, str] = {}
    for part in line.split(",")[1:]:
        if ":" in part:
            k, v = part.split(":", 1)
            fields[k.strip()] = v.strip()
    known = {"Experiment", "Test Point", "MFCA1 Gas", "MFCA1 Full Scale", "MFCA2 Gas", "MFCA2 Full Scale",
             "MFCA3 Gas", "MFCA3 Full Scale"}
    try:
        return DataHeader(
            timestamp=ts,
            experiment=int(fields["Experiment"]),
            test_point=fields["Test Point"],
            mfca1_gas=int(fields["MFCA1 Gas"]), mfca1_full_scale=float(fields["MFCA1 Full Scale"]),
            mfca2_gas=int(fields["MFCA2 Gas"]), mfca2_full_scale=float(fields["MFCA2 Full Scale"]),
            mfca3_gas=int(fields["MFCA3 Gas"]), mfca3_full_scale=float(fields["MFCA3 Full Scale"]),
            flags={k: float(v) for k, v in fields.items() if k not in known and _is_number(v)},
        )
    except KeyError as exc:
        raise ValueError(f"Header is missing field {exc}") from exc


def _is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


def _clock_series(clock: pd.Series, start: datetime) -> pd.Series:
    """Convert ``HH:MM:SS:mmm`` strings to datetimes on ``start``'s date, handling midnight rollover."""
    parts = clock.str.strip().str.extract(r"^(\d{2}):(\d{2}):(\d{2}):(\d{3})$").astype(float)
    if parts.isna().any().any():
        raise ValueError("Unparseable clock values in time column.")
    secs = parts[0] * 3600 + parts[1] * 60 + parts[2] + parts[3] / 1000.0
    midnight = datetime(start.year, start.month, start.day)
    rollover = (secs.diff() < -43200).cumsum()  # a backwards jump of > 12 h is a day change
    return pd.to_datetime(midnight) + pd.to_timedelta(secs + rollover * 86400, unit="s")


# ------------------------------------------------------------- setpoint file


@dataclass
class FlowProgramme:
    """Commanded fuel-line flow programme derived from ``_mfcSetpoints.csv``.

    Flows are *indicated* SLPM (see module caveats). Times are absolute GMT.
    """

    fuel_on: datetime | None
    fuel_off: datetime | None
    steps: pd.DataFrame          # time, fuel_slpm, diluent_slpm, total_slpm, fuel_species_fraction
    programme: str               # none | constant | ramp_up | ramp_down | up_down | stepped

    @property
    def fuel_duration_s(self) -> float | None:
        if self.fuel_on is None or self.fuel_off is None:
            return None
        return (self.fuel_off - self.fuel_on).total_seconds()


def parse_setpoints(path: str | Path) -> tuple[DataHeader, pd.DataFrame]:
    path = Path(path)
    with open(path, encoding="utf-8", errors="replace") as fh:
        header = parse_header(fh.readline())
    df = pd.read_csv(path, skiprows=1)
    df.columns = [c.strip() for c in df.columns]
    df["time"] = _clock_series(df["Time"].astype(str), header.timestamp)
    return header, df


def flow_programme(header: DataHeader, sp: pd.DataFrame) -> FlowProgramme:
    """Fuel-on/off times and the sequence of distinct commanded flows (indicated SLPM)."""
    fuel = mfc_flow_indicated_slpm(sp["MFCA3Setpoint(V)"], header.mfca3_full_scale)
    dil = mfc_flow_indicated_slpm(sp["MFCA2Setpoint(V)"], header.mfca2_full_scale)
    frame = pd.DataFrame({"time": sp["time"], "fuel_slpm": fuel, "diluent_slpm": dil})
    # Keep the last row for each timestamp (several commands are logged per millisecond).
    frame = frame.groupby("time", as_index=False).last()
    on_rows = frame.index[frame.fuel_slpm > 0]
    if len(on_rows) == 0:
        return FlowProgramme(None, None, frame.iloc[0:0].assign(total_slpm=[], fuel_species_fraction=[]), "none")
    first = on_rows[0]
    off_after = frame.index[(frame.index > first) & (frame.fuel_slpm <= 0)]
    last = off_after[0] if len(off_after) else None
    fuel_on = frame.loc[first, "time"].to_pydatetime()
    fuel_off = frame.loc[last, "time"].to_pydatetime() if last is not None else None
    steps = frame.loc[first:(last - 1 if last is not None else frame.index[-1])].copy()
    steps["total_slpm"] = steps.fuel_slpm + steps.diluent_slpm
    bottle = header.fuel_bottle or {}
    fuel_frac = sum(bottle.get(s, 0.0) for s in FUEL_SPECIES)
    steps["fuel_species_fraction"] = np.where(
        steps.total_slpm > 0, steps.fuel_slpm * fuel_frac / steps.total_slpm, np.nan)
    steps = steps.loc[(steps[["fuel_slpm", "diluent_slpm"]].diff().abs().sum(axis=1) > 1e-9)
                      | (steps.index == steps.index[0])].reset_index(drop=True)
    return FlowProgramme(fuel_on, fuel_off, steps, _classify(steps.total_slpm.to_numpy()))


def _classify(total: np.ndarray) -> str:
    if total.size == 0:
        return "none"
    if total.size == 1:
        return "constant"
    d = np.diff(total)
    up, down = np.any(d > 1e-9), np.any(d < -1e-9)
    if up and down:
        return "up_down"
    if up:
        return "ramp_up" if total.size > 2 else "stepped"
    if down:
        return "ramp_down" if total.size > 2 else "stepped"
    return "constant"


# ---------------------------------------------------------------- test-point log


@dataclass
class TestPointLog:
    test_point: str
    events: dict[str, datetime | None]
    failure_reason: str | None
    failure_time: datetime | None
    script_completed_normally: bool
    parameters: dict[str, str]

    @property
    def ignition(self) -> datetime | None:
        return self.events.get("Ignition and retraction")

    @property
    def extinction_detected(self) -> datetime | None:
        return self.events.get("Extinction detected")


_EVENT = re.compile(r"^([A-Za-z][A-Za-z0-9 #/-]*?):\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}|\*\*\*)\s*$")


def parse_tp(text: str) -> TestPointLog:
    """Parse a ``<tp>_TP.txt`` timing file [DI §4.B.4]."""
    tp = None
    events: dict[str, datetime | None] = {}
    reason = None
    params: dict[str, str] = {}
    for raw in text.splitlines():
        # Some logs carry stray leading characters (e.g. "\\Test Point:" in 20029G1).
        line = re.sub(r"^[^A-Za-z0-9]+", "", raw.strip())
        if line.startswith("Test Point:"):
            tp = line.split(":", 1)[1].strip()
            continue
        if line.startswith("Reason:"):
            reason = line.split(":", 1)[1].strip()
            continue
        m = _EVENT.match(line)
        if m:
            name, value = m.groups()
            events[name] = None if value == "***" else datetime.fromisoformat(value.replace(" ", "T"))
            continue
        pm = re.match(r"^([A-Za-z][A-Za-z0-9]*):(.*?),?$", line)
        if pm and "Script" not in line:
            params[pm.group(1)] = pm.group(2).strip()
    if tp is None:
        raise ValueError("Test-point log has no 'Test Point:' line.")
    return TestPointLog(
        test_point=tp,
        events=events,
        failure_reason=reason,
        failure_time=events.get("Test Point Failure"),
        script_completed_normally=events.get("Script complete") is not None,
        parameters=params,
    )


# ------------------------------------------------------------ experimental table

ATMOSPHERE_AUTOFILL = re.compile(r"\bN[3-9]\b")


def load_experimental_table(path: str | Path) -> pd.DataFrame:
    """Load the PSI-23 experimental table with a documented correction.

    Rule SFLAME-T1: the 'Atmosphere' and 'Fuel Bottle' columns contain 'N3'..'N6' in rows
    where the final report's Table 1 states N2. This matches spreadsheet autofill
    increments of 'N2', so they are replaced by 'N2'. The original text is kept in
    ``*_original`` columns and every corrected row is flagged.
    """
    df = pd.read_csv(path)
    df.columns = [c.strip().rstrip("*") for c in df.columns]
    df = df.loc[:, [c for c in df.columns if c and not c.startswith("Unnamed")]]
    df = df[df["Test Day"].notna()].copy()
    df["Test Day"] = df["Test Day"].astype(int).astype(str)
    df["corrections"] = ""
    for col in ("Atmosphere", "Fuel Bottle"):
        df[f"{col}_original"] = df[col]
        bad = df[col].astype(str).str.contains(ATMOSPHERE_AUTOFILL)
        df.loc[bad, col] = df.loc[bad, col].astype(str).str.replace(ATMOSPHERE_AUTOFILL, "N2", regex=True)
        df.loc[bad, "corrections"] += f"SFLAME-T1({col});"
    df["o2_nominal_values"] = df["Atmosphere"].astype(str).apply(
        lambda s: sorted({int(x) / 100.0 for x in re.findall(r"~(\d+)%", s)}))
    df["atmosphere_diluent"] = df["Atmosphere"].astype(str).str.extract(r"with (N2|He)")[0]
    return df.drop(columns=[c for c in ("Notes",) if c in df.columns])


# ------------------------------------------------------------------- telemetry

PMT_GAIN_OFF_LEVEL_V = 4.2  # PMTs read ~4.5 V before the script applies gain; such samples carry no light signal


def load_telemetry(path: str | Path) -> tuple[DataHeader, pd.DataFrame]:
    """Load ``_data.csv`` (125 Hz) with absolute time and documented conversions [NIDD].

    Adds ``fuel_indicated_slpm``, ``diluent_indicated_slpm``, ``oxidizer_indicated_slpm`` and
    ``pta3_kpa`` (low-confidence: uncalibrated transducer, see module notes). PMT and
    thermocouple columns stay in volts.
    """
    path = Path(path)
    with open(path, encoding="utf-8", errors="replace") as fh:
        header = parse_header(fh.readline())
    with open(path, "rb") as fh:
        n_lines = sum(1 for _ in fh)
    # Malformed rows (e.g. two records fused into one line) are skipped and counted, never repaired.
    df = pd.read_csv(path, skiprows=1, low_memory=False, on_bad_lines="skip")
    df.columns = [c.strip() for c in df.columns]
    times = df["Time"].astype(str).str.strip()
    good_time = times.str.fullmatch(r"\d{2}:\d{2}:\d{2}:\d{3}")
    df = df[good_time].copy()
    for col in df.columns:
        if col != "Time":
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df.attrs["malformed_rows_skipped"] = int(n_lines - 2 - len(df))
    df["time"] = _clock_series(df["Time"].astype(str), header.timestamp)
    df["oxidizer_indicated_slpm"] = mfc_flow_indicated_slpm(df["MFCA1StaticMixerFlow"], header.mfca1_full_scale)
    df["diluent_indicated_slpm"] = mfc_flow_indicated_slpm(df["MFCA2BypassFlow"], header.mfca2_full_scale)
    df["fuel_indicated_slpm"] = mfc_flow_indicated_slpm(df["MFCA3FuelFlow"], header.mfca3_full_scale)
    df["pta3_kpa"] = pressure_kpa(df["PTA3"])
    return header, df


@dataclass
class FlameDetectionConfig:
    """Flame presence from the OH* photomultiplier (PMT1, 310 nm).

    A sample is luminous when the 0.1 s rolling median of PMT1 exceeds the
    pre-fuel baseline by ``max(k_mad * MAD, min_rise_v)``. A *sustained* flame is
    a luminous run of at least ``min_sustained_s``; shorter runs (ignition
    flashes) are ignored. Gaps shorter than ``max_gap_s`` do not end a run.
    """

    channel: str = "PMT1"
    smooth_s: float = 0.1
    k_mad: float = 10.0
    min_rise_v: float = 0.02
    min_sustained_s: float = 1.0
    max_gap_s: float = 0.2
    censor_tolerance_s: float = 0.1


@dataclass
class FlameDetection:
    flame_on: datetime | None
    flame_off: datetime | None
    baseline_v: float | None
    threshold_v: float | None
    peak_v: float | None
    notes: list[str] = field(default_factory=list)

    @property
    def duration_s(self) -> float | None:
        if self.flame_on is None or self.flame_off is None:
            return None
        return (self.flame_off - self.flame_on).total_seconds()


def detect_flame(tel: pd.DataFrame, fuel_on: datetime | None, cfg: FlameDetectionConfig | None = None) -> FlameDetection:
    cfg = cfg or FlameDetectionConfig()
    notes: list[str] = []
    sig = tel[[cfg.channel, "time"]].copy()
    gained = sig[cfg.channel] < PMT_GAIN_OFF_LEVEL_V
    if not gained.any():
        return FlameDetection(None, None, None, None, None, ["PMT gain never applied; no light signal"])
    first_gain = sig.index[gained.to_numpy()][0]
    sig = sig.loc[first_gain:]
    sig = sig[sig[cfg.channel] < PMT_GAIN_OFF_LEVEL_V]
    dt = float(sig["time"].diff().dt.total_seconds().median())
    win = max(1, int(round(cfg.smooth_s / dt)))
    smooth = sig[cfg.channel].rolling(win, center=True, min_periods=1).median()
    pre = smooth[sig["time"] < pd.Timestamp(fuel_on)] if fuel_on is not None else smooth.iloc[: int(0.5 / dt)]
    if len(pre) < max(5, int(0.2 / dt)):
        pre = smooth.iloc[: max(5, int(0.2 / dt))]
        notes.append("short pre-fuel baseline; first 0.2 s after gain-on used")
    base = float(np.median(pre))
    mad = float(np.median(np.abs(pre - base))) * 1.4826
    thr = base + max(cfg.k_mad * mad, cfg.min_rise_v)
    lum = (smooth > thr).to_numpy().copy()
    times = sig["time"].to_numpy()
    # Close short gaps, then find runs.
    gap = int(round(cfg.max_gap_s / dt))
    if gap > 0 and lum.any():
        idx = np.flatnonzero(lum)
        for a, b in zip(idx[:-1], idx[1:]):
            if 1 < b - a <= gap + 1:
                lum[a:b] = True
    runs, start = [], None
    for i, v in enumerate(np.append(lum, False)):
        if v and start is None:
            start = i
        elif not v and start is not None:
            runs.append((start, i - 1))
            start = None
    sustained = [(a, b) for a, b in runs
                 if (times[b] - times[a]) / np.timedelta64(1, "s") >= cfg.min_sustained_s]
    if fuel_on is not None:
        sustained = [(a, b) for a, b in sustained if times[b] >= np.datetime64(fuel_on)]
    peak = float(smooth.max())
    if not sustained:
        if runs:
            notes.append(f"{len(runs)} short luminous event(s) (e.g. ignition flash) but no sustained flame")
        return FlameDetection(None, None, base, thr, peak, notes)
    if len(sustained) > 1:
        notes.append(f"{len(sustained)} sustained luminous periods, the first is used")
    a, b = sustained[0]
    return FlameDetection(pd.Timestamp(times[a]).to_pydatetime(), pd.Timestamp(times[b]).to_pydatetime(),
                          base, thr, peak, notes)


# --------------------------------------------------------------- dataset table


def classify_outcome(det: FlameDetection, prog: FlowProgramme, cfg: FlameDetectionConfig | None = None) -> tuple[str, bool | None]:
    """Return ``(outcome, event_observed)``.

    * ``no_sustained_flame``  -- no sustained OH* emission after fuel on (e.g. ignition failure)
    * ``extinguished``        -- emission ended while fuel was still flowing (event observed)
    * ``burning_at_fuel_off`` -- emission lasted until the fuel was shut off (right-censored)
    """
    cfg = cfg or FlameDetectionConfig()
    if det.flame_on is None:
        return "no_sustained_flame", None
    if prog.fuel_off is None:
        return "extinguished", True
    if (prog.fuel_off - det.flame_off).total_seconds() > cfg.censor_tolerance_s:
        return "extinguished", True
    return "burning_at_fuel_off", False


def flow_at(prog: FlowProgramme, when: datetime | None) -> dict[str, float]:
    """Commanded (indicated) flows in effect at ``when``."""
    if when is None or prog.steps.empty:
        return {"fuel_slpm": np.nan, "diluent_slpm": np.nan, "total_slpm": np.nan, "fuel_species_fraction": np.nan}
    active = prog.steps[prog.steps.time <= pd.Timestamp(when)]
    row = active.iloc[-1] if len(active) else prog.steps.iloc[0]
    return {k: float(row[k]) for k in ("fuel_slpm", "diluent_slpm", "total_slpm", "fuel_species_fraction")}
