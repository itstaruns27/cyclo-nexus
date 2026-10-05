"""
Satellite intensity estimate at run time (master plan v5, Task 2.3)
═══════════════════════════════════════════════════════════════════
Used by the live pipeline for every official system and satellite watch area:

    est = SatelliteIntensity.load()          # None if the models are missing or did not pass validation
    est.estimate(frame_u8, lat, lon, prev_u8, hours, month) → {"wind_kt", "band_kt", "imd_class", "eye"}

frame_u8 / prev_u8: (4, 512, 512) uint8 on the INSAT store grid (same as training; see build_unified_set).
The deployed variant (LightGBM, linear or quantile-mapped global / CNN estimate) is whatever
forecaster/intensity/train.py chose on unseen seasons; see docs/intensity_report.md.
The estimate is IMD 3-minute wind; band = 80% error range on unseen seasons.
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
        self.deploy = self.meta.get("deploy", {"kind": "gbm"})
        uses = set(self.meta.get("uses") or [])
        self.model = lgb.Booster(model_file=str(WEIGHTS / "intensity_gbm.txt")) if self.deploy["kind"] == "gbm" else None
        self.global_model = (lgb.Booster(model_file=str(WEIGHTS / "intensity_global_ir.txt"))
                             if uses & {"global_ir_kt", "blend_kt"} else None)
        self.cnn = None
        if uses & {"cnn_kt", "blend_kt"}:
            import torch
            from forecaster.intensity.cnn import Net
            ck = torch.load(WEIGHTS / "intensity_cnn.pt", map_location="cpu")
            self.cnn = Net()
            self.cnn.load_state_dict(ck["state"])
            self.cnn.eval()

    @classmethod
    def load(cls):
        try:
            s = cls()
            return s if s.meta.get("approved") else None
        except Exception:  # noqa: BLE001
            return None

    def _cnn_kt(self, frame_u8, lat, lon):
        from forecaster.intensity.cnn import insat_crop, predict
        return float(predict(self.cnn, insat_crop(frame_u8, lat, lon)[None], device="cpu")[0])

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
        if self.cnn is not None:
            row["cnn_kt"] = self._cnn_kt(frame_u8, lat, lon)
        if "global_ir_kt" in row and "cnn_kt" in row:
            row["blend_kt"] = 0.5 * row["cnn_kt"] + 0.5 * row["global_ir_kt"]
        d = self.deploy
        if d["kind"] == "gbm":
            kt = float(self.model.predict(row[self.meta["features"]])[0])
        elif d["kind"] == "linear":
            x = [row[c].fillna(v).iloc[0] for c, v in zip(d["cols"], d["fill"])]
            kt = float(d["coef"][0] + np.dot(d["coef"][1:], x))
        else:
            kt = float(np.interp(row[d["col"]].iloc[0], d["src"], d["dst"]))
        kt = max(15.0, kt)
        _, _, _, eye = refine_centre(frame_u8, lat, lon)
        out = {"wind_kt": round(kt, 1), "band_kt": self.meta.get("error_band_kt_80"),
               "imd_class": CLASSES[imd_class(kt)], "eye": bool(eye)}
        if self.cnn is not None:
            try:
                import base64
                from forecaster.intensity.cnn import insat_crop
                from forecaster.intensity.explain import heatmap_jpeg
                jpg = heatmap_jpeg(self.cnn, insat_crop(frame_u8, lat, lon))
                out["heatmap"] = "data:image/jpeg;base64," + base64.b64encode(jpg).decode()
            except Exception:  # noqa: BLE001 — the explanation never blocks the estimate
                pass
        return out
