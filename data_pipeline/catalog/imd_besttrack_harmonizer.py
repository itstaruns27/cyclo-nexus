"""
Task 5: IMD Best Track Dataset Harmonization
════════════════════════════════════════════
Owner: Agent ALPHA | Skill: [SKILL:GEOSPATIAL_INGEST]

Harmonizes IMD Best Track CSV archives into standardized Parquet format
with consistent column naming, timestamp parsing, and IMD category mapping.

STUB — Agent ALPHA will implement.
"""
# Libraries: pandas, pyarrow
# Output: Parquet file with columns: [timestamp, lat, lon, wind_kmh, wind_knots, pressure_hpa, imd_category]
# Constraints:
#   - Use IMDCategory enum from schemas/imd_scale.py
#   - Timestamps must be UTC ISO-8601
#   - Coordinates in EPSG:4326
