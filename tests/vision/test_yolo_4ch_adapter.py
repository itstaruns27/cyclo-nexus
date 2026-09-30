"""
Task 7 Verification Harness: 4-Channel YOLO Weight Surgery
═══════════════════════════════════════════════════════════
Owner: Agent BRAVO | Skill: [SKILL:YOLO_OBB_CV] + [SKILL:PYTORCH_SURGERY]

Verifies:
    1. Adapted layer has in_channels=4, all other params unchanged.
    2. First 3 channels of new weights are exact copies of the original.
    3. 4th channel weights equal the mean of channels 0–2.
    4. Bias tensor is copied verbatim.
    5. Forward pass with (1, 4, 1024, 1024) produces (1, 64, 512, 512).
    6. Error handling for invalid inputs.
    7. Gradient flow through the adapted layer.
"""

import torch
import torch.nn as nn
import pytest

from vision.models.yolo_4ch_adapter import YOLO4ChannelSurgery, ChannelAdaptationError


@pytest.fixture
def surgeon():
    return YOLO4ChannelSurgery()


@pytest.fixture
def original_conv():
    """Mock a typical YOLO backbone first layer: Conv2d(3→64, k=3, s=2, p=1)."""
    conv = nn.Conv2d(
        in_channels=3, out_channels=64,
        kernel_size=3, stride=2, padding=1, bias=True,
    )
    # Seed deterministic weights for reproducible assertions
    torch.manual_seed(42)
    nn.init.kaiming_normal_(conv.weight)
    nn.init.zeros_(conv.bias)
    return conv


@pytest.fixture
def original_conv_no_bias():
    """YOLO variant without bias (BatchNorm fused)."""
    conv = nn.Conv2d(
        in_channels=3, out_channels=32,
        kernel_size=6, stride=2, padding=2, bias=False,
    )
    torch.manual_seed(99)
    nn.init.kaiming_normal_(conv.weight)
    return conv


# ── 1. Layer Configuration Preservation ─────────────────────────────────

class TestLayerConfiguration:
    """Verify the adapted Conv2d preserves all original params except in_channels."""

    def test_in_channels_is_4(self, surgeon, original_conv):
        new_conv = surgeon.adapt_first_conv_layer(original_conv)
        assert new_conv.in_channels == 4

    def test_out_channels_preserved(self, surgeon, original_conv):
        new_conv = surgeon.adapt_first_conv_layer(original_conv)
        assert new_conv.out_channels == original_conv.out_channels == 64

    def test_kernel_size_preserved(self, surgeon, original_conv):
        new_conv = surgeon.adapt_first_conv_layer(original_conv)
        assert new_conv.kernel_size == original_conv.kernel_size

    def test_stride_preserved(self, surgeon, original_conv):
        new_conv = surgeon.adapt_first_conv_layer(original_conv)
        assert new_conv.stride == original_conv.stride

    def test_padding_preserved(self, surgeon, original_conv):
        new_conv = surgeon.adapt_first_conv_layer(original_conv)
        assert new_conv.padding == original_conv.padding

    def test_weight_shape(self, surgeon, original_conv):
        new_conv = surgeon.adapt_first_conv_layer(original_conv)
        assert new_conv.weight.shape == (64, 4, 3, 3)


# ── 2. Weight Transplant Fidelity ──────────────────────────────────────

class TestWeightTransplant:
    """Verify exact weight copy for channels 0–2 and mean-init for channel 3."""

    def test_first_3_channels_exact_copy(self, surgeon, original_conv):
        original_weights = original_conv.weight.data.clone()
        new_conv = surgeon.adapt_first_conv_layer(original_conv)

        # Channels 0, 1, 2 of the new layer must be bit-identical to the original
        assert torch.equal(
            new_conv.weight.data[:, :3, :, :],
            original_weights
        ), "First 3 channels must be exact copies of original weights"

    def test_4th_channel_is_mean_of_first_3(self, surgeon, original_conv):
        original_weights = original_conv.weight.data.clone()
        new_conv = surgeon.adapt_first_conv_layer(original_conv)

        expected_ch4 = torch.mean(original_weights[:, :3, :, :], dim=1, keepdim=True)
        actual_ch4 = new_conv.weight.data[:, 3:4, :, :]

        assert torch.allclose(actual_ch4, expected_ch4, atol=1e-7), (
            "4th channel weights must equal the mean of channels 0–2"
        )

    def test_bias_copied_verbatim(self, surgeon, original_conv):
        original_bias = original_conv.bias.data.clone()
        new_conv = surgeon.adapt_first_conv_layer(original_conv)

        assert new_conv.bias is not None, "Bias should exist"
        assert torch.equal(new_conv.bias.data, original_bias), (
            "Bias tensor must be an identical copy"
        )

    def test_no_bias_layer(self, surgeon, original_conv_no_bias):
        """Layer without bias should produce adapted layer also without bias."""
        new_conv = surgeon.adapt_first_conv_layer(original_conv_no_bias)
        assert new_conv.bias is None, "Adapted layer should have no bias"
        assert new_conv.in_channels == 4
        assert new_conv.out_channels == 32


# ── 3. Forward Pass Verification ───────────────────────────────────────

class TestForwardPass:
    """Verify the adapted layer processes 4-channel tensors at expected spatial dims."""

    def test_1024x1024_input(self, surgeon, original_conv):
        """Full-resolution satellite tensor: (1, 4, 1024, 1024) → (1, 64, 512, 512)."""
        new_conv = surgeon.adapt_first_conv_layer(original_conv)
        mock_tensor = torch.randn(1, 4, 1024, 1024)

        with torch.no_grad():
            output = new_conv(mock_tensor)

        assert output.shape == (1, 64, 512, 512), (
            f"Expected (1, 64, 512, 512), got {output.shape}"
        )

    def test_batch_input(self, surgeon, original_conv):
        """Batch of 4 tensors at reduced resolution."""
        new_conv = surgeon.adapt_first_conv_layer(original_conv)
        mock_tensor = torch.randn(4, 4, 256, 256)

        with torch.no_grad():
            output = new_conv(mock_tensor)

        assert output.shape == (4, 64, 128, 128), (
            f"Expected (4, 64, 128, 128), got {output.shape}"
        )

    def test_output_is_finite(self, surgeon, original_conv):
        """No NaN or Inf values in the output (gradient scale preservation)."""
        new_conv = surgeon.adapt_first_conv_layer(original_conv)
        mock_tensor = torch.randn(1, 4, 64, 64)

        with torch.no_grad():
            output = new_conv(mock_tensor)

        assert torch.isfinite(output).all(), "Output contains NaN or Inf values"


# ── 4. Gradient Flow ──────────────────────────────────────────────────

class TestGradientFlow:
    """Verify backpropagation works through the adapted layer."""

    def test_gradients_flow_to_all_4_channels(self, surgeon, original_conv):
        new_conv = surgeon.adapt_first_conv_layer(original_conv)
        mock_tensor = torch.randn(1, 4, 64, 64, requires_grad=True)

        output = new_conv(mock_tensor)
        loss = output.sum()
        loss.backward()

        # Weight gradients must exist for all 4 input channels
        assert new_conv.weight.grad is not None, "No gradient on weight tensor"
        assert new_conv.weight.grad.shape == (64, 4, 3, 3)

        # Input gradient must flow back to all 4 channels
        assert mock_tensor.grad is not None, "No gradient on input tensor"
        assert mock_tensor.grad.shape == (1, 4, 64, 64)


# ── 5. Error Handling ──────────────────────────────────────────────────

class TestErrorHandling:
    """Verify surgery rejects invalid inputs."""

    def test_non_conv2d_raises(self, surgeon):
        with pytest.raises(ChannelAdaptationError, match="Expected nn.Conv2d"):
            surgeon.adapt_first_conv_layer(nn.Linear(3, 64))

    def test_wrong_in_channels_raises(self, surgeon):
        """A Conv2d already at 4 channels should be rejected."""
        already_4ch = nn.Conv2d(4, 64, kernel_size=3)
        with pytest.raises(ChannelAdaptationError, match="in_channels=3"):
            surgeon.adapt_first_conv_layer(already_4ch)

    def test_1_channel_raises(self, surgeon):
        """Single-channel grayscale conv should be rejected."""
        gray_conv = nn.Conv2d(1, 32, kernel_size=3)
        with pytest.raises(ChannelAdaptationError, match="in_channels=3"):
            surgeon.adapt_first_conv_layer(gray_conv)
