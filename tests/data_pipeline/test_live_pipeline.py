"""Offline tests for the live pipeline helpers (no network, no services)."""
from datetime import datetime, timedelta, timezone

import h5py
import numpy as np
import pytest

from data_pipeline.ingestion import live_pipeline_runner as runner
from data_pipeline.ingestion.nasa_gpm_worker import NasaGpmIngestionWorker
from data_pipeline.preprocessing.axis_regridder import regrid_to_bbox, target_axes

T0 = datetime(2026, 9, 29, 13, 30, tzinfo=timezone.utc)


class FakeInsat:
    def __init__(self, times):
        self.entries = [{"granule_id": f"G{t:%H%M}.h5", "id": str(i), "obs_time": t} for i, t in enumerate(times)]

    def fetch_latest_granule_metadata(self, target_time=None):
        return max(self.entries, key=lambda e: e["obs_time"])

    def search_granules(self, start=None, end=None, count=10):
        return sorted(self.entries, key=lambda e: e["obs_time"], reverse=True)


def test_window_uses_three_hour_steps_oldest_first():
    times = [T0 - timedelta(minutes=30 * k) for k in range(40)]
    window = runner.select_window(FakeInsat(times))
    got = [w["obs_time"] for w in window]
    assert got == [T0 - timedelta(hours=3 * k) for k in range(5, -1, -1)]


def test_window_fills_gaps_with_real_neighbouring_frames():
    times = [T0 - timedelta(minutes=30 * k) for k in range(40) if not (10 <= k <= 14)]  # hole around t0-6h
    window = runner.select_window(FakeInsat(times))
    assert len(window) == 6 and all(w is not None for w in window)
    assert window[3]["obs_time"] == T0 - timedelta(hours=3)  # t0-6h slot → next real frame


def test_haversine_and_basin():
    assert runner.haversine_km(15.0, 88.0, 15.0, 88.0) == pytest.approx(0.0)
    assert runner.haversine_km(0.0, 80.0, 1.0, 80.0) == pytest.approx(111.2, abs=0.5)
    assert runner.basin_for(15.0, 65.0) == "AS"
    assert runner.basin_for(15.0, 88.0) == "BOB"


def test_regrid_is_north_up_and_marks_outside_as_nan():
    lats = np.linspace(-5, 40, 91)     # ascending source rows
    lons = np.linspace(45, 105, 121)
    field = np.repeat(lats[:, None], lons.size, axis=1).astype(np.float32)  # value == latitude
    out = regrid_to_bbox(field, lats, lons, (0.0, 32.0, 50.0, 102.0), shape=(64, 64))
    tl, _ = target_axes((0.0, 32.0, 50.0, 102.0), (64, 64))
    assert np.allclose(out[:, 10], tl, atol=1e-3)
    assert out[0, 0] > out[-1, 0]
    assert np.isnan(regrid_to_bbox(field, lats, lons, (50.0, 60.0, 50.0, 102.0), shape=(8, 8))).all()


def test_imerg_reader_transposes_and_masks_fill(tmp_path):
    lats = np.arange(-89.95, 90, 0.1)
    lons = np.arange(-179.95, 180, 0.1)
    precip = np.zeros((1, lons.size, lats.size), dtype=np.float32)  # IMERG layout: (time, lon, lat)
    li = np.argmin(np.abs(lats - 16.05)); lo = np.argmin(np.abs(lons - 88.05))
    precip[0, lo - 5:lo + 5, li - 5:li + 5] = 20.0
    precip[0, np.argmin(np.abs(lons - 60.05)), :] = -9999.9
    p = tmp_path / "imerg.HDF5"
    with h5py.File(p, "w") as f:
        f["Grid/lat"] = lats
        f["Grid/lon"] = lons
        f["Grid/precipitation"] = precip
    out = NasaGpmIngestionWorker.read_precipitation(p, (0.0, 32.0, 50.0, 102.0), shape=(320, 520))
    r, c = np.unravel_index(np.nanargmax(out), out.shape)
    assert 32.0 - (r + 0.5) * 0.1 == pytest.approx(16.0, abs=0.6)
    assert 50.0 + (c + 0.5) * 0.1 == pytest.approx(88.0, abs=0.6)
    assert np.isnan(out[:, 100]).any()  # 60°E fill column stays missing
