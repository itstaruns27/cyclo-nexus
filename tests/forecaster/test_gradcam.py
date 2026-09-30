"""
Task 13 Verification Harness: Grad-CAM Visual Explainability Engine
═══════════════════════════════════════════════════════════════════
Owner: Agent CHARLIE | Skill: [SKILL:XAI_EXPLAINABILITY]

Verifies:
    1. CycloneGradCAM correctly hooks into a standard PyTorch Conv2d module.
    2. The generated heatmap is successfully interpolated to the target spatial size.
    3. The heatmap is strictly bounded and normalized between [0.0, 1.0].
    4. Explanations successfully map gradients back to the original input tensor without crashing.
"""

import torch
import torch.nn as nn
import numpy as np
import pytest

from forecaster.models.gradcam_generator import CycloneGradCAM


class MockCNN(nn.Module):
    """
    A lightweight mock CNN to simulate the forecaster's downsampling stem
    and prediction head without introducing complex test dependencies.
    """
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Conv2d(4, 16, kernel_size=3, padding=1)
        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, padding=1)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Linear(32, 2)
        
    def forward(self, x):
        x = torch.relu(self.conv1(x))
        x = torch.relu(self.conv2(x))
        x = self.pool(x)
        x = x.view(x.size(0), -1)
        out = self.fc(x)
        return {"track_delta": out}


class TestGradCAMEngine:
    
    @pytest.fixture
    def mock_model(self):
        return MockCNN()
        
    @pytest.fixture
    def mock_tensor(self):
        # Shape: (Batch=1, Channels=4, Height=64, Width=64)
        return torch.randn(1, 4, 64, 64, requires_grad=True)

    def test_heatmap_generation_and_normalization(self, mock_model, mock_tensor):
        """
        Ensures the Grad-CAM generator produces a valid 2D NumPy array,
        interpolated to 1024x1024, and strictly bounded [0.0, 1.0].
        """
        # Attach GradCAM to the final convolutional layer
        gradcam = CycloneGradCAM(
            model=mock_model, 
            target_layer=mock_model.conv2, 
            output_key="track_delta"
        )
        
        # Target index 0 (e.g., dx offset)
        heatmap = gradcam.generate_heatmap(
            input_tensor=mock_tensor, 
            target_index=0, 
            target_size=(1024, 1024)
        )
        
        # Verify basic types and shapes
        assert isinstance(heatmap, np.ndarray), "Heatmap must be a NumPy array."
        assert heatmap.shape == (1024, 1024), "Heatmap failed to interpolate to target size."
        
        # Verify strict normalization bounds
        assert heatmap.min() >= 0.0, f"Heatmap min is below 0.0: {heatmap.min()}"
        assert heatmap.max() <= 1.0, f"Heatmap max is above 1.0: {heatmap.max()}"
        
    def test_invalid_output_key_raises(self, mock_model, mock_tensor):
        """
        Ensures generator fails gracefully if output_key is incorrect.
        """
        gradcam = CycloneGradCAM(
            model=mock_model, 
            target_layer=mock_model.conv2, 
            output_key="non_existent_key"
        )
        
        with pytest.raises(ValueError, match="not found in model output dictionary"):
            gradcam.generate_heatmap(mock_tensor, target_index=0)
