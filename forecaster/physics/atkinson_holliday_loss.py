"""
Task 12: Atkinson-Holliday Physics Residual Loss Engine
═══════════════════════════════════════════════════════
Penalises forecasts whose wind and pressure disagree with the empirical wind-pressure
relationship used by schemas/telemetry_contract.py (AtkinsonHollidayConstraint):

  expected ΔP = 0.018 · V_max_knots^1.5
  penalty     = β · mean( max(0, |ΔP_pred − expected ΔP| − τ) )

Units: v_max in knots (as live_pipeline_runner.forecast_points reads it), dp in hPa. Works for any shape
(e.g. (B, horizons)); negative winds are clamped to 0 before the power.
"""

import torch
import torch.nn as nn


class AtkinsonHollidayLoss(nn.Module):
    def __init__(self, beta: float = 0.1, tolerance_hpa: float = 5.0):
        super().__init__()
        self.beta = beta
        self.tolerance_hpa = tolerance_hpa

    def forward(self, v_max_kt: torch.Tensor, dp_hpa: torch.Tensor) -> torch.Tensor:
        v_knots = torch.clamp(v_max_kt, min=0.0)
        expected_dp = 0.018 * v_knots.pow(1.5)
        excess = torch.relu((dp_hpa - expected_dp).abs() - self.tolerance_hpa)
        return self.beta * excess.mean()


class MultiHorizonForecastLoss(nn.Module):
    """
    Supervised loss for the multi-horizon forecaster plus the physics penalty.
    Targets: track (B, H, 2) degrees, v_max (B, H) knots, dp (B, H) hPa; `mask` (B, H) is 1 where
    the best track still exists at that lead time (storms that dissipate early have fewer labels).
    Longer lead times are down-weighted because their targets are intrinsically noisier.
    """

    def __init__(self, horizon_weights=(1.0, 1.0, 0.8, 0.6, 0.5), beta: float = 0.1):
        super().__init__()
        self.register_buffer("hw", torch.tensor(horizon_weights))
        self.physics = AtkinsonHollidayLoss(beta=beta)

    def forward(self, pred: dict, target: dict, mask: torch.Tensor) -> dict:
        w = self.hw.to(mask.device) * mask
        denom = w.sum().clamp(min=1.0)
        track = (nn.functional.smooth_l1_loss(pred["track_delta"], target["track"], reduction="none").sum(-1) * w).sum() / denom
        wind = (nn.functional.smooth_l1_loss(pred["v_max_pred"] / 30, target["v_max"] / 30, reduction="none") * w).sum() / denom
        dp = (nn.functional.smooth_l1_loss(pred["dp_pred"] / 20, target["dp"] / 20, reduction="none") * w).sum() / denom
        physics = self.physics(pred["v_max_pred"], pred["dp_pred"])
        return {"total": track + wind + dp + physics, "track": track, "wind": wind, "dp": dp, "physics": physics}
