"""Offline tests for the MOSDAC INSAT L1C worker (no network)."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import h5py
import numpy as np
import pytest

from data_pipeline.ingestion.mosdac_worker import DataQualityError, MosdacIngestionWorker

BBOX = (0.0, 32.0, 50.0, 102.0)


def _write_l1c(path, bands=("IMG_TIR1", "IMG_TIR2", "IMG_WV"), rows=400, cols=450):
    """Synthetic L1C ASIA_MER file: 10-bit counts + LUT + ellipsoidal Mercator X/Y (same layout as MOSDAC)."""
    a, b = 6378137.0, 6356752.3142
    e = np.sqrt(1 - (b / a) ** 2)
    phi1, lon0 = np.radians(17.75), np.radians(77.25)
    ak0 = a * np.cos(phi1) / np.sqrt(1 - (e * np.sin(phi1)) ** 2)

    def y_of(lat):
        p = np.radians(lat)
        es = e * np.sin(p)
        return ak0 * np.log(np.tan(np.pi / 4 + p / 2) * ((1 - es) / (1 + es)) ** (e / 2))

    x = ak0 * (np.radians(np.linspace(44.5, 110.0, cols)) - lon0)
    y = np.linspace(y_of(45.5), y_of(-10.0), rows)
    with h5py.File(path, "w") as f:
        f.create_dataset("X", data=x)
        f.create_dataset("Y", data=y)
        pi = f.create_dataset("Projection_Information", data=np.array([0], dtype=np.int32))
        for k, v in {"semi_major_axis": [a], "semi_minor_axis": [b], "longitude_of_projection_origin": [77.25],
                     "standard_parallel": [17.75], "false_easting": [0.0], "false_northing": [0.0]}.items():
            pi.attrs[k] = np.array(v)
        lut = np.linspace(320.0, 180.0, 1024).astype(np.float32)  # count → K (inverted, like INSAT)
        for name in bands:
            counts = np.full((1, rows, cols), 300, dtype=np.uint16)
            counts[0, :5, :] = 1023  # fill rows
            ds = f.create_dataset(name, data=counts)
            ds.attrs["_FillValue"] = np.array([1023], dtype=np.uint16)
            f.create_dataset(f"{name}_TEMP", data=lut)
    return lut[300]


def test_mercator_axes_recover_corner_latitudes(tmp_path):
    p = tmp_path / "g.h5"
    _write_l1c(p)
    with h5py.File(p) as f:
        lats, lons = MosdacIngestionWorker._row_col_axes(f, (400, 450))
    assert lats[0] == pytest.approx(45.5, abs=1e-6)
    assert lats[-1] == pytest.approx(-10.0, abs=1e-6)
    assert lons[0] == pytest.approx(44.5, abs=1e-6)
    assert lons[-1] == pytest.approx(110.0, abs=1e-6)


def test_extract_frame_converts_counts_to_kelvin(tmp_path):
    p = tmp_path / "g.h5"
    expected_k = _write_l1c(p)
    ch = MosdacIngestionWorker().extract_frame(p, BBOX, shape=(128, 128))
    assert set(ch) == {"TIR1", "TIR2", "WV"}
    for arr in ch.values():
        assert arr.shape == (128, 128)
        assert np.nanmax(np.abs(arr - expected_k)) < 1e-3  # fill rows are outside the NIO box


def test_extract_frame_missing_band_is_an_error(tmp_path):
    p = tmp_path / "g.h5"
    _write_l1c(p, bands=("IMG_TIR1", "IMG_TIR2"))
    with pytest.raises(DataQualityError):
        MosdacIngestionWorker().extract_frame(p, BBOX, shape=(64, 64))


def test_authenticate_requires_credentials(monkeypatch):
    monkeypatch.delenv("MOSDAC_USER", raising=False)
    monkeypatch.delenv("MOSDAC_PASS", raising=False)
    with pytest.raises(EnvironmentError):
        MosdacIngestionWorker().authenticate()


def test_authenticate_keeps_credentials_in_memory_only(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    w = MosdacIngestionWorker(cache_dir=tmp_path / "cache")
    resp = MagicMock(status_code=200)
    resp.json.return_value = {"access_token": "tok", "refresh_token": "ref", "expires_in": 300}
    with patch.object(w.session, "post", return_value=resp) as post:
        w.authenticate("user", "pass")
    assert post.call_args.kwargs["json"] == {"username": "user", "password": "pass"}
    assert w._auth_header() == {"Authorization": "Bearer tok"}
    assert list(tmp_path.iterdir()) == []  # nothing written to disk


def test_search_parses_and_sorts_entries():
    w = MosdacIngestionWorker()
    resp = MagicMock()
    resp.json.return_value = {"entries": [
        {"identifier": "A.h5", "id": "1", "updated": "2026-09-29T13:00:00Z"},
        {"identifier": "B.h5", "id": "2", "updated": "2026-09-29T13:30:00Z"},
    ]}
    with patch.object(w.session, "get", return_value=resp):
        entries = w.search_granules()
        latest = w.fetch_latest_granule_metadata(datetime(2026, 9, 29, 13, 10, tzinfo=timezone.utc))
    assert [e["granule_id"] for e in entries] == ["B.h5", "A.h5"]
    assert latest["granule_id"] == "A.h5"
