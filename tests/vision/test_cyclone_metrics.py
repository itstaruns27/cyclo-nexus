"""
Task 9 Verification Harness: IMD Classification & Eye Diameter Metrics
══════════════════════════════════════════════════════════════════════
Owner: Agent BRAVO | Skill: [SKILL:YOLO_OBB_CV]

Verifies:
    1. Class ID 4 maps correctly to VSCS.
    2. Invalid class ID raises ValueError.
    3. Eye Estimator for class ID 1 returns 0.0.
    4. Eye Estimator for class ID 5 with width=0.1, height=0.15 calculates correct km.
"""

import pytest

from vision.models.cyclone_metrics import IMDClassificationHead, EyeDiameterEstimator


class TestIMDClassificationHead:
    def test_class_4_maps_to_vscs(self):
        """Test class ID 4 mapping correctly to 'VSCS'."""
        result = IMDClassificationHead.get_classification(class_id=4, confidence=0.95)
        
        assert result["category"] == "VSCS"
        assert result["name"] == "Very Severe Cyclonic Storm"
        assert result["confidence"] == 0.95

    def test_invalid_class_id_raises(self):
        """Test invalid class ID (e.g., 9) raises ValueError."""
        with pytest.raises(ValueError, match="Invalid class ID 9"):
            IMDClassificationHead.get_classification(class_id=9, confidence=0.8)


class TestEyeDiameterEstimator:
    def test_low_intensity_returns_zero(self):
        """Test Eye Estimator for class ID 1 (should return 0.0)."""
        result = EyeDiameterEstimator.estimate_eye_diameter(width_norm=0.2, height_norm=0.2, class_id=1)
        assert result == 0.0

    def test_high_intensity_calculation(self):
        """
        Test Eye Estimator for class ID 5 with width=0.1, height=0.15.
        Calculation: 0.1 * 1024 * 3.46875 * 0.15 ≈ 53.28 km.
        """
        result = EyeDiameterEstimator.estimate_eye_diameter(width_norm=0.1, height_norm=0.15, class_id=5)
        
        expected = 0.1 * 1024 * 3.46875 * 0.15
        expected_rounded = round(expected, 2)
        
        assert result == expected_rounded
        assert result == 53.28

    def test_invalid_class_id_raises(self):
        """Test invalid class ID raises ValueError."""
        with pytest.raises(ValueError, match="Invalid class ID -1"):
            EyeDiameterEstimator.estimate_eye_diameter(width_norm=0.1, height_norm=0.1, class_id=-1)
