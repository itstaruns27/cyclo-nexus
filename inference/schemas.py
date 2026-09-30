from pydantic import BaseModel, Field, validator
from typing import List

TENSOR_SHAPE = [6, 4, 1024, 1024]
# Bytes per element for each accepted transport dtype
ALLOWED_DTYPES = {"float32": 4, "uint8": 1}


def expected_tensor_bytes(dtype: str) -> int:
    """6 * 4 * 1024 * 1024 * itemsize (float32 → 100663296, uint8 → 25165824)."""
    n = 1
    for d in TENSOR_SHAPE:
        n *= d
    return n * ALLOWED_DTYPES[dtype]


class InferenceRequest(BaseModel):
    cyclone_id: str = Field(..., min_length=3, max_length=64, description="Unique storm identifier")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")
    
    tensor_b64: str = Field(..., description="Zlib compressed and base64 encoded tensor")
    tensor_shape: List[int] = Field(..., description="Shape of the tensor")
    tensor_dtype: str = Field(..., description="Data type of the tensor")

    @validator('tensor_shape')
    def validate_shape(cls, v):
        if v != [6, 4, 1024, 1024]:
            raise ValueError(f"tensor_shape must be exactly [6, 4, 1024, 1024], got {v}")
        return v
        
    @validator('tensor_dtype')
    def validate_dtype(cls, v):
        # float32: raw normalised values. uint8: round(x * 255) quantisation of the same [0, 1] values
        # (master plan v4 Task 4.1 — keeps real-data payloads under 35 MB).
        if v not in ALLOWED_DTYPES:
            raise ValueError(f"tensor_dtype must be one of {sorted(ALLOWED_DTYPES)}, got {v}")
        return v

class OBBMetrics(BaseModel):
    x_center: float
    y_center: float
    width: float
    height: float
    theta: float

class InferenceResponse(BaseModel):
    cyclone_id: str
    # False when YOLO found no storm; `obb` is then a placeholder and must not be published
    detected: bool = False
    detection_confidence: float = 0.0
    obb: OBBMetrics
    # 5 Horizons: 6h, 12h, 24h, 48h, 72h
    track_delta: List[List[float]] = Field(..., description="List of [Δlat, Δlon] offsets per horizon")
    v_max_pred: List[float] = Field(..., description="Predicted max velocity (knots) per horizon")
    dp_pred: List[float] = Field(..., description="Predicted central pressure drop (hPa) per horizon")
