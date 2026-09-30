"""
Task 13: Grad-CAM Visual Explainability Engine
══════════════════════════════════════════════
Owner: Agent CHARLIE | Skill: [SKILL:XAI_EXPLAINABILITY]

Natively wraps PyTorch architectures with forward/backward hooks
to generate Grad-CAM heatmaps. Identifies which spatial regions
most strongly influenced the network's final trajectory prediction.
"""

import torch
import torch.nn.functional as F
import numpy as np


class CycloneGradCAM:
    """
    Grad-CAM Generator for Cyclone Forecaster models.
    """
    def __init__(self, model: torch.nn.Module, target_layer: torch.nn.Module, output_key: str = "track_delta"):
        """
        Args:
            model: The complete PyTorch model.
            target_layer: The specific nn.Conv2d layer to attach hooks to (usually the final conv layer).
            output_key: The dictionary key to extract from the model's output if it returns a dictionary.
        """
        self.model = model
        self.target_layer = target_layer
        self.output_key = output_key
        
        self.activations = None
        self.gradients = None
        
        # Register hooks
        self.target_layer.register_forward_hook(self.save_activation)
        self.target_layer.register_full_backward_hook(self.save_gradient)
        
    def save_activation(self, module: torch.nn.Module, input_tensor: tuple, output_tensor: torch.Tensor):
        """Forward hook to capture spatial activation maps."""
        self.activations = output_tensor
        
    def save_gradient(self, module: torch.nn.Module, grad_input: tuple, grad_output: tuple):
        """Backward hook to capture gradients flowing back from the prediction."""
        # grad_output[0] is the gradient w.r.t the output of this layer
        self.gradients = grad_output[0]
        
    def generate_heatmap(self, input_tensor: torch.Tensor, target_index: int = 0, target_size: tuple[int, int] = (1024, 1024)) -> np.ndarray:
        """
        Executes a forward and backward pass to generate the Grad-CAM heatmap.
        
        Args:
            input_tensor: Raw input tensor to the model.
            target_index: Which specific output index to explain (e.g., 0 for dx, 1 for dy).
            target_size: The desired (H, W) of the final heatmap to overlay on the map.
            
        Returns:
            2D numpy array representing the normalized heatmap in [0.0, 1.0].
        """
        self.model.eval()
        
        # Reset states
        self.activations = None
        self.gradients = None
        
        # 1. Forward Pass
        output = self.model(input_tensor)
        
        # Extract target output
        if isinstance(output, dict):
            target_output = output.get(self.output_key)
            if target_output is None:
                raise ValueError(f"Output key '{self.output_key}' not found in model output dictionary.")
        else:
            target_output = output
            
        # Isolate the specific prediction neuron
        if target_output.dim() > 1:
            score = target_output[:, target_index].sum()
        else:
            score = target_output.sum()
            
        # 2. Backward Pass
        self.model.zero_grad()
        score.backward(retain_graph=True)
        
        if self.activations is None or self.gradients is None:
            raise RuntimeError("Hooks failed to capture activations/gradients. Ensure the target layer is executed during the forward pass.")
            
        # 3. Heatmap Generation Logic
        # Global Average Pooling of gradients to obtain neuron importance weights
        # gradients shape: (Batch, Channels, Height, Width)
        weights = torch.mean(self.gradients, dim=(2, 3), keepdim=True)
        
        # Multiply captured forward activations by these weights
        cam = torch.sum(weights * self.activations, dim=1, keepdim=True)
        
        # Apply ReLU to keep only features that positively influence the prediction
        cam = F.relu(cam)
        
        # 4. Matrix Interpolation
        # Upsample small spatial footprint back to the target spatial dimension
        cam_resized = F.interpolate(cam, size=target_size, mode='bilinear', align_corners=False)
        
        # Average across the batch/sequence dimension to produce a single aggregated spatial heatmap
        cam_mean = torch.mean(cam_resized, dim=0, keepdim=False).squeeze(0)
        
        cam_np = cam_mean.detach().cpu().numpy()
        
        # Normalize to [0.0, 1.0]
        cam_min = cam_np.min()
        cam_max = cam_np.max()
        
        if cam_max - cam_min > 1e-8:
            cam_np = (cam_np - cam_min) / (cam_max - cam_min)
        else:
            cam_np = np.zeros_like(cam_np)
            
        return cam_np
