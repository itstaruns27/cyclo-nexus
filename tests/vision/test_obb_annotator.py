"""
Task 6 Verification Harness: OBB Annotation Generator
══════════════════════════════════════════════════════
Owner: Agent BRAVO | Skill: [SKILL:YOLO_OBB_CV]

Verifies:
    1. Geographic-to-pixel coordinate projection accuracy.
    2. All 7 IMD class ID mappings return integers 0–6.
    3. CDO dimension heuristic produces physically bounded outputs.
    4. Generated label strings match YOLO-OBB whitespace-separated format.
    5. File persistence writes valid .txt label files.
    6. Theta clamping enforces [-π/2, π/2) invariant.
    7. Error handling for invalid inputs.
"""

import math
import tempfile
from pathlib import Path

import pytest

from vision.preprocessing.obb_annotator import OBBAnnotationGenerator, OBBAnnotationError


@pytest.fixture
def annotator():
    return OBBAnnotationGenerator()


# ── 1. Coordinate Projection ───────────────────────────────────────────

class TestGeoToNormalizedPixel:
    """Verify geographic coordinate → normalized image-space projection."""

    def test_basin_center_maps_to_half(self):
        """(16.0°N, 76.0°E) is the exact geographic center of the NIO grid → (0.5, 0.5)."""
        x, y = OBBAnnotationGenerator.geo_to_normalized_pixel(16.0, 76.0)
        assert abs(x - 0.5) < 1e-9, f"x_center should be 0.5, got {x}"
        assert abs(y - 0.5) < 1e-9, f"y_center should be 0.5, got {y}"

    def test_top_left_corner(self):
        """(32.0°N, 50.0°E) is the north-west corner → (0.0, 0.0) in image space."""
        x, y = OBBAnnotationGenerator.geo_to_normalized_pixel(32.0, 50.0)
        assert abs(x - 0.0) < 1e-9, f"x should be 0.0 at west edge, got {x}"
        assert abs(y - 0.0) < 1e-9, f"y should be 0.0 at north edge, got {y}"

    def test_bottom_right_corner(self):
        """(0.0°N, 102.0°E) is the south-east corner → (1.0, 1.0) in image space."""
        x, y = OBBAnnotationGenerator.geo_to_normalized_pixel(0.0, 102.0)
        assert abs(x - 1.0) < 1e-9, f"x should be 1.0 at east edge, got {x}"
        assert abs(y - 1.0) < 1e-9, f"y should be 1.0 at south edge, got {y}"

    def test_out_of_bounds_clamped(self):
        """Coordinates beyond the NIO bounding box clamp to [0.0, 1.0]."""
        x, y = OBBAnnotationGenerator.geo_to_normalized_pixel(40.0, 110.0)
        assert x == 1.0, "Longitude east of 102°E should clamp x to 1.0"
        assert y == 0.0, "Latitude north of 32°N should clamp y to 0.0"

        x2, y2 = OBBAnnotationGenerator.geo_to_normalized_pixel(-5.0, 30.0)
        assert x2 == 0.0, "Longitude west of 50°E should clamp x to 0.0"
        assert y2 == 1.0, "Latitude south of 0°N should clamp y to 1.0"

    def test_cyclone_amphan_position(self):
        """Cyclone Amphan at (16.8°N, 87.2°E) per fixtures/mock_cyclone_amphan.json."""
        x, y = OBBAnnotationGenerator.geo_to_normalized_pixel(16.8, 87.2)
        expected_x = (87.2 - 50.0) / (102.0 - 50.0)
        expected_y = (32.0 - 16.8) / (32.0 - 0.0)
        assert abs(x - expected_x) < 1e-9
        assert abs(y - expected_y) < 1e-9


# ── 2. IMD Class Mapping ───────────────────────────────────────────────

class TestIMDClassMapping:
    """Verify all 7 IMD categories map to correct integer class IDs."""

    @pytest.mark.parametrize("category,expected_id", [
        ("D",    0),
        ("DD",   1),
        ("CS",   2),
        ("SCS",  3),
        ("VSCS", 4),
        ("ESCS", 5),
        ("SuCS", 6),
    ])
    def test_valid_category_mapping(self, category, expected_id):
        assert OBBAnnotationGenerator.map_imd_to_class_id(category) == expected_id

    def test_invalid_category_raises(self):
        with pytest.raises(OBBAnnotationError, match="Unknown IMD category"):
            OBBAnnotationGenerator.map_imd_to_class_id("INVALID")

    def test_lpa_not_a_cyclone(self):
        """LPA (Low Pressure Area) is sub-depression and must be rejected."""
        with pytest.raises(OBBAnnotationError, match="Unknown IMD category"):
            OBBAnnotationGenerator.map_imd_to_class_id("LPA")


# ── 3. CDO Dimension Heuristic ─────────────────────────────────────────

class TestOBBDimensions:
    """Verify the wind-speed-to-dimension heuristic produces bounded outputs."""

    def test_depression_is_large(self):
        """Low-intensity Depression: CDO should be wider (≈0.25 range)."""
        w, h = OBBAnnotationGenerator.calculate_obb_dimensions(20.0)
        assert 0.15 <= h <= 0.25, f"Depression height {h} outside expected range"
        assert w > h, "Width should exceed height (CDO asymmetry)"

    def test_super_cyclone_is_compact(self):
        """High-intensity SuCS: CDO should be tighter (≈0.08 range)."""
        w, h = OBBAnnotationGenerator.calculate_obb_dimensions(120.0)
        assert 0.08 <= h <= 0.14, f"SuCS height {h} outside expected range"
        assert w > h, "Width should exceed height (CDO asymmetry)"

    def test_midrange_cyclonic_storm(self):
        """CS-range winds produce mid-sized CDO box."""
        w, h = OBBAnnotationGenerator.calculate_obb_dimensions(40.0)
        assert 0.08 <= h <= 0.25, f"CS height {h} outside valid range"
        assert 0.08 <= w <= 0.28, f"CS width {w} outside valid range"

    def test_sub_depression_raises(self):
        """Wind below 17 kt (sub-depression) should raise error."""
        with pytest.raises(OBBAnnotationError, match="below depression threshold"):
            OBBAnnotationGenerator.calculate_obb_dimensions(10.0)

    def test_extreme_wind_clamped(self):
        """Winds beyond 120 kt should still produce valid dimensions."""
        w, h = OBBAnnotationGenerator.calculate_obb_dimensions(180.0)
        assert 0.08 <= h <= 0.14
        assert 0.08 <= w <= 0.28


# ── 4. Label String Format ─────────────────────────────────────────────

class TestLabelGeneration:
    """Verify generated label strings match YOLO-OBB format exactly."""

    def test_label_format_structure(self, annotator):
        """Label must be: 'class_id x y w h theta' with 7 whitespace-separated tokens."""
        label = annotator.generate_obb_label(
            lat=16.0, lon=76.0, v_max_knots=50.0, category="SCS"
        )
        tokens = label.strip().split()
        assert len(tokens) == 6, f"Expected 6 tokens, got {len(tokens)}: {tokens}"

        # First token is integer class ID
        class_id = int(tokens[0])
        assert class_id == 3, f"SCS should be class 3, got {class_id}"

        # Remaining 5 tokens are floats
        for i in range(1, 6):
            float(tokens[i])  # Should not raise

    def test_label_center_coordinates(self, annotator):
        """Basin center (16°N, 76°E) must produce x=0.5, y=0.5."""
        label = annotator.generate_obb_label(
            lat=16.0, lon=76.0, v_max_knots=50.0, category="SCS"
        )
        tokens = label.strip().split()
        x_c = float(tokens[1])
        y_c = float(tokens[2])
        assert abs(x_c - 0.5) < 1e-5, f"x_center should be 0.5, got {x_c}"
        assert abs(y_c - 0.5) < 1e-5, f"y_center should be 0.5, got {y_c}"

    def test_default_theta(self, annotator):
        """Default theta should be π/4 ≈ 0.785398."""
        label = annotator.generate_obb_label(
            lat=16.0, lon=76.0, v_max_knots=30.0, category="DD"
        )
        tokens = label.strip().split()
        theta = float(tokens[5])
        assert abs(theta - math.pi / 4) < 1e-4, f"Default theta should be π/4, got {theta}"

    def test_custom_theta(self, annotator):
        """Custom theta should appear in the label if within bounds."""
        label = annotator.generate_obb_label(
            lat=16.0, lon=76.0, v_max_knots=30.0, category="DD", theta=0.3
        )
        tokens = label.strip().split()
        theta = float(tokens[5])
        assert abs(theta - 0.3) < 1e-4

    def test_super_cyclone_class_id(self, annotator):
        """SuCS (class 6) at peak intensity."""
        label = annotator.generate_obb_label(
            lat=20.0, lon=88.0, v_max_knots=120.0, category="SuCS"
        )
        tokens = label.strip().split()
        assert int(tokens[0]) == 6


# ── 5. File Persistence ────────────────────────────────────────────────

class TestFilePersistence:
    """Verify .txt label file is correctly written to disk."""

    def test_save_creates_file(self, annotator):
        label = annotator.generate_obb_label(
            lat=16.8, lon=87.2, v_max_knots=130.0, category="SuCS"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "labels" / "INSAT3D_L1C_20240524_120000.txt"
            annotator.save_yolo_label(out_path, label)

            assert out_path.exists(), "Label file was not created"
            content = out_path.read_text(encoding="utf-8").strip()
            assert content == label.strip(), "Written content does not match label"

    def test_save_multi_object(self, annotator):
        """Multiple annotation lines (multi-object frame) saved correctly."""
        label_1 = annotator.generate_obb_label(
            lat=16.0, lon=76.0, v_max_knots=50.0, category="SCS"
        )
        label_2 = annotator.generate_obb_label(
            lat=20.0, lon=85.0, v_max_knots=30.0, category="DD"
        )
        combined = label_1 + "\n" + label_2

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "multi_object.txt"
            annotator.save_yolo_label(out_path, combined)

            lines = out_path.read_text(encoding="utf-8").strip().split("\n")
            assert len(lines) == 2, f"Expected 2 label lines, got {len(lines)}"


# ── 6. Theta Clamping ──────────────────────────────────────────────────

class TestThetaClamping:
    """Verify theta is always within [-π/2, π/2) after clamping."""

    def test_theta_above_pi_half_wraps(self, annotator):
        """theta = 2.0 rad (> π/2) should wrap into [-π/2, π/2)."""
        label = annotator.generate_obb_label(
            lat=16.0, lon=76.0, v_max_knots=50.0, category="SCS", theta=2.0
        )
        tokens = label.strip().split()
        theta = float(tokens[5])
        assert -math.pi / 2 <= theta < math.pi / 2, f"Theta {theta} outside [-π/2, π/2)"

    def test_theta_negative_large_wraps(self, annotator):
        """theta = -3.0 rad should wrap into [-π/2, π/2)."""
        label = annotator.generate_obb_label(
            lat=16.0, lon=76.0, v_max_knots=50.0, category="SCS", theta=-3.0
        )
        tokens = label.strip().split()
        theta = float(tokens[5])
        assert -math.pi / 2 <= theta < math.pi / 2, f"Theta {theta} outside [-π/2, π/2)"

    def test_theta_at_boundary(self, annotator):
        """theta = -π/2 is the inclusive lower bound; should remain unchanged."""
        label = annotator.generate_obb_label(
            lat=16.0, lon=76.0, v_max_knots=50.0, category="SCS", theta=-math.pi / 2
        )
        tokens = label.strip().split()
        theta = float(tokens[5])
        assert abs(theta - (-math.pi / 2)) < 1e-6
