"""
Cyclogenesis truth and the official services' timings (master plan v5, Task 3.4)
═══════════════════════════════════════════════════════════════════════════════
For every North Indian Ocean system that IMD graded a Depression (IBTrACS NI, NEWDELHI_GRADE):
  t_imd      first best-track time IMD graded it D or stronger (the official "formation")
  t_jtwc     first time JTWC numbered it (IBTrACS USA_* fixes with a USA_ATCF_ID)
  t_invest   first time JTWC designated the disturbance an invest (90B–99B / 90A–99A), from the
             UCAR RAL ATCF archive: the invest a-deck CARQ fix nearest in space (≤ 600 km) in the 6 days before t_imd
"""

import csv
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from forecaster.guidance import sources as S

ROOT = Path(__file__).resolve().parents[2]
IBTRACS = ROOT / "data" / "static" / "ibtracs.NI.list.v04r01.csv"
CACHE = ROOT / "data" / "genesis" / "invest"
GRADES = {"D", "DD", "CS", "SCS", "VSCS", "ESCS", "SUCS", "SuCS"}


def events(since=2023):
    out = {}
    with open(IBTRACS, newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        next(rd)
        for r in rd:
            if int(r["SEASON"]) < since:
                continue
            t = datetime.strptime(r["ISO_TIME"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            e = out.setdefault(r["SID"], {"sid": r["SID"], "name": r["NAME"].strip(), "season": int(r["SEASON"]),
                                          "atcf": None, "t_imd": None, "lat": None, "lon": None, "t_jtwc": None,
                                          "peak_grade": None, "peak_kt": 0.0})
            g = r["NEWDELHI_GRADE"].strip()
            if g in GRADES and e["t_imd"] is None:
                e["t_imd"], e["lat"], e["lon"] = t, float(r["NEWDELHI_LAT"] or r["LAT"]), float(r["NEWDELHI_LON"] or r["LON"])
            if r["USA_ATCF_ID"].strip():
                e["atcf"] = e["atcf"] or r["USA_ATCF_ID"].strip()
                if r["USA_LAT"].strip() and e["t_jtwc"] is None:
                    e["t_jtwc"] = t
            w = r["NEWDELHI_WIND"].strip()
            if w and float(w) > e["peak_kt"]:
                e["peak_kt"], e["peak_grade"] = float(w), g
    return [e for e in out.values() if e["t_imd"] is not None]


def invest_fixes(years):
    """[(time, lat, lon, invest id)] — CARQ τ0 fixes of every NIO invest a-deck (archive, else real-time folder)."""
    out = []
    for y in years:
        html = ""
        for url in (f"https://hurricanes.ral.ucar.edu/repository/data/adecks_open/{y}/",):
            try:
                html = requests.get(url, timeout=60).text
            except requests.RequestException:
                pass
        names = sorted(set(re.findall(r'href="(aio9\d\d{4}\.dat)"', html)))
        if not names:      # current season: real-time folders
            try:
                rt = requests.get(f"https://hurricanes.ral.ucar.edu/realtime/plots/northindian/{y}/", timeout=60).text
                names = [f"a{n}.dat" for n in sorted(set(re.findall(r'href="(io9\d\d{4})/"', rt)))]
            except requests.RequestException:
                names = []
        for n in names:
            num = int(n[3:5])
            dest = CACHE / n
            p = S.fetch(S.RAL_ADECK.format(year=y, num=num), dest) or S.fetch(S.RAL_REALTIME.format(year=y, num=num), dest)
            if not p:
                continue
            for r in S.parse_adeck(p, {"CARQ"}):
                if r["tau"] == 0:
                    out.append((r["init"], r["lat"], ((r["lon"] + 180) % 360) - 180, n[1:5].upper() + str(y)))
    return sorted(out)


def with_invest_times(evts, fixes, window_days=6, max_km=600):
    for e in evts:
        cands = [t for t, la, lo, _ in fixes
                 if e["t_imd"] - timedelta(days=window_days) <= t <= e["t_imd"]
                 and S.great_circle_km(la, lo, e["lat"], e["lon"]) <= max_km]
        e["t_invest"] = min(cands) if cands else None
    return evts
