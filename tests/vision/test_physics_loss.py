import torch
import pytest
from vision.models.physics_loss import MishraGuptaPhysicsLoss

def test_valid_pressure_drop():
    loss_engine = MishraGuptaPhysicsLoss(lambda_physics=1.0, tolerance_hpa=5.0)
    v_true = torch.tensor([50.0, 100.0], dtype=torch.float32)
    v_pred = torch.tensor([50.0, 100.0], dtype=torch.float32)
    dp_pred = torch.tensor([12.3946, 49.5786], dtype=torch.float32)
    total_loss = loss_engine(v_pred, dp_pred, v_true)
    assert total_loss.item() < 1e-4

def test_hallucinated_pressure_drop():
    loss_engine = MishraGuptaPhysicsLoss(lambda_physics=1.0, tolerance_hpa=5.0)
    v_true = torch.tensor([30.0], dtype=torch.float32)
    v_pred = torch.tensor([30.0], dtype=torch.float32)
    dp_pred = torch.tensor([80.0], dtype=torch.float32)
    total_loss = loss_engine(v_pred, dp_pred, v_true)
    assert total_loss.item() > 70.0
    assert abs(total_loss.item() - 70.537) < 1e-2

def test_tolerance_threshold():
    loss_engine = MishraGuptaPhysicsLoss(lambda_physics=1.0, tolerance_hpa=5.0)
    v_true = torch.tensor([50.0], dtype=torch.float32)
    v_pred = torch.tensor([50.0], dtype=torch.float32)
    dp_pred = torch.tensor([16.0], dtype=torch.float32)
    total_loss = loss_engine(v_pred, dp_pred, v_true)
    assert total_loss.item() < 1e-4

def test_vectorized_gradient_flow():
    loss_engine = MishraGuptaPhysicsLoss()
    batch_size = 32
    v_true = torch.rand(batch_size, dtype=torch.float32) * 150
    v_pred = torch.nn.Parameter(v_true.clone() + torch.randn(batch_size))
    dp_pred = torch.nn.Parameter((v_pred / 14.2)**2 + torch.randn(batch_size) * 10)
    loss = loss_engine(v_pred, dp_pred, v_true)
    loss.backward()
    assert v_pred.grad is not None
    assert dp_pred.grad is not None
