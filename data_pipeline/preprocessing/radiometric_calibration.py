"""
Task 4: Radiometric Calibration & Min-Max Scaling
═════════════════════════════════════════════════
Owner: Agent ALPHA | Skill: [SKILL:GEOSPATIAL_INGEST]

Converts raw digital counts to Brightness Temperature (K), then
min-max normalizes to [0.0, 1.0] using BT range [180K, 320K].

STUB — Agent ALPHA will implement.
"""
# Libraries: numpy, h5py
# Output: Float32 arrays normalized to [0.0, 1.0]
# Constraints:
#   - BT range: 180K to 320K
#   - DO NOT confuse radiance with reflectance
#   - Keep physical BT values until final normalization step
