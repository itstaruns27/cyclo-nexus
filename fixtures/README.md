# CYCLO-NEXUS Mock Data Fixtures

> **Owner:** ARCHITECT (initial), Agent ALPHA (maintenance)  
> **Access:** Agent DELTA, Agent ECHO — Read-Only consumers

## Purpose

These fixtures enable Agent DELTA (backend) and Agent ECHO (frontend) to develop the full API and UI **immediately** without waiting for trained model weights from Google Colab.

## Files

| File | Description | Schema Conformance |
|------|-------------|-------------------|
| `mock_cyclone_amphan.json` | GeoJSON FeatureCollection for SuCS AMPHAN | `schemas/geojson_spec.json` |
| `mock_telemetry_timeseries.json` | Full telemetry payload with 6-step history + 5 forecasts | `schemas/telemetry_contract.py` → `CycloneTelemetryPayload` |
| `mock_gemini_bulletin.json` | Gemini Pro advisory bulletin (English) | `GeminiAdvisoryResponse` interface |

## Usage

### Agent DELTA (Backend)
Seed the database from fixtures during development:
```javascript
const mockData = require('../../fixtures/mock_telemetry_timeseries.json');
// Insert into MySQL via cyclone_store.js
```

### Agent ECHO (Frontend)
Import fixtures for component development:
```javascript
import mockGeoJSON from '../../../fixtures/mock_cyclone_amphan.json';
// Feed directly to MapLibre sources and TelemetryPanel
```

## Validation

All fixtures are validated against their corresponding schemas. Any fixture that fails schema validation is a blocking defect.
