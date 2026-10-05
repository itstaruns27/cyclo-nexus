"""
NWP track guidance for North Indian Ocean storms
════════════════════════════════════════════════
Three open sources, one row format:

  ECMWF open data (AWS bucket ecmwf-forecasts, 18 Jan 2023 →): ready-made tropical-cyclone tracks
      (`*-tf.bufr`) from ECMWF's own tracker for IFS HRES, the IFS 51-member ensemble, AIFS
      (ECMWF's machine-learning model) and the AIFS ensemble. CC-BY 4.0.
  UCAR RAL ATCF repository (2003 → previous season): open a-decks with NCEP's tracker output
      for GFS (AVNX/AVNO), the GEFS mean (AEMN), Canadian (CMC), UK Met Office (UKM), Navy (NGX).
  IBTrACS v04 NI (NOAA NCEI): JTWC best-track positions — the verification truth. Public domain.

Row: dict(model, init (UTC datetime), atcf "IO032024", member (0 = deterministic), tau (h),
          lat, lon, vmax_kt, pmin_hpa)   — NaN when the model did not report a value.
"""

import csv
import random
import re
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import requests

ECMWF_BUCKET = "https://ecmwf-forecasts.s3.eu-central-1.amazonaws.com"
ECMWF_LIVE = "https://data.ecmwf.int/forecasts"
RAL_ADECK = "https://hurricanes.ral.ucar.edu/repository/data/adecks_open/{year}/aio{num:02d}{year}.dat"
RAL_REALTIME = "https://hurricanes.ral.ucar.edu/realtime/plots/northindian/{year}/io{num:02d}{year}/aio{num:02d}{year}.dat"
KT_PER_MS = 1.943844
MISSING = 1e90

_session = threading.local()
_ECCODES = threading.Lock()   # eccodes handles are not thread-safe: decode one file at a time


def http():
    if not hasattr(_session, "s"):
        _session.s = requests.Session()
        _session.s.headers["User-Agent"] = "Cyclo-Nexus research (SIH26070)"
    return _session.s


def get(url, timeout=60, tries=6, **kw):
    """GET with exponential backoff on throttling (S3 "503 Slow Down") and transient errors."""
    for i in range(tries):
        try:
            r = http().get(url, timeout=timeout, **kw)
            if r.status_code not in (429, 500, 502, 503, 504):
                return r
        except requests.RequestException:
            if i == tries - 1:
                raise
        time.sleep(min(60, 2 ** i + random.random()))
    r.raise_for_status()
    return r


def fetch(url, path, timeout=60, fresh=False):
    """Download once into the cache (always, if `fresh`); returns the path, or None on 404."""
    path = Path(path)
    if not fresh and path.exists() and path.stat().st_size > 0:
        return path
    r = get(url, timeout=timeout)
    if r.status_code in (403, 404):
        return None
    r.raise_for_status()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(r.content)
    tmp.replace(path)
    return path


# ─── ECMWF tropical-cyclone track BUFR ─────────────────────────────────────

def ecmwf_model(key):
    """Model name for a `*-tf.bufr` key, from its path (the layout changed several times since 2023)."""
    k = key.lower()
    if "aifs-ens" in k:
        return "AIFS-ENS"
    if "aifs" in k:
        return "AIFS"
    if "enfo" in k:
        return "IFS-ENS"
    if "oper" in k or "scda" in k:
        return "IFS"
    return None


def ecmwf_keys(init):
    """{model: key} for every track file of one run in the AWS archive (prefers 0.25° over 0.4°)."""
    prefix = f"{init:%Y%m%d}/{init:%H}z/"
    r = get(ECMWF_BUCKET, params={"list-type": "2", "prefix": prefix})
    r.raise_for_status()
    keys = re.findall(r"<Key>([^<]*-tf\.bufr)</Key>", r.text)
    out = {}
    for k in sorted(keys, key=lambda s: ("0p4" in s, len(s))):   # 0p25 and shortest path first
        m = ecmwf_model(k)
        if m and m not in out:
            out[m] = k
    return out


def _ranked(h, name):
    """All ranks of a BUFR element: list of arrays (one value per subset)."""
    import eccodes
    out, r = [], 1
    while True:
        try:
            out.append(np.asarray(eccodes.codes_get_array(h, f"#{r}#{name}"), float))
        except Exception:
            return out
        r += 1


def parse_ecmwf_bufr(path, model, init, basins=("A", "B")):
    """Track rows for storms whose ID ends in one of `basins` (A Arabian Sea, B Bay of Bengal)."""
    import eccodes
    rows = []
    with _ECCODES, open(path, "rb") as f:
        while True:
            h = eccodes.codes_bufr_new_from_file(f)
            if h is None:
                break
            try:
                eccodes.codes_set(h, "unpack", 1)
                ns = eccodes.codes_get(h, "numberOfSubsets")
                ids = eccodes.codes_get_array(h, "#1#stormIdentifier") if ns > 1 else [eccodes.codes_get(h, "#1#stormIdentifier")]
                sid = str(ids[0]).strip()
                if not sid or sid[-1] not in basins:
                    continue
                atcf = f"IO{sid[:-1].zfill(2)}{init.year}"
                members = np.broadcast_to(np.asarray(eccodes.codes_get_array(h, "#1#ensembleMemberNumber")), (ns,))
                ftype = np.broadcast_to(np.asarray(eccodes.codes_get_array(h, "#1#ensembleForecastType")), (ns,))
                lat, lon = _ranked(h, "latitude"), _ranked(h, "longitude")
                pres, wind = _ranked(h, "pressureReducedToMeanSeaLevel"), _ranked(h, "windSpeedAt10M")
                taus = [0] + [int(np.asarray(t).ravel()[0]) for t in _ranked(h, "timePeriod")]
                for j, tau in enumerate(taus):
                    li = 1 if j == 0 else 3 + 2 * (j - 1)          # 0-based index into the rank lists
                    if li >= len(lat) or j >= len(pres) or j >= len(wind):
                        break
                    la = np.broadcast_to(lat[li], (ns,))
                    lo = np.broadcast_to(lon[li], (ns,))
                    pr = np.broadcast_to(pres[j], (ns,))
                    wd = np.broadcast_to(wind[j], (ns,))
                    for s in range(ns):
                        if abs(la[s]) > MISSING or abs(lo[s]) > MISSING:
                            continue
                        # HRES inside the ENS file duplicates the IFS file: keep ensemble members only
                        if model.endswith("-ENS") and ftype[s] == 0:
                            continue
                        member = 0 if not model.endswith("-ENS") else int(members[s])
                        rows.append(dict(
                            model=model, init=init, atcf=atcf, member=member, tau=tau,
                            lat=round(float(la[s]), 2), lon=round(float(lo[s]) % 360, 2),
                            vmax_kt=round(float(wd[s]) * KT_PER_MS, 1) if abs(wd[s]) < MISSING else np.nan,
                            pmin_hpa=round(float(pr[s]) / 100, 1) if abs(pr[s]) < MISSING else np.nan))
            finally:
                eccodes.codes_release(h)
    return rows


def ecmwf_run(init, cache, models=("IFS", "IFS-ENS", "AIFS", "AIFS-ENS")):
    """All North Indian Ocean track rows of one ECMWF run (archive)."""
    rows = []
    for model, key in ecmwf_keys(init).items():
        if model not in models:
            continue
        p = fetch(f"{ECMWF_BUCKET}/{key}", Path(cache) / "ecmwf" / key.replace("/", "_"))
        if p:
            rows += parse_ecmwf_bufr(p, model, init)
    return rows


# ─── ATCF a-decks (UCAR RAL) ───────────────────────────────────────────────

def _latlon(s):
    v = int(s[:-1]) / 10
    return -v if s[-1] in "SW" else v


def parse_adeck(path, techs=None):
    """Rows from an ATCF a-deck; one per (tech, init, tau) — the 34/50/64-kt radius lines are merged."""
    seen, rows = set(), []
    with open(path, newline="", encoding="latin-1") as f:
        for rec in csv.reader(f):
            rec = [c.strip() for c in rec]
            if len(rec) < 9 or not rec[6] or not rec[7]:
                continue
            tech = rec[4]
            if techs and tech not in techs:
                continue
            try:
                init = datetime.strptime(rec[2], "%Y%m%d%H").replace(tzinfo=timezone.utc)
                tau = int(rec[5] or 0)
                atcf = f"{rec[0]}{int(rec[1]):02d}{rec[2][:4]}"
                lat, lon = _latlon(rec[6]), _latlon(rec[7]) % 360
            except ValueError:
                continue                                           # malformed line
            key = (tech, init, tau)
            if key in seen:
                continue
            seen.add(key)
            num = lambda s: float(s) if s.replace(".", "", 1).isdigit() and float(s) > 0 else np.nan  # noqa: E731
            rows.append(dict(model=tech, init=init, atcf=atcf, member=0, tau=tau, lat=lat, lon=lon,
                             vmax_kt=num(rec[8]), pmin_hpa=num(rec[9]) if len(rec) > 9 else np.nan))
    return rows


def adeck(atcf, cache, techs=None):
    """a-deck rows for e.g. 'IO032024': RAL archive, else its real-time folder (current season). None if neither."""
    num, year = int(atcf[2:4]), int(atcf[4:])
    dest = Path(cache) / "adeck" / f"a{atcf.lower()}.dat"
    p = fetch(RAL_ADECK.format(year=year, num=num), dest) or fetch(RAL_REALTIME.format(year=year, num=num), dest)
    return parse_adeck(p, techs) if p else None


# ─── IBTrACS truth ─────────────────────────────────────────────────────────

def ibtracs_storms(csv_path, since=2018):
    """{atcf: {name, sid, season, fixes: [(time, lat, lon, wind_kt)]}} — JTWC positions at 00/06/12/18 UTC."""
    storms = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        next(rd)                                                   # units row
        for r in rd:
            if int(r["SEASON"]) < since or not r["USA_ATCF_ID"].strip():
                continue
            t = datetime.strptime(r["ISO_TIME"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if t.hour % 6 or t.minute:
                continue
            lat, lon = r["USA_LAT"].strip(), r["USA_LON"].strip()
            if not lat or not lon:
                continue
            atcf = r["USA_ATCF_ID"].strip().upper()
            s = storms.setdefault(atcf, dict(name=r["NAME"].strip(), sid=r["SID"], season=int(r["SEASON"]), fixes=[]))
            w = r["USA_WIND"].strip()
            s["fixes"].append((t, float(lat), float(lon) % 360, float(w) if w else np.nan))
    for s in storms.values():
        s["fixes"].sort()
    return storms


def truth_lookup(storms):
    """{(atcf, time): (lat, lon, wind_kt)}"""
    out = {}
    for atcf, s in storms.items():
        for t, la, lo, w in s["fixes"]:
            out[(atcf, t)] = (la, lo, w)
    return out


def great_circle_km(lat1, lon1, lat2, lon2):
    r = np.pi / 180
    a = np.sin((lat2 - lat1) * r / 2) ** 2 + np.cos(lat1 * r) * np.cos(lat2 * r) * np.sin((lon2 - lon1) * r / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def synoptic_inits(fixes, start=datetime(2023, 1, 18, tzinfo=timezone.utc)):
    """Every 00/06/12/18 UTC run from 12 h before the first fix to the last fix."""
    t = max(fixes[0][0] - timedelta(hours=12), start)
    t = t.replace(hour=t.hour - t.hour % 6, minute=0, second=0)
    out = []
    while t <= fixes[-1][0]:
        out.append(t)
        t += timedelta(hours=6)
    return out


def group_tracks(rows):
    """{(model, init, atcf, member): [(tau, lat, lon, vmax, pmin)] sorted by tau}"""
    g = defaultdict(list)
    for r in rows:
        g[(r["model"], r["init"], r["atcf"], r["member"])].append((r["tau"], r["lat"], r["lon"], r["vmax_kt"], r["pmin_hpa"]))
    for v in g.values():
        v.sort()
    return g
