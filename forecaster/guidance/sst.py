"""
Sea-surface temperature and potential intensity for the intensity forecast (master plan v5, Task 2.2)
═════════════════════════════════════════════════════════════════════════════════════════════════════
Training: NOAA OISST v2.1 daily 0.25° (NCEI, public domain), one file per day, cached in data/guidance/oisst.
Live:     Open-Meteo marine API (already used by the pipeline for watch areas).

Potential intensity (DeMaria & Kaplan 1994, the SHIPS "MPI"): V = 28.2 + 55.8·exp(0.1813·(SST − 30)) m/s.
The gap between it and the current wind is one of the strongest intensity-change predictors.
"""

import threading
from datetime import date
from functools import lru_cache
from pathlib import Path

import numpy as np
import requests

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "guidance" / "oisst"
URL = "https://www.ncei.noaa.gov/data/sea-surface-temperature-optimum-interpolation/v2.1/access/avhrr/{ym}/oisst-avhrr-v02r01.{ymd}{sfx}.nc"
KT_PER_MS = 1.943844
_lock = threading.Lock()


def potential_intensity_kt(sst_c):
    if sst_c is None or sst_c != sst_c:
        return np.nan
    return (28.2 + 55.8 * np.exp(0.1813 * (sst_c - 30.0))) * KT_PER_MS


def _path(d):
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"oisst-{d:%Y%m%d}.nc"
    if p.exists() and p.stat().st_size > 0:
        return p
    for sfx in ("", "_preliminary"):
        r = requests.get(URL.format(ym=f"{d:%Y%m}", ymd=f"{d:%Y%m%d}", sfx=sfx), timeout=120)
        if r.status_code == 200:
            p.write_bytes(r.content)
            return p
    return None


@lru_cache(maxsize=64)
def _grid(d):
    """North Indian Ocean subset of one day: (lat, lon, sst °C with NaN over land)."""
    import h5py
    with _lock:
        p = _path(d)
    if p is None:
        return None
    with h5py.File(p, "r") as h:
        lat, lon = h["lat"][:], h["lon"][:]
        ds = h["sst"]
        i0, i1 = np.searchsorted(lat, -5), np.searchsorted(lat, 32)
        j0, j1 = np.searchsorted(lon, 40), np.searchsorted(lon, 105)
        raw = ds[0, 0, i0:i1, j0:j1].astype(np.float64)
        fill = float(ds.attrs.get("_FillValue", [-999])[0])
        v = raw * float(ds.attrs.get("scale_factor", [1])[0]) + float(ds.attrs.get("add_offset", [0])[0])
        v[raw == fill] = np.nan
    return lat[i0:i1], lon[j0:j1], v


def sst_at(day, lat, lon, search_deg=1.0):
    """OISST (°C) at the nearest ocean cell within `search_deg`, or NaN (e.g. far inland)."""
    g = _grid(day if isinstance(day, date) else day.date())
    if g is None:
        return np.nan
    la, lo, v = g
    m = (np.abs(la - lat) <= search_deg)[:, None] & (np.abs(lo - lon) <= search_deg)[None, :] & np.isfinite(v)
    if not m.any():
        return np.nan
    ii, jj = np.nonzero(m)
    k = np.argmin((la[ii] - lat) ** 2 + ((lo[jj] - lon) * np.cos(np.radians(lat))) ** 2)
    return float(v[ii[k], jj[k]])
