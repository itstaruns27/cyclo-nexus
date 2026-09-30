"""
CYCLO-NEXUS Data Pipeline Configuration
════════════════════════════════════════
Owner: Agent ALPHA
"""

# ── North Indian Ocean Bounding Box (EPSG:4326) ────────────────────
NIO_BOUNDS = {
    "lat_min": 0.0,     # °N
    "lat_max": 32.0,    # °N
    "lon_min": 50.0,    # °E
    "lon_max": 102.0,   # °E
}

# ── Grid Resolution ────────────────────────────────────────────────
GRID_RESOLUTION_DEG = 0.04          # 0.04° ≈ 4 km at equator
TARGET_CRS = "EPSG:4326"           # WGS84

# ── Tensor Specification ──────────────────────────────────────────
TENSOR_CHANNELS = 4                 # TIR-1, TIR-2, WV, Clean-IR/GPM
TENSOR_HEIGHT = 1024
TENSOR_WIDTH = 1024
TENSOR_DTYPE = "float32"

# ── Channel Ordering ─────────────────────────────────────────────
CHANNEL_MAP = {
    0: "INSAT-3D TIR-1 (10.8 µm)",
    1: "INSAT-3D TIR-2 (12.0 µm)",
    2: "INSAT-3D WV (6.9 µm)",
    3: "Himawari-8 Band 13 / GPM IMERG",
}

# ── Brightness Temperature Normalization ──────────────────────────
BT_MIN_K = 180.0    # Minimum brightness temperature (Kelvin)
BT_MAX_K = 320.0    # Maximum brightness temperature (Kelvin)

# ── Data Paths (Google Drive mount convention) ────────────────────
DRIVE_BASE = "/content/drive/MyDrive/cyclo-nexus"
RAW_DATA_DIR = f"{DRIVE_BASE}/data/raw"
PROCESSED_DATA_DIR = f"{DRIVE_BASE}/data/processed"
TENSOR_OUTPUT_DIR = f"{DRIVE_BASE}/data/tensors"
BESTTRACK_DIR = f"{DRIVE_BASE}/data/besttrack"
