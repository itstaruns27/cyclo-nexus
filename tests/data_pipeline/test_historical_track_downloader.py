import io
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import pandas as pd

from data_pipeline.catalog.historical_track_downloader import (
    HistoricalTrackDownloader,
    IBTRACS_NI_URL,
    BENCHMARK_CYCLONES,
)
from data_pipeline.preprocessing.imd_track_harmonizer import IMDTrackHarmonizer

SAMPLE_IBTRACS_CSV = """SID,SEASON,NUMBER,BASIN,SUBBASIN,NAME,ISO_TIME,NATURE,LAT,LON,WMO_WIND,WMO_PRES,newdelhi_lat,newdelhi_lon,newdelhi_wind,newdelhi_pres
None,Year,Count,None,None,None,YYYY-MM-DD HH:MM:SS,None,deg_north,deg_east,kts,mb,deg_north,deg_east,kts,mb
2020137N10086,2020,01,NI,BB,AMPHAN,2020-05-17 00:00:00,TS,11.5,86.0,55,988,11.5,86.0,55,988
2020137N10086,2020,01,NI,BB,AMPHAN,2020-05-17 06:00:00,TS,12.0,86.2,65,978,12.0,86.2,65,978
2020137N10086,2020,01,NI,BB,AMPHAN,2020-05-17 12:00:00,TS,12.5,86.4,85,960,12.5,86.4,85,960
2021133N09072,2021,01,NI,AS,TAUKTAE,2021-05-15 00:00:00,TS,12.0,72.5,45,992,12.0,72.5,45,992
"""


@pytest.fixture
def temp_cache_dir(tmp_path):
    cache = tmp_path / "besttrack_cache"
    cache.mkdir()
    return cache


def test_downloader_initialization(temp_cache_dir):
    downloader = HistoricalTrackDownloader(cache_dir=temp_cache_dir)
    assert downloader.cache_dir == temp_cache_dir
    assert downloader.raw_csv_path == temp_cache_dir / "ibtracs.NI.list.v04r00.csv"


@patch("requests.get")
def test_download_ibtracs_ni(mock_get, temp_cache_dir):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = SAMPLE_IBTRACS_CSV.encode("utf-8")
    mock_get.return_value = mock_response

    downloader = HistoricalTrackDownloader(cache_dir=temp_cache_dir)
    downloaded_path = downloader.download_ibtracs_ni(force_refresh=True)

    assert downloaded_path.exists()
    assert downloaded_path.stat().st_size > 0
    mock_get.assert_called_once()


def test_load_and_filter_storm(temp_cache_dir):
    csv_path = temp_cache_dir / "test_ibtracs.csv"
    csv_path.write_text(SAMPLE_IBTRACS_CSV, encoding="utf-8")

    downloader = HistoricalTrackDownloader(cache_dir=temp_cache_dir)
    df = downloader.load_ibtracs_data(csv_path=csv_path)

    assert len(df) == 4
    assert "AMPHAN" in df["NAME"].values

    records = downloader.filter_storm(df, storm_name="AMPHAN", season=2020)
    assert len(records) == 3
    assert records[0]["cyclone_id"] == "AMPHAN_2020"
    assert records[0]["center_lat"] == 11.5
    assert records[0]["center_lon"] == 86.0
    assert records[0]["v_max_knots"] == 55.0
    assert records[0]["imd_category"] == "SCS"

    # Verify parsing with IMDTrackHarmonizer
    out_csv = temp_cache_dir / "amphan_track.csv"
    downloader.export_harmonized_csv(records, out_csv)
    assert out_csv.exists()

    harmonizer = IMDTrackHarmonizer()
    parsed = harmonizer.parse_track_csv(out_csv)
    assert len(parsed) == 3
    assert parsed[0]["cyclone_id"] == "AMPHAN_2020"
    assert parsed[0]["v_max_kmh"] == pytest.approx(55.0 * 1.852)


def test_export_parquet(temp_cache_dir):
    csv_path = temp_cache_dir / "test_ibtracs.csv"
    csv_path.write_text(SAMPLE_IBTRACS_CSV, encoding="utf-8")

    downloader = HistoricalTrackDownloader(cache_dir=temp_cache_dir)
    df = downloader.load_ibtracs_data(csv_path=csv_path)
    records = downloader.filter_storm(df, storm_name="TAUKTAE", season=2021)

    parquet_path = temp_cache_dir / "tauktae.parquet"
    out = downloader.export_harmonized_parquet(records, parquet_path)
    assert out.exists()

    loaded = pd.read_parquet(parquet_path)
    assert len(loaded) == 1
    assert loaded["cyclone_id"].iloc[0] == "TAUKTAE_2021"
