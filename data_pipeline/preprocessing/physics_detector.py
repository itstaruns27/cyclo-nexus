"""
Physics-based tropical disturbance detector (satellite watch)
═════════════════════════════════════════════════════════════
Master plan v4, Task 3.1.

Works on the real (T, 4, H, W) window the pipeline already builds, so it needs no trained
weights. Organisation is measured with the Deviation-Angle Variance technique
(DAV; Piñeros, Ritchie & Tyo 2008, IEEE TGRS; Ritchie et al. 2014, Wea. Forecasting):
for a candidate centre, the angle between each infrared brightness-temperature gradient
vector and the radial direction is computed within a 350 km radius; an axisymmetric,
rotating cloud system gives a low variance (deg²), disorganised convection a high one.

A candidate must have (in the latest frame):
  * a DAV minimum below DAV_WATCH_DEG2 at its centre,
  * a deep-convective cloud shield (< 235 K) and a heavy-rain core (IMERG) nearby,
  * the centre over ocean and at least 5° from the equator (Coriolis),
  * DAV organisation near the same place in >= MIN_PERSIST_FRAMES of the window.

Channels (TensorAssembler): 0 TIR1 BT, 1 WV BT, 2 split window, 3 IMERG rain (all normalised).
"""

from dataclasses import asdict, dataclass
from typing import List, Optional

import numpy as np
from scipy import ndimage

BT_MIN, BT_MAX = 180.0, 320.0      # TensorAssembler normalisation limits (K)
RAIN_MAX = 100.0                   # mm/hr

COLD_K = 235.0                     # deep-convection cloud-top threshold
VERY_COLD_K = 221.0                # vigorous core threshold

DAV_RADIUS_KM = 350.0
DAV_GRID_STEP = 8                  # evaluate DAV every 8 px (~0.25–0.4°)
DAV_SAMPLE_STEP = 4                # use every 4th pixel inside the radius
DAV_SMOOTH_PX = 15                 # Gaussian smoothing of Tb (px ≈ 50–80 km) — raw 4 km gradients are convective noise
DAV_WATCH_DEG2 = 2100.0            # organised disturbance (watch) — calibrated on real replays
DAV_STRONG_DEG2 = 1650.0           # well-organised TC (Piñeros et al. 2008 threshold)

MIN_SHIELD_KM2 = 40_000.0          # < 235 K within the DAV radius
MIN_HEAVY_RAIN_KM2 = 3_000.0       # >= 5 mm/hr within the DAV radius
MIN_ABS_LAT = 5.0
MIN_PERSIST_FRAMES = 3             # of 6 (>= 6 h at 3-hourly steps)
PERSIST_RADIUS_KM = 400.0
MIN_SEPARATION_KM = 500.0          # one candidate per system


@dataclass
class Candidate:
    lat: float
    lon: float
    dav_deg2: float
    shield_km2: float
    core_km2: float
    min_cloud_top_k: float
    max_rain_mmhr: float
    heavy_rain_km2: float
    persistence_frames: int
    over_ocean: bool
    passes: bool
    score: float

    def to_dict(self):
        return {k: (round(v, 4) if isinstance(v, float) else v) for k, v in asdict(self).items()}


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * np.arcsin(np.sqrt(a))


class PhysicsDetector:
    def __init__(self, bbox=(0.0, 32.0, 50.0, 102.0), shape=(1024, 1024), land_mask: Optional[np.ndarray] = None):
        self.bbox = bbox
        self.shape = shape
        min_lat, max_lat, min_lon, max_lon = bbox
        h, w = shape
        self.dlat = (max_lat - min_lat) / h
        self.dlon = (max_lon - min_lon) / w
        self.lats = max_lat - self.dlat * (np.arange(h) + 0.5)
        self.lons = min_lon + self.dlon * (np.arange(w) + 0.5)
        self.row_area = (self.dlat * 111.32) * (self.dlon * 111.32 * np.cos(np.radians(self.lats)))
        self.pix_area = np.repeat(self.row_area[:, None], w, axis=1)
        self.land_mask = land_mask  # True = land; None disables the ocean test
        self.dav_sigma = DAV_SMOOTH_PX

        # Pixel offsets of the DAV sampling disc (km distances vary slowly with latitude; use box centre)
        km_per_row = self.dlat * 111.32
        km_per_col = self.dlon * 111.32 * np.cos(np.radians((min_lat + max_lat) / 2))
        rr = int(DAV_RADIUS_KM / km_per_row)
        cr = int(DAV_RADIUS_KM / km_per_col)
        dr, dc = np.mgrid[-rr:rr + 1:DAV_SAMPLE_STEP, -cr:cr + 1:DAV_SAMPLE_STEP]
        dist = np.hypot(dr * km_per_row, dc * km_per_col)
        keep = (dist <= DAV_RADIUS_KM) & (dist > 20.0)
        self._dr, self._dc = dr[keep], dc[keep]
        self._radial = np.arctan2(-dr[keep] * km_per_row, dc[keep] * km_per_col)  # north-up angles
        self._disc_rows = rr
        self._disc_cols = cr
        self._km_per_row = km_per_row
        self._km_per_col = km_per_col

    @staticmethod
    def physical(frame: np.ndarray):
        return BT_MIN + frame[0] * (BT_MAX - BT_MIN), frame[3] * RAIN_MAX

    def _latlon(self, r, c):
        return float(self.lats[0] - r * self.dlat), float(self.lons[0] + c * self.dlon)

    # ── DAV ──────────────────────────────────────────────────────
    def dav_field(self, tb: np.ndarray, sigma: float = None):
        """DAV (deg²) on a coarse grid. Returns (rows, cols, dav) arrays; NaN where not evaluated."""
        tb_s = ndimage.gaussian_filter(tb, sigma=self.dav_sigma if sigma is None else sigma)
        # Per-km gradients (pixels are not square); row index increases southward → flip for north-up
        gy = -ndimage.sobel(tb_s, axis=0) / self._km_per_row
        gx = ndimage.sobel(tb_s, axis=1) / self._km_per_col
        gang = np.arctan2(gy, gx)
        gmag = np.hypot(gx, gy)

        h, w = tb.shape
        rows = np.arange(self._disc_rows, h - self._disc_rows, DAV_GRID_STEP)
        cols = np.arange(self._disc_cols, w - self._disc_cols, DAV_GRID_STEP)
        dav = np.full((rows.size, cols.size), np.nan, dtype=np.float32)
        # Only evaluate centres under cold cloud (saves ~90 % of the work)
        cold_near = ndimage.minimum_filter(tb_s, size=DAV_GRID_STEP * 3) < COLD_K
        for i, r in enumerate(rows):
            for j, c in enumerate(cols):
                if not cold_near[r, c]:
                    continue
                rr = r + self._dr
                cc = c + self._dc
                g = gmag[rr, cc]
                valid = g > 0.1  # K/km·(sobel scale); ignore flat regions with no gradient direction
                if valid.sum() < 50:
                    continue
                dev = gang[rr, cc][valid] - self._radial[valid]
                dev = (dev + np.pi) % (2 * np.pi) - np.pi
                dav[i, j] = np.degrees(dev).var()
        return rows, cols, dav

    def _dav_minima(self, tb: np.ndarray, threshold: float):
        """Local DAV minima below threshold as (row, col, dav), best first, >= MIN_SEPARATION_KM apart."""
        rows, cols, dav = self.dav_field(tb)
        filled = np.where(np.isnan(dav), np.inf, dav)
        local_min = filled == ndimage.minimum_filter(filled, size=5)
        idx = np.argwhere(local_min & (filled < threshold))
        pts = sorted(((rows[i], cols[j], float(filled[i, j])) for i, j in idx), key=lambda p: p[2])
        chosen = []
        for r, c, v in pts:
            lat, lon = self._latlon(r, c)
            if all(haversine_km(lat, lon, *self._latlon(r2, c2)) >= MIN_SEPARATION_KM for r2, c2, _ in chosen):
                chosen.append((r, c, v))
        return chosen

    # ── measurements around a known (official) centre ───────────
    def measure(self, frame: np.ndarray, lat: float, lon: float, radius_km: float = DAV_RADIUS_KM) -> Optional[dict]:
        """Cloud-top and rain statistics within radius_km of (lat, lon); None if outside the grid."""
        min_lat, max_lat, min_lon, max_lon = self.bbox
        if not (min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
            return None
        tb, rain = self.physical(frame)
        r = (max_lat - lat) / self.dlat - 0.5
        c = (lon - min_lon) / self.dlon - 0.5
        yy, xx = np.ogrid[:tb.shape[0], :tb.shape[1]]
        disc = (((yy - r) * self.dlat * 111.32) ** 2
                + ((xx - c) * self.dlon * 111.32 * np.cos(np.radians(lat))) ** 2) <= radius_km ** 2
        if not disc.any():
            return None
        tb_s = ndimage.gaussian_filter(tb, sigma=2)
        return {
            "radius_km": radius_km,
            "min_cloud_top_k": round(float(tb[disc].min()), 1),
            "cold_cloud_km2": round(float(self.pix_area[disc & (tb_s < COLD_K)].sum())),
            "core_km2": round(float(self.pix_area[disc & (tb_s < VERY_COLD_K)].sum())),
            "max_rain_mmhr": round(float(rain[disc].max()), 1),
            "mean_rain_mmhr": round(float(rain[disc].mean()), 2),
            "heavy_rain_km2": round(float(self.pix_area[disc & (rain >= 5.0)].sum())),
        }

    # ── main ─────────────────────────────────────────────────────
    def detect(self, window: np.ndarray) -> List[Candidate]:
        """window: (T, 4, H, W) normalised, oldest first. Returns candidates, best first."""
        tb, rain = self.physical(window[-1])
        minima = self._dav_minima(tb, DAV_WATCH_DEG2)
        if not minima:
            return []
        past = [[self._latlon(r, c) for r, c, _ in self._dav_minima(self.physical(f)[0], DAV_WATCH_DEG2)]
                for f in window[:-1]]

        tb_s = ndimage.gaussian_filter(tb, sigma=2)
        yy, xx = np.ogrid[:tb.shape[0], :tb.shape[1]]
        out = []
        for r, c, dav in minima:
            lat, lon = self._latlon(r, c)
            # Disc of DAV_RADIUS_KM around the centre (elliptical in pixel space)
            disc = (((yy - r) * self.dlat * 111.32) ** 2
                    + ((xx - c) * self.dlon * 111.32 * np.cos(np.radians(lat))) ** 2) <= DAV_RADIUS_KM ** 2
            shield = float(self.pix_area[disc & (tb_s < COLD_K)].sum())
            core = float(self.pix_area[disc & (tb_s < VERY_COLD_K)].sum())
            heavy = float(self.pix_area[disc & (rain >= 5.0)].sum())
            min_bt = float(tb[disc].min())
            max_rain = float(rain[disc].max())
            persist = 1 + sum(any(haversine_km(lat, lon, plat, plon) <= PERSIST_RADIUS_KM for plat, plon in pts)
                              for pts in past)
            over_ocean = True if self.land_mask is None else not bool(self.land_mask[r, c])

            passes = (abs(lat) >= MIN_ABS_LAT and over_ocean and shield >= MIN_SHIELD_KM2
                      and heavy >= MIN_HEAVY_RAIN_KM2 and persist >= MIN_PERSIST_FRAMES)
            # Score: organisation dominates; 1.0 ≈ well-organised, persistent, rainy system
            organisation = np.clip((DAV_WATCH_DEG2 - dav) / (DAV_WATCH_DEG2 - DAV_STRONG_DEG2 + 1e-6), 0, 1)
            score = float(0.5 * organisation
                          + 0.2 * min(1.0, persist / window.shape[0])
                          + 0.15 * min(1.0, shield / (3 * MIN_SHIELD_KM2))
                          + 0.15 * min(1.0, heavy / (3 * MIN_HEAVY_RAIN_KM2)))
            if not passes:
                score = min(score, 0.49)
            out.append(Candidate(lat=lat, lon=lon, dav_deg2=dav, shield_km2=shield, core_km2=core,
                                 min_cloud_top_k=min_bt, max_rain_mmhr=max_rain, heavy_rain_km2=heavy,
                                 persistence_frames=int(persist), over_ocean=over_ocean, passes=passes,
                                 score=score))
        return sorted(out, key=lambda c: c.score, reverse=True)
