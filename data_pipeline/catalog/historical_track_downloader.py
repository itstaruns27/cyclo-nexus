"""
Automated Historical Best Track Downloader & Harmonizer
══════════════════════════════════════════════════════
Owner: Agent ALPHA (Task 5: IMD Best Track Dataset Harmonization)

Automates downloading official historical cyclone tracks from the NOAA IBTrACS
(International Best Track Archive for Climate Stewardship) repository, which
compiles official WMO RSMC New Delhi (IMD) cyclone records for the North Indian Ocean.

Extracts, filters, and harmonizes tracks into standard CSV and Parquet formats
ready for direct consumption by IMDTrackHarmonizer and the AI Forecaster.
"""

import os
import csv
import io
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Union
import requests
import pandas as pd

from data_pipeline.preprocessing.imd_track_harmonizer import IMDTrackHarmonizer

import gzip

IBTRACS_NI_URL = (
    "https://www.ncei.noaa.gov/data/international-best-track-archive-for-"
    "climate-stewardship-ibtracs/v04r00/access/csv/ibtracs.NI.list.v04r00.csv"
)

IBTRACS_FALLBACK_URLS = [
    IBTRACS_NI_URL,
    "https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r00/access/csv/ibtracs.NI.list.v04r00.csv.gz",
    "https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.NI.list.v04r01.csv",
]

# Standard benchmark cyclones for North Indian Ocean AI training
BENCHMARK_CYCLONES = [
    {"name": "AMPHAN", "season": 2020, "id": "BOB01_2020"},
    {"name": "TAUKTAE", "season": 2021, "id": "ARB01_2021"},
    {"name": "BIPARJOY", "season": 2023, "id": "ARB02_2023"},
    {"name": "FANI", "season": 2019, "id": "BOB02_2019"},
    {"name": "MICHAUNG", "season": 2023, "id": "BOB05_2023"},
]


class HistoricalTrackDownloader:
    """Automates downloading, filtering, and harmonizing historical IMD cyclone tracks."""

    def __init__(self, cache_dir: Union[str, Path] = "data/besttrack"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.raw_csv_path = self.cache_dir / "ibtracs.NI.list.v04r00.csv"
        self.harmonizer = IMDTrackHarmonizer()

    def download_ibtracs_ni(self, force_refresh: bool = False) -> Path:
        """
        Downloads the latest North Indian Ocean IBTrACS archive if not cached.
        Supports both raw CSV and transparent gzip (.gz) decompression.
        """
        if self.raw_csv_path.exists() and not force_refresh and self.raw_csv_path.stat().st_size > 1024:
            print(f"Using cached IBTrACS archive: {self.raw_csv_path}")
            return self.raw_csv_path

        last_error = None
        for candidate_url in IBTRACS_FALLBACK_URLS:
            try:
                print(f"Downloading official NOAA IBTrACS NI archive from:\n{candidate_url}...")
                response = requests.get(candidate_url, stream=True, timeout=60)
                if response.status_code == 200:
                    raw_bytes = response.content
                    # Check if response is gzipped (magic bytes 0x1f, 0x8b)
                    if raw_bytes.startswith(b"\x1f\x8b") or candidate_url.endswith(".gz"):
                        print("Decompressing gzipped IBTrACS payload...")
                        decompressed = gzip.decompress(raw_bytes)
                        with open(self.raw_csv_path, "wb") as f:
                            f.write(decompressed)
                    else:
                        with open(self.raw_csv_path, "wb") as f:
                            f.write(raw_bytes)

                    print(
                        f"Successfully saved IBTrACS archive to {self.raw_csv_path} "
                        f"({self.raw_csv_path.stat().st_size / (1024*1024):.1f} MB)"
                    )
                    return self.raw_csv_path
                else:
                    last_error = f"HTTP {response.status_code}"
            except Exception as e:
                last_error = str(e)
                continue

        raise FileNotFoundError(
            f"Failed to download IBTrACS from all candidate URLs. Last error: {last_error}"
        )

        print(f"Successfully downloaded IBTrACS archive to {self.raw_csv_path} ({self.raw_csv_path.stat().st_size / (1024*1024):.1f} MB)")
        return self.raw_csv_path

    def load_ibtracs_data(self, csv_path: Optional[Path] = None) -> pd.DataFrame:
        """
        Loads and parses the IBTrACS CSV, properly skipping the second metadata/units row.
        """
        target_path = csv_path or self.raw_csv_path
        if not target_path.exists():
            target_path = self.download_ibtracs_ni()

        # Row 0 is header, Row 1 is units (skip it with skiprows=[1])
        df = pd.read_csv(target_path, skiprows=[1], low_memory=False)
        return df

    def filter_storm(
        self,
        df: pd.DataFrame,
        storm_name: str,
        season: Optional[int] = None,
        cyclone_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Filters the dataset for a specific cyclone, prioritizing RSMC New Delhi (IMD)
        estimates for latitude, longitude, wind speed, and pressure.
        """
        name_upper = storm_name.strip().upper()
        mask = df["NAME"].str.upper() == name_upper

        if season is not None:
            mask = mask & (df["SEASON"].astype(str) == str(season))

        matched = df[mask].copy()
        if matched.empty:
            print(f"No records found for storm: {storm_name} (Season: {season})")
            return []

        # Sort chronologically by ISO_TIME
        matched["ISO_TIME"] = pd.to_datetime(matched["ISO_TIME"])
        matched = matched.sort_values("ISO_TIME")

        records = []
        c_id = cyclone_id or f"{name_upper}_{season if season else matched['SEASON'].iloc[0]}"

        for _, row in matched.iterrows():
            # Extract coordinates: prefer RSMC New Delhi observation, fallback to WMO/USA
            lat_val = row.get("newdelhi_lat")
            if pd.isna(lat_val) or str(lat_val).strip() == "":
                lat_val = row.get("LAT")

            lon_val = row.get("newdelhi_lon")
            if pd.isna(lon_val) or str(lon_val).strip() == "":
                lon_val = row.get("LON")

            # Wind speed (knots): prefer newdelhi_wind, fallback to WMO_WIND
            wind_val = row.get("newdelhi_wind")
            if pd.isna(wind_val) or str(wind_val).strip() == "":
                wind_val = row.get("WMO_WIND")
            
            # Central pressure (hPa): prefer newdelhi_pres, fallback to WMO_PRES
            pres_val = row.get("newdelhi_pres")
            if pd.isna(pres_val) or str(pres_val).strip() == "":
                pres_val = row.get("WMO_PRES")

            # Fallback reasonable defaults if intermediate points lack explicit pressure/wind
            try:
                center_lat = float(lat_val)
                center_lon = float(lon_val)
            except (TypeError, ValueError):
                continue

            try:
                v_max_knots = float(wind_val) if not pd.isna(wind_val) else 30.0
            except (TypeError, ValueError):
                v_max_knots = 30.0

            try:
                p_central_hpa = float(pres_val) if not pd.isna(pres_val) else 1000.0
            except (TypeError, ValueError):
                p_central_hpa = 1000.0

            # Calculate pressure deficit and IMD category
            delta_p = 1010.0 - p_central_hpa
            imd_cat = self.harmonizer.classify_intensity(v_max_knots)

            iso_ts = row["ISO_TIME"].strftime("%Y-%m-%dT%H:%M:%SZ")

            records.append({
                "cyclone_id": c_id,
                "timestamp": iso_ts,
                "center_lat": round(center_lat, 2),
                "center_lon": round(center_lon, 2),
                "v_max_knots": round(v_max_knots, 1),
                "p_central_hpa": round(p_central_hpa, 1),
                "delta_p_hpa": round(delta_p, 1),
                "imd_category": imd_cat
            })

        return records

    def export_harmonized_csv(self, records: List[Dict], output_path: Union[str, Path]) -> Path:
        """
        Exports records to a standardized CSV fully compatible with IMDTrackHarmonizer.
        """
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "cyclone_id", "timestamp", "center_lat", "center_lon",
            "v_max_knots", "p_central_hpa", "delta_p_hpa", "imd_category"
        ]

        with open(out_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in records:
                writer.writerow(r)

        print(f"Exported {len(records)} track records to {out_file}")
        return out_file

    def export_harmonized_parquet(self, records: List[Dict], output_path: Union[str, Path]) -> Path:
        """
        Exports records to Parquet format per Task 5 specification.
        """
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(records)
        df.to_parquet(out_file, index=False)
        print(f"Exported Parquet to {out_file}")
        return out_file

    def download_and_extract_benchmark_cyclones(
        self,
        cyclone_list: Optional[List[Dict]] = None,
        export_parquet: bool = True
    ) -> Dict[str, Path]:
        """
        One-click automated workflow:
        1. Downloads IBTrACS database.
        2. Filters all target benchmark cyclones (Amphan, Tauktae, Biparjoy, etc.).
        3. Exports standardized CSV and Parquet files into the besttrack directory.
        """
        cyclones = cyclone_list or BENCHMARK_CYCLONES
        df = self.load_ibtracs_data()

        generated_files = {}
        for storm in cyclones:
            name = storm["name"]
            season = storm.get("season")
            c_id = storm.get("id")

            records = self.filter_storm(df, storm_name=name, season=season, cyclone_id=c_id)
            if not records:
                continue

            csv_path = self.cache_dir / f"track_{name.lower()}_{season}.csv"
            self.export_harmonized_csv(records, csv_path)
            generated_files[name] = csv_path

            if export_parquet:
                parquet_path = self.cache_dir / f"track_{name.lower()}_{season}.parquet"
                self.export_harmonized_parquet(records, parquet_path)

        return generated_files


if __name__ == "__main__":
    downloader = HistoricalTrackDownloader()
    print("Running automated historical track downloader for benchmark cyclones...")
    results = downloader.download_and_extract_benchmark_cyclones()
    print(f"Generated {len(results)} historical best track files.")
