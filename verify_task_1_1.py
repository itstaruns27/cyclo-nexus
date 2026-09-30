"""Verification Task 1.1 — tensor zlib + base64 round-trip (standalone, no torch/FastAPI needed)."""
import base64
import sys
import zlib
from pathlib import Path

import numpy as np

sys.path.append(str(Path(__file__).resolve().parent))
from inference.schemas import InferenceRequest

SHAPE = (6, 4, 1024, 1024)
EXPECTED_BYTES = 6 * 4 * 1024 * 1024 * 4
assert EXPECTED_BYTES == 100663296

# Encode (mirrors live_pipeline_runner.py) — static, repetitive data
tensor_f32 = np.ascontiguousarray(np.ones(SHAPE, dtype=np.float32) * 250.0)
tensor_b64 = base64.b64encode(zlib.compress(tensor_f32.tobytes(), level=6)).decode("ascii")
b64_mb = len(tensor_b64) / (1024 * 1024)
print(f"Raw tensor:     {tensor_f32.nbytes / 1024 / 1024:.2f} MB")
print(f"Base64 payload: {b64_mb:.4f} MB")
assert b64_mb < 35, "FAIL: payload exceeds 35 MB"

# Schema guard accepts the valid payload...
InferenceRequest(cyclone_id="TEST-001", timestamp="2026-09-29T00:00:00Z",
                 tensor_b64=tensor_b64, tensor_shape=list(SHAPE), tensor_dtype="float32")
# ...and rejects a bad shape/dtype
try:
    InferenceRequest(cyclone_id="TEST-001", timestamp="2026-09-29T00:00:00Z",
                     tensor_b64="x", tensor_shape=[1, 1], tensor_dtype="float64")
    raise AssertionError("FAIL: schema accepted bad shape/dtype")
except ValueError as e:  # pydantic.ValidationError subclasses ValueError
    print(f"Schema guard rejected bad payload ({len(e.errors())} errors) - OK")

# Decode (mirrors serve.py /predict)
raw = zlib.decompress(base64.b64decode(tensor_b64))
assert len(raw) == EXPECTED_BYTES, f"FAIL: byte length {len(raw)} != {EXPECTED_BYTES}"
restored = np.frombuffer(raw, dtype=np.float32).reshape(SHAPE)
assert np.array_equal(restored, tensor_f32), "FAIL: round-trip mismatch"

print(f"Byte guard OK ({len(raw)} bytes), round-trip identical, shape {restored.shape}")
print("VERIFICATION 1.1: PASS")
