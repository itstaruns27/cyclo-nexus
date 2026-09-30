"""
Task 6: Oriented Bounding Box (OBB) Annotation Generator
═════════════════════════════════════════════════════════
Owner: Agent BRAVO | Skill: [SKILL:YOLO_OBB_CV]

Converts cyclone track metadata (IMD category, geographic coordinates, wind
speed) into Ultralytics YOLO-OBB label strings and persists them as .txt files
alongside their corresponding satellite tensor images.

Label format per vision/annotation/label_format.md:
    class_id x_c y_c w h θ

Coordinate system:
    The 1024×1024 spatial grid covers the North Indian Ocean basin
    (0.0°N–32.0°N, 50.0°E–102.0°E) in EPSG:4326.  Image-space origin is
    top-left, so latitude is inverted (32°N → y=0, 0°N → y=1).
"""

import math
from pathlib import Path
from typing import Tuple

from schemas.imd_scale import IMDCategory

# ── Constants ───────────────────────────────────────────────────────────

# North Indian Ocean bounding box (must match reprojector.py exactly)
_MIN_LAT = 0.0
_MAX_LAT = 32.0
_MIN_LON = 50.0
_MAX_LON = 102.0

# IMD category → YOLO integer class ID (canonical ordering from label_format.md)
_IMD_CLASS_MAP: dict[str, int] = {
    "D":    0,
    "DD":   1,
    "CS":   2,
    "SCS":  3,
    "VSCS": 4,
    "ESCS": 5,
    "SuCS": 6,
}

# Default spiral-band tilt angle (radians) for Northern Hemisphere cyclones
_DEFAULT_THETA: float = math.pi / 4  # 0.7854 rad ≈ 45°

# Theta bounds: YOLO-OBB convention [-π/2, π/2)
_THETA_MIN: float = -math.pi / 2
_THETA_MAX: float = math.pi / 2


class OBBAnnotationError(Exception):
    """Raised when annotation inputs violate physical or geometric constraints."""
    pass


class OBBAnnotationGenerator:
    """
    Generates YOLO-OBB formatted annotation labels for tropical cyclone
    satellite imagery over the North Indian Ocean basin.

    Each label encodes:
        class_id  x_center  y_center  width  height  theta
    where coordinates and dimensions are normalized to [0.0, 1.0] relative
    to the 1024×1024 grid, and theta is in radians within [-π/2, π/2).
    """

    # ── Class ID Mapping ────────────────────────────────────────────────

    @staticmethod
    def map_imd_to_class_id(category: str) -> int:
        """
        Maps an IMD intensity category string to its YOLO class integer.

        Args:
            category: One of 'D', 'DD', 'CS', 'SCS', 'VSCS', 'ESCS', 'SuCS'.

        Returns:
            Integer class ID in [0, 6].

        Raises:
            OBBAnnotationError: If the category string is not a valid IMD tier.
        """
        if category not in _IMD_CLASS_MAP:
            raise OBBAnnotationError(
                f"Unknown IMD category '{category}'. "
                f"Valid categories: {list(_IMD_CLASS_MAP.keys())}"
            )
        return _IMD_CLASS_MAP[category]

    # ── Coordinate Projection ───────────────────────────────────────────

    @staticmethod
    def geo_to_normalized_pixel(lat: float, lon: float) -> Tuple[float, float]:
        """
        Projects geographic coordinates to normalized image-space [0.0, 1.0].

        Image convention: top-left origin.
            x_norm = (lon - min_lon) / (max_lon - min_lon)
            y_norm = (max_lat - lat) / (max_lat - min_lat)

        Coordinates outside the NIO bounding box are clamped to [0.0, 1.0].

        Args:
            lat: Latitude in degrees North (0.0–32.0 for NIO).
            lon: Longitude in degrees East (50.0–102.0 for NIO).

        Returns:
            (x_normalized, y_normalized) tuple, each in [0.0, 1.0].
        """
        x_norm = (lon - _MIN_LON) / (_MAX_LON - _MIN_LON)
        y_norm = (_MAX_LAT - lat) / (_MAX_LAT - _MIN_LAT)

        # Clamp to valid image bounds
        x_norm = max(0.0, min(1.0, x_norm))
        y_norm = max(0.0, min(1.0, y_norm))

        return (x_norm, y_norm)

    # ── CDO Dimension Heuristic ─────────────────────────────────────────

    @staticmethod
    def calculate_obb_dimensions(v_max_knots: float) -> Tuple[float, float]:
        """
        Estimates normalized CDO bounding box width and height from maximum
        sustained wind speed, reflecting the inverse relationship between
        intensity and CDO spatial extent.

        Meteorological basis:
            - Weak systems (D/DD/CS, <48 kt): Large, diffuse convective
              envelopes with sheared outer bands → wider bounding box.
            - Intense systems (SCS+, ≥48 kt): Compact, axisymmetric CDO
              core with well-defined eyewall → tighter bounding box.

        The mapping uses linear interpolation between anchor points:
            17 kt (D threshold)   → 0.25 normalized
            120 kt (SuCS regime)  → 0.08 normalized

        Width is scaled 1.1× relative to height to capture CDO asymmetry
        typical of translating tropical cyclones (elongated along shear axis).

        Args:
            v_max_knots: Maximum sustained wind speed in knots (≥ 17.0).

        Returns:
            (width_norm, height_norm) each in approximately [0.08, 0.25].

        Raises:
            OBBAnnotationError: If v_max_knots is below depression threshold.
        """
        if v_max_knots < 17.0:
            raise OBBAnnotationError(
                f"Wind speed {v_max_knots} kt is below depression threshold (17 kt). "
                f"No cyclonic system detected."
            )

        # Piecewise linear interpolation: higher wind → smaller CDO box
        # Anchor points: (17 kt → 0.25), (120 kt → 0.08)
        v_clamped = max(17.0, min(120.0, v_max_knots))
        t = (v_clamped - 17.0) / (120.0 - 17.0)  # 0.0 at 17kt, 1.0 at 120kt
        base_dim = 0.25 - t * (0.25 - 0.08)       # 0.25 → 0.08

        # Introduce asymmetry: width slightly larger than height
        width = base_dim * 1.1
        height = base_dim

        # Clamp to physically reasonable normalized bounds
        width = max(0.08, min(0.28, width))
        height = max(0.08, min(0.25, height))

        return (round(width, 6), round(height, 6))

    # ── Label String Generation ─────────────────────────────────────────

    @staticmethod
    def _clamp_theta(theta: float) -> float:
        """Clamps rotation angle to YOLO-OBB range [-π/2, π/2)."""
        while theta >= _THETA_MAX:
            theta -= math.pi
        while theta < _THETA_MIN:
            theta += math.pi
        return theta

    def generate_obb_label(
        self,
        lat: float,
        lon: float,
        v_max_knots: float,
        category: str,
        theta: float = _DEFAULT_THETA,
    ) -> str:
        """
        Generates a single YOLO-OBB annotation line.

        Args:
            lat: Cyclone eye latitude (degrees North).
            lon: Cyclone eye longitude (degrees East).
            v_max_knots: Maximum sustained wind speed (knots).
            category: IMD intensity category string.
            theta: Rotation angle in radians (default π/4).

        Returns:
            Whitespace-separated string:
                'class_id x_center y_center width height theta'
            with 6 decimal places for floating-point fields.

        Raises:
            OBBAnnotationError: On invalid category or sub-threshold wind.
        """
        class_id = self.map_imd_to_class_id(category)
        x_center, y_center = self.geo_to_normalized_pixel(lat, lon)
        width, height = self.calculate_obb_dimensions(v_max_knots)
        theta = self._clamp_theta(theta)

        return (
            f"{class_id} "
            f"{x_center:.6f} {y_center:.6f} "
            f"{width:.6f} {height:.6f} "
            f"{theta:.6f}"
        )

    # ── File Persistence ────────────────────────────────────────────────

    @staticmethod
    def save_yolo_label(output_path: Path, label_str: str) -> None:
        """
        Writes a YOLO-OBB label string to a .txt file.

        Creates parent directories if they do not exist.  Supports
        multi-object labels (multiple lines in label_str).

        Args:
            output_path: Destination .txt file path (should share the
                         basename of its corresponding tensor image,
                         e.g. INSAT3D_L1C_20240524_120000.txt).
            label_str: One or more YOLO-OBB label lines separated by '\\n'.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(label_str.strip() + "\n", encoding="utf-8")
