"""
CYCLO-NEXUS Forecaster Configuration
═════════════════════════════════════
Owner: Agent CHARLIE
"""

# ── Temporal Sequence Parameters ─────────────────────────
SEQUENCE_LENGTH = 6           # Number of past timesteps
TIMESTEP_HOURS = 3            # 3-hour cadence
LOOKBACK_HOURS = 15           # t-15h to t0

# ── Forecast Horizons ───────────────────────────────────
FORECAST_HORIZONS = [6, 12, 24, 48, 72]  # Hours ahead

# ── Atkinson-Holliday Parameters ────────────────────────
AH_COEFFICIENT = 0.018
AH_EXPONENT = 1.5
P_ENV_DEFAULT = 1010.0        # Ambient pressure (hPa)
AH_TOLERANCE = 5.0            # Physics penalty tolerance (hPa)

# ── Loss Weights ────────────────────────────────────────
LOSS_ALPHA = 1.0              # Huber loss weight for V_max
LOSS_BETA = 0.5               # Atkinson-Holliday penalty weight
LOSS_TAU = 3.0                # Physics tolerance margin (hPa)

# ── Model Architecture ─────────────────────────────────
CONVLSTM_HIDDEN_DIM = 64
CONVLSTM_KERNEL_SIZE = 3
BIGRU_HIDDEN_DIM = 128
BIGRU_NUM_LAYERS = 2
DROPOUT = 0.2

# ── Data Paths (Google Drive) ──────────────────────────
DRIVE_BASE = "/content/drive/MyDrive/cyclo-nexus"
SEQUENCE_DATA_DIR = f"{DRIVE_BASE}/data/sequences"
MODEL_WEIGHTS_DIR = f"{DRIVE_BASE}/models/forecaster"
GRADCAM_OUTPUT_DIR = f"{DRIVE_BASE}/outputs/gradcam"
