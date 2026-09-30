# CYCLO-NEXUS API Reference

> **Owner:** Agent DELTA  
> **Base URL:** `https://<hostinger-domain>/api/v1`

## Authentication

Webhook endpoints require HMAC-SHA256 signature. See [api_webhook_contract.md](../schemas/api_webhook_contract.md).

## Endpoints

### Health Check
```
GET /api/v1/health
```
**Response:** `{ success: true, status: "healthy", version: "1.0.0" }`

---

### Webhook — Receive Inference Payload
```
POST /api/v1/webhook/inference
Headers: X-CycloNexus-Signature, X-CycloNexus-Timestamp, X-CycloNexus-Version
Body: GeoJSON FeatureCollection (schemas/geojson_spec.json)
```
**Response:** `200 OK` or `401 Unauthorized` or `400 Bad Request`

---

### List Active Cyclones
```
GET /api/v1/cyclones
```
**Response:** `{ success: true, data: CycloneListItem[], cached: boolean }`

---

### Get Cyclone Details
```
GET /api/v1/cyclones/:id
```
**Response:** `{ success: true, data: CycloneTelemetryPayload, cached: boolean }`

---

### Get Forecast GeoJSON
```
GET /api/v1/cyclones/:id/forecast
```
**Response:** GeoJSON FeatureCollection with track, cone, and Grad-CAM features.

---

### Get Advisory Bulletin
```
GET /api/v1/cyclones/:id/advisory?lang=en
```
**Parameters:** `lang` — ISO 639-1 code (en, hi, bn, or, ta, te, ml, mr, gu)

**Response:** `{ success: true, data: GeminiAdvisoryResponse }`
