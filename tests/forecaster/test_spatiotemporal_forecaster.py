"""
Task 11 Verification Harness: ConvLSTM + Bi-GRU Spatiotemporal Forecaster
══════════════════════════════════════════════════════════════════════════
Owner: Agent CHARLIE | Skill: [SKILL:SPATIOTEMPORAL_AI]

Verifies:
    1. CycloneForecaster correctly processes 5D sequential spatiotemporal tensors.
    2. Model outputs the required 3 heads: track_delta, v_max_pred, dp_pred.
    3. Output shapes: one value per lead time (multi-horizon) and the legacy single-horizon layout.
    4. Backpropagation gradient flow correctly routes through the Bi-GRU,
       ConvLSTM layers, Spatial Downsampling stem, all the way to the input tensor.
    5. load_forecaster detects the horizon count from a checkpoint.
"""

import torch
import pytest

from forecaster.models.spatiotemporal_forecaster import CycloneForecaster, load_forecaster


class TestSpatiotemporalForecaster:

    @pytest.fixture
    def mock_sequence(self):
        # Shape: (Batch, Seq, Channels, Height, Width)
        # Using 256x256 to prevent VRAM/RAM exhaustion during unit tests.
        return torch.randn(2, 3, 4, 256, 256, requires_grad=True)

    @pytest.fixture
    def model(self):
        return CycloneForecaster(in_channels=4, conv_hidden=16, gru_hidden=32)

    def test_forward_pass_outputs_and_shapes(self, model, mock_sequence):
        outputs = model(mock_sequence)

        assert "track_delta" in outputs
        assert "v_max_pred" in outputs
        assert "dp_pred" in outputs

        assert outputs["track_delta"].shape == (2, 5, 2), "Track delta must be (Batch, 5 horizons, 2)"
        assert outputs["v_max_pred"].shape == (2, 5), "V_max must be (Batch, 5 horizons)"
        assert outputs["dp_pred"].shape == (2, 5), "Pressure drop must be (Batch, 5 horizons)"

    def test_legacy_single_horizon_shapes(self, mock_sequence):
        legacy = CycloneForecaster(in_channels=4, conv_hidden=16, gru_hidden=32, n_horizons=1)
        outputs = legacy(mock_sequence)
        assert outputs["track_delta"].shape == (2, 2)
        assert outputs["v_max_pred"].shape == (2, 1)
        assert outputs["dp_pred"].shape == (2, 1)

    def test_gradient_flow(self, model, mock_sequence):
        outputs = model(mock_sequence)
        loss = (
            outputs["track_delta"].sum() +
            outputs["v_max_pred"].sum() +
            outputs["dp_pred"].sum()
        )
        loss.backward()

        assert mock_sequence.grad is not None, "Input tensor gradients are None; graph is detached."
        assert mock_sequence.grad.shape == (2, 3, 4, 256, 256)
        assert not (mock_sequence.grad == 0).all(), "Input tensor gradients are all zero."

    @pytest.mark.parametrize("n_horizons", [1, 5])
    def test_load_forecaster_detects_horizons(self, tmp_path, n_horizons):
        path = tmp_path / "f.pt"
        torch.save(CycloneForecaster(n_horizons=n_horizons).state_dict(), path)
        assert load_forecaster(path).n_horizons == n_horizons
