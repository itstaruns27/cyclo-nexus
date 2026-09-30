"""
Real-imagery training-set builder (master plan v4, Task 3.4)
════════════════════════════════════════════════════════════
Replaces the synthetic tensors the shipped weights were trained on. For IBTrACS North Indian
Ocean best-track points (6-hourly, over ocean) it fetches the matching INSAT L1C granule
(INSAT-3DR from 2016, INSAT-3DS from 2024) and NASA IMERG rainfall through the same workers
as the live pipeline, and stores the (4, 1024, 1024) frame. Storm-free times are added as
negatives. Output: data/training/frames/*.npz + data/training/manifest.jsonl (resumable).

Run on a machine with an Indian IP (MOSDAC) and plenty of time; each frame is ~25 MB to download.
  python -m data_pipeline.training.build_training_set --since 2016 --per-storm 8 --negatives 150
Then: python -m data_pipeline.training.export_yolo_dataset
"""

import argparse
import csv
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from data_pipeline.ingestion.live_pipeline_runner import build_frame, log  # noqa: E402
from data_pipeline.ingestion.mosdac_worker import MosdacIngestionWorker  # noqa: E402
from data_pipeline.ingestion.nasa_gpm_worker import NasaGpmIngestionWorker  # noqa: E402
from data_pipeline.preprocessing.tensor_assembler import TensorAssembler  # noqa: E402

IBTRACS_NI = ROOT / "data" / "static" / "ibtracs.NI.list.v04r01.csv"
OUT = ROOT / "data" / "training"
FRAMES = OUT / "frames"
MANIFEST = OUT / "manifest.jsonl"
BBOX = (0.0, 32.0, 50.0, 102.0)
MATCH_TOLERANCE = timedelta(minutes=45)


def utc(s):
    t = datetime.fromisoformat(s.replace(" ", "T"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def load_points(since):
    pts = []
    for r in list(csv.DictReader(open(IBTRACS_NI, encoding="utf-8")))[1:]:
        if int(r["SEASON"]) < since or r["SUBBASIN"] not in ("BB", "AS"):
            continue
        t = utc(r["ISO_TIME"])
        lat, lon = float(r["LAT"]), float(r["LON"])
        if t.hour % 6 or float(r["DIST2LAND"] or 0) < 50:
            continue
        if not (BBOX[0] + 1 <= lat <= BBOX[1] - 1 and BBOX[2] + 1 <= lon <= BBOX[3] - 1):
            continue
        pts.append({"sid": r["SID"], "name": r["NAME"], "time": t, "lat": lat, "lon": lon,
                    "grade": r["NEWDELHI_GRADE"].strip() or None,
                    "wind_kt": float(r["NEWDELHI_WIND"].strip() or r["WMO_WIND"].strip() or 0) or None})
    return pts


def pick_positives(points, per_storm):
    by_sid = {}
    for p in points:
        by_sid.setdefault(p["sid"], []).append(p)
    chosen = []
    for pts in by_sid.values():
        step = max(1, len(pts) // per_storm)
        chosen += pts[::step][:per_storm]
    return chosen


def pick_negatives(points, n, since, seed=7):
    rng = random.Random(seed)
    storm_times = [p["time"] for p in points]
    start = datetime(since, 1, 1, tzinfo=timezone.utc)
    end = datetime.now(timezone.utc) - timedelta(days=3)
    out, tries = [], 0
    while len(out) < n and tries < n * 50:
        tries += 1
        t = start + timedelta(hours=6 * rng.randrange(int((end - start).total_seconds() // 21600)))
        if all(abs((t - s).total_seconds()) > 3 * 86400 for s in storm_times):
            out.append({"sid": None, "name": None, "time": t, "lat": None, "lon": None, "grade": None, "wind_kt": None})
    return out


def dataset_for(t):
    return "3SIMG_L1C_ASIA_MER" if t >= datetime(2024, 4, 1, tzinfo=timezone.utc) else "3RIMG_L1C_ASIA_MER"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=int, default=2016)
    ap.add_argument("--per-storm", type=int, default=8)
    ap.add_argument("--negatives", type=int, default=150)
    ap.add_argument("--max-frames", type=int, default=0, help="stop after this many new frames (0 = no limit)")
    args = ap.parse_args()

    points = load_points(args.since)
    samples = pick_positives(points, args.per_storm) + pick_negatives(points, args.negatives, args.since)
    random.Random(11).shuffle(samples)  # interleave positives/negatives so partial runs stay balanced
    log(f"{len(samples)} samples planned ({sum(s['sid'] is not None for s in samples)} positive)")

    OUT.mkdir(parents=True, exist_ok=True)
    done = set()
    if MANIFEST.exists():
        done = {json.loads(l)["key"] for l in MANIFEST.read_text().splitlines() if l.strip()}

    gpm = NasaGpmIngestionWorker()
    gpm.authenticate()
    assembler = TensorAssembler()
    workers = {}
    new = 0
    for s in samples:
        key = f"{s['time']:%Y%m%d%H}_{s['sid'] or 'neg'}"
        if key in done:
            continue
        ds = dataset_for(s["time"])
        if ds not in workers:
            workers[ds] = MosdacIngestionWorker(dataset_id=ds)
            workers[ds].authenticate()
        w = workers[ds]
        try:
            entries = w.search_granules(start=s["time"] - timedelta(days=1), end=s["time"], count=100)
            meta = min(entries, key=lambda e: abs(e["obs_time"] - s["time"]), default=None)
            if not meta or abs(meta["obs_time"] - s["time"]) > MATCH_TOLERANCE:
                log(f"{key}: no granule within {MATCH_TOLERANCE}")
                continue
            _, info = build_frame(meta, w, gpm, assembler, frame_dir=FRAMES, keep_frames=0)
        except Exception as exc:
            log(f"{key}: failed ({exc})")
            continue
        rec = {**s, "time": s["time"].isoformat(), "key": key, "frame": Path(meta["granule_id"]).stem + ".npz",
               "frame_info": info}
        with open(MANIFEST, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        new += 1
        log(f"{key}: ok ({new} new)")
        if args.max_frames and new >= args.max_frames:
            break
    for w in workers.values():
        w.logout()


if __name__ == "__main__":
    main()
