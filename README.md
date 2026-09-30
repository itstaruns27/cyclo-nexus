# CYCLO-NEXUS 🌀

> **AI-Driven Multimodal Tropical Cyclone Detection, Classification & Trajectory Forecasting Platform**  
> Smart India Hackathon (SIH)

## Architecture Overview

CYCLO-NEXUS synthesizes multi-spectral satellite imagery (INSAT-3D/3DR, Himawari-8/9, NASA GPM) with physics-constrained deep learning to deliver sub-hourly cyclone intelligence for the North Indian Ocean basin.

### System Topology

```
┌─────────────────────────┐     ┌──────────────────────────┐
│   Google Colab (T4 GPU) │     │   Hostinger Node.js API  │
│                         │     │                          │
│  YOLO-OBB Detection     │────▶│  Webhook Receiver        │
│  ConvLSTM Forecaster    │     │  MySQL Datastore         │
│  Grad-CAM XAI           │     │  Gemini Advisory Engine  │
└─────────────────────────┘     └──────────┬───────────────┘
                                           │
                                           ▼
                                ┌──────────────────────────┐
                                │  React PWA (Vite)        │
                                │  MapLibre GL             │
                                │  9-Language i18next      │
                                │  Offline-First           │
                                └──────────────────────────┘
```

### Key Technologies

| Layer | Stack |
|-------|-------|
| **Data Ingestion** | Python, h5py, rasterio, netCDF4 |
| **Vision** | Ultralytics YOLO-OBB, PyTorch |
| **Forecasting** | ConvLSTM, Bi-GRU, Atkinson-Holliday physics loss |
| **Backend** | Express.js, MySQL, HMAC-SHA256 webhooks |
| **Frontend** | Vite + React + Tailwind CSS + MapLibre GL |
| **Advisory** | Google Gemini Pro API |

## Monorepo Structure

```
schemas/           Shared data contracts (Pydantic, JSON Schema, TypeScript)
fixtures/          Mock data for development without model weights
data_pipeline/     Agent ALPHA: Satellite data ingestion & preprocessing
vision/            Agent BRAVO: YOLO-OBB cyclone eye detection
forecaster/        Agent CHARLIE: ConvLSTM trajectory forecasting
colab_notebooks/   Google Colab training & inference notebooks
backend/           Agent DELTA: Express.js API gateway
frontend/          Agent ECHO: React PWA dashboard
docs/              Architecture & deployment documentation
```

## Quick Start

### Backend
```bash
cd backend && npm install && npm run dev
```

### Frontend
```bash
cd frontend && npm install && npm run dev
```

## Documentation

- [Architecture Blueprint](docs/architecture.md)
- [Agent Guardrails](docs/agent_guardrails.md)
- [API Reference](docs/api_reference.md)
- [Deployment Guide](docs/deployment_guide.md)

## License

Built for Smart India Hackathon. All rights reserved.
