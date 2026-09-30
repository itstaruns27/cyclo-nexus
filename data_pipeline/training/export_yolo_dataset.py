"""
Export the real-imagery training set to Ultralytics YOLO-OBB format (master plan v4, Task 3.4)
═════════════════════════════════════════════════════════════════════════════════════════════
Images: channels [TIR1, WV, split-window] of each (4, 1024, 1024) frame as an 8-bit RGB PNG —
exactly what inference/serve.py feeds YOLO (tensor[-1][:3]).
Labels: one axis-aligned oriented box per best-track point, centred on the official circulation
centre, side length by IMD grade (D/DD 3°, CS/SCS 4°, VSCS+ 5°). Negatives get empty label files.
Split: seasons >= --val-from go to val (no storm appears in both splits).

  python -m data_pipeline.training.export_yolo_dataset --val-from 2024
Produces data/training/yolo/{images,labels}/{train,val} and data/training/yolo/data.yaml.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

TRAIN = ROOT / "data" / "training"
BBOX = (0.0, 32.0, 50.0, 102.0)
SIZE_DEG = {"D": 3.0, "DD": 3.0, "CS": 4.0, "SCS": 4.0, "VSCS": 5.0, "ESCS": 5.0, "SuCS": 5.0}


def obb_label(lat, lon, grade):
    """YOLO-OBB line: class x1 y1 x2 y2 x3 y3 x4 y4 (normalised, clockwise from top-left)."""
    min_lat, max_lat, min_lon, max_lon = BBOX
    half = SIZE_DEG.get(grade or "D", 3.0) / 2
    x = lambda lo: min(max((lo - min_lon) / (max_lon - min_lon), 0.0), 1.0)
    y = lambda la: min(max((max_lat - la) / (max_lat - min_lat), 0.0), 1.0)
    corners = [(lon - half, lat + half), (lon + half, lat + half), (lon + half, lat - half), (lon - half, lat - half)]
    return "0 " + " ".join(f"{x(lo):.6f} {y(la):.6f}" for lo, la in corners)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--val-from", type=int, default=2024)
    args = ap.parse_args()

    out = TRAIN / "yolo"
    rows = [json.loads(l) for l in (TRAIN / "manifest.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    counts = {"train": [0, 0], "val": [0, 0]}
    for r in rows:
        split = "val" if int(r["time"][:4]) >= args.val_from else "train"
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)
        tensor = np.load(TRAIN / "frames" / r["frame"])["tensor"]
        rgb = (np.clip(tensor[:3], 0, 1) * 255).round().astype(np.uint8).transpose(1, 2, 0)
        Image.fromarray(rgb).save(out / "images" / split / f"{r['key']}.png")
        label = obb_label(r["lat"], r["lon"], r["grade"]) + "\n" if r["sid"] else ""
        (out / "labels" / split / f"{r['key']}.txt").write_text(label)
        counts[split][0 if r["sid"] else 1] += 1

    (out / "data.yaml").write_text(
        f"path: {out.as_posix()}\ntrain: images/train\nval: images/val\nnames:\n  0: tropical_cyclone\n")
    print(f"train: {counts['train'][0]} positive / {counts['train'][1]} negative; "
          f"val: {counts['val'][0]} positive / {counts['val'][1]} negative → {out}")


if __name__ == "__main__":
    main()
