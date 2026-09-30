"""
Task 2: NASA GPM IMERG Precipitation Pipeline
═════════════════════════════════════════════
Owner: Agent ALPHA
Skill: [SKILL:GEOSPATIAL_INGEST]

Downloads NASA GPM IMERG half-hourly precipitation rate estimates.
Resamples to match the NIO 0.04° grid for channel 4 fusion.

STUB — Agent ALPHA will implement.
"""

# Agent ALPHA: Implement this module per Task 2 specification.
# Input: NASA GPM IMERG HDF5 (precipitation rate mm/hr)
# Output: Resampled Float32 array on 0.04° grid, EPSG:4326
# Libraries: h5py, numpy, scipy (interpolation)
# Constraints:
#   - DO NOT confuse radiance with reflectance
#   - Precipitation rate stays in physical units until final normalization
