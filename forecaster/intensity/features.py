"""
Satellite intensity features (Dvorak / ADT-style) from the 512² uint8 frame store
═════════════════════════════════════════════════════════════════════════════════
Same grid and encoding as the live transport (data_pipeline/training/build_unified_set.py):
  x (4, 512, 512) uint8 over lat 0–32°N, lon 50–102°E (north up), channels
    0 TIR1 brightness temperature   180–320 K
    1 water-vapour temperature      180–320 K
    2 split window TIR1 − TIR2      −10…+10 K
    3 IMERG rain rate               0–100 mm/h

Around a storm centre we measure what a Dvorak analyst looks at:
  * cloud-top temperature in rings (0–25, 25–50, 50–100, 100–150, 150–200, 200–300, 300–400 km);
  * the eye: warmest point within 40 km and its contrast with the coldest surrounding ring;
  * how much of each disc is covered by cold cloud (< 233, 213, 203, 193 K);
  * symmetry (spread of ring temperatures by quadrant), water-vapour and rain in the core;
  * and, when a frame 3–9 h earlier exists, the change of the main features (intensifying or not).
"""

import math

import numpy as np
from scipy.ndimage import uniform_filter

BBOX = (0.0, 32.0, 50.0, 102.0)          # lat min, lat max, lon min, lon max
PX = 512
DLAT = (BBOX[1] - BBOX[0]) / PX           # 0.0625° per row
DLON = (BBOX[3] - BBOX[2]) / PX           # 0.1016° per column
RINGS_KM = (0, 25, 50, 100, 150, 200, 300, 400)
COLD_K = (233.0, 213.0, 203.0, 193.0)
DISCS_KM = (50, 100, 200)
REACH_KM = 420


def physical(x_u8):
    """(4, H, W) uint8 → dict of physical fields (float32)."""
    u = x_u8.astype(np.float32) / 255.0
    return {"tb": 180.0 + 140.0 * u[0], "wv": 180.0 + 140.0 * u[1], "swd": -10.0 + 20.0 * u[2], "rain": 100.0 * u[3]}


def _window(lat, lon, origin=None, shape=(PX, PX)):
    """Pixel window around the centre and each pixel's distance (km) and quadrant.
    origin = (north edge lat, west edge lon) of the grid; default the INSAT store. Pixel size is always DLAT × DLON."""
    north, west = origin or (BBOX[1], BBOX[2])
    km_lat = 111.2 * DLAT
    km_lon = 111.2 * math.cos(math.radians(lat)) * DLON
    cx = (lon - west) / DLON
    cy = (north - lat) / DLAT
    rx, ry = int(REACH_KM / km_lon) + 1, int(REACH_KM / km_lat) + 1
    x0, x1 = max(0, int(cx) - rx), min(shape[1], int(cx) + rx + 1)
    y0, y1 = max(0, int(cy) - ry), min(shape[0], int(cy) + ry + 1)
    if x1 <= x0 or y1 <= y0:
        return None
    yy, xx = np.mgrid[y0:y1, x0:x1]
    dx = (xx + 0.5 - cx) * km_lon
    dy = (cy - yy - 0.5) * km_lat
    dist = np.hypot(dx, dy)
    quad = ((np.degrees(np.arctan2(dx, dy)) + 360) % 360 // 90).astype(int)    # 0 NE, 1 SE, 2 SW, 3 NW
    return (slice(y0, y1), slice(x0, x1)), dist, quad


FEATURES = (
    [f"tb_ring_{a}_{b}" for a, b in zip(RINGS_KM[:-1], RINGS_KM[1:])]
    + [f"cold{int(k)}_{d}" for k in COLD_K for d in DISCS_KM]
    + ["eye_tb", "cold_ring_tb", "eye_contrast", "min_tb_100", "p10_tb_200", "tb_std_100_300",
       "quad_spread_50_150", "wv_core_50", "wv_ring_100_200", "swd_core_50",
       "rain_mean_50", "rain_mean_100", "rain_mean_200", "rain_max_100", "rain_cover_200",
       "valid_frac"]
)
TREND = ["tb_ring_0_25", "tb_ring_25_50", "tb_ring_50_100", "cold213_100", "eye_contrast", "rain_mean_100"]


def frame_features(x_u8, lat, lon, origin=None):
    """Feature dict for one frame and centre, or None when the centre is off the grid."""
    w = _window(lat, lon, origin, x_u8.shape[1:])
    if w is None:
        return None
    sl, dist, quad = w
    f = {k: v[sl] for k, v in physical(x_u8).items()}
    tb = f["tb"]
    valid = (x_u8[0][sl] > 0) & (dist <= REACH_KM)          # 0 = no data / outside the satellite disc
    out = {"valid_frac": float(valid.sum() / max(1, (dist <= REACH_KM).sum()))}
    if out["valid_frac"] < 0.5:
        return None

    def sel(a, b):
        return valid & (dist >= a) & (dist < b)

    for a, b in zip(RINGS_KM[:-1], RINGS_KM[1:]):
        m = sel(a, b)
        out[f"tb_ring_{a}_{b}"] = float(tb[m].mean()) if m.any() else np.nan
    for k in COLD_K:
        for d in DISCS_KM:
            m = sel(0, d)
            out[f"cold{int(k)}_{d}"] = float((tb[m] < k).mean()) if m.any() else np.nan
    core = sel(0, 40)
    out["eye_tb"] = float(tb[core].max()) if core.any() else np.nan
    rings = [tb[sel(r, r + 25)].mean() for r in range(25, 150, 25) if sel(r, r + 25).any()]
    out["cold_ring_tb"] = float(min(rings)) if rings else np.nan
    out["eye_contrast"] = out["eye_tb"] - out["cold_ring_tb"]
    m = sel(0, 100)
    out["min_tb_100"] = float(tb[m].min()) if m.any() else np.nan
    m = sel(0, 200)
    out["p10_tb_200"] = float(np.percentile(tb[m], 10)) if m.any() else np.nan
    m = sel(100, 300)
    out["tb_std_100_300"] = float(tb[m].std()) if m.any() else np.nan
    qm = [tb[sel(50, 150) & (quad == q)].mean() for q in range(4) if (sel(50, 150) & (quad == q)).any()]
    out["quad_spread_50_150"] = float(np.ptp(qm)) if len(qm) == 4 else np.nan
    m = sel(0, 50)
    out["wv_core_50"] = float(f["wv"][m].mean()) if m.any() else np.nan
    out["swd_core_50"] = float(f["swd"][m].mean()) if m.any() else np.nan
    m = sel(100, 200)
    out["wv_ring_100_200"] = float(f["wv"][m].mean()) if m.any() else np.nan
    for d in DISCS_KM:
        m = sel(0, d)
        out[f"rain_mean_{d}"] = float(f["rain"][m].mean()) if m.any() else np.nan
    m = sel(0, 100)
    out["rain_max_100"] = float(f["rain"][m].max()) if m.any() else np.nan
    m = sel(0, 200)
    out["rain_cover_200"] = float((f["rain"][m] > 5).mean()) if m.any() else np.nan
    return out


EYE_SEARCH_KM = 100
EYE_MIN_SCORE_K = 20.0


def refine_centre(x_u8, lat, lon, origin=None):
    """Automatic eye centring (as in ADT): the warmest spot within EYE_SEARCH_KM that is surrounded by cold
    cloud. Returns (lat, lon, score K, found). Best-track and real-time centres are often 10–90 km off the eye."""
    w = _window(lat, lon, origin, x_u8.shape[1:])
    if w is None:
        return lat, lon, np.nan, False
    sl, dist, _ = w
    tb = (180.0 + 140.0 * x_u8[0].astype(np.float32) / 255.0)[sl]
    local = uniform_filter(tb, 3)
    box13, box5 = uniform_filter(tb, 13), uniform_filter(tb, 5)
    ring = (box13 * 169 - box5 * 25) / 144                      # annulus ≈ 3–6 px (20–60 km) around each point
    score = local - ring
    cand = (dist <= EYE_SEARCH_KM) & (ring < 240.0) & (x_u8[0][sl] > 0)
    if not cand.any():
        return lat, lon, np.nan, False
    i = int(np.argmax(np.where(cand, score, -1e9)))
    yy, xx = divmod(i, tb.shape[1])
    best = float(score[yy, xx])
    if best < EYE_MIN_SCORE_K:
        return lat, lon, best, False
    row, col = sl[0].start + yy, sl[1].start + xx
    north, west = origin or (BBOX[1], BBOX[2])
    return north - (row + 0.5) * DLAT, west + (col + 0.5) * DLON, best, True


def sample_features(x_now, lat, lon, x_prev=None, prev_lat=None, prev_lon=None, hours=None, extra=None,
                    origin=None, prev_origin=None):
    """Full feature vector (dict): current frame + trend per hour vs an earlier frame + context."""
    elat, elon, score, found = refine_centre(x_now, lat, lon, origin)
    cur = frame_features(x_now, elat, elon, origin)
    if cur is None:
        return None
    out = dict(cur)
    out["eye_score"], out["eye_found"] = score, float(found)
    if x_prev is not None:
        plat, plon, _, _ = refine_centre(x_prev, prev_lat, prev_lon, prev_origin)
        prev = frame_features(x_prev, plat, plon, prev_origin)
    else:
        prev = None
    for k in TREND:
        out[f"d_{k}"] = (cur[k] - prev[k]) / hours if prev and hours else np.nan
    out["abs_lat"] = abs(lat)
    out.update(extra or {})
    return out
