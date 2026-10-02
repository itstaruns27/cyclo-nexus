"""
Phase 4: FastAPI Inference Microservice
Owner: Agent
Skill: [SKILL:VIBE_CODER]
"""

import sys
import os
from pathlib import Path

# Add project root to path for module resolution
sys.path.append(str(Path(__file__).resolve().parent.parent))

import gc
import hmac
import numpy as np
import psutil
import torch
import traceback
import base64
import zlib
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from inference.schemas import InferenceRequest, InferenceResponse, OBBMetrics, expected_tensor_bytes
from forecaster.models.spatiotemporal_forecaster import load_forecaster

# Globals to hold models
models: Dict[str, Any] = {}

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
VISION_WEIGHTS = BASE_DIR / "vision" / "weights" / "vision_best.pt"
FORECASTER_WEIGHTS = BASE_DIR / "forecaster" / "weights" / "forecaster_best.pt"

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Singleton Initialization
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Loading models onto {device}...")
    
    # Load Forecaster
    try:
        forecaster = load_forecaster(FORECASTER_WEIGHTS, device)
        models["forecaster"] = forecaster
        print(f"Forecaster loaded successfully ({forecaster.n_horizons} horizon(s)).")
    except Exception as e:
        print(f"Error loading Forecaster: {e}")

    # Load YOLO
    try:
        from ultralytics import YOLO
        yolo = YOLO(VISION_WEIGHTS)
        yolo.to(device)
        models["yolo"] = yolo
        print("YOLO OBB loaded successfully.")
    except Exception as e:
        print(f"Error loading YOLO: {e}")
        
    yield
    
    # Cleanup
    models.clear()
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

app = FastAPI(lifespan=lifespan, title="CYCLO-NEXUS Inference API")

# Optional shared key: required on /predict when INFERENCE_API_KEY is set (public deployments)
INFERENCE_API_KEY = os.environ.get("INFERENCE_API_KEY", "")


@app.middleware("http")
async def api_key_guard(request: Request, call_next):
    if INFERENCE_API_KEY and request.url.path == "/predict":
        supplied = request.headers.get("x-api-key", "")
        if not hmac.compare_digest(supplied.encode(), INFERENCE_API_KEY.encode()):
            return JSONResponse(status_code=401, content={"detail": "Invalid or missing X-API-Key"})
    return await call_next(request)


# Memory monitor middleware
@app.middleware("http")
async def memory_guard(request: Request, call_next):
    mem_usage = psutil.virtual_memory().percent
    if mem_usage > 90.0:
        return JSONResponse(
            status_code=503,
            content={"detail": "Service Unavailable: Memory capacity exceeded"}
        )
    response = await call_next(request)
    return response

# Error Handlers
@app.exception_handler(RuntimeError)
async def pytorch_exception_handler(request: Request, exc: RuntimeError):
    msg = str(exc).lower()
    if "out of memory" in msg:
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return JSONResponse(
            status_code=503,
            content={"detail": "Service Unavailable: Out of memory during inference"}
        )
    elif "size mismatch" in msg or "shape" in msg:
        return JSONResponse(
            status_code=400,
            content={"detail": f"Bad Request: Tensor shape/dimension error. {str(exc)}"}
        )
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal Server Error: {str(exc)}"}
    )

@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )

@app.get("/health")
async def health():
    loaded = {name: name in models for name in ("forecaster", "yolo")}
    return JSONResponse(
        status_code=200 if all(loaded.values()) else 503,
        content={"status": "ok" if all(loaded.values()) else "degraded", "models": loaded,
                 "device": "cuda" if torch.cuda.is_available() else "cpu",
                 "memory_percent": psutil.virtual_memory().percent},
    )


@app.post("/predict", response_model=InferenceResponse)
async def predict(payload: InferenceRequest):
    if "forecaster" not in models or "yolo" not in models:
        return JSONResponse(status_code=503, content={"detail": "Models are not loaded properly."})
        
    device = next(models["forecaster"].parameters()).device
    
    try:
        raw_bytes = base64.b64decode(payload.tensor_b64)
        decompressed_bytes = zlib.decompress(raw_bytes)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to decode or decompress payload.")
        
    # float32 → 100663296 bytes, uint8 → 25165824 bytes
    EXPECTED_BYTES = expected_tensor_bytes(payload.tensor_dtype)
    if len(decompressed_bytes) != EXPECTED_BYTES:
        raise HTTPException(
            status_code=422,
            detail=f"Byte length mismatch. Expected {EXPECTED_BYTES}, got {len(decompressed_bytes)}."
        )

    if payload.tensor_dtype == "uint8":
        np_tensor = (np.frombuffer(decompressed_bytes, dtype=np.uint8).reshape(payload.tensor_shape)
                     .astype(np.float32) / 255.0)
    else:
        np_tensor = np.frombuffer(decompressed_bytes, dtype=np.float32).reshape(payload.tensor_shape)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    try:
        tensor_data = torch.from_numpy(np_tensor.copy()).to(device)
        with torch.inference_mode():
            # Forecaster expects (Batch, Seq_Length, Channels, H, W)
            # Same preprocessing as training (build_unified_set.py): block-mean to 256² (forecaster)
            # and 512² (YOLO), rounded to the uint8 levels the training data was stored at.
            def _as_trained(t, size):
                k = t.shape[-1] // size
                t = torch.nn.functional.avg_pool2d(t, k) if k > 1 else t
                return torch.round(t.clamp(0, 1) * 255) / 255
            forecaster_input = _as_trained(tensor_data, 256).unsqueeze(0)
            forecaster_output = models["forecaster"](forecaster_input)
            
            track_delta_raw = forecaster_output["track_delta"].squeeze(0).tolist()
            v_max_pred_raw = forecaster_output["v_max_pred"].squeeze(0).tolist()
            dp_pred_raw = forecaster_output["dp_pred"].squeeze(0).tolist()
            
            # Multi-horizon checkpoints give one value per lead time (6h, 12h, 24h, 48h, 72h).
            # Legacy single-horizon checkpoints are duplicated so the schema stays valid.
            if models["forecaster"].n_horizons == 1:
                track_delta = [track_delta_raw] * 5
                v_max_pred = [v_max_pred_raw if isinstance(v_max_pred_raw, float) else v_max_pred_raw[0]] * 5
                dp_pred = [dp_pred_raw if isinstance(dp_pred_raw, float) else dp_pred_raw[0]] * 5
            else:
                track_delta = track_delta_raw
                v_max_pred = v_max_pred_raw
                dp_pred = dp_pred_raw
            
            # YOLO expects 3 channels (e.g., RGB equivalent). We slice the first 3 channels (TIR1, WV, SW)
            yolo_input = _as_trained(tensor_data[-1][:3].unsqueeze(0), 512)
            yolo_size = float(yolo_input.shape[-1])
            yolo_results = models["yolo"](yolo_input)
            
            # Parse YOLO-OBB result (assuming the strongest detection)
            # Fallback values if no object is detected
            obb = OBBMetrics(x_center=0.5, y_center=0.5, width=0.08, height=0.08, theta=0.0)
            detected = False
            detection_confidence = 0.0

            if len(yolo_results) > 0 and hasattr(yolo_results[0], 'obb') and yolo_results[0].obb is not None and len(yolo_results[0].obb) > 0:
                # Strongest detection. OBB xywhr format: x_center, y_center, width, height, rotation
                best = int(yolo_results[0].obb.conf.argmax())
                detected = True
                detection_confidence = float(yolo_results[0].obb.conf[best])
                box = yolo_results[0].obb.xywhr[best].tolist()
                obb = OBBMetrics(
                    x_center=box[0] / yolo_size,  # normalised to the image YOLO saw
                    y_center=box[1] / yolo_size,
                    width=box[2] / yolo_size,
                    height=box[3] / yolo_size,
                    theta=box[4]
                )
                
    except RuntimeError as re:
        raise re
    except Exception as e:
        traceback.print_exc()
        raise RuntimeError(f"Unexpected error during inference: {e}")
    finally:
        # 3. Aggressive Garbage Collection
        # Explicitly delete massive intermediate tensors to return RAM to the OS
        if 'tensor_data' in locals(): del tensor_data
        if 'forecaster_input' in locals(): del forecaster_input
        if 'yolo_input' in locals(): del yolo_input
        if 'forecaster_output' in locals(): del forecaster_output
        if 'yolo_results' in locals(): del yolo_results
        
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    return InferenceResponse(
        cyclone_id=payload.cyclone_id,
        detected=detected,
        detection_confidence=detection_confidence,
        obb=obb,
        track_delta=track_delta,
        v_max_pred=v_max_pred,
        dp_pred=dp_pred
    )
