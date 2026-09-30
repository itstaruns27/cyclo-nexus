"""
Multi-horizon forecaster: real-window dataset builder + trainer (master plan v4, remaining item 7)
═════════════════════════════════════════════════════════════════════════════════════════════
Step 1 — build windows (needs MOSDAC + Earthdata, Indian IP; resumable):
  python -m forecaster.train_multi_horizon build --since 2016 --per-storm 6
  For each IBTrACS best-track point it assembles the same 6 × 3 h INSAT + IMERG window the live
  pipeline uses (select_window + build_frame), stores it downsampled to 256² as uint8, and labels
  every lead time in HORIZONS_H from the best track itself:
    track  = (lat, lon) at t+h minus (lat, lon) at t      [degrees]
    v_max  = wind at t+h                                  [knots]
    dp     = 1010 − pressure at t+h                       [hPa]
    mask   = 0 where the storm no longer exists at t+h
  Output: data/training/windows/*.npz + windows.jsonl

Step 2 — train (GPU recommended: Kaggle / Colab):
  python -m forecaster.train_multi_horizon train --epochs 40
  Storms from seasons >= --val-from are held out. Loss: MultiHorizonForecastLoss (track, wind,
  pressure + Atkinson-Holliday penalty). Best checkpoint → forecaster/weights/forecaster_best.pt
  (the previous file is kept as forecaster_best.legacy.pt). inference/serve.py detects the new
  heads automatically; keep AI_FORECAST_ENABLED=false until the val track error is acceptable.
"""

import argparse
import json
import shutil
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from forecaster.models.spatiotemporal_forecaster import CycloneForecaster  # noqa: E402

HORIZONS_H = CycloneForecaster.HORIZONS_H
OUT = ROOT / "data" / "training" / "windows"
INDEX = OUT / "windows.jsonl"
SIZE = 256
ENV_PRESSURE = 1010.0


# ── Labels ───────────────────────────────────────────────────────────────

def storm_tracks(since):
    """All best-track rows per storm (any hour), for label lookup at t+h."""
    import csv
    from data_pipeline.training.build_training_set import IBTRACS_NI, utc
    tracks = {}
    for r in list(csv.DictReader(open(IBTRACS_NI, encoding="utf-8")))[1:]:
        if int(r["SEASON"]) < since:
            continue
        wind = (r["NEWDELHI_WIND"].strip() or r["WMO_WIND"].strip())
        pres = (r["NEWDELHI_PRES"].strip() or r["WMO_PRES"].strip())
        tracks.setdefault(r["SID"], {})[utc(r["ISO_TIME"])] = (
            float(r["LAT"]), float(r["LON"]), float(wind) if wind else None, float(pres) if pres else None)
    return tracks


def labels_for(track, t):
    lat0, lon0, _, _ = track[t]
    y_track = np.zeros((len(HORIZONS_H), 2), np.float32)
    y_wind = np.zeros(len(HORIZONS_H), np.float32)
    y_dp = np.zeros(len(HORIZONS_H), np.float32)
    mask = np.zeros(len(HORIZONS_H), np.float32)
    for i, h in enumerate(HORIZONS_H):
        row = track.get(t + timedelta(hours=h))
        if not row or row[2] is None or row[3] is None:
            continue
        y_track[i] = (row[0] - lat0, row[1] - lon0)
        y_wind[i] = row[2]
        y_dp[i] = ENV_PRESSURE - row[3]
        mask[i] = 1.0
    return y_track, y_wind, y_dp, mask


# ── Step 1: build ────────────────────────────────────────────────────────

def downsample(frame):
    """(4, 1024, 1024) float in [0, 1] → (4, SIZE, SIZE) uint8 via block mean."""
    k = frame.shape[-1] // SIZE
    small = frame.reshape(frame.shape[0], SIZE, k, SIZE, k).mean(axis=(2, 4))
    return (np.clip(small, 0, 1) * 255).round().astype(np.uint8)


def build(args):
    from data_pipeline.ingestion.live_pipeline_runner import build_frame, select_window, log
    from data_pipeline.ingestion.mosdac_worker import MosdacIngestionWorker
    from data_pipeline.ingestion.nasa_gpm_worker import NasaGpmIngestionWorker
    from data_pipeline.preprocessing.tensor_assembler import TensorAssembler
    from data_pipeline.training.build_training_set import load_points, pick_positives, dataset_for

    tracks = storm_tracks(args.since)
    samples = [p for p in pick_positives(load_points(args.since), args.per_storm)
               if labels_for(tracks[p["sid"]], p["time"])[3][0] > 0]  # need at least the 6 h label
    OUT.mkdir(parents=True, exist_ok=True)
    done = {json.loads(l)["key"] for l in INDEX.read_text().splitlines() if l.strip()} if INDEX.exists() else set()
    log(f"{len(samples)} windows planned, {len(done)} already built")

    gpm = NasaGpmIngestionWorker()
    gpm.authenticate()
    assembler = TensorAssembler()
    workers, new = {}, 0
    frame_cache = ROOT / "data" / "training" / "window_frames"
    for s in samples:
        key = f"{s['time']:%Y%m%d%H}_{s['sid']}"
        if key in done:
            continue
        ds = dataset_for(s["time"])
        if ds not in workers:
            workers[ds] = MosdacIngestionWorker(dataset_id=ds)
            workers[ds].authenticate()
        try:
            window = select_window(workers[ds], at=s["time"] + timedelta(minutes=30))
            frames = [downsample(build_frame(m, workers[ds], gpm, assembler, frame_dir=frame_cache, keep_frames=12)[0])
                      for m in window]
        except Exception as exc:
            log(f"{key}: failed ({exc})")
            continue
        y_track, y_wind, y_dp, mask = labels_for(tracks[s["sid"]], s["time"])
        np.savez_compressed(OUT / f"{key}.npz", x=np.stack(frames), track=y_track, wind=y_wind, dp=y_dp, mask=mask)
        with open(INDEX, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"key": key, "sid": s["sid"], "season": s["time"].year, "time": s["time"].isoformat()}) + "\n")
        new += 1
        log(f"{key}: ok ({new} new)")
        if args.max_windows and new >= args.max_windows:
            break
    for w in workers.values():
        w.logout()


# ── Step 2: train ────────────────────────────────────────────────────────

def train(args):
    import torch
    from torch.utils.data import DataLoader, Dataset
    from forecaster.physics.atkinson_holliday_loss import MultiHorizonForecastLoss

    rows = [json.loads(l) for l in INDEX.read_text().splitlines() if l.strip()]
    split = {"train": [r for r in rows if r["season"] < args.val_from], "val": [r for r in rows if r["season"] >= args.val_from]}
    print(f"windows: {len(split['train'])} train / {len(split['val'])} val")
    if not split["train"] or not split["val"]:
        sys.exit("Need windows in both splits; build more or change --val-from.")

    class Windows(Dataset):
        def __init__(self, items):
            self.items = items

        def __len__(self):
            return len(self.items)

        def __getitem__(self, i):
            z = np.load(OUT / f"{self.items[i]['key']}.npz")
            return (torch.from_numpy(z["x"].astype(np.float32) / 255.0),
                    {k: torch.from_numpy(z[k]) for k in ("track", "wind", "dp")}, torch.from_numpy(z["mask"]))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = CycloneForecaster().to(device)
    loss_fn = MultiHorizonForecastLoss().to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    loaders = {k: DataLoader(Windows(v), batch_size=args.batch, shuffle=(k == "train"), num_workers=2)
               for k, v in split.items()}

    def run(loader, training):
        model.train(training)
        total, err_km, n = 0.0, np.zeros(len(HORIZONS_H)), np.zeros(len(HORIZONS_H))
        with torch.set_grad_enabled(training):
            for x, y, mask in loader:
                x, mask = x.to(device), mask.to(device)
                y = {"track": y["track"].to(device), "v_max": y["wind"].to(device), "dp": y["dp"].to(device)}
                pred = model(x)
                out = loss_fn(pred, y, mask)
                if training:
                    opt.zero_grad()
                    out["total"].backward()
                    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                    opt.step()
                total += out["total"].item() * len(x)
                d = (pred["track_delta"] - y["track"]).detach()
                km = torch.sqrt((d[..., 0] * 111.2) ** 2 + (d[..., 1] * 111.2 * 0.95) ** 2)  # ~cos(18°)
                err_km += (km * mask).sum(0).cpu().numpy()
                n += mask.sum(0).cpu().numpy()
        return total / len(loader.dataset), err_km / np.maximum(n, 1)

    best, weights = float("inf"), ROOT / "forecaster" / "weights"
    weights.mkdir(parents=True, exist_ok=True)
    for epoch in range(1, args.epochs + 1):
        tr, _ = run(loaders["train"], True)
        va, err = run(loaders["val"], False)
        sched.step()
        print(f"epoch {epoch:3d}  train {tr:.4f}  val {va:.4f}  track error km "
              + "  ".join(f"{h}h:{e:.0f}" for h, e in zip(HORIZONS_H, err)))
        if va < best:
            best = va
            torch.save(model.state_dict(), weights / "forecaster_multi_horizon.pt")

    dest = weights / "forecaster_best.pt"
    if dest.exists():
        shutil.copy(dest, weights / "forecaster_best.legacy.pt")
    shutil.copy(weights / "forecaster_multi_horizon.pt", dest)
    print(f"Best val loss {best:.4f} → {dest}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--since", type=int, default=2016)
    b.add_argument("--per-storm", type=int, default=6)
    b.add_argument("--max-windows", type=int, default=0)
    t = sub.add_parser("train")
    t.add_argument("--epochs", type=int, default=40)
    t.add_argument("--batch", type=int, default=4)
    t.add_argument("--lr", type=float, default=3e-4)
    t.add_argument("--val-from", type=int, default=2024)
    args = ap.parse_args()
    (build if args.cmd == "build" else train)(args)


if __name__ == "__main__":
    main()
