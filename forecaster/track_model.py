"""
Storm-centred track + intensity model (replaces the full-domain forecaster for the AI forecast)
════════════════════════════════════════════════════════════════════════════════════════════════
Why: the full-domain ConvLSTM sees the whole North Indian Ocean but is never told which system to
forecast or how it has been moving, so with a few hundred real windows it collapsed to one constant
answer (worse than persistence). This model follows the standard statistical–dynamical recipe:

  inputs   6 × 3 h INSAT + IMERG frames cropped around the system's current (official) centre,
           plus its recent motion, position, intensity and season
  outputs  for each lead time (6, 12, 24, 48, 72 h): a CORRECTION to persistence track
           (Δlat, Δlon in degrees) and the wind change from now (knots)

So the model only has to learn when and how a storm deviates from "keeps moving as it has been",
and its worst case degrades towards persistence instead of nonsense.
"""

import math
from datetime import datetime

import numpy as np
import torch
import torch.nn as nn

HORIZONS_H = (6, 12, 24, 48, 72)
BBOX = (0.0, 32.0, 50.0, 102.0)      # store grid: 512 × 512 over lat 0–32, lon 50–102
STORE_PX = 512
CROP_PX = 128                        # ≈ 8° lat × 13° lon around the centre
OUT_PX = 64                          # block-averaged for the network
N_SCALARS = 12


def latlon_to_px(lat, lon):
    return ((lon - BBOX[2]) / (BBOX[3] - BBOX[2]) * STORE_PX, (BBOX[1] - lat) / (BBOX[1] - BBOX[0]) * STORE_PX)


def crop(frames_u8, lat, lon, shift=(0, 0)):
    """frames (T, C, 512, 512) uint8 → (T*C, 64, 64) float32 crop centred on lat/lon (zero-padded)."""
    T, C = frames_u8.shape[:2]
    x, y = latlon_to_px(lat, lon)
    cx, cy = int(round(x)) + shift[0], int(round(y)) + shift[1]
    h = CROP_PX // 2
    out = np.zeros((T, C, CROP_PX, CROP_PX), np.float32)
    x0, x1, y0, y1 = cx - h, cx + h, cy - h, cy + h
    sx0, sy0 = max(0, x0), max(0, y0)
    sx1, sy1 = min(STORE_PX, x1), min(STORE_PX, y1)
    if sx1 > sx0 and sy1 > sy0:
        out[:, :, sy0 - y0:sy1 - y0, sx0 - x0:sx1 - x0] = frames_u8[:, :, sy0:sy1, sx0:sx1] / 255.0
    k = CROP_PX // OUT_PX
    out = out.reshape(T, C, OUT_PX, k, OUT_PX, k).mean(axis=(3, 5))
    return out.reshape(T * C, OUT_PX, OUT_PX)


def motion(track, t, hours):
    """(Δlat, Δlon) per hour over the last `hours`, or zeros if the earlier fix is missing."""
    from datetime import timedelta
    prev = track.get(t - timedelta(hours=hours))
    if not prev:
        return np.zeros(2, np.float32), 0.0
    cur = track[t]
    return np.array([cur["lat"] - prev["lat"], cur["lon"] - prev["lon"]], np.float32) / hours, 1.0


def persistence_velocity(track, t):
    """Degrees per hour: mean of 6 h and 12 h motion where available (smoother than 6 h alone)."""
    v6, ok6 = motion(track, t, 6)
    v12, ok12 = motion(track, t, 12)
    if ok6 and ok12:
        return (v6 + v12) / 2
    return v6 if ok6 else v12


def scalars(track, t):
    """Fixed-length feature vector describing the system now and its recent history."""
    from datetime import timedelta
    cur = track[t]
    v6, ok6 = motion(track, t, 6)
    v12, ok12 = motion(track, t, 12)
    prev12 = track.get(t - timedelta(hours=12))
    dwind = (cur["wind_kt"] - prev12["wind_kt"]) if prev12 and prev12["wind_kt"] is not None else 0.0
    doy = t.timetuple().tm_yday / 365.25 * 2 * math.pi
    return np.array([
        cur["lat"] / 30, (cur["lon"] - 76) / 26, (cur["wind_kt"] or 25) / 100, dwind / 20,
        v6[0] * 6, v6[1] * 6, v12[0] * 6, v12[1] * 6, ok6, ok12, math.sin(doy), math.cos(doy),
    ], np.float32)


class TrackNet(nn.Module):
    def __init__(self, in_ch=24, use_image=True, width=32, dropout=0.3):
        super().__init__()
        self.use_image = use_image
        feat = 0
        if use_image:
            layers, c = [], in_ch
            for w in (width, width * 2, width * 2, width * 4):
                layers += [nn.Conv2d(c, w, 3, padding=1), nn.BatchNorm2d(w), nn.ReLU(inplace=True), nn.MaxPool2d(2)]
                c = w
            self.cnn = nn.Sequential(*layers, nn.AdaptiveAvgPool2d(1), nn.Flatten(), nn.Dropout(dropout))
            feat = c
        self.mlp = nn.Sequential(
            nn.Linear(feat + N_SCALARS, 128), nn.ReLU(inplace=True), nn.Dropout(dropout),
            nn.Linear(128, 64), nn.ReLU(inplace=True),
        )
        self.track = nn.Linear(64, len(HORIZONS_H) * 2)
        self.wind = nn.Linear(64, len(HORIZONS_H))
        # start exactly at persistence / no intensity change
        for head in (self.track, self.wind):
            nn.init.zeros_(head.weight)
            nn.init.zeros_(head.bias)

    def forward(self, img, sc):
        f = torch.cat([self.cnn(img), sc], 1) if self.use_image else sc
        h = self.mlp(f)
        return self.track(h).view(-1, len(HORIZONS_H), 2), self.wind(h)
