"""
CYCLO-NEXUS Telemetry Contract — Python Source of Truth
═══════════════════════════════════════════════════════
Version: 1.0.0
Owner: ARCHITECT (locked after initial commit)
Consumers: ALL AGENTS (Read-Only)

All inter-service payloads MUST conform to these models.
Any modification requires an RFC update in schemas/README.md.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ── IMD 7-Tier Intensity Scale ──────────────────────────────────────────

class IMDCategory(str, enum.Enum):
    """India Meteorological Department tropical cyclone intensity scale."""
    D    = "D"      # Depression:                       31–49  km/h
    DD   = "DD"     # Deep Depression:                  50–61  km/h
    CS   = "CS"     # Cyclonic Storm:                   62–88  km/h
    SCS  = "SCS"    # Severe Cyclonic Storm:            89–117 km/h
    VSCS = "VSCS"   # Very Severe Cyclonic Storm:      118–166 km/h
    ESCS = "ESCS"   # Extremely Severe Cyclonic Storm: 167–221 km/h
    SuCS = "SuCS"   # Super Cyclonic Storm:             ≥222  km/h


IMD_WIND_RANGES_KMH: dict[IMDCategory, tuple[float, float]] = {
    IMDCategory.D:    (31.0,  49.0),
    IMDCategory.DD:   (50.0,  61.0),
    IMDCategory.CS:   (62.0,  88.0),
    IMDCategory.SCS:  (89.0, 117.0),
    IMDCategory.VSCS: (118.0, 166.0),
    IMDCategory.ESCS: (167.0, 221.0),
    IMDCategory.SuCS: (222.0, 999.0),
}


def classify_imd(wind_speed_kmh: float) -> IMDCategory:
    """Deterministic IMD classification from sustained wind speed (km/h)."""
    for category, (lo, hi) in IMD_WIND_RANGES_KMH.items():
        if lo <= wind_speed_kmh <= hi:
            return category
    raise ValueError(f"Wind speed {wind_speed_kmh} km/h outside IMD range [31, ∞)")


# ── Oriented Bounding Box Parameters ───────────────────────────────────

class OrientedBoundingBox(BaseModel):
    """
    YOLO-OBB 5-parameter rotated bounding box for cyclone eye detection.
    Coordinates are in normalized image space [0.0, 1.0] during training,
    or geographic degrees (EPSG:4326) in production inference outputs.
    """
    x_center: float = Field(..., description="Center x-coordinate (lon or normalized)")
    y_center: float = Field(..., description="Center y-coordinate (lat or normalized)")
    width: float    = Field(..., gt=0, description="Box width along rotated major axis")
    height: float   = Field(..., gt=0, description="Box height along rotated minor axis")
    theta: float    = Field(
        ...,
        ge=-3.141592653589793,
        le=3.141592653589793,
        description="Rotation angle in radians, range [-π, π]"
    )


# ── Eye Metrics ────────────────────────────────────────────────────────

class EyeMetrics(BaseModel):
    """Physical properties of the detected cyclone eye."""
    eye_diameter_km: float       = Field(..., gt=0, le=400, description="Eye diameter in km")
    eyewall_thickness_km: Optional[float] = Field(
        None, gt=0, le=200, description="Eyewall annular thickness in km"
    )
    eye_symmetry_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="0=highly asymmetric, 1=perfectly circular"
    )


# ── Atmospheric State Vector ──────────────────────────────────────────

class AtmosphericState(BaseModel):
    """Thermodynamic state of the cyclone at a single timestep."""
    timestamp: datetime          = Field(..., description="ISO-8601 UTC observation time")
    latitude: float              = Field(..., ge=0.0, le=32.0, description="°N (NIO bounds)")
    longitude: float             = Field(..., ge=50.0, le=102.0, description="°E (NIO bounds)")
    sustained_wind_kmh: float    = Field(..., ge=0, description="10-min sustained wind (km/h)")
    sustained_wind_knots: float  = Field(..., ge=0, description="10-min sustained wind (knots)")
    central_pressure_hpa: float  = Field(..., ge=870, le=1020, description="Min central pressure")
    environmental_pressure_hpa: float = Field(
        default=1010.0, ge=990, le=1020, description="Ambient peripheral pressure"
    )
    imd_category: IMDCategory    = Field(..., description="IMD intensity classification")

    @field_validator("imd_category")
    @classmethod
    def validate_imd_consistency(cls, v: IMDCategory, info) -> IMDCategory:
        """Verify IMD category is consistent with reported wind speed."""
        wind = info.data.get("sustained_wind_kmh")
        if wind is not None:
            expected = classify_imd(wind)
            if v != expected:
                raise ValueError(
                    f"IMD category '{v.value}' inconsistent with wind {wind} km/h "
                    f"(expected '{expected.value}')"
                )
        return v


# ── Atkinson-Holliday Physics Constraint ──────────────────────────────

class AtkinsonHollidayConstraint(BaseModel):
    """
    Validates the empirical wind-pressure relationship:
    ΔP = P_env - P_c = 0.018 × (V_max_knots)^1.5

    Tolerance: ±5 hPa to account for real-world variance.
    """
    v_max_knots: float           = Field(..., gt=0)
    central_pressure_hpa: float  = Field(..., gt=0)
    environmental_pressure_hpa: float = Field(default=1010.0)
    tolerance_hpa: float         = Field(default=5.0)

    @model_validator(mode="after")
    def check_physics(self) -> "AtkinsonHollidayConstraint":
        expected_dp = 0.018 * (self.v_max_knots ** 1.5)
        actual_dp = self.environmental_pressure_hpa - self.central_pressure_hpa
        if abs(actual_dp - expected_dp) > self.tolerance_hpa:
            raise ValueError(
                f"Atkinson-Holliday violation: expected ΔP≈{expected_dp:.1f} hPa, "
                f"got {actual_dp:.1f} hPa (tolerance ±{self.tolerance_hpa} hPa)"
            )
        return self


# ── Forecast Point (single horizon) ──────────────────────────────────

class ForecastPoint(BaseModel):
    """Predicted state at a single forecast horizon."""
    forecast_hour: int           = Field(..., description="Hours ahead: 6, 12, 24, 48, or 72")
    predicted_lat: float         = Field(..., ge=-5.0, le=40.0)
    predicted_lon: float         = Field(..., ge=40.0, le=110.0)
    predicted_wind_kmh: float    = Field(..., ge=0)
    predicted_pressure_hpa: float = Field(..., ge=870, le=1020)
    predicted_imd_category: IMDCategory
    sigma_lat: float             = Field(..., ge=0, description="Lat uncertainty (±°)")
    sigma_lon: float             = Field(..., ge=0, description="Lon uncertainty (±°)")
    confidence: float            = Field(..., ge=0.0, le=1.0, description="Model confidence")

    @field_validator("forecast_hour")
    @classmethod
    def valid_horizon(cls, v: int) -> int:
        if v not in (6, 12, 24, 48, 72):
            raise ValueError(f"Invalid forecast horizon: {v}h. Must be 6, 12, 24, 48, or 72.")
        return v


# ── Grad-CAM XAI Metadata ────────────────────────────────────────────

class GradCAMMetadata(BaseModel):
    """Metadata for a Grad-CAM spatial attention heatmap."""
    heatmap_uri: str             = Field(..., description="URL or path to heatmap image (PNG/WebP)")
    target_layer: str            = Field(..., description="PyTorch module path of hooked layer")
    channel_index: int           = Field(..., ge=0, le=3, description="Which input channel (0-3)")
    min_activation: float        = Field(..., ge=0.0)
    max_activation: float        = Field(..., ge=0.0)
    timestamp: datetime


# ── Top-Level Cyclone Telemetry Payload ───────────────────────────────

class CycloneTelemetryPayload(BaseModel):
    """
    Master payload transmitted from Colab inference worker → Hostinger webhook.
    This is the single source of truth for all cyclone intelligence.
    """
    # Identification
    payload_version: str         = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    cyclone_id: str              = Field(..., min_length=3, max_length=64,
                                         description="Unique storm identifier, e.g., 'BOB_02_2024'")
    cyclone_name: Optional[str]  = Field(None, description="Named storm, e.g., 'AMPHAN'")
    basin: str                   = Field(default="NIO", description="North Indian Ocean basin")
    generated_at: datetime       = Field(..., description="UTC timestamp of inference run")

    # Current Detection (YOLO-OBB output)
    current_state: AtmosphericState
    obb: OrientedBoundingBox
    eye_metrics: Optional[EyeMetrics] = None
    detection_confidence: float  = Field(..., ge=0.0, le=1.0)

    # Historical Track (6 timesteps, t-15h to t0)
    historical_track: list[AtmosphericState] = Field(
        ..., min_length=1, max_length=12,
        description="Past observations at 3h cadence, chronologically ordered"
    )

    # Forecast Track (+6h to +72h)
    forecast_track: list[ForecastPoint] = Field(
        ..., min_length=1, max_length=5,
        description="Predicted positions at 6, 12, 24, 48, 72h horizons"
    )

    # Explainability
    gradcam: Optional[list[GradCAMMetadata]] = Field(
        None, description="Grad-CAM heatmaps per channel/timestep"
    )

    @field_validator("historical_track")
    @classmethod
    def chronological_order(cls, v: list[AtmosphericState]) -> list[AtmosphericState]:
        for i in range(1, len(v)):
            if v[i].timestamp <= v[i - 1].timestamp:
                raise ValueError("historical_track must be in strict chronological order")
        return v
