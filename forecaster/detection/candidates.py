"""
Detector-fusion training set: every candidate the detectors raise on every stored INSAT frame
═══════════════════════════════════════════════════════════════════════════════════════════════
  python -m forecaster.detection.candidates            # → data/training/candidates.csv

For each of the 1,249 stored frames (2018–2025), the 3-hourly history before it is rebuilt from the store and
fed to the live physics detector (DAV organisation + cold cloud + rain + persistence) exactly as the pipeline
does (512² store upsampled to the live 1024² grid). Every DAV minimum is a candidate — passing or not.
YOLO-OBB boxes (all confidences ≥ 0.05) become candidates too.

Each candidate gets leak-free descriptors:
  * the physics detector's own measurements;
  * Dvorak-style ring / eye features at the candidate (forecaster/intensity/features.py, after eye auto-centring);
  * the GLOBAL infrared intensity model's estimate (trained on HURSAT-B1 2004–2015 storms worldwide — no INSAT
    season is in its training set, so it can be used in leave-one-season-out validation);
  * the YOLO confidence nearby (YOLO was trained on 2018–22: used only for comparison on 2024–25).
Label: within 300 km of a system in the IMD/IBTrACS best track at that time (any grade, D and above).
"""

import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from data_pipeline.preprocessing.physics_detector import PhysicsDetector  # noqa: E402
from forecaster.intensity.features import sample_features  # noqa: E402

TRAIN = ROOT / "data" / "training"
OUT = TRAIN / "candidates.csv"
BBOX = (0.0, 32.0, 50.0, 102.0)
MATCH_KM = 300.0
YOLO_WEIGHTS = ROOT / "vision" / "weights" / "vision_best.pt"


def hav(lat1, lon1, lat2, lon2):
    r = math.pi / 180
    a = math.sin((lat2 - lat1) * r / 2) ** 2 + math.cos(lat1 * r) * math.cos(lat2 * r) * math.sin((lon2 - lon1) * r / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(min(1.0, a)))


def load_x(stem):
    return np.load(TRAIN / "store" / f"{stem}.npz")["x"]


def to_live(x_u8):
    """512² uint8 store frame → live-like (4, 1024, 1024) float in [0, 1]."""
    return np.repeat(np.repeat(x_u8.astype(np.float32) / 255.0, 2, axis=1), 2, axis=2)


def yolo_boxes(model, x_u8):
    """[(lat, lon, conf)] for all OBB detections on the 512² store frame (first 3 channels, as served)."""
    import torch
    t = torch.from_numpy(x_u8[:3].astype(np.float32) / 255.0).unsqueeze(0)
    res = model(t, conf=0.05, verbose=False)
    out = []
    if res and res[0].obb is not None and len(res[0].obb):
        for (cx, cy, *_), c in zip(res[0].obb.xywhr.tolist(), res[0].obb.conf.tolist()):
            lat = BBOX[1] - cy / 512 * (BBOX[1] - BBOX[0])
            lon = BBOX[2] + cx / 512 * (BBOX[3] - BBOX[2])
            out.append((lat, lon, float(c)))
    return out


def main():
    import lightgbm as lgb
    from ultralytics import YOLO
    gmeta = json.loads((ROOT / "forecaster" / "weights" / "intensity_meta.json").read_text(encoding="utf-8"))
    gmodel = lgb.Booster(model_file=str(ROOT / "forecaster" / "weights" / "intensity_global_ir.txt"))
    gcols = gmeta["global_features"]
    yolo = YOLO(str(YOLO_WEIGHTS))
    det = PhysicsDetector(BBOX)
    frames = sorted((json.loads(line) for line in open(TRAIN / "frames.jsonl", encoding="utf-8")), key=lambda r: r["time"])
    times = [datetime.fromisoformat(r["time"]) for r in frames]
    rows = []
    for i, (r, t) in enumerate(zip(frames, times)):
        # 3-hourly history (up to 6 frames, oldest first) from the store
        hist, last = [i], t
        for j in range(i - 1, -1, -1):
            h = (last - times[j]).total_seconds() / 3600
            if h < 1.5:
                continue
            if h > 4.5:
                break
            hist.insert(0, j)
            last = times[j]
            if len(hist) == 6:
                break
        xs = [load_x(frames[k]["frame"]) for k in hist]
        window = np.stack([to_live(x) for x in xs])
        x = xs[-1]
        prev = xs[-2] if len(xs) > 1 else None
        prev_h = (t - times[hist[-2]]).total_seconds() / 3600 if len(hist) > 1 else None
        systems = [s for s in r["systems"] if s.get("in_domain") and s.get("wind_kt") is not None]
        cands = [("physics", c.lat, c.lon, c) for c in det.detect(window)]
        cands += [("yolo", la, lo, None) for la, lo, _ in yolo_boxes(yolo, x)]
        yb = yolo_boxes(yolo, x)
        for src, lat, lon, c in cands:
            f = sample_features(x, lat, lon, prev, lat if prev is not None else None, lon if prev is not None else None, prev_h,
                                extra={"month_sin": np.sin(2 * np.pi * t.month / 12), "month_cos": np.cos(2 * np.pi * t.month / 12),
                                       "arabian_sea": float(lon < 77.5 and lat > 5)})
            if f is None:
                continue
            g = float(gmodel.predict(pd.DataFrame([f])[gcols])[0])
            dists = [(hav(lat, lon, s["lat"], s["lon"]), s) for s in systems]
            near = min(dists, key=lambda d: d[0]) if dists else (np.inf, None)
            yconf = max([cf for la, lo, cf in yb if hav(lat, lon, la, lo) <= MATCH_KM], default=0.0)
            row = {"frame": r["frame"], "time": r["time"], "season": r["season"], "source": src, "lat": lat, "lon": lon,
                   "dist_km": near[0], "label": int(near[0] <= MATCH_KM),
                   "sys_sid": near[1]["sid"] if near[1] else None, "sys_wind_kt": near[1]["wind_kt"] if near[1] else None,
                   "global_ir_kt": g, "yolo_conf": yconf, "n_hist": len(hist), **f}
            if c is not None:
                row.update({"phys_score": c.score, "phys_passes": int(c.passes), "dav_deg2": c.dav_deg2,
                            "shield_km2": c.shield_km2, "core_km2": c.core_km2, "heavy_rain_km2": c.heavy_rain_km2,
                            "persist": c.persistence_frames, "min_bt": c.min_cloud_top_k, "max_rain": c.max_rain_mmhr})
            rows.append(row)
        if i % 50 == 0:
            print(f"{i}/{len(frames)} frames, {len(rows)} candidates", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT, index=False)
    print(f"{len(df)} candidates ({df.label.sum()} near a system) from {df.frame.nunique()} frames → {OUT}")


if __name__ == "__main__":
    main()
