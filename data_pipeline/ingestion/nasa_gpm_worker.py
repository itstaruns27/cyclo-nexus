"""
NASA GPM IMERG live ingestion (GES DISC, HTTPS + Earthdata Login)
═════════════════════════════════════════════════════════════════
Finds the most recent half-hourly IMERG granule, downloads it with the
Earthdata credentials from data_pipeline/.env, and returns the precipitation
field (mm/hr) regridded onto the NIO target grid.

Product: GPM_3IMERGHHE (Early run, ~4-6 h latency). Falls back to the
Late run (GPM_3IMERGHHL, ~14 h latency) if no Early granule is found.

One-time account step: the Earthdata user must have authorised the
"NASA GESDISC DATA ARCHIVE" application (Earthdata profile → Applications).
"""

import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qs, urlparse

import h5py
import numpy as np
import requests
from dotenv import load_dotenv

from data_pipeline.preprocessing.axis_regridder import regrid_to_bbox

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

GESDISC_DATA_ROOT = "https://gpm1.gesdisc.eosdis.nasa.gov/data/GPM_L3"
COLLECTIONS = ("GPM_3IMERGHHE.07", "GPM_3IMERGHHL.07")
EARTHDATA_HOST = "urs.earthdata.nasa.gov"
DEFAULT_CACHE = Path(__file__).resolve().parents[2] / "data" / "live" / "gpm"
FILL_THRESHOLD = -9000.0  # IMERG fill value is -9999.9

_GRANULE_RE = re.compile(r'href="(3B-HHR-[EL]\.MS\.MRG\.3IMERG\.(\d{8})-S(\d{6})-E\d{6}\.\d{4}\.V\w+\.HDF5)"')


class DataQualityError(Exception):
    pass


class _EarthdataSession(requests.Session):
    """Keeps Basic auth only across redirects to/from Earthdata Login (NASA's recommended pattern)."""

    def rebuild_auth(self, prepared_request, response):
        headers = prepared_request.headers
        if "Authorization" in headers:
            original = requests.utils.urlparse(response.request.url).hostname
            redirect = requests.utils.urlparse(prepared_request.url).hostname
            if original != redirect and EARTHDATA_HOST not in (original, redirect):
                del headers["Authorization"]


@dataclass
class GpmFrame:
    precip: np.ndarray        # (H, W) float32 mm/hr on the target grid, NaN = no data
    bounds: tuple             # (min_lat, max_lat, min_lon, max_lon)
    obs_time: datetime        # granule start time (UTC)
    granule: str              # file name


class NasaGpmIngestionWorker:
    """Worker for ingesting NASA GPM IMERG half-hourly precipitation."""

    def __init__(self, cache_dir: Optional[Path] = None, keep_files: int = 4):
        self.cache_dir = Path(cache_dir or DEFAULT_CACHE)
        self.keep_files = keep_files
        self.session = _EarthdataSession()

    def authenticate(self, user: str = None, password: str = None) -> None:
        """Attach Earthdata Login credentials (validated on first download)."""
        nasa_user = user or os.environ.get("NASA_EARTHDATA_USER")
        nasa_pass = password or os.environ.get("NASA_EARTHDATA_PASS")
        if not nasa_user or not nasa_pass:
            raise EnvironmentError("NASA_EARTHDATA_USER and NASA_EARTHDATA_PASS are required in data_pipeline/.env")
        self.session.auth = (nasa_user, nasa_pass)

    # ── Discovery ──────────────────────────────────────────────────
    def find_latest_granule(self, before: Optional[datetime] = None, max_lookback_days: int = 2):
        """Return (collection, day_url, filename, start_time) of the newest granule at/before `before`."""
        before = before or datetime.now(timezone.utc)
        for collection in COLLECTIONS:
            for back in range(max_lookback_days + 1):
                day = before - timedelta(days=back)
                day_url = f"{GESDISC_DATA_ROOT}/{collection}/{day:%Y}/{day:%j}/"
                listing = self._list_day(day_url, settled=day < datetime.now(timezone.utc) - timedelta(days=3))
                if listing is None:
                    continue
                candidates = []
                for name, ymd, hms in listing:
                    start = datetime.strptime(ymd + hms, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
                    if start <= before:
                        candidates.append((start, name))
                if candidates:
                    start, name = max(candidates)
                    return collection, day_url, name, start
        raise FileNotFoundError(f"No IMERG granule found within {max_lookback_days} days before {before.isoformat()}")

    # Directory listings of past days never change; training builds hit the same day many times
    _settled_listings = {}

    def _list_day(self, day_url: str, settled: bool):
        if settled and day_url in self._settled_listings:
            return self._settled_listings[day_url]
        resp = self.session.get(day_url, timeout=60)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        listing = set(_GRANULE_RE.findall(resp.text))
        if settled:
            self._settled_listings[day_url] = listing
        return listing

    # ── Download ───────────────────────────────────────────────────
    def download(self, url: str, filename: str) -> Path:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        dest = self.cache_dir / filename
        if dest.exists() and dest.stat().st_size > 0:
            return dest
        tmp = dest.with_suffix(".part")
        with self.session.get(url, stream=True, timeout=300) as resp:
            if resp.status_code == 401:
                raise PermissionError(
                    "Earthdata Login rejected the credentials (HTTP 401). Check NASA_EARTHDATA_USER/PASS and that "
                    "the 'NASA GESDISC DATA ARCHIVE' application is authorised in your Earthdata profile."
                )
            resp.raise_for_status()
            if "text/html" in resp.headers.get("Content-Type", ""):
                reason = ""
                for hop in resp.history:
                    q = parse_qs(urlparse(hop.headers.get("Location", "")).query)
                    if "error_msg" in q:
                        reason = q["error_msg"][0]
                        break
                raise PermissionError(
                    f"GES DISC returned a login page instead of data ({reason or 'no reason given'}). "
                    "Authorise the 'NASA GESDISC DATA ARCHIVE' application in your Earthdata profile: "
                    "https://urs.earthdata.nasa.gov/profile → Applications → Authorized Apps → Approve More Applications."
                )
            with open(tmp, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    fh.write(chunk)
        tmp.replace(dest)
        self._prune_cache()
        return dest

    def _prune_cache(self):
        files = sorted(self.cache_dir.glob("*.HDF5"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in files[self.keep_files:]:
            old.unlink(missing_ok=True)

    # ── Read + regrid ──────────────────────────────────────────────
    @staticmethod
    def read_precipitation(path: Path, bbox: tuple, shape=(1024, 1024)) -> np.ndarray:
        """Read /Grid/precipitation (time, lon, lat) and regrid to the north-up target grid."""
        min_lat, max_lat, min_lon, max_lon = bbox
        with h5py.File(path, "r") as f:
            lats = f["Grid/lat"][:]
            lons = f["Grid/lon"][:]
            # Subset with a 1-cell margin before loading to keep memory low
            li = np.where((lats >= min_lat - 0.2) & (lats <= max_lat + 0.2))[0]
            lo = np.where((lons >= min_lon - 0.2) & (lons <= max_lon + 0.2))[0]
            precip = f["Grid/precipitation"][0, lo[0]:lo[-1] + 1, li[0]:li[-1] + 1]  # (lon, lat)
        precip = precip.T.astype(np.float32)  # → (lat, lon)
        precip[precip < FILL_THRESHOLD] = np.nan
        return regrid_to_bbox(precip, lats[li[0]:li[-1] + 1], lons[lo[0]:lo[-1] + 1], bbox, shape)

    def fetch_latest(self, bbox: tuple, before: Optional[datetime] = None) -> GpmFrame:
        collection, day_url, name, start = self.find_latest_granule(before)
        path = self.download(day_url + name, name)
        precip = self.read_precipitation(path, bbox)
        if np.all(np.isnan(precip)):
            raise DataQualityError(f"IMERG granule {name} has no valid precipitation over {bbox}")
        return GpmFrame(precip=precip, bounds=bbox, obs_time=start, granule=name)

    def stream_and_subgrid_gpm(self, target_time: datetime, bbox: tuple) -> np.ndarray:
        """Backward-compatible API: precipitation array for the newest granule at/before target_time."""
        return self.fetch_latest(bbox, before=target_time).precip
