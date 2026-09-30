# CYCLO-NEXUS: Detailed System Documentation
# Phase-Wise Architectural Manual

> **Project:** CYCLO-NEXUS — AI-Driven Multimodal Tropical Cyclone Detection, Classification, and Trajectory Forecasting Platform  
> **Author:** Principal Systems Auditor  
> **Version:** 1.0  
> **Audit Date:** 2026-09-21  
> **Build Status:** ✅ All 5 Phases Complete & Verified

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Phase 1: Data Engineering](#2-phase-1-data-engineering)
3. [Phase 2: Computer Vision](#3-phase-2-computer-vision)
4. [Phase 3: Trajectory Forecasting](#4-phase-3-trajectory-forecasting)
5. [Phase 4: Backend API Gateway](#5-phase-4-backend-api-gateway)
6. [Phase 5: Frontend PWA](#6-phase-5-frontend-pwa)
7. [Inter-Phase Data Flow Contracts](#7-inter-phase-data-flow-contracts)
8. [Testing Coverage Summary](#8-testing-coverage-summary)

---

## 1. System Architecture Overview

### High-Level End-to-End Data Flow

```
MOSDAC / INSAT-3D Satellites
    │
    │  Raw HDF5 / NetCDF files (multi-spectral)
    ▼
┌───────────────────────────────────┐
│         PHASE 1: DATA PIPELINE    │
│  GeospatialReprojector            │
│  TensorAssembler                  │
│  → 4-channel tensor (4,1024,1024) │
│  → Float32, normalized [0.0, 1.0] │
└──────────────────┬────────────────┘
                   │
    ┌──────────────▼────────────────┐
    │      PHASE 2: VISION          │
    │  OBBAnnotationGenerator       │
    │  YOLO4ChannelSurgery          │
    │  PhysicsAwareAugmenter        │
    │  IMDClassificationHead        │
    │  EyeDiameterEstimator         │
    │  → YOLO-OBB predictions       │
    │  → IMD class, v_max, eye_diam │
    └──────────────┬────────────────┘
                   │
    ┌──────────────▼────────────────┐
    │      PHASE 3: FORECASTING     │
    │  TemporalMatrixBuilder        │
    │  CycloneForecaster            │
    │  CycloneGradCAM               │
    │  → track_delta (dx, dy)       │
    │  → v_max_pred, dp_pred        │
    │  → 1024×1024 XAI heatmap      │
    └──────────────┬────────────────┘
                   │ HMAC-secured HTTP POST
    ┌──────────────▼────────────────┐
    │     PHASE 4: BACKEND API      │
    │  Express / HMAC Webhook       │
    │  MySQL: cyclones, advisories  │
    │  Gemini Advisory Engine       │
    │  REST API: /api/cyclones/…    │
    └──────────────┬────────────────┘
                   │ HTTPS REST JSON
    ┌──────────────▼────────────────┐
    │      PHASE 5: FRONTEND PWA    │
    │  useCycloneData hook          │
    │  MapLibre GL (CycloneMap)     │
    │  AdvisoryPanel                │
    │  DashboardShell               │
    │  → Interactive dark-mode map  │
    │  → Multilingual advisories    │
    └───────────────────────────────┘
```

### Agent Responsibility Matrix

| Agent | Phase | Domain | Permitted Directories |
|---|---|---|---|
| ALPHA | 1 | Data Ingestion & Pipeline | `data_pipeline/`, `colab_notebooks/01*` |
| BRAVO | 2 | Computer Vision & OBB | `vision/`, `colab_notebooks/02*`, `03*` |
| CHARLIE | 3 | Spatiotemporal Forecasting | `forecaster/`, `colab_notebooks/04*-06*` |
| DELTA | 4 | Backend Gateway & DB | `backend/` |
| ECHO | 5 | Frontend PWA | `frontend/` |

---

## 2. Phase 1: Data Engineering

**Owner:** Agent ALPHA  
**Implementation File:** [`data_pipeline/preprocessing/tensor_assembler.py`](../data_pipeline/preprocessing/tensor_assembler.py)

### 2.1 Multi-Sensor Tensor Fusion

The `TensorAssembler` class is the single transformation boundary between raw satellite swath data and the AI model's expected input format.

#### Input Sources

| Channel | Sensor | Physical Quantity | Physical Bounds |
|---|---|---|---|
| 0 | INSAT-3D TIR-1 | Brightness Temperature | 180 K – 320 K |
| 1 | INSAT-3D Water Vapor (WV) | Water Vapor Brightness Temp | 180 K – 320 K |
| 2 | Derived (TIR-1 − TIR-2) | Split-Window Difference | −10 K – +10 K |
| 3 | GPM IMERG | Precipitation Rate | 0.0 – 100.0 mm/hr |

**Thermodynamic Basis for Channel 2:** The split-window difference is a classical atmospheric physics technique. The differential absorption of water vapor between the two thermal infrared bands creates a signal directly correlated with total precipitable water (TPW) and atmospheric opacity within the cyclone's CDO.

#### Normalization Pipeline

The normalization protocol applies per-channel, physics-motivated Min-Max scaling:

```
normalized = clip(array, vmin, vmax) - vmin
             ─────────────────────────────
                     vmax - vmin
```

**Verified:** The output of `normalize_channel` is explicitly cast via `.astype(np.float32)`, ensuring all channels are bounded `[0.0, 1.0]` in 32-bit floating point.

### 2.2 Geospatial Reprojection Constraints

The `GeospatialReprojector` enforces a fixed spatial domain:

| Parameter | Value |
|---|---|
| Grid Resolution | 1024 × 1024 pixels |
| Projection | EPSG:4326 (WGS-84 geographic) |
| Latitude Bounds | 0.0°N – 32.0°N |
| Longitude Bounds | 50.0°E – 102.0°E |

The bounding box is applied uniformly to all source arrays, regardless of their native spatial resolution, ensuring all four channels are perfectly pixel-aligned before stacking into the `(4, 1024, 1024)` output tensor.

**Output Shape Contract:** `np.ndarray` of shape `(4, 1024, 1024)`, dtype `float32`, values strictly in `[0.0, 1.0]`.

---

## 3. Phase 2: Computer Vision

**Owner:** Agent BRAVO  
**Implementation Files:**
- [`vision/preprocessing/obb_annotator.py`](../vision/preprocessing/obb_annotator.py)
- [`vision/models/yolo_4ch_adapter.py`](../vision/models/yolo_4ch_adapter.py)
- [`vision/preprocessing/physics_aware_augment.py`](../vision/preprocessing/physics_aware_augment.py)
- [`vision/models/cyclone_metrics.py`](../vision/models/cyclone_metrics.py)

### 3.1 OBB Annotation System

#### Label Format

```
class_id  x_center  y_center  width  height  θ
```

- **class_id**: Integer [0, 6] mapping to the 7-tier IMD intensity scale.
- **x_center, y_center**: Normalized pixel coordinates in [0.0, 1.0].
- **width, height**: Normalized CDO bounding box dimensions in [0.0, 1.0].
- **θ (theta)**: Spiral-band tilt angle in radians, bounded in `[-π/2, π/2)`.

#### IMD Class Map

| class_id | Category | Description |
|---|---|---|
| 0 | D | Depression |
| 1 | DD | Deep Depression |
| 2 | CS | Cyclonic Storm |
| 3 | SCS | Severe Cyclonic Storm |
| 4 | VSCS | Very Severe Cyclonic Storm |
| 5 | ESCS | Extremely Severe Cyclonic Storm |
| 6 | SuCS | Super Cyclonic Storm |

#### Coordinate Projection Formula

The geo-to-pixel transformation correctly inverts latitude to match the image-space top-left origin:

```
x_norm = (lon - 50.0) / (102.0 - 50.0)
y_norm = (32.0 - lat) / (32.0 - 0.0)
```

#### CDO Dimension Heuristic

Wind speed and CDO size have an inverse relationship. Intense cyclones have compact, axisymmetric eyes. The heuristic linearly interpolates:

- 17 kt (Depression threshold) → 0.25 normalized width
- 120 kt (Super Cyclone regime) → 0.08 normalized width

Width is scaled ×1.1 relative to height to capture the CDO asymmetry typical of translating cyclones.

#### Theta Wrapping

Theta is continuously clamped to `[-π/2, π/2)` with w/h dimension swapping at every π/2 boundary crossing.

### 3.2 YOLO 4-Channel Weight Surgery

The pre-trained YOLO backbone expects 3-channel RGB inputs. CYCLO-NEXUS requires 4-channel multi-spectral input. The `YOLO4ChannelSurgery` module performs deterministic surgical weight transplantation:

#### Surgery Protocol

1. Clone all Conv2d hyperparameters (kernel_size, stride, padding, groups, dilation).
2. Create a new `Conv2d(in_channels=4)`.
3. **Channels 0–2:** Exact verbatim copy from pre-trained weights (preserves all ImageNet features).
4. **Channel 3 (GPM):** Initialized as the mean of channels 0–2 via `torch.mean(..., dim=1, keepdim=True)`. This preserves gradient scale, preventing training instability from large weight disparities.
5. Copy bias tensor unchanged (bias is per-output-channel, not per-input).

**Key Invariant:** All weight operations occur inside `torch.no_grad()` blocks, preventing spurious autograd graph construction during surgery.

### 3.3 Coriolis-Safe Physics Augmentation

The `PhysicsAwareAugmenter` enforces the fundamental Coriolis constraint of the Northern Hemisphere:

> **Horizontal and vertical flips are strictly forbidden.** A horizontal flip would invert the cyclone's rotation from CCW (physically correct for NIO) to CW, producing a physically impossible training sample that would corrupt the model's learned spiral-band dynamics.

**Permitted Augmentation:** Rotation only, in range `[-180°, +180°]`.

#### Tensor-Label Synchronization

A critical design decision ensures the tensor rotation and OBB label rotation remain mathematically consistent:

- `F.rotate` with a positive angle rotates **CCW** in image space.
- Our label rotation math is **CW** in image space.
- Therefore, `F.rotate(tensor, -angle_degrees)` is called. The negation synchronizes the two coordinate systems, preventing coordinate drift between the image and its label.

#### Theta Wrapping in Label Rotation

```python
while new_theta >= math.pi / 2:
    new_theta -= math.pi / 2
    w, h = h, w       # swap dimensions at each quadrant boundary
while new_theta < -math.pi / 2:
    new_theta += math.pi / 2
    w, h = h, w
```

### 3.4 IMD Classification & Eye Diameter Metrics

#### Eye Diameter Heuristic

The `EyeDiameterEstimator` computes physical scale using the derived grid resolution:

```
Grid: 1024 px covers 32° latitude
32° × 111 km/° = 3552 km total
3552 km / 1024 px = 3.46875 km/px   ← KM_PER_PIXEL constant
```

The calculation applies only for class_id ≥ 3 (SCS and above), as low-intensity systems (D, DD, CS) lack well-defined eyes:

```
eye_diameter_km = min(width_norm, height_norm) × 1024 × 3.46875 × 0.15
```

The `0.15` coefficient encodes the meteorological heuristic that the eye diameter is approximately 15% of the Cold Dense Overcast (CDO) minor axis.

---

## 4. Phase 3: Trajectory Forecasting

**Owner:** Agent CHARLIE  
**Implementation Files:**
- [`forecaster/data/temporal_matrix_builder.py`](../forecaster/data/temporal_matrix_builder.py)
- [`forecaster/models/spatiotemporal_forecaster.py`](../forecaster/models/spatiotemporal_forecaster.py)
- [`forecaster/models/gradcam_generator.py`](../forecaster/models/gradcam_generator.py)

### 4.1 Spatiotemporal Matrix Builder & Leakage Validator

#### Filename Convention

Tensors must follow the naming pattern:
```
INSAT3D_L1C_YYYYMMDD_HHMMSS.npy
```

The `TemporalMatrixBuilder.extract_datetime()` uses a strict regex to parse dates from filenames, raising `ValueError` on any non-conforming input.

#### Sliding Window Pipeline

```
1. Sort all file paths chronologically (prevents leakage)
2. Generate sliding windows of width = seq_length (default 6)
3. Validate each window through LeakageValidator
4. Stack validated tensors into (seq_length, 4, 1024, 1024) tensors
```

#### Leakage Validation — The `SequenceLeakageError`

The `LeakageValidator` enforces two hard constraints before any window can enter the forecasting model:

1. **Sort Invariant:** The timestamps within a window must be strictly ascending.
2. **30-Minute Continuity:** Every consecutive pair must differ by **exactly** `timedelta(minutes=30)`. This corresponds to INSAT-3D's standard 30-minute imaging cadence.

**Scientific rationale:** A time gap invalidates the momentum continuity assumptions of the ConvLSTM (which tracks vortex spatial displacement per 30-min interval). An out-of-order window would cause the model to learn physically impossible backward-in-time translations.

### 4.2 ConvLSTM + Bi-GRU Spatiotemporal Forecaster

#### Architecture Diagram

```
Input: (B, Seq=6, C=4, H=1024, W=1024)
           │
           │ view(B×Seq, 4, 1024, 1024)
           ▼
┌─────────────────────────────────────┐
│   SPATIAL DOWNSAMPLING STEM (CNN)   │
│   Conv2d(4→16) + ReLU + MaxPool2    │  1024 → 512
│   Conv2d(16→32) + ReLU + MaxPool2   │  512  → 256
│   Conv2d(32→64) + ReLU + MaxPool2   │  256  → 128
│   Conv2d(64→64) + ReLU + MaxPool2   │  128  → 64
└───────────────────┬─────────────────┘
                    │ view(B, Seq, 64, 64, 64)
                    ▼
┌─────────────────────────────────────┐
│        ConvLSTMCell (×Seq)          │
│   Gates: I, F, O, G (via Conv2d)   │
│   State: h_t, c_t of shape          │
│          (B, 64, 64, 64)            │
└───────────────────┬─────────────────┘
                    │ AdaptiveAvgPool2d(1)
                    │ view(B, Seq, 64)
                    ▼
┌─────────────────────────────────────┐
│   Bi-GRU (hidden=128, bidirectional)│
│   Output: (B, Seq, 256)             │
└───────────────────┬─────────────────┘
                    │ final_out = gru_out[:, -1, :]
                    ▼
┌─────────────────────────────────────┐
│   Multi-Task Output Heads           │
│   track_head(256→2): dx, dy offset  │
│   v_max_head(256→1): wind intensity │
│   dp_head(256→1): pressure drop     │
└─────────────────────────────────────┘
```

#### VRAM OOM Prevention: The CNN Stem

**Critical Design Constraint:** Without the downsampling stem, feeding a 5D tensor `(B, Seq, 4, 1024, 1024)` frame-by-frame into a ConvLSTM would attempt to maintain hidden states of shape `(B, 64, 1024, 1024)`. For a batch of 4 sequences, this is `4 × 64 × 1024 × 1024 × 4 bytes ≈ 1 GB` per hidden state tensor — instantly exhausting VRAM.

The four-layer stem reduces the spatial footprint from `1024×1024` → `64×64` (a 256× area reduction) before entering the recurrent loop.

**Implementation:** Rather than looping over each temporal step individually, the stem processes the entire sequence batch-efficiently by first reshaping `(B, Seq, C, H, W)` → `(B×Seq, C, H, W)`, processing all frames in a single forward pass through the shared weights, then reshaping back to `(B, Seq, F_c, H', W')`.

#### ConvLSTMCell Design

Replaces the standard matrix multiplication in LSTM gates with `Conv2d` operations:

```python
combined = torch.cat([x, h_prev], dim=1)  # Channel-wise concat
gates = self.conv(combined)               # Single Conv2d for all 4 gates
i, f, o, g = torch.split(gates, hidden_channels, dim=1)
c_next = sigmoid(f) * c_prev + sigmoid(i) * tanh(g)
h_next = sigmoid(o) * tanh(c_next)
```

This preserves 2D spatial topology across time steps, allowing the model to track the vortex's translational dynamics rather than collapsing them into a 1D feature vector.

### 4.3 Grad-CAM Visual Explainability Engine

#### Mathematical Formulation

Grad-CAM (Gradient-weighted Class Activation Mapping) is implemented natively using PyTorch hooks:

**Step 1 — Forward Pass (Activation Capture):**
```python
register_forward_hook → self.activations = A^k  # (B, K, h, w)
```

**Step 2 — Backward Pass (Gradient Capture):**
```python
register_full_backward_hook → self.gradients = ∂score/∂A^k  # (B, K, h, w)
```

**Step 3 — Neuron Importance Weights (Global Average Pooling):**
```
α_k = (1/Z) × Σ_{i,j} [∂score / ∂A^k_{ij}]
```

**Step 4 — Weighted Activation Combination:**
```
L^c = ReLU(Σ_k α_k × A^k)
```
The ReLU isolates features that **positively** contribute to the prediction, discarding negative suppressors.

**Step 5 — Spatial Upsampling:**
```
L_resized = bilinear_interpolate(L^c, target=(1024, 1024))
```

**Step 6 — Normalization:**
```
heatmap = (L_resized - L_min) / (L_max - L_min)  ∈ [0.0, 1.0]
```

**Dependency Constraint:** `pytorch-grad-cam` and all external XAI libraries are explicitly excluded. The implementation relies solely on `torch.nn.Module.register_forward_hook` and `register_full_backward_hook` from PyTorch's native API.

The `1024×1024` normalized heatmap is returned as a NumPy array aligned with the original satellite tensor, making it directly overlayable on the MapLibre frontend map.

---

## 5. Phase 4: Backend API Gateway

**Owner:** Agent DELTA  
**Implementation Files:**
- [`backend/utils/hmac.js`](../backend/utils/hmac.js)
- [`backend/webhook.js`](../backend/webhook.js)
- [`backend/services/gemini_advisory.js`](../backend/services/gemini_advisory.js)
- [`backend/server.js`](../backend/server.js)
- [`backend/routes/api.js`](../backend/routes/api.js)
- [`backend/db/schema.sql`](../backend/db/schema.sql)

### 5.1 HMAC Webhook Security Layer

#### Security Protocol

Incoming inference payloads from Google Colab are authenticated using HMAC-SHA256 signatures sent in the `x-signature-256` HTTP header.

**Failure Modes:**
- **Missing header:** `401 Unauthorized`
- **Signature mismatch:** `403 Forbidden`

#### Raw Buffer Interception

The most critical security implementation detail: HMAC must be computed over the **exact raw byte sequence** transmitted over the network. JSON parsing by Express can alter whitespace, key ordering, or encoding — any change would invalidate a legitimate signature.

```javascript
app.use(express.json({
  verify: (req, res, buf) => {
    req.rawBody = buf.toString('utf8');  // Captured before any parsing
  }
}));
```

The `verifyHMAC` middleware then operates on `req.rawBody`, not `req.body`.

#### Timing-Safe Comparison

```javascript
crypto.timingSafeEqual(expectedBuffer, providedBuffer)
```

Standard string comparison (`===`) leaks timing information proportional to the length of the common prefix, enabling signature enumeration attacks. `crypto.timingSafeEqual` executes in constant time regardless of where the first differing byte occurs, rendering timing attacks computationally infeasible.

#### Prefix Support

The middleware transparently handles both bare hex signatures and `sha256=`-prefixed signatures (GitHub-style):

```javascript
const providedSignature = signature.startsWith('sha256=')
  ? signature.slice(7)
  : signature;
```

### 5.2 Production Server — Security Middleware Stack

The Express server initializes security layers in a strict order:

```
1. helmet()              — HTTP security headers (CSP, DNS prefetch, XSS filter)
2. cors()                — Cross-origin policy for React frontend domain
3. rateLimit(100/15min)  — DDoS / brute-force protection for Gemini API calls
4. express.json(verify)  — Body parsing with rawBody capture for HMAC
5. /api  → apiRouter     — REST endpoints
6. /webhook → webhook    — Secured ingest endpoint
```

**DDoS Mitigation:** The rate limiter (max 100 req / 15 min) specifically protects the `/api/cyclones/:id/advisories` endpoint, which triggers Gemini API invocations. Without limiting, an adversary could exhaust Gemini API quota and incur unbounded costs.

### 5.3 MySQL Database Schema

```sql
TABLE cyclones:
  id VARCHAR(36) PRIMARY KEY
  name VARCHAR(255)
  center_lat DECIMAL(9, 6)
  center_lon DECIMAL(9, 6)
  v_max_knots FLOAT
  imd_category VARCHAR(50)
  timestamp DATETIME

TABLE advisories:
  id VARCHAR(36) PRIMARY KEY
  cyclone_id VARCHAR(36) → cyclones(id) ON DELETE CASCADE
  language VARCHAR(10)         -- e.g. 'hi-IN', 'en-US'
  content TEXT
  issued_at DATETIME
```

The `ON DELETE CASCADE` foreign key constraint ensures orphaned advisories are cleaned up when a cyclone record is removed.

### 5.4 Gemini Advisory Engine

#### Model & Prompt Configuration

| Parameter | Value | Rationale |
|---|---|---|
| Model | `gemini-2.5-pro` | Strongest multilingual NLU for regional language accuracy |
| Temperature | `0.2` | Near-deterministic output to prevent hallucinated coordinates or intensity values in critical safety advisories |

#### System Instruction (Anti-Hallucination Framework)

The system instruction establishes a strict operational identity and data grounding directive:

```
You are an official system acting on behalf of a National Disaster Management Authority.
Your task is to ingest technical cyclone telemetry and output a concise, actionable, 
and localized public safety warning.
The advisory MUST be translated into the following locale/language: {targetLanguage}.
Do not hallucinate data. Base all intensity and location warnings strictly on the 
provided JSON telemetry.
```

The cyclone telemetry JSON is embedded directly into the user prompt, ensuring the model's output is grounded in verified backend data rather than parametric knowledge.

### 5.5 REST API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/cyclones/latest` | GET | Returns current active cyclone telemetry array |
| `/api/cyclones/:id/advisories` | GET | Returns localized Gemini advisories for a cyclone |
| `/webhook/ingest` | POST | Secured ingest for Colab inference payloads (HMAC required) |

---

## 6. Phase 5: Frontend PWA

**Owner:** Agent ECHO  
**Implementation Files:**
- [`frontend/src/components/CycloneMap.jsx`](../frontend/src/components/CycloneMap.jsx)
- [`frontend/src/components/DashboardShell.jsx`](../frontend/src/components/DashboardShell.jsx)
- [`frontend/src/components/AdvisoryPanel.jsx`](../frontend/src/components/AdvisoryPanel.jsx)
- [`frontend/src/hooks/useCycloneData.js`](../frontend/src/hooks/useCycloneData.js)

### 6.1 MapLibre GL Integration

#### Dependency Constraint

**Google Maps and Leaflet are strictly forbidden.** The system uses `maplibre-gl`, an open-source fork of Mapbox GL JS with no commercial API key requirements.

#### Map Configuration

| Parameter | Value | Rationale |
|---|---|---|
| Base Tiles | CartoDB Dark Matter (`basemaps.cartocdn.com`) | Free, open-source, dark mode for professional command-center aesthetics |
| Default Center | `[85.0, 15.0]` (lng, lat) | Geographically optimal for Bay of Bengal / Arabian Sea coverage |
| Zoom Level | 4 | Sufficient to see the entire NIO basin |

Note: MapLibre uses `[longitude, latitude]` ordering, opposite to standard geographic convention. All coordinate feeds from the backend must swap to `[center_lon, center_lat]`.

#### WebGL Context Lifecycle Management

```javascript
useEffect(() => {
  if (map.current) return;         // Prevent double-init in React Strict Mode
  
  map.current = new maplibregl.Map({...});
  
  return () => {                   // Cleanup on unmount
    if (map.current) {
      map.current.remove();        // Destroys the WebGL context
      map.current = null;          // Clears the ref
    }
  };
}, []);
```

Failure to call `.remove()` on unmount leaves the WebGL context open and consuming GPU memory. In a long-running PWA, this would cause progressive memory leakage.

#### `map.on('load')` GeoJSON Injection

**Critical Constraint:** Sources and layers must only be added **after** the base map style is fully parsed:

```javascript
map.current.on('load', () => {
  map.current.addSource('cyclone-path', { type: 'geojson', data: {...} });
  map.current.addLayer({ id: 'cyclone-line', type: 'line', ... });
  map.current.addLayer({ id: 'cyclone-point', type: 'circle', ... });
});
```

Attempting to add a source before the `'load'` event fires causes a fatal WebGL renderer crash. The second `useEffect` (which reacts to data changes) handles the race condition by checking `map.current.isStyleLoaded()` before calling `source.setData()`, and falls back to `map.current.once('load', updateData)` if the style is not yet loaded.

### 6.2 Vector Layer Rendering

Two layers are rendered for each active cyclone:

| Layer ID | Type | Purpose |
|---|---|---|
| `cyclone-line` | `line` | Dashed red trajectory path |
| `cyclone-point` | `circle` | Precise eye location marker |

The `setData()` method on the GeoJSON source allows seamless hot-updating of cyclone coordinates without re-adding layers, enabling real-time telemetry streaming without flickering.

When new data arrives, the map automatically triggers a cinematic `flyTo()` animation:
```javascript
map.current.flyTo({ center: [lon, lat], zoom: 5, speed: 0.8 });
```

### 6.3 Native Fetch Data Hook

The `useCycloneData` hook is deliberately dependency-free:

```javascript
// ✅ CORRECT — native browser API
const resCyclone = await fetch(`${API_BASE}/cyclones/latest`);

// ❌ PROHIBITED — would add ~50KB to bundle
import axios from 'axios';
```

**Rationale:** Disaster response scenarios often involve degraded network conditions (poor bandwidth, high latency). Keeping the PWA bundle minimal is a direct mission requirement.

#### Data Cascade Pattern

```
1. fetch /cyclones/latest → setCyclone(data[0])
2. fetch /cyclones/{id}/advisories → setAdvisories(data)
3. Error: setError(msg) → rendered in AdvisoryPanel
4. Finally: setLoading(false) → removes skeleton state
```

### 6.4 Dashboard Shell Layout

The `DashboardShell` implements a strict 30/70 responsive layout:

```
┌────────────────┬──────────────────────────────────────┐
│  LEFT PANEL    │                                      │
│  (30% width)   │         MAPLIBRE GL MAP              │
│                │         (70% width)                  │
│  Telemetry     │                                      │
│  Advisories    │  ← GeoJSON vector layers             │
│                │  ← Real-time coordinate tracking     │
└────────────────┴──────────────────────────────────────┘
```

The map `div` uses `position: absolute` with `top/bottom/left/right: 0` to ensure the WebGL canvas fills 100% of its flex container without overflow issues.

---

## 7. Inter-Phase Data Flow Contracts

### Phase 1 → Phase 2 Contract

| Property | Requirement |
|---|---|
| Shape | `(4, 1024, 1024)` |
| dtype | `float32` |
| Value range | `[0.0, 1.0]` |
| Projection | EPSG:4326, bbox `(0°N–32°N, 50°E–102°E)` |

### Phase 2 → Phase 3 Contract

| Property | Requirement |
|---|---|
| Tensor sequence | `(seq_length, 4, 1024, 1024)` |
| Temporal spacing | Exactly 30 minutes between frames |
| Sort order | Strictly ascending chronological |
| Label format | YOLO-OBB 6-tuple: `(class_id, x_c, y_c, w, h, θ)` |

### Phase 3 → Phase 4 Contract (Webhook)

| Property | Requirement |
|---|---|
| Protocol | HTTP POST |
| Payload | JSON (GeoJSON FeatureCollection) |
| Authentication | HMAC-SHA256 in `x-signature-256` header |
| Signature | Over raw UTF-8 body bytes |

### Phase 4 → Phase 5 Contract (REST API)

| Endpoint | Response Schema |
|---|---|
| `/api/cyclones/latest` | `[{id, name, center_lat, center_lon, v_max_knots, imd_category, timestamp}]` |
| `/api/cyclones/:id/advisories` | `[{id, cyclone_id, language, content, issued_at}]` |

---

## 8. Testing Coverage Summary

### Python Regression Suite (pytest)

| Module | Tests | Status |
|---|---|---|
| Data Pipeline (Reprojector, TensorAssembler) | 34 | ✅ Pass |
| OBB Annotator (Task 6) | 29 | ✅ Pass |
| YOLO 4ch Adapter (Task 7) | 17 | ✅ Pass |
| Physics Augmenter (Task 8) | 5 | ✅ Pass |
| Cyclone Metrics Head (Task 9) | 5 | ✅ Pass |
| Temporal Matrix Builder (Task 10) | 5 | ✅ Pass |
| Spatiotemporal Forecaster (Task 11) | 2 | ✅ Pass |
| Grad-CAM Engine (Task 13) | 2 | ✅ Pass |
| **Total** | **99** | **✅ 0 Failures** |

### Node.js Test Suite (jest)

| Module | Tests | Status |
|---|---|---|
| HMAC Webhook Security (Task 14) | 4 | ✅ Pass |
| Gemini Advisory Engine (Task 15) | 2 | ✅ Pass |
| API Endpoints & Security (Task 16) | 3 | ✅ Pass |
| **Total** | **9** | **✅ 0 Failures** |

### Frontend Build Verification (Vite)

| Build | Status |
|---|---|
| `npm run build` (Task 17 scaffold) | ✅ 1487 modules, built in 6.69s |
| `npm run build` (Task 18 API integration) | ✅ 1489 modules, built in 2.87s |

---

*Documentation generated by Principal Systems Auditor following full codebase audit of CYCLO-NEXUS v1.0.*
