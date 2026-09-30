"""
Axis Regridder
══════════════
Resamples a 2-D field defined on separable 1-D latitude / longitude axes
(regular lat-lon like GPM IMERG, or Mercator rows like INSAT L1C ASIA_MER)
onto the CYCLO-NEXUS north-up target grid.

The output grid uses cell centres of a `shape` raster spanning `bbox`
(min_lat, max_lat, min_lon, max_lon), row 0 = northernmost — the same
convention as rasterio.transform.from_bounds used by GeospatialReprojector,
so the result can be passed to TensorAssembler with src_bounds == bbox.
"""

import numpy as np
from scipy.ndimage import map_coordinates


def target_axes(bbox: tuple, shape: tuple = (1024, 1024)):
    """Cell-centre latitudes (north→south) and longitudes (west→east) of the target grid."""
    min_lat, max_lat, min_lon, max_lon = bbox
    h, w = shape
    dlat = (max_lat - min_lat) / h
    dlon = (max_lon - min_lon) / w
    lats = max_lat - dlat * (np.arange(h) + 0.5)
    lons = min_lon + dlon * (np.arange(w) + 0.5)
    return lats, lons


def _fractional_index(src_axis: np.ndarray, targets: np.ndarray) -> np.ndarray:
    """Map target coordinates to fractional indices along a monotonic source axis (NaN if outside)."""
    src_axis = np.asarray(src_axis, dtype=np.float64)
    idx = np.arange(src_axis.size, dtype=np.float64)
    if src_axis[0] > src_axis[-1]:  # descending axis (e.g. north-up rows)
        src_axis, idx = src_axis[::-1], idx[::-1]
    frac = np.interp(targets, src_axis, idx, left=np.nan, right=np.nan)
    return frac


def regrid_to_bbox(data: np.ndarray, src_lats: np.ndarray, src_lons: np.ndarray,
                   bbox: tuple, shape: tuple = (1024, 1024), order: int = 1) -> np.ndarray:
    """
    Args:
        data: 2-D array indexed [lat_index, lon_index]; NaN marks missing values.
        src_lats: 1-D latitude of each row (ascending or descending).
        src_lons: 1-D longitude of each column (ascending).
        bbox: (min_lat, max_lat, min_lon, max_lon) of the target grid.
        order: 0 = nearest, 1 = bilinear.

    Returns:
        float32 array of `shape`, north-up. Cells outside source coverage are NaN.
    """
    if data.ndim != 2 or data.shape != (len(src_lats), len(src_lons)):
        raise ValueError(f"data shape {data.shape} does not match axes ({len(src_lats)}, {len(src_lons)})")

    tlats, tlons = target_axes(bbox, shape)
    rows = _fractional_index(src_lats, tlats)
    cols = _fractional_index(src_lons, tlons)
    rr, cc = np.meshgrid(rows, cols, indexing="ij")
    outside = np.isnan(rr) | np.isnan(cc)

    src = np.asarray(data, dtype=np.float32)
    nan_mask = np.isnan(src)
    filled = np.where(nan_mask, 0.0, src)

    out = map_coordinates(filled, [np.nan_to_num(rr), np.nan_to_num(cc)], order=order, mode="nearest")
    if nan_mask.any():
        # Propagate missing data: any interpolation touching a NaN cell stays NaN
        touched = map_coordinates(nan_mask.astype(np.float32), [np.nan_to_num(rr), np.nan_to_num(cc)],
                                  order=order, mode="nearest")
        out[touched > 0.5] = np.nan
    out[outside] = np.nan
    return out.astype(np.float32)
