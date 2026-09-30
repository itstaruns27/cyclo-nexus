"""
Task 8 Verification Harness: Physics-Aware Augmentation
════════════════════════════════════════════════════════
Owner: Agent BRAVO | Skill: [SKILL:YOLO_OBB_CV]

Verifies:
    1. Tensor rotation respects the 4-channel shape and edge padding.
    2. OBB label coordinates map correctly (e.g. 90-degree prompt requirement).
    3. Theta bounds are strictly wrapped to [-pi/2, pi/2).
    4. Width and height are swapped upon crossing 90-degree boundaries.
"""

import math
import torch
import pytest

from vision.preprocessing.physics_aware_augment import PhysicsAwareAugmenter


@pytest.fixture
def augmenter():
    return PhysicsAwareAugmenter()


class TestLabelRotation:
    def test_90_degree_prompt_example(self, augmenter):
        """
        Prompt requirement: 
        Pass a mock tensor and label (0, 0.75, 0.5, 0.2, 0.1, 0.0) into a 90-degree rotation.
        Assert x_c, y_c correctly map to (0.5, 0.75).
        Assert theta correctly wraps, and width and height swap if a 90-degree threshold is crossed.
        """
        label = (0, 0.75, 0.5, 0.2, 0.1, 0.0)
        angle_degrees = 90.0
        
        new_label = augmenter.rotate_obb_label(label, angle_degrees)
        class_id, x_c, y_c, w, h, theta = new_label
        
        # 1. Assert x_c, y_c correctly map to (0.5, 0.75)
        assert abs(x_c - 0.5) < 1e-6, f"Expected x_c=0.5, got {x_c}"
        assert abs(y_c - 0.75) < 1e-6, f"Expected y_c=0.75, got {y_c}"
        
        # 2. Assert theta correctly wraps 
        # (0.0 + 90 deg = 90 deg -> wraps to 0.0)
        assert abs(theta - 0.0) < 1e-6, f"Expected theta=0.0 (wrapped), got {theta}"
        
        # 3. Assert width and height swap
        # Original w=0.2, h=0.1. Swapped w=0.1, h=0.2.
        assert abs(w - 0.1) < 1e-6, f"Expected w=0.1, got {w}"
        assert abs(h - 0.2) < 1e-6, f"Expected h=0.2, got {h}"

    def test_minus_90_degree_rotation(self, augmenter):
        """
        Testing -90 degree rotation to ensure bound wrapping behaves consistently.
        """
        label = (0, 0.75, 0.5, 0.2, 0.1, 0.0)
        angle_degrees = -90.0
        
        new_label = augmenter.rotate_obb_label(label, angle_degrees)
        class_id, x_c, y_c, w, h, theta = new_label
        
        # -90 deg maps (0.75, 0.5) -> (0.5, 0.25)
        assert abs(x_c - 0.5) < 1e-6
        assert abs(y_c - 0.25) < 1e-6
        
        # -90 deg = -pi/2. It is INCLUSIVE in YOLO-OBB bounds [-pi/2, pi/2).
        # So it does not wrap, and w/h do NOT swap.
        assert abs(theta - (-math.pi / 2)) < 1e-6
        assert abs(w - 0.2) < 1e-6
        assert abs(h - 0.1) < 1e-6

    def test_180_degree_rotation(self, augmenter):
        """
        180 degree rotation crosses 90 degree threshold twice.
        w, h should swap twice (remain the same).
        theta should wrap into bounds.
        """
        label = (0, 0.75, 0.5, 0.2, 0.1, 0.1) # theta = 0.1 rad
        angle_degrees = 180.0
        
        new_label = augmenter.rotate_obb_label(label, angle_degrees)
        class_id, x_c, y_c, w, h, theta = new_label
        
        # 180 deg maps (0.75, 0.5) -> (0.25, 0.5)
        assert abs(x_c - 0.25) < 1e-6
        assert abs(y_c - 0.5) < 1e-6
        
        # theta = 0.1 + pi = 3.2415
        # crosses pi/2 twice -> 3.2415 - pi = 0.1
        assert abs(theta - 0.1) < 1e-6
        
        # w and h swapped twice
        assert abs(w - 0.2) < 1e-6
        assert abs(h - 0.1) < 1e-6


class TestTensorRotation:
    def test_tensor_rotation_shape_and_padding(self, augmenter):
        """
        Assert the tensor shape remains (4, 1024, 1024) without crashing.
        """
        mock_tensor = torch.ones(4, 1024, 1024) # Fill with 1s
        angle_degrees = 90.0
        
        rotated = augmenter.rotate_tensor(mock_tensor, angle_degrees)
        
        assert rotated.shape == (4, 1024, 1024), f"Expected shape (4, 1024, 1024), got {rotated.shape}"
        
        # At 90 degrees, corners are padded with 0.0
        # (Since rotation of a square by 90 degrees perfectly aligns, actually there is no padding at 90!
        # But if we rotate by 45 degrees, there will be padding.)
        rotated_45 = augmenter.rotate_tensor(mock_tensor, 45.0)
        assert rotated_45.shape == (4, 1024, 1024)
        
        # Check a corner for padding
        assert rotated_45[0, 0, 0].item() == 0.0, "Expected padded corner to be 0.0"

    def test_random_transform(self, augmenter):
        """
        Integration test for the random transform method.
        """
        mock_tensor = torch.randn(4, 1024, 1024)
        mock_label = (1, 0.5, 0.5, 0.1, 0.1, 0.0)
        
        new_tensor, new_label = augmenter.random_transform(mock_tensor, mock_label)
        
        assert new_tensor.shape == (4, 1024, 1024)
        assert len(new_label) == 6
        assert -math.pi / 2 <= new_label[5] < math.pi / 2
