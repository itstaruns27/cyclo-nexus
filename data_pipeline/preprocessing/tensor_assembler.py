import numpy as np
from data_pipeline.preprocessing.reprojector import GeospatialReprojector

class DataQualityError(Exception):
    pass

class TensorAssembler:
    """
    Assembles, calibrates, and normalizes multi-sensor meteorological data into a
    unified 4-channel tensor (4, 1024, 1024) strictly bounded between [0.0, 1.0] for AI inference.
    """
    def __init__(self):
        # Initialize the strictly bounded NIO grid reprojector from Task #3
        self.reprojector = GeospatialReprojector(target_shape=(1024, 1024), bbox=(0.0, 32.0, 50.0, 102.0))

    def _validate_channel(self, array: np.ndarray, name: str):
        if np.all(array == 0.0):
            raise DataQualityError(f"Channel '{name}' is entirely zero — satellite fetch likely failed")
        if np.all(np.isnan(array)):
            raise DataQualityError(f"Channel '{name}' is entirely NaN")
        if array.shape[0] < 64 or array.shape[1] < 64:
            raise DataQualityError(f"Channel '{name}' has implausible shape {array.shape}")

    def normalize_channel(self, array: np.ndarray, vmin: float, vmax: float) -> np.ndarray:
        """
        Clamps values outside physical limits and applies Min-Max normalization.
        
        Args:
            array: Input physical parameters (e.g., Kelvin, mm/hr).
            vmin: Minimum threshold for the atmospheric/physical limit.
            vmax: Maximum threshold for the atmospheric/physical limit.
            
        Returns:
            np.ndarray: float32 array strictly bounded within [0.0, 1.0].
        """
        # Clamp out-of-range outliers or deep-space noise
        clipped = np.clip(array, vmin, vmax)
        # Scale into standard AI normalized bounds
        normalized = (clipped - vmin) / (vmax - vmin)
        
        return normalized.astype(np.float32)

    def assemble_tensor(self, 
                        tir1: np.ndarray, tir1_bounds: tuple, 
                        tir2: np.ndarray, tir2_bounds: tuple, 
                        wv: np.ndarray, wv_bounds: tuple, 
                        gpm: np.ndarray, gpm_bounds: tuple) -> np.ndarray:
        """
        Alings asynchronous swaths into the core 4-channel prediction tensor.
        
        Returns:
            np.ndarray of shape (4, 1024, 1024):
            - Channel 0: TIR-1 Brightness Temp [180K, 320K]
            - Channel 1: Water Vapor Brightness Temp [180K, 320K]
            - Channel 2: Split-Window Difference (TIR-1 - TIR-2) [-10K, +10K]
            - Channel 3: GPM Precipitation Rate [0.0, 100.0 mm/hr]
        """
        # 1. Spatially snap all varying grids strictly to the (1024, 1024) EPSG:4326 grid
        grid_tir1 = self.reprojector.reproject_array(tir1, tir1_bounds, is_categorical=False)
        grid_tir2 = self.reprojector.reproject_array(tir2, tir2_bounds, is_categorical=False)
        grid_wv   = self.reprojector.reproject_array(wv, wv_bounds, is_categorical=False)
        grid_gpm  = self.reprojector.reproject_array(gpm, gpm_bounds, is_categorical=False)
        
        # Validate data quality before normalization
        self._validate_channel(grid_tir1, "TIR1")
        self._validate_channel(grid_tir2, "TIR2")
        self._validate_channel(grid_wv, "WV")
        self._validate_channel(grid_gpm, "GPM")
        
        # 2. Derive thermodynamic relationships
        grid_split_window = grid_tir1 - grid_tir2
        
        # 3. Radiometric Calibration & Normalization limits
        norm_tir1 = self.normalize_channel(grid_tir1, vmin=180.0, vmax=320.0)
        norm_wv   = self.normalize_channel(grid_wv, vmin=180.0, vmax=320.0)
        norm_sw   = self.normalize_channel(grid_split_window, vmin=-10.0, vmax=10.0)
        norm_gpm  = self.normalize_channel(grid_gpm, vmin=0.0, vmax=100.0)
        
        # 4. Construct the C-H-W tensor architecture
        tensor = np.stack([norm_tir1, norm_wv, norm_sw, norm_gpm], axis=0)
        
        # Validate variance
        if tensor.std() < 0.02:
            raise DataQualityError("Assembled tensor has variance < 0.02 — likely synthetic/empty input")
        
        return tensor
