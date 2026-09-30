import numpy as np
import rasterio.transform
from rasterio.warp import reproject, Resampling

class GeospatialRegistrationError(Exception):
    pass

class GeospatialReprojector:
    def __init__(self, target_crs: str = "EPSG:4326", target_shape: tuple = (1024, 1024), bbox: tuple = (0.0, 32.0, 50.0, 102.0)):
        self.target_crs = target_crs
        self.target_shape = target_shape
        self.min_lat, self.max_lat, self.min_lon, self.max_lon = bbox
        self.target_transform = self.compute_target_transform()

    def compute_target_transform(self) -> rasterio.transform.Affine:
        return rasterio.transform.from_bounds(
            west=self.min_lon,
            south=self.min_lat,
            east=self.max_lon,
            north=self.max_lat,
            width=self.target_shape[1],
            height=self.target_shape[0]
        )

    def reproject_array(self, source_array: np.ndarray, src_bounds: tuple, src_crs: str = "EPSG:4326", is_categorical: bool = False) -> np.ndarray:
        if source_array.ndim != 2 or source_array.size == 0:
            raise GeospatialRegistrationError(f"Invalid input shape {source_array.shape}. Expected non-empty 2D array.")
        if np.all(np.isnan(source_array)):
            raise GeospatialRegistrationError("Input array contains entirely NaN values.")

        src_min_lat, src_max_lat, src_min_lon, src_max_lon = src_bounds
        src_transform = rasterio.transform.from_bounds(
            west=src_min_lon,
            south=src_min_lat,
            east=src_max_lon,
            north=src_max_lat,
            width=source_array.shape[1],
            height=source_array.shape[0]
        )
        
        destination_array = np.zeros(self.target_shape, dtype=np.float32)
        resampling_algo = Resampling.nearest if is_categorical else Resampling.bilinear
        nodata_value = 0.0
        
        reproject(
            source=source_array,
            destination=destination_array,
            src_transform=src_transform,
            src_crs=src_crs,
            dst_transform=self.target_transform,
            dst_crs=self.target_crs,
            resampling=resampling_algo,
            src_nodata=np.nan,
            dst_nodata=np.nan
        )
        np.nan_to_num(destination_array, copy=False, nan=nodata_value)
        return destination_array
