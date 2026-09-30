"""
Validation case-set builder (master plan v4, Tasks 3.3 / 3.4)
═════════════════════════════════════════════════════════════
Builds real 6×3-hourly INSAT + IMERG windows for:
  * positives — each 2024+ North Indian Ocean system (IBTrACS NI best track) at its first
    3-hourly time over open ocean (DIST2LAND >= 100 km), plus the peak of CS+ systems;
  * negatives — times with no NI system active within ±3 days.
Frames are cached in data/validation/frames (never pruned) and cases listed in
data/validation/cases.jsonl. The same frames seed the real-imagery retraining set.

Usage:
  python -m data_pipeline.validation.build_case_set --max-positives 14 --max-negatives 8
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from data_pipeline.ingestion.live_pipeline_runner import build_frame, select_window, log  # noqa: E402
from data_pipeline.ingestion.mosdac_worker import MosdacIngestionWorker  # noqa: E402
from data_pipeline.ingestion.nasa_gpm_worker import NasaGpmIngestionWorker  # noqa: E402
from data_pipeline.preprocessing.tensor_assembler import TensorAssembler  # noqa: E402

IBTRACS_NI = ROOT / "data" / "static" / "ibtracs.NI.list.v04r01.csv"
OUT_DIR = ROOT / "data" / "validation"
FRAME_DIR = OUT_DIR / "frames"
CASES = OUT_DIR / "cases.jsonl"
BBOX = (0.0, 32.0, 50.0, 102.0)
NEGATIVE_CANDIDATES = [  # spread across seasons; filtered against IBTrACS below
    "2024-06-18T06:00Z", "2024-07-08T06:00Z", "2024-11-06T06:00Z", "2025-01-15T06:00Z",
    "2025-03-12T06:00Z", "2025-04-20T06:00Z", "2025-06-12T06:00Z", "2025-08-06T06:00Z",
    "2025-11-12T06:00Z", "2026-01-20T06:00Z", "2026-03-05T06:00Z",
]


def parse_t(s: str) -> datetime:
    """IBTrACS 'YYYY-MM-DD HH:MM:SS' (UTC) or ISO strings with Z → aware UTC datetime."""
    t = datetime.fromisoformat(s.replace("Z", "+00:00").replace(" ", "T"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def load_tracks(since_year=2024):
    rows = list(csv.DictReader(open(IBTRACS_NI, encoding="utf-8")))[1:]
    tracks = {}
    for r in rows:
        if int(r["SEASON"]) < since_year or r["SUBBASIN"] not in ("BB", "AS"):
            continue
        tracks.setdefault(r["SID"], []).append({
            "sid": r["SID"], "name": r["NAME"], "time": parse_t(r["ISO_TIME"]),
            "lat": float(r["LAT"]), "lon": float(r["LON"]),
            "dist2land": float(r["DIST2LAND"] or 0), "grade": r["NEWDELHI_GRADE"].strip(),
            "wind": float(r["NEWDELHI_WIND"].strip() or r["WMO_WIND"].strip() or 0),
        })
    return tracks


def in_box(p):
    return BBOX[0] + 3 <= p["lat"] <= BBOX[1] - 3 and BBOX[2] + 3.5 <= p["lon"] <= BBOX[3] - 3.5


def select_cases(tracks, max_pos, max_neg):
    pos = []
    for sid, pts in tracks.items():
        ocean = [p for p in pts if p["time"].hour % 3 == 0 and p["dist2land"] >= 100 and in_box(p)]
        if not ocean:
            continue
        first = ocean[0]
        pos.append({"kind": "positive", "stage": "genesis", **first})
        peak = max(ocean, key=lambda p: p["wind"])
        if peak["wind"] >= 34 and peak["time"] != first["time"]:
            pos.append({"kind": "positive", "stage": "peak", **peak})
    pos.sort(key=lambda c: c["time"])
    pos = pos[:max_pos]

    all_pts = [p for pts in tracks.values() for p in pts]
    neg = []
    for s in NEGATIVE_CANDIDATES:
        t = parse_t(s)
        if t > datetime.now(timezone.utc) - timedelta(days=2):
            continue
        if any(abs((p["time"] - t).total_seconds()) <= 3 * 86400 for p in all_pts):
            continue
        neg.append({"kind": "negative", "stage": "none", "sid": None, "name": None, "time": t,
                    "lat": None, "lon": None, "dist2land": None, "grade": None, "wind": 0.0})
    neg = neg[:max_neg]
    # Interleave (≈ 2 positives : 1 negative) so a partially built set is still balanced
    ordered = []
    while pos or neg:
        ordered += [pos.pop(0) for _ in range(min(2, len(pos)))]
        if neg:
            ordered.append(neg.pop(0))
    return ordered


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-positives", type=int, default=14)
    ap.add_argument("--max-negatives", type=int, default=8)
    ap.add_argument("--list-only", action="store_true")
    args = ap.parse_args()

    cases = select_cases(load_tracks(), args.max_positives, args.max_negatives)
    for c in cases:
        pos = "" if c["lat"] is None else f"{c['lat']:.1f}N {c['lon']:.1f}E"
        log(f"{c['kind']:8s} {c['stage']:7s} {c['time']:%Y-%m-%d %H}Z {c['name'] or '':10s} {pos} {c['grade'] or ''}")
    if args.list_only:
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    done = set()
    if CASES.exists():
        done = {json.loads(l)["case_id"] for l in CASES.read_text().splitlines() if l.strip()}

    gpm = NasaGpmIngestionWorker()
    gpm.authenticate()
    assembler = TensorAssembler()
    for c in cases:
        case_id = f"{c['kind']}_{c['time']:%Y%m%d%H}_{c['sid'] or 'none'}"
        if case_id in done:
            continue
        # INSAT-3DS from 2024; fall back to INSAT-3DR if the 3DS archive has no granule
        for dataset in ("3SIMG_L1C_ASIA_MER", "3RIMG_L1C_ASIA_MER"):
            insat = MosdacIngestionWorker(dataset_id=dataset)
            try:
                insat.authenticate()
                window = select_window(insat, c["time"] + timedelta(minutes=29))
                frames = []
                for i, m in enumerate(window, 1):
                    frames.append(build_frame(m, insat, gpm, assembler, frame_dir=FRAME_DIR, keep_frames=0)[1])
                    log(f"{case_id}: frame {i}/{len(window)} {m['granule_id']}")
                break
            except Exception as exc:
                log(f"{case_id}: {dataset} failed: {exc}")
                frames = None
            finally:
                insat.logout()
        if not frames:
            continue
        rec = {**c, "time": c["time"].isoformat(), "case_id": case_id,
               "frames": [Path(f["insat_granule"]).stem + ".npz" for f in frames], "frame_info": frames}
        with open(CASES, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        log(f"case done: {case_id}")


if __name__ == "__main__":
    main()
