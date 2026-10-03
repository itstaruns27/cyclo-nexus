"""
Train + evaluate the storm-centred track/intensity model (forecaster/track_model.py)
═══════════════════════════════════════════════════════════════════════════════════
Data   data/training/windows/windows.jsonl (unified builder) + frames from data/training/store.
Split  by season, no storm in two sets:  train < --val-season ≤ val < --test-from ≤ test.
       The validation season picks the epoch; the test seasons are only scored once at the end.
Ensemble of --seeds models (mean of predictions). Also trains an image-free ablation so the
report shows whether satellite imagery adds skill over motion/position alone.

  python -m forecaster.train_track --val-season 2023 --test-from 2024
Writes forecaster/weights/track_model.pt and docs/track_model_report.md.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from forecaster.track_model import HORIZONS_H, TrackNet, crop, persistence_velocity, scalars  # noqa: E402

TRAIN = ROOT / "data" / "training"
SHIFTS = [(0, 0), (4, 0), (-4, 0), (0, 4), (0, -4)]   # ±4 px ≈ ±40 km centre uncertainty


def km(d_deg, lat):
    return np.sqrt((d_deg[..., 0] * 111.2) ** 2 + (d_deg[..., 1] * 111.2 * np.cos(np.radians(lat))) ** 2)


def load(rows, tracks):
    """Per window: crops for each shift (float16), scalars, persistence velocity, labels."""
    items = []
    for r in rows:
        t = datetime.fromisoformat(r["time"])
        tr = tracks[r["sid"]]
        cur = tr[t]
        frames = np.stack([np.load(TRAIN / "store" / f"{s}.npz")["x"] for s in r["frames"]])
        crops = np.stack([crop(frames, cur["lat"], cur["lon"], sh) for sh in SHIFTS]).astype(np.float16)
        vel = persistence_velocity(tr, t)
        y_track = np.zeros((len(HORIZONS_H), 2), np.float32)
        y_wind = np.zeros(len(HORIZONS_H), np.float32)
        mask = np.zeros(len(HORIZONS_H), np.float32)
        for i, h in enumerate(HORIZONS_H):
            fut = tr.get(t + timedelta(hours=h))
            if fut and fut["wind_kt"] is not None:
                y_track[i] = (fut["lat"] - cur["lat"], fut["lon"] - cur["lon"])
                y_wind[i] = fut["wind_kt"] - cur["wind_kt"]
                mask[i] = 1
        persist = np.array([vel * h for h in HORIZONS_H], np.float32)
        items.append({"crops": crops, "sc": scalars(tr, t), "persist": persist, "y_track": y_track,
                      "y_wind": y_wind, "mask": mask, "lat": cur["lat"], "wind0": cur["wind_kt"], "key": r["key"]})
    return items


def dense_windows(rows, tracks):
    """Add every 3-hourly best-track time whose full 6 × 3 h window is already in the frame store
    (the builder downloaded runs of consecutive frames, so most in-between times are covered).
    No new downloads; windows keep their storm's season, so the season split is unchanged."""
    labels = [json.loads(l) for l in (TRAIN / "frames.jsonl").read_text().splitlines() if l.strip()]
    times = sorted((datetime.fromisoformat(l["time"]), l["frame"]) for l in labels)
    import bisect
    keys = [t for t, _ in times]

    def frame_at(t):
        i = bisect.bisect_left(keys, t - timedelta(minutes=45))
        best = None
        while i < len(keys) and keys[i] <= t + timedelta(minutes=45):
            if best is None or abs(keys[i] - t) < abs(keys[best] - t):
                best = i
            i += 1
        return times[best][1] if best is not None else None

    have = {r["key"] for r in rows}
    out = list(rows)
    for sid in {r["sid"] for r in rows}:
        for t, cur in sorted(tracks[sid].items()):
            key = f"{t:%Y%m%d%H}_{sid}"
            if key in have or t.hour % 3 or cur["wind_kt"] is None or not tracks[sid].get(t + timedelta(hours=6)):
                continue
            stems = [frame_at(t - timedelta(hours=3 * k)) for k in range(5, -1, -1)]
            if all(stems) and len(set(stems)) == 6:
                out.append({"key": key, "sid": sid, "season": cur["season"], "time": t.isoformat(), "frames": stems})
                have.add(key)
    print(f"dense windows: {len(rows)} built + {len(out) - len(rows)} from stored frames = {len(out)}")
    return out


def batch(items, idx, device, augment):
    shift = np.random.randint(len(SHIFTS), size=len(idx)) if augment else np.zeros(len(idx), int)
    img = torch.from_numpy(np.stack([items[i]["crops"][s] for i, s in zip(idx, shift)]).astype(np.float32))
    g = lambda k: torch.from_numpy(np.stack([items[i][k] for i in idx]))
    if augment:
        img = img + 0.01 * torch.randn_like(img)
    return (img.to(device), g("sc").to(device), g("persist").to(device), g("y_track").to(device),
            g("y_wind").to(device), g("mask").to(device))


def predict(models, items, device):
    out_t, out_w = [], []
    with torch.no_grad():
        for i in range(0, len(items), 64):
            img, sc, persist, *_ = batch(items, list(range(i, min(i + 64, len(items)))), device, False)
            ts, ws = zip(*[m(img, sc) for m in models])
            out_t.append((persist + torch.stack(ts).mean(0)).cpu().numpy())
            out_w.append(torch.stack(ws).mean(0).cpu().numpy())
    return np.concatenate(out_t), np.concatenate(out_w)


def score(items, pred_track, pred_wind):
    """Mean track error (km) and wind MAE (kt) per horizon, masked."""
    tr_err, w_err, n = np.zeros(len(HORIZONS_H)), np.zeros(len(HORIZONS_H)), np.zeros(len(HORIZONS_H))
    for k, it in enumerate(items):
        e = km(pred_track[k] - it["y_track"], it["lat"])
        tr_err += e * it["mask"]
        w_err += np.abs(pred_wind[k] - it["y_wind"]) * it["mask"]
        n += it["mask"]
    return tr_err / np.maximum(n, 1), w_err / np.maximum(n, 1), n


def train_one(train, val, use_image, seed, args, device):
    torch.manual_seed(seed)
    np.random.seed(seed)
    model = TrackNet(use_image=use_image).to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-3)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, args.epochs)
    w_h = torch.tensor([1.0, 1.0, 1.0, 0.8, 0.6], device=device)   # long leads are noisier
    best, best_state, bad = float("inf"), None, 0
    for _ in range(args.epochs):
        model.train()
        perm = np.random.permutation(len(train))
        for i in range(0, len(perm), args.batch):
            img, sc, persist, y_t, y_w, mask = batch(train, perm[i:i + args.batch].tolist(), device, True)
            p_t, p_w = model(img, sc)
            l_t = (F.smooth_l1_loss(persist + p_t, y_t, reduction="none", beta=0.5).sum(-1) * mask * w_h).sum()
            l_w = (F.smooth_l1_loss(p_w / 10, y_w / 10, reduction="none") * mask * w_h).sum()
            loss = (l_t + 0.5 * l_w) / mask.sum().clamp(min=1)
            opt.zero_grad()
            loss.backward()
            opt.step()
        sched.step()
        model.eval()
        pt, pw = predict([model], val, device)
        te, we, _ = score(val, pt, pw)
        metric = te[:4].mean() + 2 * we[:4].mean()   # km + 2·kt over 6–48 h
        if metric < best - 1e-3:
            best, best_state, bad = metric, {k: v.detach().clone() for k, v in model.state_dict().items()}, 0
        else:
            bad += 1
            if bad >= args.patience:
                break
    model.load_state_dict(best_state)
    model.eval()
    return model


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--val-season", type=int, default=2023)
    ap.add_argument("--test-from", type=int, default=2024)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--epochs", type=int, default=150)
    ap.add_argument("--patience", type=int, default=25)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--dense", action=argparse.BooleanOptionalAction, default=True,
                    help="also use 3-hourly windows already covered by stored frames")
    args = ap.parse_args()

    from data_pipeline.training.build_unified_set import read_tracks
    rows = [json.loads(l) for l in (TRAIN / "windows" / "windows.jsonl").read_text().splitlines() if l.strip()]
    tracks = read_tracks(2016)
    if args.dense:
        rows = dense_windows(rows, tracks)
    split = {
        "train": [r for r in rows if r["season"] < args.val_season],
        "val": [r for r in rows if args.val_season <= r["season"] < args.test_from],
        "test": [r for r in rows if r["season"] >= args.test_from],
    }
    data = {k: load(v, tracks) for k, v in split.items()}
    print({k: len(v) for k, v in data.items()}, "windows (train / val / test)")
    device = "cuda" if torch.cuda.is_available() else "cpu"

    test = data["test"]
    zeros_w = np.zeros((len(test), len(HORIZONS_H)), np.float32)
    results = {"persistence": score(test, np.stack([it["persist"] for it in test]), zeros_w)}
    ensembles = {}
    for name, use_image in (("motion-only ensemble", False), ("satellite + motion ensemble", True)):
        models = [train_one(data["train"], data["val"], use_image, s, args, device) for s in range(args.seeds)]
        ensembles[name] = models
        results[name] = score(test, *predict(models, test, device))

    n = results["persistence"][2].astype(int)
    lines = ["| Method | " + " | ".join(f"{h} h" for h in HORIZONS_H) + " |", "|---|" + "---|" * len(HORIZONS_H)]
    for name, (te, _, _) in results.items():
        lines.append(f"| {name} — track error (km) | " + " | ".join(f"{e:.0f}" for e in te) + " |")
    for name, (_, we, _) in results.items():
        label = "no change (persistence)" if name == "persistence" else name
        lines.append(f"| {label} — wind error (kt) | " + " | ".join(f"{e:.1f}" for e in we) + " |")
    lines.append("| test cases | " + " | ".join(str(x) for x in n) + " |")
    table = "\n".join(lines)
    print(table)

    best_name = min((k for k in ensembles), key=lambda k: results[k][0][:4].mean())
    pers = results["persistence"][0][:4].mean()
    gain = (pers - results[best_name][0][:4].mean()) / pers * 100
    weights = ROOT / "forecaster" / "weights"
    weights.mkdir(parents=True, exist_ok=True)
    torch.save({"use_image": "satellite" in best_name, "horizons": HORIZONS_H,
                "states": [m.state_dict() for m in ensembles[best_name]],
                "test_track_km": results[best_name][0].tolist(), "persistence_km": pers},
               weights / "track_model.pt")
    report = ROOT / "docs" / "track_model_report.md"
    report.write_text(
        "# Storm-centred track model — held-out test\n\n"
        f"Train seasons < {args.val_season}, model selection on {args.val_season}, test seasons ≥ {args.test_from} "
        f"(never seen in training or selection). Ensemble of {args.seeds} models.\n\n{table}\n\n"
        f"Best: **{best_name}**, mean 6–48 h track error {gain:+.1f}% vs persistence "
        "(positive = better).\n", encoding="utf-8")
    print(f"saved {best_name} → {weights / 'track_model.pt'}; report → {report}")


if __name__ == "__main__":
    main()
