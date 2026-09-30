import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np
import pytest

from data_pipeline.ingestion.historical_satellite_downloader import (
    HistoricalSatelliteDownloader,
    BENCHMARK_STORM_WINDOWS,
)


@pytest.fixture
def temp_dirs(tmp_path):
    out = tmp_path / "tensors"
    raw = tmp_path / "raw"
    out.mkdir()
    raw.mkdir()
    return out, raw


def test_downloader_initialization(temp_dirs):
    out, raw = temp_dirs
    downloader = HistoricalSatelliteDownloader(output_dir=out, raw_dir=raw)
    assert downloader.output_dir == out
    assert downloader.raw_dir == raw


def test_synthetic_channels_generation(temp_dirs):
    out, raw = temp_dirs
    downloader = HistoricalSatelliteDownloader(output_dir=out, raw_dir=raw)
    channels = downloader._generate_synthetic_channels(datetime(2020, 5, 18, 12, 0))

    assert "TIR1" in channels
    assert "TIR2" in channels
    assert "WV" in channels
    assert "GPM" in channels

    assert channels["TIR1"].shape == (1024, 1024)
    assert channels["TIR1"].min() >= 180.0
    assert channels["TIR1"].max() <= 320.0
    assert channels["GPM"].min() >= 0.0


def test_process_time_step(temp_dirs):
    out, raw = temp_dirs
    downloader = HistoricalSatelliteDownloader(output_dir=out, raw_dir=raw)
    target_time = datetime(2020, 5, 18, 12, 0)

    tensor_path = downloader.process_time_step(target_time)
    assert tensor_path.exists()
    assert tensor_path.name == "INSAT3D_L1C_20200518_120000.npy"

    tensor = np.load(tensor_path)
    assert tensor.shape == (4, 1024, 1024)
    assert tensor.dtype == np.float32
    assert tensor.min() >= 0.0
    assert tensor.max() <= 1.0


def test_download_historical_window_with_max_frames(temp_dirs):
    out, raw = temp_dirs
    downloader = HistoricalSatelliteDownloader(output_dir=out, raw_dir=raw)

    start = datetime(2020, 5, 18, 0, 0)
    end = datetime(2020, 5, 18, 6, 0)

    files = downloader.download_historical_window(
        start_time=start,
        end_time=end,
        interval_minutes=30,
        max_frames=3,
    )

    assert len(files) == 3
    for f in files:
        assert f.exists()
        arr = np.load(f)
        assert arr.shape == (4, 1024, 1024)


def test_download_benchmark_storm(temp_dirs):
    out, raw = temp_dirs
    downloader = HistoricalSatelliteDownloader(output_dir=out, raw_dir=raw)

    files = downloader.download_benchmark_storm("AMPHAN", interval_minutes=60, max_frames=2)
    assert len(files) == 2

    with pytest.raises(ValueError):
        downloader.download_benchmark_storm("NON_EXISTENT_STORM")
