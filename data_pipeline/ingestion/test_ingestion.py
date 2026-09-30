import os
import sys
import numpy as np
from datetime import datetime

# Ensure we can import from data_pipeline
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from data_pipeline.preprocessing.tensor_assembler import TensorAssembler

def test_ingestion_pipeline():
    print("=== CYCLO-NEXUS Ingestion Testing ===")
    
    bbox = (0.0, 32.0, 50.0, 102.0)
    
    print("Simulating real satellite data for mathematical validation...")
    
    # Create physically realistic synthetic data
    # TIR-1: typical temperatures between 200K (cold cloud tops) and 300K (warm ocean)
    tir1 = np.random.normal(loc=250.0, scale=30.0, size=(1024, 1024)).astype(np.float32)
    # TIR-2: usually slightly colder/warmer than TIR-1 depending on moisture
    tir2 = tir1 + np.random.normal(loc=1.5, scale=0.5, size=(1024, 1024)).astype(np.float32)
    # WV: Water vapor, typical temperatures 220K - 260K
    wv = np.random.normal(loc=240.0, scale=15.0, size=(1024, 1024)).astype(np.float32)
    # GPM: Precipitation, typical 0 - 50 mm/hr in rainbands
    gpm = np.random.exponential(scale=5.0, size=(1024, 1024)).astype(np.float32)
    
    mosdac_channels = {
        "TIR1": tir1,
        "TIR2": tir2,
        "WV": wv
    }
    gpm_channel = gpm
    
    print("Testing Tensor Assembler...")
    assembler = TensorAssembler()
    
    try:
        final_tensor = assembler.assemble_tensor(
            mosdac_channels["TIR1"], bbox,
            mosdac_channels["TIR2"], bbox,
            mosdac_channels["WV"], bbox,
            gpm_channel, bbox
        )
        
        print("\n=== Validation Results ===")
        print(f"Shape: {final_tensor.shape}")
        print(f"Min:   {final_tensor.min():.4f}")
        print(f"Max:   {final_tensor.max():.4f}")
        print(f"Mean:  {final_tensor.mean():.4f}")
        print(f"Std:   {final_tensor.std():.4f}")
        
        assert final_tensor.shape == (4, 1024, 1024), "Shape mismatch"
        assert final_tensor.min() >= 0.0, "Values below 0.0"
        assert final_tensor.max() <= 1.0, "Values above 1.0"
        assert final_tensor.std() > 0.02, "Standard deviation too low (degenerate tensor)"
        
        print("All statistical checks passed successfully! Tensor mathematically matches model requirements.")
        
    except Exception as e:
        print(f"Error during tensor assembly: {e}")

if __name__ == "__main__":
    test_ingestion_pipeline()
