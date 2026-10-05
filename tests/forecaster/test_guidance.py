"""NWP track guidance and consensus (forecaster/guidance) — offline tests."""

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from forecaster.guidance import sources as S
from forecaster.guidance.consensus import blend, consensus, intensity_at, shifted

FIX = Path(__file__).parent / "fixtures"
T0 = datetime(2024, 10, 24, 0, tzinfo=timezone.utc)

ADECK = """IO, 03, 2024102306, 03, AVNX, 000, 167N,  891E,  45,  996, XX,  34, NEQ, 0112, 0093, 0087, 0125
IO, 03, 2024102306, 03, AVNX, 000, 167N,  891E,  45,  996, XX,  50, NEQ, 0040, 0030, 0000, 0000
IO, 03, 2024102306, 03, AVNX, 012, 182N,  886E,  48,  992, XX,  34, NEQ, 0139, 0129, 0078, 0000
IO, 03, 2024102306, 01, CARQ,   0, 166N, 0893E,  35,  999, XX,  34, NEQ,    0,   65,   55,    0
IO, 03, , 03, AVNX, 018, 190N,  880E,  50,  990
"""


def test_adeck_merges_radius_lines_and_skips_malformed(tmp_path):
    p = tmp_path / "aio032024.dat"
    p.write_text(ADECK)
    rows = S.parse_adeck(p)
    avnx = [r for r in rows if r["model"] == "AVNX"]
    assert [r["tau"] for r in avnx] == [0, 12]                  # 34/50-kt lines merged, blank-date line skipped
    assert avnx[0]["atcf"] == "IO032024" and avnx[0]["lat"] == 16.7 and avnx[0]["lon"] == 89.1
    assert avnx[1]["vmax_kt"] == 48 and avnx[1]["pmin_hpa"] == 992
    assert any(r["model"] == "CARQ" for r in rows)


def test_ecmwf_bufr_decodes_cyclone_dana():
    pytest.importorskip("eccodes")
    rows = S.parse_ecmwf_bufr(FIX / "ecmwf_tf_20241024_00z.bufr", "IFS", T0)
    dana = sorted((r for r in rows if r["atcf"] == "IO032024"), key=lambda r: r["tau"])
    assert {r["atcf"] for r in rows} == {"IO032024"}             # only Bay of Bengal / Arabian Sea storms kept
    assert dana[0]["tau"] == 0 and dana[0]["lat"] == pytest.approx(18.8) and dana[0]["lon"] == pytest.approx(87.8)
    assert 40 < dana[0]["vmax_kt"] < 50 and dana[0]["pmin_hpa"] == pytest.approx(985)
    by = {r["tau"]: r for r in dana}
    assert by[24]["lat"] > 20.5 and by[24]["lon"] < 87       # Dana crossed the Odisha coast near 20.9N 86.9E
    assert all(r["member"] == 0 for r in dana)


def test_ecmwf_model_names_follow_archive_layout():
    assert S.ecmwf_model("20250601/00z/aifs-single/0p25/oper/x-oper-tf.bufr") == "AIFS"
    assert S.ecmwf_model("20261004/00z/aifs-ens/0p25/enfo/x-enfo-tf.bufr") == "AIFS-ENS"
    assert S.ecmwf_model("20241024/06z/ifs/0p25/enfo/x-enfo-tf.bufr") == "IFS-ENS"
    assert S.ecmwf_model("20241024/06z/ifs/0p25/scda/x-scda-tf.bufr") == "IFS"


def test_shift_moves_track_by_fraction_of_start_error():
    tr = {0: (15.0, 88.0, 40.0), 24: (17.0, 87.0, 50.0)}
    s = shifted(tr, (15.4, 88.2, 45.0), alpha=0.5)
    assert s[0][:2] == pytest.approx((15.2, 88.1))
    assert s[24][:2] == pytest.approx((17.2, 87.1))
    assert shifted({24: tr[24]}, (15, 88, 40)) is None          # no τ0 → cannot be shifted


def test_consensus_uses_primary_members_when_both_present():
    start = (15.0, 88.0, 50.0)
    mem = {
        "AIFS": {0: (15.0, 88.0, 40.0), 24: (17.0, 87.0, 50.0)},
        "IFS-ENSM": {0: (15.0, 88.0, 40.0), 24: (17.4, 87.4, 46.0)},
        "GFS": {0: (15.0, 88.0, 40.0), 24: (25.0, 80.0, 60.0)},      # outlier, ignored when the primary pair exists
    }
    fc = consensus(mem, {"GFS": {"24": 1.0}}, {}, start)
    assert fc[24][:2] == pytest.approx((17.2, 87.2))
    assert fc[24][2] == pytest.approx(50 + np.mean([10, 20]))     # v0 + mean change of AIFS and GFS
    only = consensus({"GFS": mem["GFS"], "UKM": mem["IFS-ENSM"]}, {"GFS": {"24": 1.0}, "UKM": {"24": 3.0}}, {}, start)
    assert only[24][:2] == pytest.approx(((25 + 3 * 17.4) / 4, (80 + 3 * 87.4) / 4))   # fitted-weight fallback


def test_blend_needs_two_members_and_intensity_falls_back():
    assert blend({"AIFS": {24: (17.0, 87.0, 50.0)}}, {"AIFS": {"24": 1.0}}, 24) is None
    assert intensity_at({}, 24, 45.0) == 45.0                          # persistence when no model reports wind
    assert intensity_at({"IFS": {0: (0, 0, 30.0), 24: (0, 0, 20.0)}}, 24, 18.0) == 15.0   # floored at 15 kt
