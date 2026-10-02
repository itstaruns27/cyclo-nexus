"""
MOSDAC INSAT-3DS / 3DR live ingestion (MOSDAC Data Download API)
════════════════════════════════════════════════════════════════
1. Search  : public OpenSearch  https://mosdac.gov.in/apios/datasets.json
2. Token   : POST /download_api/gettoken  (MOSDAC_USER / MOSDAC_PASS from data_pipeline/.env)
3. Download: GET  /download_api/download?id=<granule id>  (Bearer token, resumable)
4. Extract : L1C ASIA_MER HDF5 → TIR1 / TIR2 / WV brightness temperature (K) via the
             per-band count→temperature look-up tables, then regrid Mercator rows
             onto the NIO lat-lon target grid.

Default product: 3SIMG_L1C_ASIA_MER (INSAT-3DS Imager, Mercator, 44.5–110°E, 10°S–45.5°N,
half-hourly, ~24 MB). Override with MOSDAC_DATASET_ID (e.g. 3RIMG_L1C_ASIA_MER for INSAT-3DR).
"""

import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import h5py
import numpy as np
import requests
from dotenv import load_dotenv

from data_pipeline.preprocessing.axis_regridder import regrid_to_bbox

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

SEARCH_URL = "https://mosdac.gov.in/apios/datasets.json"
TOKEN_URL = "https://mosdac.gov.in/download_api/gettoken"
REFRESH_URL = "https://mosdac.gov.in/download_api/refresh-token"
DOWNLOAD_URL = "https://mosdac.gov.in/download_api/download"
LOGOUT_URL = "https://mosdac.gov.in/download_api/logout"

DEFAULT_DATASET = "3SIMG_L1C_ASIA_MER"
DEFAULT_CACHE = Path(__file__).resolve().parents[2] / "data" / "live" / "mosdac"
BANDS = {"TIR1": "IMG_TIR1", "TIR2": "IMG_TIR2", "WV": "IMG_WV"}


class DataQualityError(Exception):
    pass


@dataclass
class InsatFrame:
    channels: Dict[str, np.ndarray]  # TIR1 / TIR2 / WV brightness temperature (K), NaN = no data
    bounds: tuple                    # (min_lat, max_lat, min_lon, max_lon)
    obs_time: datetime               # acquisition start (UTC)
    granule: str


class MosdacIngestionWorker:
    """Worker for ingesting INSAT Imager L1C granules from MOSDAC."""

    def __init__(self, dataset_id: Optional[str] = None, cache_dir: Optional[Path] = None, keep_files: int = 8):
        self.dataset_id = dataset_id or os.environ.get("MOSDAC_DATASET_ID", DEFAULT_DATASET)
        self.cache_dir = Path(cache_dir or DEFAULT_CACHE)
        self.keep_files = keep_files
        self.session = requests.Session()
        self._user = None
        self._password = None
        self._access_token = None
        self._refresh_token = None
        self._token_expiry = 0.0

    # ── Auth ───────────────────────────────────────────────────────
    def authenticate(self, user: str = None, password: str = None) -> None:
        """Obtain a MOSDAC download token. Credentials stay in memory only."""
        self._user = user or os.environ.get("MOSDAC_USER")
        self._password = password or os.environ.get("MOSDAC_PASS")
        if not self._user or not self._password:
            raise EnvironmentError("MOSDAC_USER and MOSDAC_PASS are required in data_pipeline/.env")
        self._request_token()

    def _request_token(self):
        resp = self.session.post(TOKEN_URL, json={"username": self._user, "password": self._password}, timeout=60)
        if resp.status_code in (400, 401, 403):
            raise PermissionError(f"MOSDAC rejected the credentials (HTTP {resp.status_code}). "
                                  "Check MOSDAC_USER / MOSDAC_PASS in data_pipeline/.env.")
        resp.raise_for_status()
        self._store_token(resp.json())

    def _store_token(self, body: dict):
        if "access_token" not in body:
            raise PermissionError(f"MOSDAC token response had no access_token: {list(body.keys())}")
        self._access_token = body["access_token"]
        self._refresh_token = body.get("refresh_token")
        self._token_expiry = time.time() + int(body.get("expires_in", 300)) - 30

    def _auth_header(self) -> dict:
        if self._access_token is None:
            self.authenticate()
        elif time.time() >= self._token_expiry:
            try:
                resp = self.session.post(REFRESH_URL, json={"refresh_token": self._refresh_token}, timeout=60)
                resp.raise_for_status()
                self._store_token(resp.json())
            except Exception:
                self._request_token()
        return {"Authorization": f"Bearer {self._access_token}"}

    def logout(self):
        if self._user and self._access_token:
            try:
                self.session.post(LOGOUT_URL, json={"username": self._user}, timeout=30)
            except requests.RequestException:
                pass
        self._access_token = None

    # ── Search ─────────────────────────────────────────────────────
    def search_granules(self, start: Optional[datetime] = None, end: Optional[datetime] = None,
                        count: int = 10) -> List[dict]:
        """Newest-first list of up to `count` granule entries (identifier, id, obs_time)."""
        page_size = 100  # MOSDAC OpenSearch rejects larger pages with HTTP 400
        params = {"datasetId": self.dataset_id}
        if start:
            params["startTime"] = start.strftime("%Y-%m-%d")
        if end:
            params["endTime"] = end.strftime("%Y-%m-%d")
        entries, start_index = [], 1
        while len(entries) < count:
            params.update(count=min(page_size, count - len(entries)), startIndex=start_index)
            resp = self.session.get(SEARCH_URL, params=params, timeout=60)
            resp.raise_for_status()
            page = resp.json().get("entries", [])
            for e in page:
                obs = datetime.strptime(e["updated"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                entries.append({"granule_id": e["identifier"], "id": e["id"], "obs_time": obs})
            if len(page) < params["count"]:
                break
            start_index += len(page)
        return sorted(entries, key=lambda x: x["obs_time"], reverse=True)

    def fetch_latest_granule_metadata(self, target_time: Optional[datetime] = None) -> dict:
        """Newest granule at or before target_time (default: now)."""
        target_time = target_time or datetime.now(timezone.utc)
        if target_time.tzinfo is None:
            target_time = target_time.replace(tzinfo=timezone.utc)
        # Search dates are whole calendar days, so this spans up to 3 days (up to several hundred granules with INSAT-3DS rapid scans): fetch them all
        entries = self.search_granules(start=target_time - timedelta(days=1), end=target_time, count=2000)
        for e in entries:
            if e["obs_time"] <= target_time:
                return e
        raise FileNotFoundError(f"No {self.dataset_id} granule found at/before {target_time.isoformat()}")

    # ── Download ───────────────────────────────────────────────────
    def download_granule(self, metadata: dict, output_dir: Optional[str] = None, retries: int = 5) -> Path:
        """Resumable download of one granule; returns the local path (cached if already complete)."""
        out_dir = Path(output_dir) if output_dir else self.cache_dir
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / metadata["granule_id"]
        if dest.exists() and dest.stat().st_size > 0:
            return dest
        part = dest.with_name(dest.name + ".part")

        for attempt in range(1, retries + 1):
            have = part.stat().st_size if part.exists() else 0
            headers = self._auth_header()
            if have:
                headers["Range"] = f"bytes={have}-"
            try:
                with self.session.get(DOWNLOAD_URL, params={"id": metadata["id"]}, headers=headers,
                                      stream=True, timeout=(30, 120)) as resp:
                    if resp.status_code == 401:
                        self._access_token = None
                        raise PermissionError("MOSDAC download token rejected (HTTP 401)")
                    if resp.status_code == 416:  # range past end → already complete
                        break
                    resp.raise_for_status()
                    ctype = resp.headers.get("Content-Type", "")
                    if "json" in ctype or "html" in ctype:
                        raise PermissionError(f"MOSDAC returned {ctype} instead of HDF5: {resp.text[:300]}")
                    mode = "ab" if have and resp.status_code == 206 else "wb"
                    with open(part, mode) as fh:
                        for chunk in resp.iter_content(chunk_size=1024 * 1024):
                            fh.write(chunk)
                break
            except (requests.ConnectionError, requests.Timeout, requests.exceptions.ChunkedEncodingError) as exc:
                if attempt == retries:
                    raise ConnectionError(f"MOSDAC download of {metadata['granule_id']} failed after "
                                          f"{retries} attempts: {exc}") from exc
                time.sleep(min(2 ** attempt, 30))

        with h5py.File(part, "r"):
            pass  # raises if truncated / corrupt
        part.replace(dest)
        self._prune_cache(out_dir)
        return dest

    def _prune_cache(self, out_dir: Path):
        files = sorted(out_dir.glob("*.h5"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in files[self.keep_files:]:
            old.unlink(missing_ok=True)

    # ── Extract ────────────────────────────────────────────────────
    @staticmethod
    def _band_temperature(f: h5py.File, name: str) -> np.ndarray:
        """Counts → brightness temperature (K) through the band's look-up table."""
        counts = f[name][...]
        if counts.ndim == 3:
            counts = counts[0]
        lut = f[f"{name}_TEMP"][...].astype(np.float32)
        fill = f[name].attrs.get("_FillValue")
        fill = int(np.ravel(fill)[0]) if fill is not None else None
        idx = counts.astype(np.int64)
        valid = (idx >= 0) & (idx < lut.size)
        if fill is not None:
            valid &= idx != fill
        bt = np.full(counts.shape, np.nan, dtype=np.float32)
        bt[valid] = lut[idx[valid]]
        bt[(bt < 150.0) | (bt > 350.0)] = np.nan
        return bt

    @staticmethod
    def _row_col_axes(f: h5py.File, shape: tuple):
        """1-D latitude per row and longitude per column of the Mercator grid."""
        if "Latitude" in f and "Longitude" in f and f["Latitude"].ndim == 1:
            return f["Latitude"][...].astype(np.float64), f["Longitude"][...].astype(np.float64)
        if "X" in f and "Y" in f and "Projection_Information" in f:
            # Exact inverse of the ellipsoidal Mercator (standard parallel variant) in Projection_Information
            p = f["Projection_Information"].attrs
            a_ax = float(np.ravel(p["semi_major_axis"])[0])
            b_ax = float(np.ravel(p["semi_minor_axis"])[0])
            lon0 = np.radians(float(np.ravel(p["longitude_of_projection_origin"])[0]))
            phi1 = np.radians(float(np.ravel(p["standard_parallel"])[0]))
            fe = float(np.ravel(p.get("false_easting", [0.0]))[0])
            fn = float(np.ravel(p.get("false_northing", [0.0]))[0])
            e = np.sqrt(1.0 - (b_ax / a_ax) ** 2)
            ak0 = a_ax * np.cos(phi1) / np.sqrt(1.0 - (e * np.sin(phi1)) ** 2)
            x = f["X"][...].astype(np.float64) - fe
            y = f["Y"][...].astype(np.float64) - fn
            lons = np.degrees(lon0 + x / ak0)
            t = np.exp(-y / ak0)
            phi = np.pi / 2 - 2 * np.arctan(t)
            for _ in range(8):
                es = e * np.sin(phi)
                phi = np.pi / 2 - 2 * np.arctan(t * ((1 - es) / (1 + es)) ** (e / 2))
            return np.degrees(phi), lons
        a = f.attrs
        upper = float(np.ravel(a["upper_latitude"])[0])
        lower = float(np.ravel(a["lower_latitude"])[0])
        left = float(np.ravel(a["left_longitude"])[0])
        right = float(np.ravel(a["right_longitude"])[0])
        rows, cols = shape
        # Mercator: rows are evenly spaced in y = ln(tan(π/4 + φ/2)); row 0 = north
        merc = lambda lat: np.log(np.tan(np.pi / 4 + np.radians(lat) / 2))
        y = np.linspace(merc(upper), merc(lower), rows)
        lats = np.degrees(2 * np.arctan(np.exp(y)) - np.pi / 2)
        lons = np.linspace(left, right, cols)
        return lats, lons

    def extract_frame(self, path: Path, bbox: tuple, shape=(1024, 1024)) -> Dict[str, np.ndarray]:
        """TIR1 / TIR2 / WV brightness temperature (K) on the north-up NIO target grid."""
        channels = {}
        with h5py.File(path, "r") as f:
            for key, ds in BANDS.items():
                if ds not in f:
                    raise DataQualityError(f"{path.name} is missing band {ds}")
                bt = self._band_temperature(f, ds)
                lats, lons = self._row_col_axes(f, bt.shape)
                channels[key] = regrid_to_bbox(bt, lats, lons, bbox, shape)
        for key, arr in channels.items():
            if np.isnan(arr).mean() > 0.5:
                raise DataQualityError(f"{path.name}: channel {key} is >50% missing over the NIO box")
        return channels

    def extract_raw_channels(self, granule_path: Path, bbox: tuple = (0.0, 32.0, 50.0, 102.0)) -> Dict[str, np.ndarray]:
        """Backward-compatible single-call API (legacy callers)."""
        return self.extract_frame(Path(granule_path), bbox)

    def fetch_latest(self, bbox: tuple, before: Optional[datetime] = None) -> InsatFrame:
        meta = self.fetch_latest_granule_metadata(before)
        path = self.download_granule(meta)
        return InsatFrame(channels=self.extract_frame(path, bbox), bounds=bbox,
                          obs_time=meta["obs_time"], granule=meta["granule_id"])

    def fetch_insat3d_channels(self, target_time: datetime, bbox: tuple) -> Dict[str, np.ndarray]:
        """Backward-compatible API: channels for the newest granule at/before target_time."""
        return self.fetch_latest(bbox, before=target_time).channels
