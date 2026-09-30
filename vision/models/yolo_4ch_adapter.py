"""
Task 7: 4-Channel YOLO Architecture Adaptation (Weight Surgery)
═══════════════════════════════════════════════════════════════
Owner: Agent BRAVO | Skill: [SKILL:YOLO_OBB_CV] + [SKILL:PYTORCH_SURGERY]

Adapts the first convolutional layer of any pre-trained YOLO backbone from
3-channel RGB input to 4-channel multi-spectral satellite input (TIR-1, WV,
Split-Window, GPM) without destroying learned ImageNet feature kernels.

Weight Surgery Protocol:
    1. Clone the original Conv2d configuration (out_channels, kernel_size,
       stride, padding, groups, dilation, bias).
    2. Create a new Conv2d with in_channels=4.
    3. Copy the pre-trained weights from channels 0–2 verbatim.
    4. Initialize channel 3 (precipitation) as the mean of channels 0–2.
       This preserves gradient scale and avoids training instability.
    5. Copy bias tensor unchanged (bias is per-output-channel, not per-input).

This module is deliberately decoupled from the Ultralytics package — it
operates on standard PyTorch nn.Conv2d layers for testability and portability.
"""

import torch
import torch.nn as nn


class ChannelAdaptationError(Exception):
    """Raised when the source convolution has an unexpected configuration."""
    pass


class YOLO4ChannelSurgery:
    """
    Performs deterministic weight surgery to extend a 3-channel Conv2d
    layer to accept 4-channel multi-spectral satellite tensors.

    Usage:
        surgeon = YOLO4ChannelSurgery()
        new_conv = surgeon.adapt_first_conv_layer(model.backbone[0].conv)
        model.backbone[0].conv = new_conv
    """

    TARGET_IN_CHANNELS: int = 4
    SOURCE_IN_CHANNELS: int = 3

    def adapt_first_conv_layer(self, original_conv: nn.Conv2d) -> nn.Conv2d:
        """
        Creates a new Conv2d(in_channels=4) with surgically transplanted
        weights from the original Conv2d(in_channels=3).

        Args:
            original_conv: The pre-trained first convolutional layer with
                           in_channels=3. Must be a standard nn.Conv2d.

        Returns:
            A new nn.Conv2d with in_channels=4, where:
                - Channels 0–2: Exact copies of the original weights.
                - Channel 3: Mean of channels 0–2 (gradient-safe init).
                - Bias: Copied verbatim if present.

        Raises:
            ChannelAdaptationError: If original_conv.in_channels != 3 or
                                    the layer is not a standard Conv2d.
        """
        if not isinstance(original_conv, nn.Conv2d):
            raise ChannelAdaptationError(
                f"Expected nn.Conv2d, got {type(original_conv).__name__}"
            )

        if original_conv.in_channels != self.SOURCE_IN_CHANNELS:
            raise ChannelAdaptationError(
                f"Expected in_channels={self.SOURCE_IN_CHANNELS}, "
                f"got in_channels={original_conv.in_channels}. "
                f"Weight surgery only applies to the first 3-channel conv layer."
            )

        # ── 1. Replicate the exact Conv2d configuration ─────────────────
        has_bias = original_conv.bias is not None

        new_conv = nn.Conv2d(
            in_channels=self.TARGET_IN_CHANNELS,
            out_channels=original_conv.out_channels,
            kernel_size=original_conv.kernel_size,
            stride=original_conv.stride,
            padding=original_conv.padding,
            dilation=original_conv.dilation,
            groups=original_conv.groups,
            bias=has_bias,
            padding_mode=original_conv.padding_mode,
        )

        # ── 2. Perform the weight transplant ────────────────────────────
        with torch.no_grad():
            original_weights = original_conv.weight.data
            # Shape: (out_channels, 3, kH, kW)

            # Construct the 4th channel as the mean of the first 3
            ch4_weights = torch.mean(
                original_weights[:, :self.SOURCE_IN_CHANNELS, :, :],
                dim=1,
                keepdim=True,
            )
            # Shape: (out_channels, 1, kH, kW)

            # Concatenate: [ch0, ch1, ch2, mean(ch0:ch2)]
            new_weights = torch.cat(
                [original_weights, ch4_weights],
                dim=1,
            )
            # Shape: (out_channels, 4, kH, kW)

            new_conv.weight.data.copy_(new_weights)

            # ── 3. Copy bias verbatim ───────────────────────────────────
            if has_bias:
                new_conv.bias.data.copy_(original_conv.bias.data)

        return new_conv
