"""
Global pre-training data for the satellite intensity estimate: NOAA HURSAT-B1 (v06)
â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
  python -m forecaster.intensity.hursat --years 2004-2015 --threads 6

HURSAT-B1 (NOAA NCEI, public domain): storm-centred ISCCP-B1 geostationary images, 3-hourly, 0.07Â°,
for every tropical cyclone worldwide 1978â€“2015, channels 11 Âµm (IRWIN), 6.7 Âµm (IRWVP), 12 Âµm (IRSPL).
Each storm archive is streamed: download â†’ one image per 3-hourly time (smallest viewing angle) â†’
resampled to the INSAT store's pixel size and uint8 encoding â†’ the same Dvorak-style features as the
INSAT model (no rain channel: rain features are left empty) â†’ archive deleted.

Labels: JTWC / NHC 1-minute wind (IBTrACS v04 USA_WIND) so all basins share one wind definition
(HURSAT's own WindSpd mixes 1- and 10-minute agency winds). The INSAT model later learns the
conversion to IMD's 3-minute wind.

Outputs: data/hursat/features.csv Â· data/hursat/crops/<sid>.npz (uint8 128Â² crops, for CNN work)
"""

import argparse
import csv
import re
import shutil
import sys
import tarfile
import tempfile
import threading
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
import pickle
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests
from scipy.ndimage import map_coordinates

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from forecaster.intensity.features import DLAT, DLON, sample_features  # noqa: E402

BASE = "https://www.ncei.noaa.gov/data/hurricane-satellite-hursat-b1/archive/v06"
IBTRACS_ALL = ("https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/"
               "v04r01/access/csv/ibtracs.since1980.list.v04r01.csv")
OUT = ROOT / "data" / "hursat"
HALF_DEG = 10.0                 # canvas Â±10Â° around the centre (HURSAT images are Â±10.5Â°)
CROP = 128
_lock = threading.Lock()


def get(url, **kw):
    for i in range(5):
        try:
            r = requests.get(url, timeout=300, **kw)
            if r.status_code < 500:
                return r
        except requests.RequestException:
            pass
        import time
        time.sleep(2 ** i)
    raise RuntimeError(f"failed: {url}")


def usa_winds():
    """{(sid, 'YYYY-MM-DD HH:MM'): (usa_wind_kt, lat, lon)} from IBTrACS since 1980 (downloaded once)."""
    path = OUT / "ibtracs.since1980.list.v04r01.csv"
    if not path.exists():
        OUT.mkdir(parents=True, exist_ok=True)
        with get(IBTRACS_ALL, stream=True) as r, open(path.with_suffix(".part"), "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        path.with_suffix(".part").replace(path)
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        next(rd)
        for r in rd:
            w = r["USA_WIND"].strip()
            if w and r["USA_LAT"].strip():
                out[(r["SID"], r["ISO_TIME"][:16])] = (float(w), float(r["USA_LAT"]), float(r["USA_LON"]))
    return out


def storm_list(years):
    out = []
    for y in years:
        html = get(f"{BASE}/{y}/").text
        out += [(y, f) for f in sorted(set(re.findall(r'href="(HURSAT_b1_v06_[^"]+\.tar\.gz)"', html)))]
    return out


def to_canvas(ds, clat, clon):
    """HURSAT image â†’ uint8 (4, H, W) canvas with the INSAT store's pixel size, origin (north, west)."""
    lat = ds["lat"].astype(np.float64)
    lon = np.unwrap(np.radians(ds["lon"].astype(np.float64))) * 180 / np.pi
    clon_u = clon if abs(clon - lon.mean()) < 180 else clon + 360 * np.sign(lon.mean() - clon)
    north, west = clat + HALF_DEG, clon_u - HALF_DEG
    ny, nx = int(2 * HALF_DEG / DLAT), int(2 * HALF_DEG / DLON)
    glat = north - (np.arange(ny) + 0.5) * DLAT
    glon = west + (np.arange(nx) + 0.5) * DLON
    # fractional indices into the HURSAT grid (lat ascending or descending)
    fy = np.interp(glat, lat if lat[0] < lat[-1] else lat[::-1], np.arange(len(lat)) if lat[0] < lat[-1] else np.arange(len(lat))[::-1], left=np.nan, right=np.nan)
    fx = np.interp(glon, lon, np.arange(len(lon)), left=np.nan, right=np.nan)
    yy, xx = np.meshgrid(fy, fx, indexing="ij")
    bad = ~np.isfinite(yy) | ~np.isfinite(xx)
    coords = [np.nan_to_num(yy), np.nan_to_num(xx)]

    def chan(name):
        a = ds[name]
        v = map_coordinates(np.nan_to_num(a, nan=-999), coords, order=1, mode="constant", cval=-999)
        v[bad | (v < 100)] = np.nan
        return v
    ir, wv, sp = chan("IRWIN"), chan("IRWVP"), chan("IRSPL")
    x = np.zeros((4, ny, nx), np.uint8)
    enc = lambda v, lo, hi: np.where(np.isfinite(v), np.clip((v - lo) / (hi - lo), 1 / 255, 1) * 255, 0).round()  # noqa: E731
    x[0] = enc(ir, 180, 320)
    x[1] = np.where(np.isfinite(wv), enc(wv, 180, 320), 0)
    x[2] = np.where(np.isfinite(ir - sp), enc(ir - sp, -10, 10), 0)
    return x, (north, west), clon_u


RAIN = ["rain_mean_50", "rain_mean_100", "rain_mean_200", "rain_max_100", "rain_cover_200", "d_rain_mean_100"]


_WINDS = None


def _init(path):
    global _WINDS
    with open(path, "rb") as f:
        _WINDS = pickle.load(f)


def read_nc(path):
    """The few HURSAT variables we need, via h5py (â‰ˆ 100Ã— faster than xarray here); packed ints decoded."""
    import h5py
    out = {}
    with h5py.File(path, "r") as h:
        out["lat"], out["lon"] = h["lat"][:], h["lon"][:]
        out["VZA"] = float(h["VZA"][0])
        for v in ("IRWIN", "IRWVP", "IRSPL"):
            if v not in h:                                   # some older satellites lack 6.7 / 12 Âµm
                out[v] = np.full((len(out["lat"]), len(out["lon"])), np.nan)
                continue
            d = h[v]
            raw = d[0].astype(np.float64)
            a = raw * float(d.attrs.get("scale_factor", [1])[0]) + float(d.attrs.get("add_offset", [0])[0])
            a[raw == float(d.attrs.get("_FillValue", [-20100])[0])] = np.nan
            out[v] = a
    return out


def process_storm(year, fname, winds=None):
    winds = winds if winds is not None else _WINDS
    sid = fname.split("_")[3]
    tmp = Path(tempfile.mkdtemp(prefix="hursat_"))
    try:
        archive = tmp / fname                                    # streamed to disk: archives reach ~300 MB
        with get(f"{BASE}/{year}/{fname}", stream=True) as r:
            if r.status_code != 200:
                return []
            with open(archive, "wb") as fh:
                for chunk in r.iter_content(1 << 20):
                    fh.write(chunk)
        by_time = defaultdict(list)
        with tarfile.open(archive, mode="r:gz") as tf:
            for m in tf.getmembers():
                if m.name.endswith(".nc"):
                    parts = m.name.split(".")
                    by_time[(parts[2], parts[3], parts[4], parts[5])].append(m)
            frames = []
            for key in sorted(by_time):
                t = datetime(int(key[0]), int(key[1]), int(key[2]), int(key[3][:2]), int(key[3][2:]), tzinfo=timezone.utc)
                lab = winds.get((sid, t.strftime("%Y-%m-%d %H:%M")))
                if not lab or lab[0] < 20:
                    continue
                best = None
                for m in by_time[key]:
                    tf.extract(m, tmp, filter="data")
                    ds = read_nc(tmp / m.name)
                    if best is None or ds["VZA"] < best[0]:
                        best = (ds["VZA"], ds)
                for m in by_time[key]:
                    (tmp / m.name).unlink(missing_ok=True)
                if best is None or best[0] > 65:
                    continue
                x, origin, clon_u = to_canvas(best[1], lab[1], lab[2])
                frames.append((t, x, origin, lab, clon_u))
        rows, crops, times = [], [], []
        for i, (t, x, origin, lab, clon_u) in enumerate(frames):
            prev = None
            for tp, xp, op, lp, cp in reversed(frames[:i]):
                h = (t - tp).total_seconds() / 3600
                if 3 <= h <= 9:
                    prev = (xp, op, lp, cp, h)
                    break
                if h > 9:
                    break
            f = sample_features(x, lab[1], clon_u, prev[0] if prev else None, prev[2][1] if prev else None,
                                prev[3] if prev else None, prev[4] if prev else None,
                                extra={"arabian_sea": 0.0}, origin=origin, prev_origin=prev[1] if prev else None)
            if f is None:
                continue
            for k in RAIN:
                f[k] = np.nan
            rows.append({"sid": sid, "time": t.isoformat(), "wind_kt": lab[0], "lat": lab[1], **f})
            cy, cx = x.shape[1] // 2, x.shape[2] // 2
            crops.append(x[:3, cy - CROP // 2:cy + CROP // 2, cx - CROP // 2:cx + CROP // 2])
            times.append(t.isoformat())
        if crops:
            np.savez_compressed(OUT / "crops" / f"{sid}.npz", x=np.stack(crops), time=np.array(times),
                                wind=np.array([r["wind_kt"] for r in rows]))
        return rows
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2004-2015")
    ap.add_argument("--threads", type=int, default=6, help="worker processes")
    a = ap.parse_args()
    y0, y1 = (int(v) for v in a.years.split("-"))
    (OUT / "crops").mkdir(parents=True, exist_ok=True)
    print("loading IBTrACS USA winds â€¦", flush=True)
    pk = OUT / "usa_winds.pkl"
    if not pk.exists():
        with open(pk, "wb") as f:
            pickle.dump(usa_winds(), f)
    storms = storm_list(range(y0, y1 + 1))
    done_path = OUT / "done.txt"
    done = set(done_path.read_text().split()) if done_path.exists() else set()
    todo = [(y, f) for y, f in storms if f not in done]
    print(f"{len(storms)} storms, {len(todo)} to process", flush=True)
    feats = OUT / "features.csv"
    header_written = feats.exists()
    n = 0
    for attempt in range(8):                         # a crashed worker breaks the pool: restart on what is left
        if not todo:
            break
        broken = []
        with ProcessPoolExecutor(a.threads, initializer=_init, initargs=(str(pk),)) as ex:
            futs = {ex.submit(process_storm, y, f): (y, f) for y, f in todo}
            for fut in as_completed(futs):
                y, f = futs[fut]
                try:
                    rows = fut.result()
                except BrokenProcessPool:
                    broken.append((y, f))
                    continue
                except Exception as e:  # noqa: BLE001
                    print(f"  {f}: {e}", flush=True)
                    continue
                if rows:
                    with open(feats, "a", newline="", encoding="utf-8") as fh:
                        w = csv.DictWriter(fh, list(rows[0].keys()))
                        if not header_written:
                            w.writeheader()
                            header_written = True
                        w.writerows(rows)
                with open(done_path, "a") as fh:
                    fh.write(f + "\n")
                n += 1
                if n % 20 == 0:
                    print(f"  {n} storms done", flush=True)
        if broken:
            print(f"  pool broke; restarting for {len(broken)} storms (attempt {attempt + 1})", flush=True)
        todo = broken
    print("done", flush=True)


if __name__ == "__main__":
    main()
