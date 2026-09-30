import torch

from forecaster.physics.atkinson_holliday_loss import AtkinsonHollidayLoss, MultiHorizonForecastLoss


def test_consistent_prediction_has_zero_penalty():
    v = torch.tensor([[55.0, 90.0]])
    dp = 0.018 * v.pow(1.5)
    assert AtkinsonHollidayLoss()(v, dp).item() == 0.0


def test_inconsistent_prediction_is_penalised_beyond_tolerance():
    v = torch.tensor([150.0])
    expected = 0.018 * 150.0 ** 1.5
    loss = AtkinsonHollidayLoss(beta=1.0, tolerance_hpa=5.0)(v, torch.tensor([expected + 15.0]))
    assert abs(loss.item() - 10.0) < 1e-3


def test_multi_horizon_loss_respects_mask_and_backprops():
    B, H = 2, 5
    pred = {"track_delta": torch.randn(B, H, 2, requires_grad=True),
            "v_max_pred": torch.rand(B, H, requires_grad=True) * 100,
            "dp_pred": torch.rand(B, H, requires_grad=True) * 30}
    target = {"track": torch.randn(B, H, 2), "v_max": torch.rand(B, H) * 100, "dp": torch.rand(B, H) * 30}
    mask = torch.ones(B, H)
    mask[:, 3:] = 0  # storm dissipated before 48 h
    out = MultiHorizonForecastLoss()(pred, target, mask)
    out["total"].backward()
    assert torch.isfinite(out["total"])
    # Masked lead times get no track gradient
    assert (pred["track_delta"].grad[:, 3:] == 0).all()
