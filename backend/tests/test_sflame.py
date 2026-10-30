"""Tests for the s-Flame (PSI-23) parsers, conversions and labelling, using small inline fixtures
transcribed in format from real NASA files (values shortened)."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from backend.data import sflame as sf

HEADER = ("2019-09-11 254 18:37:31:240 ,Experiment: 2,Test Point: 19254H3,MFCA1 Gas: 1,MFCA1 Full Scale: 20.000000,"
          "MFCA2 Gas: 0,MFCA2 Full Scale: 0.500000,MFCA3 Gas: 6,MFCA3 Full Scale: 0.500000,EField: 0,Igniter: 0,"
          "PMT 1 Gain: 5.750000")

TP_TEXT = """\\\\Test Point: 19254H1

Script start: 2019-09-11 18:37:31
Ignition and retraction: 2019-09-11 18:38:28
MFCs on for priming: ***
MFCs off: 2019-09-11 18:38:32
Script complete after abort: 2019-09-11 18:38:55
Extinction detected: 2019-09-11 18:38:32
Test Point Failure: 2019-09-11 18:38:32
Reason: EXTINCTION DETECTED

testpointName:19254H1,
burnerTemperatureLimitC:250,
"""


def test_documented_conversions():
    assert sf.mfc_flow_indicated_slpm(5.0, 0.5) == pytest.approx(0.5)
    assert sf.mfc_flow_indicated_slpm(1.08, 0.5) == pytest.approx(0.108)
    assert sf.pressure_kpa(0.5) == pytest.approx(0.0)
    assert sf.pressure_kpa(4.5) == pytest.approx(145.038 * 6.894757, rel=1e-6)  # 4.5 V = 145 psia full scale
    assert sf.cold_junction_c(0.00295 * 298.15) == pytest.approx(25.0)


def test_gas_code_tables_are_normalised():
    for table in (sf.MFCA1_GAS, sf.MFCA2_GAS, sf.MFCA3_GAS):
        for code, comp in table.items():
            assert sum(comp.values()) == pytest.approx(1.0, abs=2e-3), code
    assert sf.MFCA3_GAS[6] == {"C2H4": 0.5, "N2": 0.5}
    assert sf.MFCA3_GAS[14] == {"H2": 0.45, "He": 0.55}


def test_parse_header():
    h = sf.parse_header(HEADER)
    assert h.timestamp == datetime(2019, 9, 11, 18, 37, 31, 240000)
    assert (h.experiment, h.test_point, h.mfca3_gas, h.mfca3_full_scale) == (2, "19254H3", 6, 0.5)
    assert h.fuel_bottle == {"C2H4": 0.5, "N2": 0.5} and h.diluent == {"N2": 1.0}
    assert h.flags["PMT 1 Gain"] == pytest.approx(5.75)
    with pytest.raises(ValueError):
        sf.parse_header("garbage")


def test_parse_tp_tolerates_stray_prefix_and_reads_events():
    log = sf.parse_tp(TP_TEXT)
    assert log.test_point == "19254H1"
    assert log.ignition == datetime(2019, 9, 11, 18, 38, 28)
    assert log.events["MFCs on for priming"] is None
    assert log.failure_reason == "EXTINCTION DETECTED" and not log.script_completed_normally
    assert log.parameters["burnerTemperatureLimitC"] == "250"


def test_clock_series_midnight_rollover():
    s = sf._clock_series(pd.Series(["23:59:59:900", "00:00:00:100"]), datetime(2019, 9, 11, 23, 0))
    assert (s.iloc[1] - s.iloc[0]).total_seconds() == pytest.approx(0.2)


def _setpoints(rows):
    df = pd.DataFrame(rows, columns=["Time", "MFCA1Setpoint(V)", "MFCA2Setpoint(V)", "MFCA3Setpoint(V)"])
    df["time"] = sf._clock_series(df["Time"], datetime(2019, 9, 11))
    return sf.parse_header(HEADER), df


def test_flow_programme_constant_and_ramp():
    h, sp = _setpoints([["19:33:00:000", 0, 0, 0], ["19:33:05:785", 0, 1.08, 0], ["19:33:05:785", 0, 1.08, 0.543],
                        ["19:33:51:896", 0, 0, 0.543], ["19:33:51:896", 0, 0, 0]])
    p = sf.flow_programme(h, sp)
    assert p.programme == "constant" and p.fuel_duration_s == pytest.approx(46.111)
    first = p.steps.iloc[0]
    assert first.fuel_slpm == pytest.approx(0.0543) and first.diluent_slpm == pytest.approx(0.108)
    assert first.fuel_species_fraction == pytest.approx(0.5 * 0.0543 / 0.1623)

    h, sp = _setpoints([["01:00:00:000", 0, 1.0, 1.0], ["01:00:10:000", 0, 1.0, 2.0],
                        ["01:00:11:000", 0, 1.0, 3.0], ["01:00:20:000", 0, 0, 0]])
    p = sf.flow_programme(h, sp)
    assert p.programme == "ramp_up" and len(p.steps) == 3
    assert sf.flow_at(p, datetime(2019, 9, 11, 1, 0, 10, 500000))["fuel_slpm"] == pytest.approx(0.2)


def _telemetry(pmt, dt=0.008, start=datetime(2019, 9, 11, 12)):
    t = [start + timedelta(seconds=i * dt) for i in range(len(pmt))]
    return pd.DataFrame({"time": pd.to_datetime(t), "PMT1": pmt})


def _programme(on_s, off_s, start=datetime(2019, 9, 11, 12)):
    steps = pd.DataFrame({"time": [pd.Timestamp(start + timedelta(seconds=on_s))], "fuel_slpm": [0.1],
                          "diluent_slpm": [0.1], "total_slpm": [0.2], "fuel_species_fraction": [0.25]})
    return sf.FlowProgramme(start + timedelta(seconds=on_s), start + timedelta(seconds=off_s), steps, "constant")


def test_detect_flame_ignores_gain_off_level_and_flash():
    rng = np.random.default_rng(0)
    n = int(20 / 0.008)
    pmt = rng.normal(0, 0.0005, n)
    pmt[: int(1 / 0.008)] = 4.5                                   # gain not yet applied
    pmt[int(3 / 0.008): int(3.3 / 0.008)] += 0.5                  # 0.3 s ignition flash
    det = sf.detect_flame(_telemetry(pmt), datetime(2019, 9, 11, 12, 0, 2))
    assert det.flame_on is None and "no sustained flame" in det.notes[0]
    assert sf.classify_outcome(det, _programme(2, 18)) == ("no_sustained_flame", None)


def test_detect_flame_extinguished_vs_censored():
    rng = np.random.default_rng(1)
    n = int(20 / 0.008)
    base = rng.normal(0, 0.0005, n)
    lit = base.copy()
    lit[int(4 / 0.008): int(12 / 0.008)] += 1.0                   # flame 4 s .. 12 s
    det = sf.detect_flame(_telemetry(lit), datetime(2019, 9, 11, 12, 0, 3))
    assert det.duration_s == pytest.approx(8.0, abs=0.1)
    assert sf.classify_outcome(det, _programme(3, 15)) == ("extinguished", True)
    assert sf.classify_outcome(det, _programme(3, 12)) == ("burning_at_fuel_off", False)


def test_experimental_table_autofill_correction(tmp_path):
    p = tmp_path / "table.csv"
    p.write_text("Test Type,Test Day*,Year,Month,Date,Atmosphere*,Fuel Bottle,Flames Ignited*,Notes\n"
                 "x,19254,2019,Sept.,11,~21% O2 with N2,50% C2H4 with N2,13,n\n"
                 "x,19256,2019,Sept.,13,~21% O2 with N3,50% C2H4 with N3,16,\n"
                 "x,20155,2020,June,3,~30% and ~21% O2 with He,45% H2 with He,9,\n")
    t = sf.load_experimental_table(p).set_index("Test Day")
    assert t.loc["19256", "Atmosphere"] == "~21% O2 with N2"
    assert t.loc["19256", "Atmosphere_original"] == "~21% O2 with N3"
    assert "SFLAME-T1(Atmosphere)" in t.loc["19256", "corrections"]
    assert t.loc["19254", "corrections"] == ""
    assert t.loc["20155", "o2_nominal_values"] == [0.21, 0.30]
    assert t.loc["20155", "atmosphere_diluent"] == "He"
