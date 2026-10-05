"""
Satellite intensity estimate at run time (master plan v5, Task 2.3)
═══════════════════════════════════════════════════════════════════
Used by the live pipeline for every official system and satellite watch area:

    est = SatelliteIntensity.load()          # None if the models are missing or did not pass validation
    est.estimate(frame_u8, lat, lon, prev_u8, hours, month) → {"wind_kt", "band_kt", "imd_class", "eye"}

frame_u8 / prev_u8: (4, 512, 512) uint8 on the INSAT store grid (same as training; see build_unified_set).
The estimate is IMD 3-minute wind; band = 80% error range on unseen seasons (docs/intensity_report.md).
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from forecaster.intensity.features import refine_centre, sample_features
from forecaster.intensity.scale import CLASSES, imd_class

WEIGHTS = Path(__file__).resolve().parents[1] / "weights"


class SatelliteIntensity:
    def __init__(self):
        import lightgbm as lgb
        self.meta = json.loads((WEIGHTS / "intensity_meta.json").read_text(encoding="utf-8"))
        self.model = lgb.Booster(model_file=str(WEIGHTS / "intensity_gbm.txt"))
        g = WEIGHTS / "intensity_global_ir.txt"
        self.global_model = lgb.Booster(model_file=str(g)) if self.meta.get("global_features") and g.exists() else None

    @classmethod
    def load(cls):
        try:
            s = cls()
            return s if s.meta.get("approved") else None
        except Exception:  # noqa: BLE001
            return None

    def estimate(self, frame_u8, lat, lon, prev_u8=None, hours=None, month=None):
        f = sample_features(frame_u8, lat, lon, prev_u8, lat if prev_u8 is not None else None,
                            lon if prev_u8 is not None else None, hours,
                            extra={"month_sin": np.sin(2 * np.pi * (month or 6) / 12),
                                   "month_cos": np.cos(2 * np.pi * (month or 6) / 12),
                                   "arabian_sea": float(lon < 77.5 and lat > 5)})
        if f is None:
            return None
        row = pd.DataFrame([f])
        if self.global_model is not None:
            row["global_ir_kt"] = self.global_model.predict(row[self.meta["global_features"]])
        kt = float(max(15.0, self.model.predict(row[self.meta["features"]])[0]))
        _, _, score, eye = refine_centre(frame_u8, lat, lon)
        return {"wind_kt": round(kt, 1), "band_kt": self.meta.get("error_band_kt_80"),
                "imd_class": CLASSES[imd_class(kt)], "eye": bool(eye)}
