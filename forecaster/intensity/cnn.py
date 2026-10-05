"""
CNN intensity estimate: pre-train on HURSAT-B1 (global), fine-tune on INSAT (master plan v5, Task 2.1)
═══════════════════════════════════════════════════════════════════════════════════════════════════════
  python -m forecaster.intensity.cnn cv        # leave-one-season-out out-of-fold predictions on INSAT → csv
  python -m forecaster.intensity.cnn final     # pre-train + fine-tune on all seasons → weights

Input: 3 channels (11 µm IR, 6.7 µm WV, split window) as 128 × 128 crops on the INSAT store pixel grid
(≈ 7 × 11 km), centred on the best-track position. Augmentation: rotation (cyclones have no preferred
orientation), ± 4 px shifts, small brightness jitter. Target: wind in kt (HURSAT: JTWC 1-min; INSAT: IMD 3-min,
learned in fine-tuning). Out-of-fold predictions are stacked with the feature model in train.py.
"""

import argparse
import glob
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from forecaster.intensity.features import BBOX, DLAT, DLON  # noqa: E402

TRAIN = ROOT / "data" / "training"
HURSAT = ROOT / "data" / "hursat" / "crops"
OOF = TRAIN / "intensity_cnn_oof.csv"
WEIGHTS = ROOT / "forecaster" / "weights" / "intensity_cnn.pt"
CROP = 128
DEV = "cuda" if torch.cuda.is_available() else "cpu"


class Net(nn.Module):
    def __init__(self, c=3):
        super().__init__()
        def block(i, o):
            return nn.Sequential(nn.Conv2d(i, o, 3, padding=1, bias=False), nn.BatchNorm2d(o), nn.ReLU(inplace=True),
                                 nn.Conv2d(o, o, 3, padding=1, bias=False), nn.BatchNorm2d(o), nn.ReLU(inplace=True),
                                 nn.MaxPool2d(2))
        self.f = nn.Sequential(block(c, 32), block(32, 64), block(64, 96), block(96, 128), block(128, 160))   # 128 → 4
        self.head = nn.Sequential(nn.Flatten(), nn.Dropout(0.3), nn.Linear(160 * 16, 128), nn.ReLU(inplace=True), nn.Linear(128, 1))

    def forward(self, x):
        return self.head(self.f(x)).squeeze(1) * 50 + 60          # output around the wind range


def insat_crop(x_u8, lat, lon):
    cx = int(round((lon - BBOX[2]) / DLON))
    cy = int(round((BBOX[1] - lat) / DLAT))
    out = np.zeros((3, CROP, CROP), np.uint8)
    h = CROP // 2
    y0, x0 = cy - h, cx - h
    sy0, sx0, sy1, sx1 = max(0, y0), max(0, x0), min(512, y0 + CROP), min(512, x0 + CROP)
    if sy1 > sy0 and sx1 > sx0:
        out[:, sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = x_u8[:3, sy0:sy1, sx0:sx1]
    return out


def load_insat():
    rows = [json.loads(line) for line in open(TRAIN / "frames.jsonl", encoding="utf-8")]
    X, y, season, sid, frame = [], [], [], [], []
    for r in rows:
        x = None
        for s in r["systems"]:
            if s.get("in_domain") and s.get("wind_kt") is not None:
                x = x if x is not None else np.load(TRAIN / "store" / f"{r['frame']}.npz")["x"]
                X.append(insat_crop(x, s["lat"], s["lon"]))
                y.append(s["wind_kt"]); season.append(s["season"]); sid.append(s["sid"]); frame.append(r["frame"])
    return np.stack(X), np.array(y, np.float32), np.array(season), np.array(sid), np.array(frame)


def load_hursat():
    X, y = [], []
    for f in sorted(glob.glob(str(HURSAT / "*.npz"))):
        z = np.load(f)
        if len(z["x"]) and z["x"].shape[1:] == (3, CROP, CROP):
            X.append(z["x"]); y.append(z["wind"].astype(np.float32))
    return (np.concatenate(X), np.concatenate(y)) if X else (None, None)


def augment(xb):
    """Random rotation (any angle), ±4 px shift, brightness jitter, on a GPU batch (B, 3, H, W) in [0, 1]."""
    b = xb.shape[0]
    ang = torch.rand(b, device=xb.device) * 2 * np.pi
    cos, sin = torch.cos(ang), torch.sin(ang)
    shift = (torch.rand(b, 2, device=xb.device) - 0.5) * (8 / CROP) * 2
    theta = torch.stack([torch.stack([cos, -sin, shift[:, 0]], 1), torch.stack([sin, cos, shift[:, 1]], 1)], 1)
    grid = F.affine_grid(theta, xb.shape, align_corners=False)
    out = F.grid_sample(xb, grid, align_corners=False, padding_mode="zeros")
    return (out + (torch.rand(b, 1, 1, 1, device=xb.device) - 0.5) * 0.04).clamp(0, 1)


def run_epochs(net, X, y, epochs, lr, batch=128, weights=None):
    opt = torch.optim.AdamW(net.parameters(), lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=epochs * ((len(X) + batch - 1) // batch))
    Xt = torch.from_numpy(X)
    yt = torch.from_numpy(y)
    wt = torch.from_numpy(weights.astype(np.float32)) if weights is not None else torch.ones(len(y))
    net.train()
    for _ in range(epochs):
        perm = torch.randperm(len(X))
        for i in range(0, len(X), batch):
            idx = perm[i:i + batch]
            xb = augment(Xt[idx].to(DEV).float() / 255)
            with torch.autocast(DEV, dtype=torch.bfloat16, enabled=DEV == "cuda"):
                pred = net(xb)
            loss = (F.smooth_l1_loss(pred.float(), yt[idx].to(DEV), beta=5.0, reduction="none") * wt[idx].to(DEV)).mean()
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            sched.step()
    return net


@torch.no_grad()
def predict(net, X, tta=8):
    net.eval()
    out = []
    Xt = torch.from_numpy(X)
    for i in range(0, len(X), 64):
        xb = Xt[i:i + 64].to(DEV).float() / 255
        preds = []
        for k in range(tta):                         # rotation test-time augmentation (k = 0: as is)
            ang = torch.full((len(xb),), 2 * np.pi * k / tta, device=DEV)
            theta = torch.stack([torch.stack([torch.cos(ang), -torch.sin(ang), torch.zeros_like(ang)], 1),
                                 torch.stack([torch.sin(ang), torch.cos(ang), torch.zeros_like(ang)], 1)], 1)
            xr = F.grid_sample(xb, F.affine_grid(theta, xb.shape, align_corners=False), align_corners=False) if k else xb
            with torch.autocast(DEV, dtype=torch.bfloat16, enabled=DEV == "cuda"):
                preds.append(net(xr).float())
        out.append(torch.stack(preds).mean(0).cpu().numpy())
    return np.concatenate(out)


def class_weights(y):
    from forecaster.intensity.scale import imd_class
    c = np.array([imd_class(v) for v in y])
    freq = np.bincount(c, minlength=7).astype(float)
    return np.clip(len(y) / (np.count_nonzero(freq) * np.maximum(freq[c], 1)), 0, 6)


def pretrained(Xh, yh, epochs):
    torch.manual_seed(0)
    net = Net().to(DEV)
    if Xh is not None:
        run_epochs(net, Xh, yh, epochs, 2e-3)
    return net


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["cv", "final"])
    ap.add_argument("--pre-epochs", type=int, default=12)
    ap.add_argument("--ft-epochs", type=int, default=25)
    a = ap.parse_args()
    X, y, season, sid, frame = load_insat()
    Xh, yh = load_hursat()
    print(f"INSAT {len(X)} crops; HURSAT {0 if Xh is None else len(Xh)} crops; device {DEV}", flush=True)
    base = pretrained(Xh, yh, a.pre_epochs)
    state = {k: v.clone() for k, v in base.state_dict().items()}
    if a.cmd == "cv":
        import pandas as pd
        oof = np.full(len(X), np.nan, np.float32)
        for s in sorted(set(season)):
            net = Net().to(DEV)
            net.load_state_dict(state)
            tr = season != s
            run_epochs(net, X[tr], y[tr], a.ft_epochs, 5e-4, weights=class_weights(y[tr]))
            oof[~tr] = predict(net, X[~tr])
            e = oof[~tr] - y[~tr]
            print(f"  season {s}: RMSE {np.sqrt((e ** 2).mean()):.1f} kt (n={int((~tr).sum())})", flush=True)
        e = oof - y
        print(f"LOSO all: RMSE {np.sqrt((e ** 2).mean()):.1f}, MAE {np.abs(e).mean():.1f}; ≥64 kt MAE {np.abs(e[y >= 64]).mean():.1f}")
        pd.DataFrame({"frame": frame, "sid": sid, "season": season, "wind_kt": y, "cnn_kt": oof}).to_csv(OOF, index=False)
    else:
        net = Net().to(DEV)
        net.load_state_dict(state)
        run_epochs(net, X, y, a.ft_epochs, 5e-4, weights=class_weights(y))
        torch.save({"state": net.state_dict(), "trained": datetime.utcnow().isoformat(), "crop": CROP}, WEIGHTS)
        print(f"saved {WEIGHTS}")


if __name__ == "__main__":
    main()
