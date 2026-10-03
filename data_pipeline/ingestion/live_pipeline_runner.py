"""
CYCLO-NEXUS Live Pipeline Orchestrator
══════════════════════════════════════
Every cycle:
  1. Find the newest INSAT-3DS L1C granule on MOSDAC and the 5 granules at 3-hour
     steps before it (t-15h … t0, the cadence the forecaster was trained on).
  2. For each step build a (4, 1024, 1024) tensor: INSAT TIR1 / WV / split-window
     plus the nearest NASA GPM IMERG precipitation field at or before that time.
     Built frames are cached in data/live/frames/ so later cycles only fetch new data.
  3. Satellite analysis (master plan v4, Task 3.2):
       a. every official system (JTWC / IBTrACS, from the backend) in the box gets INSAT/IMERG
          measurements within 350 km of its official centre → linked AI analysis;
       b. the physics detector (DAV organisation + deep convection + rain + persistence) looks
          for organised systems away from official ones; candidates over warm ocean
          (Open-Meteo marine SST ≥ 26.5 °C) are published as satellite *watch areas*.
  4. The window is also sent to the FastAPI inference service (uint8 transport, Task 4.1).
     YOLO detections are used only as extra candidates (same SST/ocean test); the forecaster
     track is attached only when AI_FORECAST_ENABLED=true (not validated on real data yet).
  5. A signed heartbeat reports the run (drives /api/v1/health freshness).
All webhooks are gzip + HMAC-SHA256 over "<timestamp>.<body>".

Usage:
  python -m data_pipeline.ingestion.live_pipeline_runner                    # one cycle
  python -m data_pipeline.ingestion.live_pipeline_runner --interval-minutes 30
  python -m data_pipeline.ingestion.live_pipeline_runner --at 2024-05-26T12:00Z --dry-run
"""

import argparse
import base64
import gzip
import hashlib
import hmac
import json
import math
import os
import sys
import time
import traceback
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import requests
from dotenv import load_dotenv

# Ensure the root directory is in the Python path so 'data_pipeline' can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from data_pipeline.ingestion.mosdac_worker import MosdacIngestionWorker
from data_pipeline.ingestion.nasa_gpm_worker import NasaGpmIngestionWorker
from data_pipeline.preprocessing.physics_detector import Candidate, PhysicsDetector
from data_pipeline.preprocessing.tensor_assembler import TensorAssembler

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

BBOX = (0.0, 32.0, 50.0, 102.0)  # (min_lat, max_lat, min_lon, max_lon) — NIO
SEQ_LEN = 6
STEP_HOURS = 3
STEP_TOLERANCE = timedelta(minutes=45)
MAX_GPM_LAG = timedelta(hours=1)
FORECAST_HORIZONS = [6, 12, 24, 48, 72]
FRAME_DIR = Path(__file__).resolve().parents[2] / "data" / "live" / "frames"
KEEP_FRAMES = 24

INFERENCE_URL = os.environ.get("INFERENCE_URL", "http://localhost:8000/predict")
BACKEND_API = os.environ.get("BACKEND_API_URL", "http://localhost:3001/api/v1").rstrip("/")
WEBHOOK_URL = f"{BACKEND_API}/webhook/inference"
HEARTBEAT_URL = f"{BACKEND_API}/webhook/heartbeat"
TENSOR_TRANSPORT = os.environ.get("TENSOR_TRANSPORT", "uint8")        # uint8 | float32
MIN_CONFIDENCE = float(os.environ.get("DETECTION_MIN_CONFIDENCE", "0.7"))  # YOLO; 0.7 → 3/55 storm-free false alarms (docs/validation_report.md)
WATCH_MIN_SCORE = float(os.environ.get("WATCH_MIN_SCORE", "0.95"))       # physics detector; see docs/validation_report.md
AI_FORECAST_ENABLED = os.environ.get("AI_FORECAST_ENABLED", "false").lower() == "true"
MIN_GENESIS_SST_C = 26.5
OFFICIAL_EXCLUSION_KM = 500.0     # candidates this close to an official system belong to it
WATCH_MATCH_KM = 400.0            # reuse a watch-area ID within this distance …
WATCH_MATCH_AGE = timedelta(hours=12)  # … if it was seen this recently


def log(msg: str):
    print(f"[{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%SZ}] {msg}", flush=True)


def iso_z(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(s) -> datetime:
    t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


# ── Frame building ─────────────────────────────────────────────────

def _fill_missing(arr: np.ndarray, value: float) -> np.ndarray:
    out = arr.copy()
    out[np.isnan(out)] = value
    return out


def build_frame(meta: dict, insat: MosdacIngestionWorker, gpm: NasaGpmIngestionWorker,
                assembler: TensorAssembler, frame_dir: Path = FRAME_DIR, keep_frames: int = KEEP_FRAMES) -> tuple:
    """(4,1024,1024) tensor + provenance for one INSAT granule, cached on disk (keep_frames=0: never prune)."""
    frame_dir.mkdir(parents=True, exist_ok=True)
    cache = frame_dir / (Path(meta["granule_id"]).stem + ".npz")
    if cache.exists():
        with np.load(cache, allow_pickle=False) as z:
            info = json.loads(str(z["info"]))
            lag = datetime.fromisoformat(info["insat_time"]) - datetime.fromisoformat(info["gpm_time"])
            recent = datetime.now(timezone.utc) - datetime.fromisoformat(info["insat_time"]) < timedelta(hours=24)
            if lag <= MAX_GPM_LAG or not recent:
                return z["tensor"], info
        log(f"Rebuilding {cache.name}: cached GPM lagged {lag}, a closer granule may exist now")

    path = insat.download_granule(meta)
    ch = insat.extract_frame(path, BBOX)
    gframe = gpm.fetch_latest(BBOX, before=meta["obs_time"] + timedelta(minutes=29))

    # Gaps (outside disk / bad scan lines) → field median for BT, dry for rain
    tir1 = _fill_missing(ch["TIR1"], float(np.nanmedian(ch["TIR1"])))
    tir2 = _fill_missing(ch["TIR2"], float(np.nanmedian(ch["TIR2"])))
    wv = _fill_missing(ch["WV"], float(np.nanmedian(ch["WV"])))
    rain = _fill_missing(gframe.precip, 0.0)

    tensor = assembler.assemble_tensor(tir1, BBOX, tir2, BBOX, wv, BBOX, rain, BBOX)
    info = {
        "insat_granule": meta["granule_id"], "insat_time": meta["obs_time"].isoformat(),
        "gpm_granule": gframe.granule, "gpm_time": gframe.obs_time.isoformat(),
    }
    np.savez_compressed(cache, tensor=tensor, info=json.dumps(info))
    if keep_frames:
        for old in sorted(frame_dir.glob("*.npz"), key=lambda p: p.stat().st_mtime, reverse=True)[keep_frames:]:
            old.unlink(missing_ok=True)
    return tensor, info


def select_window(insat: MosdacIngestionWorker, at: datetime = None) -> list:
    """Granule metadata for t0-15h … t0 at 3-hour steps (oldest first); t0 = newest granule at/before `at`."""
    latest = insat.fetch_latest_granule_metadata(at)
    t0 = latest["obs_time"]
    entries = insat.search_granules(start=t0 - timedelta(hours=STEP_HOURS * SEQ_LEN + 24), end=t0, count=2000)
    window = []
    for k in range(SEQ_LEN - 1, -1, -1):
        target = t0 - timedelta(hours=STEP_HOURS * k)
        best = min(entries, key=lambda e: abs(e["obs_time"] - target), default=None)
        if best is None or abs(best["obs_time"] - target) > STEP_TOLERANCE:
            log(f"WARNING: no INSAT granule within {STEP_TOLERANCE} of {iso_z(target)}")
            window.append(None)
        else:
            window.append(best)
    if window[-1] is None:
        window[-1] = latest
    # Fill gaps with the nearest later real frame (never synthetic data)
    for i in range(len(window) - 2, -1, -1):
        if window[i] is None:
            window[i] = window[i + 1]
    return window


# ── Geography helpers ──────────────────────────────────────────────

def haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def basin_for(lat: float, lon: float) -> str:
    return "AS" if lon < 78.0 else "BOB"


def sea_surface_temperature(points: list) -> list:
    """Current SST (°C) per (lat, lon) from Open-Meteo marine; None over land. Raises if the API fails."""
    if not points:
        return []
    resp = requests.get("https://marine-api.open-meteo.com/v1/marine", params={
        "latitude": ",".join(f"{p[0]:.3f}" for p in points),
        "longitude": ",".join(f"{p[1]:.3f}" for p in points),
        "current": "sea_surface_temperature",
    }, timeout=30)
    resp.raise_for_status()
    body = resp.json()
    body = body if isinstance(body, list) else [body]
    return [b.get("current", {}).get("sea_surface_temperature") for b in body]


# ── Backend I/O ────────────────────────────────────────────────────

def fetch_active_systems() -> list:
    resp = requests.get(f"{BACKEND_API}/cyclones", timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", [])


def post_signed(url: str, payload: dict) -> requests.Response:
    """gzip + HMAC-SHA256 over "<timestamp>.<body>" (Micro-Task 1.4 + replay protection)."""
    secret = os.environ.get("WEBHOOK_SECRET", "")
    if len(secret) < 32:
        raise EnvironmentError("WEBHOOK_SECRET missing or too short in data_pipeline/.env")
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ts = iso_z(datetime.now(timezone.utc))
    sig = hmac.new(secret.encode(), ts.encode() + b"." + body, hashlib.sha256).hexdigest()
    compressed = gzip.compress(body, compresslevel=6)
    log(f"POST {url.rsplit('/', 1)[-1]}: {len(body)} bytes raw -> {len(compressed)} bytes gzip, sig {sig[:16]}…")
    resp = requests.post(url, data=compressed, timeout=60, headers={
        "Content-Type": "application/json", "Content-Encoding": "gzip", "X-CycloNexus-Version": "1.0.0",
        "X-CycloNexus-Signature": sig, "X-CycloNexus-Timestamp": ts,
    })
    if not resp.ok:
        raise RuntimeError(f"{url} failed with status {resp.status_code}: {resp.text[:500]}")
    return resp


def send_heartbeat(status: str, message: str, last_data_time: datetime = None, details: dict = None):
    try:
        post_signed(HEARTBEAT_URL, {
            "component": "satellite_pipeline", "status": status, "message": message[:1000],
            "last_data_time": iso_z(last_data_time) if last_data_time else None, "details": details or {},
        })
    except Exception as exc:
        log(f"WARNING: heartbeat not delivered: {exc}")


def feature_collection(cyclone_id: str, lat: float, lon: float, obs_time: datetime, props: dict,
                       status: str = None, link_cyclone_id: str = None, forecast: list = None) -> dict:
    meta = {
        "payload_version": "1.0.0", "cyclone_id": cyclone_id, "basin": basin_for(lat, lon),
        "generated_at": iso_z(datetime.now(timezone.utc)), "source": "AI_SATELLITE",
    }
    if status:
        meta["status"] = status
    if link_cyclone_id:
        meta["link_cyclone_id"] = link_cyclone_id
    features = [{
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [round(lon, 4), round(lat, 4)]},
        "properties": {"feature_type": "current_eye", "timestamp": iso_z(obs_time), **props},
    }]
    for f in forecast or []:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(f["lon"], 4), round(f["lat"], 4)]},
            "properties": {"feature_type": "forecast_track", "forecast_hour": f["hour"],
                           "sustained_wind_knots": f["wind_kt"], "central_pressure_hpa": f["pressure_hpa"]},
        })
    return {"type": "FeatureCollection", "metadata": meta, "features": features}


# ── Inference ──────────────────────────────────────────────────────

def run_inference(window_tensor: np.ndarray, obs_time: datetime) -> dict:
    if TENSOR_TRANSPORT == "uint8":
        raw = np.ascontiguousarray(np.round(np.clip(window_tensor, 0.0, 1.0) * 255.0).astype(np.uint8))
    else:
        raw = np.ascontiguousarray(window_tensor, dtype=np.float32)
    tensor_b64 = base64.b64encode(zlib.compress(raw.tobytes(), level=6)).decode("ascii")
    log(f"Inference payload: {len(tensor_b64) / 1024 / 1024:.1f} MB base64 ({TENSOR_TRANSPORT})")
    headers = {"X-API-Key": os.environ["INFERENCE_API_KEY"]} if os.environ.get("INFERENCE_API_KEY") else {}
    resp = requests.post(INFERENCE_URL, timeout=600, headers=headers, json={
        "cyclone_id": f"SCAN-{obs_time:%Y%m%d%H%M}", "timestamp": obs_time.isoformat(),
        "tensor_b64": tensor_b64, "tensor_shape": [SEQ_LEN, 4, 1024, 1024], "tensor_dtype": TENSOR_TRANSPORT,
    })
    if not resp.ok:
        raise RuntimeError(f"Inference API failed with status {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def forecast_points(result: dict, lat: float, lon: float) -> list:
    """Forecaster output → absolute points, or [] when disabled / non-finite."""
    if not AI_FORECAST_ENABLED or not result:
        return []
    pts = []
    for i, h in enumerate(FORECAST_HORIZONS):
        d_lat, d_lon = (float(x) for x in result["track_delta"][i])
        wind, dp = float(result["v_max_pred"][i]), float(result["dp_pred"][i])
        if not all(math.isfinite(x) for x in (d_lat, d_lon, wind, dp)):
            log("WARNING: forecaster returned non-finite values; AI forecast skipped")
            return []
        pts.append({"hour": h, "lat": lat + d_lat, "lon": lon + d_lon, "wind_kt": wind, "pressure_hpa": 1010.0 - dp})
    return pts


# ── Main cycle ─────────────────────────────────────────────────────

def run_live_pipeline(at: datetime = None, dry_run: bool = False) -> dict:
    """One cycle. `at` replays a past time (default: newest data); `dry_run` skips all webhooks."""
    log(f"CYCLO-NEXUS cycle starting ({'replay at ' + iso_z(at) if at else 'live'}{', dry run' if dry_run else ''})")
    insat = MosdacIngestionWorker()
    gpm = NasaGpmIngestionWorker()
    insat.authenticate()
    gpm.authenticate()
    assembler = TensorAssembler()

    try:
        window = select_window(insat, at)
        frames, infos = [], []
        for meta in window:
            tensor, info = build_frame(meta, insat, gpm, assembler)
            frames.append(tensor)
            infos.append(info)
            log(f"frame {info['insat_granule']}  (GPM {info['gpm_granule'][:40]}…, "
                f"lag {datetime.fromisoformat(info['insat_time']) - datetime.fromisoformat(info['gpm_time'])})")
    finally:
        insat.logout()

    obs_time = window[-1]["obs_time"]
    window_tensor = np.stack(frames, axis=0)  # (6, 4, 1024, 1024)
    assert window_tensor.shape == (SEQ_LEN, 4, 1024, 1024), window_tensor.shape
    assert np.isfinite(window_tensor).all(), "non-finite values in input window"
    gpm_lag_h = (obs_time - parse_time(infos[-1]["gpm_time"])).total_seconds() / 3600
    summary = {"obs_time": iso_z(obs_time), "gpm_lag_hours": round(gpm_lag_h, 1),
               "frames": [i["insat_granule"] for i in infos], "published": [], "warnings": []}

    # 3b. Physics detector → (candidate, method) pairs above the watch threshold
    detector = PhysicsDetector(BBOX)
    candidates = [(c, "physics_dav_v1") for c in detector.detect(window_tensor)
                  if c.passes and c.score >= WATCH_MIN_SCORE]
    log(f"Physics detector: {len(candidates)} candidate(s) at or above score {WATCH_MIN_SCORE}")

    # 4. Inference service (optional for the physics path; failures degrade, not abort)
    result = None
    try:
        result = run_inference(window_tensor, obs_time)
        conf = float(result.get("detection_confidence", 0.0))
        log(f"YOLO: detected={result.get('detected')} confidence={conf:.3f}")
        if result.get("detected") and conf >= MIN_CONFIDENCE:
            obb = result["obb"]
            ylat = BBOX[1] - float(obb["y_center"]) * (BBOX[1] - BBOX[0])
            ylon = BBOX[2] + float(obb["x_center"]) * (BBOX[3] - BBOX[2])
            m = detector.measure(window_tensor[-1], ylat, ylon)
            if m:
                candidates.append((Candidate(
                    lat=ylat, lon=ylon, dav_deg2=float("nan"), shield_km2=m["cold_cloud_km2"],
                    core_km2=m["core_km2"], min_cloud_top_k=m["min_cloud_top_k"], max_rain_mmhr=m["max_rain_mmhr"],
                    heavy_rain_km2=m["heavy_rain_km2"], persistence_frames=1, over_ocean=True, passes=True,
                    score=conf), "yolo_obb"))
    except Exception as exc:
        summary["warnings"].append(f"inference: {exc}")
        log(f"WARNING: inference unavailable ({exc}); continuing with the physics detector")

    # 3a. Official systems
    try:
        systems = fetch_active_systems()
    except Exception as exc:
        systems = []
        summary["warnings"].append(f"backend: {exc}")
        log(f"WARNING: could not fetch active systems ({exc})")
    official = [s for s in systems if str(s.get("source", "")).startswith("OFFICIAL_")]
    watches = [s for s in systems if s.get("source") == "AI_SATELLITE" and s.get("status") == "watch"]

    payloads = []
    for s in official:
        lat, lon = float(s["current_lat"]), float(s["current_lon"])
        m = detector.measure(window_tensor[-1], lat, lon)
        if not m:
            continue
        log(f"Analysis of {s['cyclone_id']} at {lat:.1f}N {lon:.1f}E: min Tb {m['min_cloud_top_k']} K, "
            f"max rain {m['max_rain_mmhr']} mm/h")
        payloads.append(feature_collection(
            s["cyclone_id"], lat, lon, obs_time, {
                "detection_confidence": 1.0, "method": "insat_imerg_350km",
                "min_cloud_top_k": m["min_cloud_top_k"], "max_rain_mmhr": m["max_rain_mmhr"], "analysis": m,
            }, link_cyclone_id=s["cyclone_id"], forecast=forecast_points(result, lat, lon)))

    # 3b. Watch areas: away from official systems, over warm ocean
    fresh = [(c, method) for c, method in candidates if all(
        haversine_km(c.lat, c.lon, float(s["current_lat"]), float(s["current_lon"])) > OFFICIAL_EXCLUSION_KM
        for s in official)]
    try:
        ssts = sea_surface_temperature([(c.lat, c.lon) for c, _ in fresh])
    except Exception as exc:
        ssts = []
        summary["warnings"].append(f"sst: {exc}")
        log(f"WARNING: SST lookup failed ({exc}); watch areas withheld this cycle")
    for (c, method), sst in zip(fresh, ssts):
        if sst is None or sst < MIN_GENESIS_SST_C:
            log(f"Candidate {c.lat:.1f}N {c.lon:.1f}E rejected: {'over land' if sst is None else f'SST {sst} °C'}")
            continue
        match = min(((haversine_km(c.lat, c.lon, float(w["current_lat"]), float(w["current_lon"])), w["cyclone_id"])
                     for w in watches if obs_time - parse_time(w["observation_time"]) <= WATCH_MATCH_AGE),
                    default=None)
        cid = match[1] if match and match[0] <= WATCH_MATCH_KM else f"SATWATCH-{obs_time:%Y%m%d%H%M}-{len(payloads)}"
        d = c.to_dict()
        summary_text = (f"Organised deep convection over warm water (SST {sst:.1f} °C): coldest cloud top "
                        f"{d.get('min_cloud_top_k', 0):.0f} K, peak rain {d.get('max_rain_mmhr', 0):.0f} mm/h, "
                        f"persisting {d.get('persistence_frames', '?')} of {SEQ_LEN} frames (3-hourly).")
        log(f"Watch area {cid} at {c.lat:.1f}N {c.lon:.1f}E score {c.score:.2f} ({method})")
        payloads.append(feature_collection(cid, c.lat, c.lon, obs_time, {
            "detection_confidence": round(float(c.score), 3), "method": method, "sst_c": sst,
            "min_cloud_top_k": d.get("min_cloud_top_k"), "max_rain_mmhr": d.get("max_rain_mmhr"),
            "summary": summary_text, "candidate": d,
        }, status="watch", forecast=forecast_points(result, c.lat, c.lon)))

    status = "ok" if not summary["warnings"] else "degraded"
    message = (f"{len(official)} official system(s) analysed, "
               f"{sum(p['metadata'].get('status') == 'watch' for p in payloads)} watch area(s); "
               f"frame {window[-1]['granule_id']}, IMERG lag {gpm_lag_h:.1f} h")
    if dry_run:
        for p in payloads:
            log(f"[dry run] would publish {p['metadata']['cyclone_id']}: {json.dumps(p['features'][0]['properties'])[:300]}")
        summary["would_publish"] = [p["metadata"]["cyclone_id"] for p in payloads]
        log(f"Dry run complete — {message}")
        return summary

    for p in payloads:
        try:
            post_signed(WEBHOOK_URL, p)
            summary["published"].append(p["metadata"]["cyclone_id"])
        except Exception as exc:
            status = "degraded"
            summary["warnings"].append(f"webhook {p['metadata']['cyclone_id']}: {exc}")
            log(f"WARNING: {exc}")
    send_heartbeat(status, message + (f"; warnings: {'; '.join(summary['warnings'])}" if summary["warnings"] else ""),
                   obs_time, {"frames": summary["frames"], "gpm_lag_hours": summary["gpm_lag_hours"],
                              "published": summary["published"]})
    log(f"Cycle {status}: {message}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the CYCLO-NEXUS live pipeline on MOSDAC + NASA GPM data.")
    parser.add_argument("--interval-minutes", type=float, default=0,
                        help="Repeat every N minutes (0 = run one cycle and exit).")
    parser.add_argument("--at", type=parse_time, help="Replay a past UTC time, e.g. 2024-05-26T12:00Z (validation).")
    parser.add_argument("--dry-run", action="store_true", help="Run everything but do not call any webhook.")
    args = parser.parse_args()

    if args.at and args.interval_minutes > 0:
        parser.error("--at cannot be combined with --interval-minutes")
    if args.interval_minutes <= 0:
        print(json.dumps(run_live_pipeline(at=args.at, dry_run=args.dry_run), indent=2, default=str))
    else:
        while True:
            started = time.time()
            try:
                run_live_pipeline(dry_run=args.dry_run)
            except Exception as exc:
                log("Cycle failed:\n" + traceback.format_exc())
                if not args.dry_run:
                    send_heartbeat("error", f"Cycle failed: {exc}")
            time.sleep(max(60.0, args.interval_minutes * 60 - (time.time() - started)))
