import os
import sys
import zlib
import gzip
import hmac
import hashlib
import base64
import json
from datetime import datetime, timezone
from pathlib import Path
import requests
import numpy as np
from dotenv import load_dotenv

# Windows consoles default to cp1252, which cannot print the status emoji below
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Read the shared secret from backend/.env — never hard-code it
load_dotenv(Path(__file__).resolve().parent / "backend" / ".env")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "")
if len(WEBHOOK_SECRET) < 32:
    sys.exit("WEBHOOK_SECRET missing or too short in backend/.env")

# Server Endpoints
FASTAPI_URL = "http://localhost:8000/predict" 
WEBHOOK_URL = "http://localhost:3001/api/v1/webhook/inference"

def run_e2e_tests():
    print("🚀 Starting CYCLO-NEXUS Phase 1 E2E Integration Test...\n")
    
    # ---------------------------------------------------------
    # 1. & 2. Mock Tensor Generation & Compression Guard
    # ---------------------------------------------------------
    print("[Test 1] Generating mock tensor & compressing...")
    shape = (6, 4, 1024, 1024)
    # Real satellite data has spatial coherence and a lot of empty space/zeros.
    # np.random.rand() generates pure high-entropy noise which cannot be compressed,
    # resulting in a 115MB payload. We will generate a sparse matrix simulating a storm.
    dummy_tensor = np.zeros(shape, dtype=np.float32)
    dummy_tensor[:, :, 400:600, 400:600] = np.random.rand(6, 4, 200, 200).astype(np.float32)
    
    tensor_f32 = np.ascontiguousarray(dummy_tensor, dtype=np.float32)
    
    compressed_bytes = zlib.compress(tensor_f32.tobytes(), level=6)
    tensor_b64 = base64.b64encode(compressed_bytes).decode("ascii")
    
    b64_size_mb = len(tensor_b64) / (1024 * 1024)
    print(f"   -> Payload Size: {b64_size_mb:.2f} MB")
    assert b64_size_mb < 35.0, f"Payload exceeded 35 MB HTTP limit! ({b64_size_mb:.2f} MB)"
    print("✅ PASS: Compression size guard.\n")

    # ---------------------------------------------------------
    # 3. FastAPI Inference Test
    # ---------------------------------------------------------
    print("[Test 2] Testing FastAPI Inference Pipeline...")
    inference_payload = {
        "cyclone_id": "TEST-CYCLONE-1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tensor_b64": tensor_b64,
        "tensor_shape": [6, 4, 1024, 1024],
        "tensor_dtype": "float32"
    }
    
    try:
        res = requests.post(FASTAPI_URL, json=inference_payload, timeout=60)
        print(f"   -> Response Status: {res.status_code}")
        assert res.status_code == 200, f"FastAPI failed: {res.text}"
        print("✅ PASS: FastAPI deserialization, reconstruction, and inference.\n")
    except requests.exceptions.ConnectionError:
        print("❌ FAILED: Could not connect to FastAPI at localhost:8000. Is it running?")
        sys.exit(1)

    # ---------------------------------------------------------
    # 4. Express Webhook & HMAC Test
    # ---------------------------------------------------------
    print("[Test 3] Testing Node.js Webhook HMAC & Decompression...")
    mock_webhook_payload = {
        "type": "FeatureCollection",
        "metadata": {
            "payload_version": "1.0.0",
            "cyclone_id": "E2E-TEST-CYCLONE",
            "basin": "NIO",
            "generated_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        },
        # Observation time is deliberately old so this test row never appears
        # in /api/v1/cyclones (which lists only the last 24 h).
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [88.0, 15.0]},
            "properties": {"feature_type": "current_eye", "timestamp": "2000-01-01T00:00:00Z",
                           "sustained_wind_knots": 30.0, "central_pressure_hpa": 1000.0}
        }]
    }
    
    body_bytes = json.dumps(mock_webhook_payload, separators=(',', ':')).encode('utf-8')
    timestamp_str = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    signature = hmac.new(WEBHOOK_SECRET.encode(), timestamp_str.encode() + b"." + body_bytes,
                         hashlib.sha256).hexdigest()
    
    compressed_body = gzip.compress(body_bytes, compresslevel=6)
    headers = {
        "Content-Type": "application/json",
        "Content-Encoding": "gzip",
        "X-CycloNexus-Signature": signature,
        "X-CycloNexus-Timestamp": timestamp_str,
    }
    
    try:
        res = requests.post(WEBHOOK_URL, data=compressed_body, headers=headers)
        print(f"   -> Response Status: {res.status_code}")
        assert res.status_code == 200, f"Node.js Webhook failed: {res.text}"
        print("✅ PASS: Express webhook accepted signed and compressed payload.\n")

        # Replay: same body + signature under a fresh timestamp must be rejected
        replay_headers = dict(headers)
        replay_headers["X-CycloNexus-Timestamp"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        res = requests.post(WEBHOOK_URL, data=compressed_body, headers=replay_headers)
        print(f"   -> Replay with swapped timestamp: {res.status_code}")
        assert res.status_code == 401, f"Replay was not rejected: {res.status_code} {res.text}"
        print("✅ PASS: Timestamp-swapped replay rejected.\n")
    except requests.exceptions.ConnectionError:
        print("❌ FAILED: Could not connect to Express at localhost:3001. Is it running?")
        sys.exit(1)

    # ---------------------------------------------------------
    # 5. Zip Bomb Rejection Test
    # ---------------------------------------------------------
    print("[Test 4] Testing Zip Bomb (DoS) Guards...")
    bomb_headers = {
        "Content-Type": "application/json",
        "Content-Encoding": "gzip",
        "X-CycloNexus-Signature": "fake_signature_doesnt_matter",
        "X-CycloNexus-Timestamp": timestamp_str,
    }

    # Test 4A: The 2MB Wire Limit
    print("   -> Testing 2.5MB uncompressible wire payload...")
    heavy_wire_payload = os.urandom(int(2.5 * 1024 * 1024))
    res1 = requests.post(WEBHOOK_URL, data=heavy_wire_payload, headers=bomb_headers)
    print(f"   -> Response Status: {res1.status_code}")
    assert res1.status_code == 413, "Expected 413 Payload Too Large"
    
    # Test 4B: The 10MB Decompression Memory Trap
    print("   -> Testing 12MB highly compressible payload (Zip Bomb)...")
    zip_bomb = b'\x00' * (12 * 1024 * 1024)
    bomb_compressed = gzip.compress(zip_bomb, compresslevel=9)
    res2 = requests.post(WEBHOOK_URL, data=bomb_compressed, headers=bomb_headers)
    print(f"   -> Response Status: {res2.status_code}")
    assert res2.status_code == 400, "Expected 400 Decompression failed or payload too large"
    
    print("✅ PASS: Both 2MB wire limit and 10MB memory guard successfully blocked the DoS attack.\n")
    print("🎉 ALL PHASE 1 TESTS PASSED SUCCESSFULLY! The architecture is hardened.")

if __name__ == "__main__":
    run_e2e_tests()
