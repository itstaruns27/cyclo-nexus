"""
Task 2: JAXA Himawari-8/9 NetCDF Ingestion Pipeline
════════════════════════════════════════════════════
Owner: Agent ALPHA
Skill: [SKILL:GEOSPATIAL_INGEST]

Downloads Himawari-8/9 AHI Band 13 (Clean IR, ~10.4 µm) via JAXA P-Tree.
Outputs georeferenced Float32 arrays in EPSG:4326.

STUB — Agent ALPHA will implement.
"""

# Agent ALPHA: Implement this module per Task 2 specification.
# Input: JAXA Himawari-8/9 NetCDF4 files
# Output: Georeferenced NumPy arrays (Band 13 Clean IR)
# Libraries: netCDF4, numpy, rasterio
# Constraints:
#   - Chunked streaming reads
#   - Enforce EPSG:4326 CRS
#   - NIO bounding box clip: 0–32°N, 50–102°E
