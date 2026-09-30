import os
import time
import shutil
from pathlib import Path
from datetime import datetime
import re

class LiveSimulationSpooler:
    """
    Hackathon-Ready Spooler: Simulates a live satellite feed by chronologically 
    copying historical files into an active ingestion directory at a fixed interval.
    
    This ensures the TemporalMatrixBuilder and the rest of the AI pipeline 
    receive uninterrupted, perfectly sequenced data during a live presentation,
    guarding against upstream API downtime.
    """
    def __init__(self, source_dir: str, active_dir: str, interval_seconds: int = 5):
        self.source_dir = Path(source_dir)
        self.active_dir = Path(active_dir)
        self.interval_seconds = interval_seconds
        
        self.active_dir.mkdir(parents=True, exist_ok=True)

    def extract_timestamp(self, filepath: Path) -> datetime:
        """Extracts timestamp from standardized filenames (e.g., INSAT3D_L1C_20240524_120000.npy)."""
        match = re.search(r'(\d{8})_(\d{6})', filepath.name)
        if not match:
            # Fallback to file modification time if regex fails
            return datetime.fromtimestamp(filepath.stat().st_mtime)
        date_str, time_str = match.groups()
        return datetime.strptime(f"{date_str}{time_str}", "%Y%m%d%H%M%S")

    def run_spooler(self) -> None:
        """Sorts files chronologically and spools them into the active directory."""
        # Support both numpy tensors and raw hdf5 satellite granules
        files = list(self.source_dir.glob("*.npy")) + list(self.source_dir.glob("*.h5"))
        if not files:
            print(f"No historical files found in {self.source_dir}")
            return
            
        # Sort chronologically to preserve the strict 30-min deltas required by the forecaster
        sorted_files = sorted(files, key=self.extract_timestamp)
        
        print(f"Spooling {len(sorted_files)} files to {self.active_dir} every {self.interval_seconds}s...")
        
        for file_path in sorted_files:
            target_path = self.active_dir / file_path.name
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Injecting: {file_path.name}")
            shutil.copy2(file_path, target_path)
            time.sleep(self.interval_seconds)
            
        print("Live simulation complete.")

if __name__ == "__main__":
    # Standalone execution entry point for hackathon demo runs
    spooler = LiveSimulationSpooler(
        source_dir="data/historical_archive",
        active_dir="data/active_ingest",
        interval_seconds=10
    )
    spooler.run_spooler()
