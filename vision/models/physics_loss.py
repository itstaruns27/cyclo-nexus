import torch
import torch.nn as nn
import torch.nn.functional as F

class MishraGuptaPhysicsLoss(nn.Module):
    """
    Enforces the Mishra and Gupta (1976) empirical wind-pressure relationship
    for the North Indian Ocean (Bay of Bengal & Arabian Sea).
    
    Thermodynamic Formula: V_max = 14.2 * sqrt(P_env - P_c)
    Penalty Activation: |Delta P_pred - (V_pred / 14.2)^2| > tau
    """
    def __init__(self, lambda_physics: float = 1.0, tolerance_hpa: float = 5.0):
        super(MishraGuptaPhysicsLoss, self).__init__()
        self.lambda_physics = lambda_physics
        self.tolerance_hpa = tolerance_hpa
        self.mse_loss = nn.MSELoss()

    def forward(self, v_pred: torch.Tensor, dp_pred: torch.Tensor, v_true: torch.Tensor) -> torch.Tensor:
        """
        Computes the total loss composite including the physical penalty bounds.
        """
        loss_mse = self.mse_loss(v_pred, v_true)
        dp_expected = (v_pred / 14.2) ** 2
        dp_deviation = torch.abs(dp_pred - dp_expected)
        physics_penalty = F.relu(dp_deviation - self.tolerance_hpa)
        loss_physics = torch.mean(physics_penalty)
        loss_total = loss_mse + (self.lambda_physics * loss_physics)
        return loss_total
