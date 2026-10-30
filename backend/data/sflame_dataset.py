"""Build the s-Flame test-point table from NASA PSI-23 raw files.

Usage:
    python -m backend.data.sflame_dataset --raw data/raw/PSI-23 --out data/processed

One row per test point (from ``_mfcSetpoints.csv``), joined with the timing log
(``_TP.txt``), the parameter file (``as run<tp>.txt``), the 125 Hz telemetry
(``_data.csv``) and the experimental table. Outputs:

* ``sflame_test_points.csv``  -- the table (columns documented in DATA_DICTIONARY.md)
* ``sflame_quality_report.json`` -- counts, cross-checks against NASA's own stop reasons, issues
* ``sflame_manifest.json`` -- SHA-256 of every input file, so the table is reproducible

Labelling rules (SCIENTIFIC_ASSUMPTIONS.md, A-SF-*):

* A flame is "sustained" when OH* emission (PMT1) stays above baseline for >= 1 s.
* ``extinguished``: emission ended >= 0.1 s before the fuel was shut off (event observed).
* ``burning_at_fuel_off``: emission lasted until the fuel was shut off (right-censored).
* ``ambiguous_nasa_extinction``: NASA's onboard detector declared extinction, but OH*
  emission persisted until fuel shut-off. Excluded from timing labels.
* ``no_sustained_flame``: no sustained emission, e.g. ignition failure.
* Flame lifetime is measured from emission onset, not from commanded fuel-on, because
  emission sometimes starts before the setpoint log records fuel-on.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from backend.data.sflame import (
    FUEL_SPECIES,
    MFCA2_GAS,
    MFCA3_GAS,
    FlameDetectionConfig,
    classify_outcome,
    detect_flame,
    flow_at,
    flow_programme,
    load_experimental_table,
    load_telemetry,
    parse_setpoints,
    parse_tp,
)

SCHEMA = "flame-in-freefall/sflame-test-points/v1"
EMISSION_AFTER_FUEL_OFF_LIMIT_S = 1.0


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_as_run(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(errors="replace").splitlines():
        m = re.match(r"^\s*([A-Za-z][A-Za-z0-9]*):\s*([^,]*),?\s*$", line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def _mixture(bottle: dict[str, float], fuel_slpm: float, diluent: dict[str, float], diluent_slpm: float) -> dict[str, float]:
    """Mole fractions of the delivered fuel-line mixture from indicated (N2-equivalent) flows."""
    total = fuel_slpm + diluent_slpm
    if not total or not math.isfinite(total) or total <= 0:
        return {}
    mix: dict[str, float] = {}
    for comp, frac in bottle.items():
        mix[comp] = mix.get(comp, 0.0) + frac * fuel_slpm / total
    for comp, frac in diluent.items():
        mix[comp] = mix.get(comp, 0.0) + frac * diluent_slpm / total
    return mix


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat(timespec="milliseconds") if dt else None


def build_row(run_id: str, raw: Path, day_table: pd.DataFrame, cfg: FlameDetectionConfig,
              shared: bool = False) -> tuple[dict, list[Path]]:
    """One row per *run*. NASA saves a re-run of a test point as ``<tp>_1``, ``<tp>_2``... [IDD §8.1];
    the run's own files carry the suffix, while ``_TP.txt`` and ``as run`` files exist once per test point."""
    used: list[Path] = []
    flags: list[str] = []
    tp = run_id.split("_")[0]
    sp_path = raw / f"{run_id}_mfcSetpoints.csv"
    header, sp = parse_setpoints(sp_path)
    used.append(sp_path)
    prog = flow_programme(header, sp)
    row: dict = {
        "test_point": run_id,
        "test_point_base": tp,
        "run_suffix": run_id[len(tp) + 1:] if run_id != tp else "",
        "test_day": tp[:5],
        "test_date_utc": header.timestamp.date().isoformat(),
        "round": 2 if tp[:5] >= "20132" else 1,
        "fuel_bottle_code": header.mfca3_gas,
        "fuel_bottle": json.dumps(MFCA3_GAS.get(header.mfca3_gas)),
        "diluent_mfc_gas": "+".join(MFCA2_GAS.get(header.mfca2_gas, {"unknown": 1})),
        "flow_programme": prog.programme,
        "fuel_on_utc": _iso(prog.fuel_on),
        "fuel_off_utc": _iso(prog.fuel_off),
        "fuel_duration_s": prog.fuel_duration_s,
    }
    if MFCA3_GAS.get(header.mfca3_gas) is None:
        flags.append("unknown_fuel_bottle_code")

    day = day_table[day_table["Test Day"] == tp[:5]]
    if len(day):
        d = day.iloc[0]
        o2_values = d["o2_nominal_values"]
        row["atmosphere_day"] = d["Atmosphere"]
        row["atmosphere_inert"] = d["atmosphere_diluent"]
        row["o2_nominal"] = o2_values[0] if len(o2_values) == 1 else np.nan
        if len(o2_values) != 1:
            flags.append("o2_ambiguous_mixed_day")
        if d["corrections"]:
            flags.append("experimental_table_corrected")
    else:
        row.update(atmosphere_day=None, atmosphere_inert=None, o2_nominal=np.nan)
        flags.append("test_day_not_in_experimental_table")

    if not prog.steps.empty:
        first, steps = prog.steps.iloc[0], prog.steps
        row.update(
            initial_fuel_slpm=float(first.fuel_slpm),
            initial_diluent_slpm=float(first.diluent_slpm),
            initial_total_slpm=float(first.total_slpm),
            initial_fuel_species_fraction=float(first.fuel_species_fraction),
            max_total_slpm=float(steps.total_slpm.max()),
            min_total_slpm=float(steps.total_slpm.min()),
            n_flow_steps=int(len(steps)),
        )
        mix = _mixture(MFCA3_GAS.get(header.mfca3_gas, {}), first.fuel_slpm,
                       MFCA2_GAS.get(header.mfca2_gas, {}), first.diluent_slpm)
        for sp_name in FUEL_SPECIES + ("N2", "He"):
            row[f"initial_x_{sp_name}"] = mix.get(sp_name, 0.0) if mix else np.nan

    as_run = raw / f"as run{tp}.txt"
    if shared:
        flags.append("multiple_runs_share_test_point_id")
    if as_run.exists() and not shared:
        used.append(as_run)
        params = _parse_as_run(as_run)
        row["planned_constant_flow_s"] = float(params["constantFlowTimeSec"]) if "constantFlowTimeSec" in params else np.nan
        row["burner_temperature_limit_c"] = float(params.get("burnerTemperatureLimitC", "nan") or "nan")
    else:
        row["planned_constant_flow_s"] = np.nan
        row["burner_temperature_limit_c"] = np.nan
        if as_run.exists():
            flags.append("as_run_not_attributed_shared_test_point")

    tp_path = raw / f"{tp}_TP.txt"
    log = parse_tp(tp_path.read_text(errors="replace")) if tp_path.exists() else None
    start = log.events.get("Script start") if log else None
    # The timing log belongs to this run only if its script start matches the run's data header (same script).
    matches = start is not None and abs((start - header.timestamp.replace(microsecond=0)).total_seconds()) <= 60
    if log is not None and matches:
        used.append(tp_path)
        row["nasa_stop_reason"] = log.failure_reason or ("completed" if log.script_completed_normally else "unknown")
        row["nasa_ignition_utc"] = _iso(log.ignition)
        row["nasa_extinction_detected_utc"] = _iso(log.extinction_detected)
    elif log is not None:
        row.update(nasa_stop_reason="log_belongs_to_other_run", nasa_ignition_utc=None, nasa_extinction_detected_utc=None)
        flags.append("test_point_log_belongs_to_other_run")
    else:
        row.update(nasa_stop_reason="no_log", nasa_ignition_utc=None, nasa_extinction_detected_utc=None)
        flags.append("no_test_point_log")

    data_path = raw / f"{run_id}_data.csv"
    if not data_path.exists() or prog.fuel_on is None:
        row["outcome"] = "no_data" if not data_path.exists() else "no_fuel_flow"
        row["event_observed"] = None
        row["quality_flags"] = ";".join(flags)
        return row, used
    used.append(data_path)
    _, tel = load_telemetry(data_path)
    if tel.attrs.get("malformed_rows_skipped"):
        flags.append(f"telemetry_malformed_rows={tel.attrs['malformed_rows_skipped']}")
    det = detect_flame(tel, prog.fuel_on, cfg)
    outcome, event = classify_outcome(det, prog, cfg)
    if outcome == "burning_at_fuel_off" and row["nasa_stop_reason"] == "EXTINCTION DETECTED":
        outcome, event = "ambiguous_nasa_extinction", None
    row.update(
        flame_on_utc=_iso(det.flame_on),
        flame_off_utc=_iso(det.flame_off),
        flame_duration_s=det.duration_s,
        ignition_delay_s=(det.flame_on - prog.fuel_on).total_seconds() if det.flame_on else np.nan,
        pmt1_baseline_v=det.baseline_v,
        pmt1_peak_v=det.peak_v,
        outcome=outcome,
        event_observed=event,
    )
    flags.extend(f"detection:{n.replace(';', ',')}" for n in det.notes)
    if det.flame_on and det.flame_on < prog.fuel_on:
        flags.append("emission_before_logged_fuel_on")
    if det.flame_off and prog.fuel_off and (det.flame_off - prog.fuel_off).total_seconds() > EMISSION_AFTER_FUEL_OFF_LIMIT_S:
        flags.append("emission_persisted_after_fuel_off")
    if outcome == "extinguished":
        at = flow_at(prog, det.flame_off)
        row.update(
            total_slpm_at_extinction=at["total_slpm"],
            fuel_species_fraction_at_extinction=at["fuel_species_fraction"],
            detection_lag_s=(prog.fuel_off - det.flame_off).total_seconds() if prog.fuel_off else np.nan,
        )
        changes = prog.steps.time[prog.steps.time <= pd.Timestamp(det.flame_off)]
        row["time_since_last_flow_change_s"] = (
            (pd.Timestamp(det.flame_off) - changes.iloc[-1]).total_seconds() if len(changes) else np.nan)
    if det.flame_on is not None:
        window = tel[(tel.time >= pd.Timestamp(det.flame_on)) & (tel.time <= pd.Timestamp(det.flame_on) + pd.Timedelta(seconds=1))]
        row["pta3_kpa_at_ignition_low_confidence"] = float(window.pta3_kpa.median()) if len(window) else np.nan
    row["quality_flags"] = ";".join(flags)
    return row, used


def build(raw: Path, cfg: FlameDetectionConfig | None = None) -> tuple[pd.DataFrame, dict, dict]:
    cfg = cfg or FlameDetectionConfig()
    table_files = sorted(raw.glob("*Experimental table*.csv"))
    if not table_files:
        raise FileNotFoundError("PSI-23 experimental table not found in raw directory.")
    day_table = load_experimental_table(table_files[0])
    used: set[Path] = {table_files[0]}
    rows = []
    run_ids = sorted(sp.name[: -len("_mfcSetpoints.csv")] for sp in raw.glob("*_mfcSetpoints.csv"))
    bases = pd.Series([r.split("_")[0] for r in run_ids])
    shared_bases = set(bases[bases.duplicated(keep=False)])
    for run_id in run_ids:
        sp = raw / f"{run_id}_mfcSetpoints.csv"
        try:
            row, files = build_row(run_id, raw, day_table, cfg, shared=run_id.split("_")[0] in shared_bases)
        except (ValueError, KeyError) as exc:
            row, files = {"test_point": run_id, "outcome": "parse_error", "quality_flags": f"parse_error:{exc}"}, [sp]
        rows.append(row)
        used.update(files)
    df = pd.DataFrame(rows)
    df["test_order_in_day"] = df.groupby("test_day")["fuel_on_utc"].rank(method="first")
    report = quality_report(df, day_table)
    manifest = {
        "schema": SCHEMA,
        "source": "NASA PSI-23 (ACME s-Flame), CC0-1.0, DOI 10.60555/k57n-p030",
        "built_at": datetime.now(timezone.utc).isoformat(),
        "detection_config": cfg.__dict__,
        "inputs": {p.name: _sha256(p) for p in sorted(used)},
    }
    return df, report, manifest


def quality_report(df: pd.DataFrame, day_table: pd.DataFrame) -> dict:
    cross = pd.crosstab(df["outcome"], df.get("nasa_stop_reason", pd.Series(dtype=str)).fillna("missing"))
    flags = df["quality_flags"].fillna("").str.split(";").explode()
    flags = flags[flags != ""].str.replace(r"=\d+$", "", regex=True).str.replace(r":.*", "", regex=True)
    return {
        "schema": SCHEMA,
        "test_points": int(len(df)),
        "outcomes": df["outcome"].value_counts().to_dict(),
        "outcome_vs_nasa_stop_reason": {o: r.to_dict() for o, r in cross.iterrows()},
        "flag_counts": flags.value_counts().to_dict(),
        "experimental_table_corrections": day_table.loc[day_table["corrections"] != "",
                                                        ["Test Day", "corrections"]].to_dict("records"),
        "known_source_discrepancies": [
            "PSI-23 experimental table lists day 20190 fuel as '35% H2 with He'; the final report (Table 1, §C) "
            "and the MFC header gas code 14 both give 45% H2 / 55% He. The header code is used.",
            "Days with '~30% and ~21% O2' (and some 17.5% O2 tests on 20190 per the final report) have no "
            "per-test O2 in the downloaded files; o2_nominal is left empty for those tests.",
        ],
        "caveats": [
            "Flows are indicated N2-equivalent SLPM without gas conversion factors.",
            "pta3_kpa is from an uncalibrated ACME transducer (NASA data interpretation guide).",
            "Labels derive from PMT1 (OH*, 310 nm) with a 1 s sustain rule; see SCIENTIFIC_ASSUMPTIONS.md A-SF.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the s-Flame test-point table from PSI-23 raw files.")
    parser.add_argument("--raw", type=Path, default=Path("data/raw/PSI-23"))
    parser.add_argument("--out", type=Path, default=Path("data/processed"))
    ns = parser.parse_args()
    df, report, manifest = build(ns.raw)
    ns.out.mkdir(parents=True, exist_ok=True)
    df.to_csv(ns.out / "sflame_test_points.csv", index=False)
    (ns.out / "sflame_quality_report.json").write_text(json.dumps(report, indent=2, default=str))
    (ns.out / "sflame_manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    print(json.dumps({"test_points": report["test_points"], "outcomes": report["outcomes"]}, indent=2))


if __name__ == "__main__":
    main()
