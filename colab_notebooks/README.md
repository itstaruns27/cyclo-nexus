# CYCLO-NEXUS Colab Notebooks

> **Owners:** Agent BRAVO (02-03), Agent CHARLIE (04-06)  
> **Runtime:** Google Colab (free T4 GPU tier)

## Setup

1. Mount Google Drive:
```python
from google.colab import drive
drive.mount('/content/drive')
```

2. Standard base path:
```python
BASE = "/content/drive/MyDrive/cyclo-nexus"
```

3. Directory structure on Drive:
```
/content/drive/MyDrive/cyclo-nexus/
├── data/
│   ├── raw/              # HDF5, NetCDF, CSV downloads
│   ├── processed/        # Reprojected, calibrated rasters
│   ├── tensors/          # Assembled (4, 1024, 1024) tensors
│   ├── sequences/        # 6-step temporal matrices
│   ├── besttrack/        # IMD Best Track Parquet files
│   └── yolo_obb/         # YOLO-OBB dataset (images + labels)
├── models/
│   ├── vision/           # YOLO-OBB trained weights (.pt)
│   └── forecaster/       # ConvLSTM/BiGRU weights (.pt)
├── outputs/
│   ├── inference/        # GeoJSON payloads for webhook
│   └── gradcam/          # Grad-CAM heatmap images (.webp)
└── configs/              # Cloned from repo vision/config/ & forecaster/config.py
```

## Notebooks

| # | Name | Agent | Purpose |
|---|------|-------|---------|
| 01 | Data Preparation | ALPHA | Orchestrate ingestion pipeline |
| 02 | YOLO-OBB Train | BRAVO | Train 4ch OBB model on T4 |
| 03 | YOLO-OBB Inference | BRAVO | Run detection → GeoJSON |
| 04 | Forecaster Train | CHARLIE | Train ConvLSTM/Bi-GRU |
| 05 | Forecaster Inference | CHARLIE | Run forecast → GeoJSON |
| 06 | Grad-CAM Export | CHARLIE | Generate XAI heatmaps |
| 07 | Webhook Dispatcher | SHARED | POST results to Hostinger |

## Webhook Dispatch

Notebook 07 uses `schemas/api_webhook_contract.md` protocol:
```python
import hmac, hashlib, gzip, json, requests

payload = json.dumps(geojson_result, separators=(",", ":")).encode()
sig = hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
compressed = gzip.compress(payload)

requests.post(WEBHOOK_URL, data=compressed, headers={
    "Content-Type": "application/json",
    "Content-Encoding": "gzip",
    "X-CycloNexus-Signature": sig,
    "X-CycloNexus-Version": "1.0.0",
    "X-CycloNexus-Timestamp": datetime.utcnow().isoformat() + "Z",
})
```
