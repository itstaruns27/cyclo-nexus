import pytest
import numpy as np
import rasterio.transform
from data_pipeline.preprocessing.reprojector import GeospatialReprojector, GeospatialRegistrationError

def test_reprojector_initialization_and_transform():
    reprojector = GeospatialReprojector()
    assert reprojector.target_shape == (1024, 1024)
    transform = reprojector.compute_target_transform()
    assert isinstance(transform, rasterio.transform.Affine)
    assert transform.c == 50.0
    assert transform.f == 32.0

def test_reproject_continuous_array():
    reprojector = GeospatialReprojector()
    src_array = np.ones((500, 500), dtype=np.float32)
    src_bounds = (0.0, 20.0, 60.0, 80.0)
    res = reprojector.reproject_array(src_array, src_bounds, is_categorical=False)
    assert res.shape == (1024, 1024)
    assert np.any(res == 1.0)
    assert np.any(res == 0.0)

def test_reproject_categorical_array():
    reprojector = GeospatialReprojector()
    src_array = np.zeros((100, 100), dtype=np.float32)
    src_array[45:55, 45:55] = 5.0
    src_bounds = (10.0, 15.0, 70.0, 75.0)
    res = reprojector.reproject_array(src_array, src_bounds, is_categorical=True)
    assert res.shape == (1024, 1024)
    unique_vals = np.unique(res)
    assert 5.0 in unique_vals
    assert not any((val > 0.0 and val < 5.0) for val in unique_vals)

def test_invalid_shapes_raise_error():
    reprojector = GeospatialReprojector()
    src_bounds = (0.0, 10.0, 50.0, 60.0)
    with pytest.raises(GeospatialRegistrationError):
        reprojector.reproject_array(np.array([]), src_bounds)
    with pytest.raises(GeospatialRegistrationError):
        reprojector.reproject_array(np.ones((10, 10, 3)), src_bounds)

def test_all_nan_raises_error():
    reprojector = GeospatialReprojector()
    src_array = np.full((100, 100), np.nan, dtype=np.float32)
    src_bounds = (0.0, 10.0, 50.0, 60.0)
    with pytest.raises(GeospatialRegistrationError, match="entirely NaN"):
        reprojector.reproject_array(src_array, src_bounds)
