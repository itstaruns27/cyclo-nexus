import pytest
import numpy as np

from data_pipeline.preprocessing.tensor_assembler import TensorAssembler

def test_normalize_channel_limits():
    """Validates the normalization engine correctly clamps extremes and scales to [0.0, 1.0]."""
    assembler = TensorAssembler()
    
    # Edge case array: Below vmin, strictly at center, above vmax
    raw_array = np.array([170.0, 250.0, 330.0], dtype=np.float32)
    
    # Apply standard thermal bounds [180K, 320K]
    normalized = assembler.normalize_channel(raw_array, vmin=180.0, vmax=320.0)
    
    expected = np.array([0.0, 0.5, 1.0], dtype=np.float32)
    
    assert np.allclose(normalized, expected, atol=1e-5)


def test_assemble_tensor_shapes_and_bounds():
    """
    Validates synthetic, misaligned spatial arrays are mathematically warped into the 
    strict (4, 1024, 1024) bounding box tensor with normalized physics signatures.
    """
    assembler = TensorAssembler()
    
    tir1 = np.full((500, 500), 300.0, dtype=np.float32)
    tir2 = np.full((500, 500), 295.0, dtype=np.float32) # Split window yields +5.0K
    wv   = np.full((500, 500), 240.0, dtype=np.float32)
    gpm  = np.full((500, 500), 120.0, dtype=np.float32) # Above 100mm/hr boundary
    
    synthetic_bounds = (10.0, 20.0, 60.0, 80.0)
    
    tensor = assembler.assemble_tensor(
        tir1, synthetic_bounds,
        tir2, synthetic_bounds,
        wv, synthetic_bounds,
        gpm, synthetic_bounds
    )
    
    assert tensor.shape == (4, 1024, 1024), f"Invalid architecture depth: {tensor.shape}"
    assert tensor.dtype == np.float32, f"Invalid datatype injection: {tensor.dtype}"
    assert np.all(tensor >= 0.0), "Fatal normalization leak: Values breached below 0.0 limit"
    assert np.all(tensor <= 1.0), "Fatal normalization leak: Values breached above 1.0 limit"
    
    sw_values = np.unique(tensor[2, ...])
    assert np.isclose(0.75, np.max(sw_values), atol=1e-3), "Split-Window thermodynamic derivative miscalculated"
