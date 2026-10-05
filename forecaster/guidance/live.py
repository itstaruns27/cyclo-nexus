"""
Live AI consensus forecast (master plan v5, Task 1.4)
═════════════════════════════════════════════════════
  python -m forecaster.guidance.live            # publish for every active official system
  python -m forecaster.guidance.live --dry-run  # print, publish nothing

For each active official system (from the backend):
  1. newest ECMWF run whose track files are out (AIFS, IFS ensemble, IFS, AIFS ensemble — open data);
  2. the system's real-time a-deck from UCAR RAL (GFS, UKMET, Canadian, Navy …), downloaded fresh;
  3. the consensus of forecaster/weights/consensus.json, started from the official position at the run time;
  4. leads re-expressed as hours after the latest official observation, up to 72 h (the verified range),
     each with its 67% uncertainty radius, POSTed to /api/v1/webhook/forecast (signed) as AI_CONSENSUS.
Nothing is published unless AI_FORECAST_ENABLED=true and consensus.json passed the official-error check.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from forecaster.guidance import sources as S  # noqa: E402
from forecaster.guidance.consensus import blend, intensity_at, shifted  # noqa: E402

SETTINGS = ROOT / "forecaster" / "weights" / "consensus.json"
CACHE = ROOT / "data" / "guidance" / "live"
BACKEND_API = os.environ.get("BACKEND_API_URL", "http://localhost:3001/api/v1").rstrip("/")
MAX_LEAD_H = 72
MATCH_KM = 300
ECMWF_MODELS = ("IFS", "IFS-ENS", "AIFS", "AIFS-ENS")


def log(msg):
    print(f"[{datetime.now(timezone.utc):%H:%M:%SZ}] consensus: {msg}", flush=True)


def enabled():
    return os.environ.get("AI_FORECAST_ENABLED", "false").lower() == "true"


def latest_ecmwf_run(now, max_back_h=36):
    """(init, {model: key}) of the newest run that has AIFS or IFS-ENS tracks."""
    t = now.replace(minute=0, second=0, microsecond=0)
    t -= timedelta(hours=t.hour % 6)
    for _ in range(max_back_h // 6 + 1):
        keys = {m: k for m, k in S.ecmwf_keys(t).items() if m in ECMWF_MODELS}
        if "AIFS" in keys or "IFS-ENS" in keys:
            return t, keys
        t -= timedelta(hours=6)
    return None, {}


def ecmwf_tracks(init, keys):
    """{atcf: {model: {tau: (lat, lon, vmax)}}} with ensemble means (≥ 40% of members)."""
    rows = []
    for model, key in keys.items():
        p = S.fetch(f"{S.ECMWF_BUCKET}/{key}", CACHE / "ecmwf" / key.replace("/", "_"))
        if p:
            rows += S.parse_ecmwf_bufr(p, model, init)
    out = {}
    for (model, _, atcf, member), tr in S.group_tracks(rows).items():
        if model.endswith("-ENS"):
            continue
        out.setdefault(atcf, {})[model] = {tau: (la, lo, v) for tau, la, lo, v, _ in tr}
    for model in ("IFS-ENS", "AIFS-ENS"):
        by = {}
        for r in rows:
            if r["model"] == model:
                by.setdefault(r["atcf"], {}).setdefault(r["tau"], []).append(r)
        for atcf, taus in by.items():
            n0 = len(taus.get(0, [])) or max(len(v) for v in taus.values())
            out.setdefault(atcf, {})[f"{model}M"] = {
                tau: (float(np.mean([r["lat"] for r in rs])), float(np.mean([r["lon"] for r in rs])),
                      float(np.nanmean([r["vmax_kt"] for r in rs])) if any(r["vmax_kt"] == r["vmax_kt"] for r in rs) else np.nan)
                for tau, rs in taus.items() if len(rs) >= max(5, 0.4 * n0)}
    return out


def adeck_tracks(atcf, init):
    """{model: {tau: (lat, lon, vmax)}} for one run time from the fresh real-time a-deck; CARQ τ0 if present."""
    num, year = int(atcf[2:4]), int(atcf[4:])
    p = S.fetch(S.RAL_REALTIME.format(year=year, num=num), CACHE / "adeck" / f"a{atcf.lower()}.dat", fresh=True)
    if not p:
        return {}
    out = {}
    for r in S.parse_adeck(p):
        if r["init"] != init:
            continue
        m = "GFS" if r["model"] in ("AVNX", "AVNO") else r["model"]
        out.setdefault(m, {})[r["tau"]] = (r["lat"], r["lon"], r["vmax_kt"])
    return out


def position_at(detail, t):
    """Official position at time t from the system's track (±3 h), else None."""
    best = None
    for h in detail.get("history") or []:
        ht = datetime.fromisoformat(str(h["timestamp"]).replace("Z", "+00:00"))
        if ht.tzinfo is None:
            ht = ht.replace(tzinfo=timezone.utc)
        d = abs((ht - t).total_seconds())
        if d <= 3 * 3600 and (best is None or d < best[0]):
            best = (d, float(h["latitude"]), float(h["longitude"]), float(h["sustained_wind_knots"] or 0) or np.nan)
    return best[1:] if best else None


def match_atcf(system, tracks, start):
    """ATCF id of the ECMWF storm for this system: same JTWC number, else the nearest τ0 within MATCH_KM."""
    m = re.search(r"JTWC-(\d\d)([AB])-(\d{4})", system["cyclone_id"])
    if m:
        atcf = f"IO{m.group(1)}{m.group(3)}"
        if atcf in tracks:
            return atcf
    best = None
    for atcf, models in tracks.items():
        if int(atcf[2:4]) >= 70:
            continue                                       # model-generated genesis tracks
        for tr in models.values():
            if 0 in tr:
                d = S.great_circle_km(start[0], start[1] % 360, tr[0][0], tr[0][1])
                if d <= MATCH_KM and (best is None or d < best[0]):
                    best = (d, atcf)
    return best[1] if best else None


def forecast_for(system, detail, init, tracks, settings):
    start = position_at(detail, init)
    if start is None:
        log(f"{system['cyclone_id']}: no official position near {init:%d %H}Z — skipped")
        return None
    atcf = match_atcf(system, tracks, start)
    if not atcf:
        log(f"{system['cyclone_id']}: no ECMWF track within {MATCH_KM} km — skipped")
        return None
    models = dict(tracks[atcf])
    ad = adeck_tracks(atcf, init)
    if "CARQ" in ad and 0 in ad["CARQ"]:
        start = (ad["CARQ"][0][0], ad["CARQ"][0][1], start[2])   # JTWC's real-time analysis, as in verification
    models.update({k: v for k, v in ad.items() if k in settings["members"]})
    mem = {}
    for m, tr in models.items():
        if m in settings["members"]:
            s = shifted(tr, start, settings["alphas"].get(m, 1.0))
            if s:
                mem[m] = s
    obs = datetime.fromisoformat(str(system["observation_time"]).replace("Z", "+00:00"))
    if obs.tzinfo is None:
        obs = obs.replace(tzinfo=timezone.utc)
    lag_h = (obs - init).total_seconds() / 3600
    points = []
    for lead in range(6, MAX_LEAD_H + int(max(lag_h, 0)) + 1, 6):
        prim = {m: mem[m] for m in settings["primary"] if m in mem and lead in mem[m]}
        b = blend(prim, {m: {str(lead): 1.0} for m in prim}, lead) if len(prim) >= 2 else blend(mem, settings["weights"], lead)
        hour = int(round(lead - lag_h))
        if b is None or hour < 6 or hour > MAX_LEAD_H:
            continue
        cone = settings["cone_km"]
        keys = sorted(int(k) for k in cone)
        radius = float(np.interp(lead, keys, [cone[str(k)] for k in keys])) if keys else None
        v = intensity_at(mem, lead, start[2])
        verified = settings.get("test_mean_km", {})
        vk = sorted(int(k) for k in verified)
        err = float(np.interp(lead, vk, [verified[str(k)] for k in vk])) if vk else None
        points.append({"hour": hour, "lat": round(b[0], 2), "lon": round(((b[1] + 180) % 360) - 180, 2),
                       "wind_kt": None if v != v else round(v, 1), "cone_radius_km": None if radius is None else round(radius),
                       "verified_error_km": None if err is None else round(err)})
    if not points:
        return None
    return {"cyclone_id": system["cyclone_id"], "source": "AI_CONSENSUS",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "init_time": init.strftime("%Y-%m-%dT%H:%M:%SZ"), "members": sorted(mem), "points": points}


def publish(systems=None, post=None, dry_run=False, now=None):
    """Build and (unless dry_run) post consensus forecasts; returns the payloads."""
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    if not dry_run and not (enabled() and settings.get("passed_official_check")):
        log("disabled (AI_FORECAST_ENABLED off or consensus did not pass its verification)")
        return []
    if systems is None:
        systems = requests.get(f"{BACKEND_API}/cyclones", timeout=30).json().get("data", [])
    official = [s for s in systems if str(s.get("source", "")).startswith("OFFICIAL_") and s.get("status") == "active"]
    if not official:
        log("no active official systems")
        return []
    init, keys = latest_ecmwf_run(now or datetime.now(timezone.utc))
    if not init:
        log("no recent ECMWF track files")
        return []
    tracks = ecmwf_tracks(init, keys)
    log(f"ECMWF run {init:%Y-%m-%d %H}Z ({', '.join(sorted(keys))}): {len(tracks)} North Indian Ocean tracks")
    out = []
    for s in official:
        detail = requests.get(f"{BACKEND_API}/cyclones/{s['cyclone_id']}", timeout=30).json().get("data", {})
        fc = forecast_for(s, detail, init, tracks, settings)
        if not fc:
            continue
        out.append(fc)
        pts = ", ".join(f"+{p['hour']}h {p['lat']}N {p['lon']}E" for p in fc["points"][::2])
        log(f"{s['cyclone_id']}: {len(fc['members'])} members ({', '.join(fc['members'])}) → {pts}")
        if not dry_run and post:
            post(f"{BACKEND_API}/webhook/forecast", fc)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    poster = None
    if not args.dry_run:
        from data_pipeline.ingestion.live_pipeline_runner import post_signed
        poster = post_signed
    publish(post=poster, dry_run=args.dry_run)
