"""
Task 3: Geospatial Reprojection & Grid Registration
════════════════════════════════════════════════════
Owner: Agent ALPHA | Skill: [SKILL:GEOSPATIAL_INGEST]

Reprojects all satellite rasters to EPSG:4326 (WGS84) on uniform 0.04° grid.

STUB — Agent ALPHA will implement.
"""
# Libraries: rasterio, pyproj, numpy
# Output: (H, W) arrays on 0.04° grid, CRS=EPSG:4326
# Constraints:
#   - Enforce WGS84 EPSG:4326
#   - NIO bounds: 0-32°N, 50-102°E
#   - Preserve affine transform matrices
