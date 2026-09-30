"""
CYCLO-NEXUS — Canonical IMD Intensity Scale
════════════════════════════════════════════
Version: 1.0.0
Owner: ARCHITECT (locked)

India Meteorological Department 7-tier tropical cyclone classification.
Wind speeds are 10-minute mean sustained winds per IMD convention.
"""

from __future__ import annotations

import enum


class IMDCategory(str, enum.Enum):
    """IMD tropical cyclone intensity categories."""
    D    = "D"
    DD   = "DD"
    CS   = "CS"
    SCS  = "SCS"
    VSCS = "VSCS"
    ESCS = "ESCS"
    SuCS = "SuCS"


# Wind speed ranges in km/h (inclusive bounds)
IMD_WIND_RANGES_KMH: dict[IMDCategory, tuple[float, float]] = {
    IMDCategory.D:    (31.0,  49.0),
    IMDCategory.DD:   (50.0,  61.0),
    IMDCategory.CS:   (62.0,  88.0),
    IMDCategory.SCS:  (89.0, 117.0),
    IMDCategory.VSCS: (118.0, 166.0),
    IMDCategory.ESCS: (167.0, 221.0),
    IMDCategory.SuCS: (222.0, 999.0),
}

# Full descriptive labels
IMD_LABELS: dict[IMDCategory, str] = {
    IMDCategory.D:    "Depression",
    IMDCategory.DD:   "Deep Depression",
    IMDCategory.CS:   "Cyclonic Storm",
    IMDCategory.SCS:  "Severe Cyclonic Storm",
    IMDCategory.VSCS: "Very Severe Cyclonic Storm",
    IMDCategory.ESCS: "Extremely Severe Cyclonic Storm",
    IMDCategory.SuCS: "Super Cyclonic Storm",
}

# Alert level thresholds (km/h)
ALERT_THRESHOLDS = {
    "RED":    118.0,   # VSCS and above → mandatory immediate evacuation
    "ORANGE":  62.0,   # CS/SCS → halt maritime operations
    "YELLOW":  31.0,   # D/DD → advisory for fishermen
}


def classify_imd(wind_speed_kmh: float) -> IMDCategory:
    """Deterministic IMD classification from sustained wind speed (km/h)."""
    for category, (lo, hi) in IMD_WIND_RANGES_KMH.items():
        if lo <= wind_speed_kmh <= hi:
            return category
    raise ValueError(f"Wind speed {wind_speed_kmh} km/h outside valid IMD range [31, ∞)")


def get_alert_level(wind_speed_kmh: float) -> str:
    """Map wind speed to alert level (RED/ORANGE/YELLOW)."""
    if wind_speed_kmh >= ALERT_THRESHOLDS["RED"]:
        return "RED"
    elif wind_speed_kmh >= ALERT_THRESHOLDS["ORANGE"]:
        return "ORANGE"
    elif wind_speed_kmh >= ALERT_THRESHOLDS["YELLOW"]:
        return "YELLOW"
    else:
        raise ValueError(f"Wind speed {wind_speed_kmh} km/h below depression threshold")


def kmh_to_knots(kmh: float) -> float:
    """Convert km/h to knots (nautical miles per hour)."""
    return kmh / 1.852


def knots_to_kmh(knots: float) -> float:
    """Convert knots to km/h."""
    return knots * 1.852
