# CYCLO-NEXUS: Master Execution Blueprint (v2)
## AI-Driven Multimodal Tropical Cyclone Detection, Classification & Trajectory Forecasting System

**Target:** Smart India Hackathon (SIH)
**System Purpose:** Zero-latency, edge-compatible deep learning pipeline for multi-spectral satellite cyclone intelligence.

---

## 1. Comprehensive Project Overview & Scientific Rationale

### 1.1 The Meteorological Challenge in the North Indian Ocean
The North Indian Ocean (NIO) basin, comprising the Bay of Bengal and the Arabian Sea, is highly susceptible to rapid-onset tropical cyclones. Existing operational early warning systems rely heavily on Numerical Weather Prediction (NWP) models and semi-automated heuristic interpretations (like the Dvorak technique) applied to single-sensor infrared data. These methods suffer from high computational latency (3-6 hour update cycles) and struggle to model Rapid Intensification (RI)—a phenomenon increasingly common due to rising sea surface temperatures. CYCLO-NEXUS solves this by shifting from heavy physical simulations to lightweight, sub-hourly deep learning inference at the edge.

### 1.2 Multimodal Sensor Fusion Strategy
Instead of relying on isolated data streams, CYCLO-NEXUS synthesizes a comprehensive atmospheric profile by stacking diverse satellite channels into a unified tensor:
*   **INSAT-3D/3DR (TIR-1 & TIR-2):** Maps cloud top temperatures to identify deep convection cores.
*   **INSAT-3D/3DR (Water Vapor):** Analyzes mid-level atmospheric moisture driving cyclone thermodynamics.
*   **JAXA Himawari-8/9 (Clean IR):** Provides supplementary high-resolution geostationary cross-validation.
*   **NASA GPM:** Supplies precipitation rate proxies critical for mapping asymmetric spiral rainbands.

### 1.3 Algorithmic Paradigm Shift: YOLO-OBB & Physics-Informed LSTM
Standard object detection networks use axis-aligned bounding boxes, which introduce immense noise when capturing elliptical and spiraling cyclone structures. CYCLO-NEXUS employs **YOLO-OBB (Oriented Bounding Box)** to extract the exact rotational angle (θ), primary eyewall radius, and Central Dense Overcast (CDO) dimensions. 
For forecasting, the system abandons purely statistical models in favor of a **Spatio-Temporal Bi-GRU/ConvLSTM network**. To prevent the neural network from predicting impossible atmospheric states (a common flaw in pure ML meteorology), the loss function is mathematically constrained by the **Atkinson-Holliday wind-pressure relationship** ($\Delta P = 0.018 	imes V_{max}^{1.5}$).

### 1.4 Zero-Cost Edge Architecture & Socio-Technical Impact
Designed for severe budget and resource constraints, the architecture completely decouples heavy ML inference from web serving. Heavy PyTorch loads run on transient, free-tier compute nodes (Kaggle/HF Spaces), while the user-facing web gateway runs on a standard Node.js/PHP business hosting plan. For end-users, a highly optimized, offline-capable Progressive Web App (PWA) visualizes the data through MapLibre GL, utilizing i18next to automatically translate critical disaster intelligence into 9 major Indian languages, directly serving grassroots first responders.

---

## 2. AI Agent Core Directives (MUST_FOLLOW_RULES)

As an AI agent working on this project, you must prioritize caution over speed [cite: 1]. Your primary goal is to implement requested features without destabilizing perfectly running code.

*   **Think Before Coding:** State assumptions explicitly. If multiple interpretations exist, surface the tradeoffs. If unclear, stop and ask [cite: 1].
*   **Simplicity First:** Write the minimum code necessary to solve the problem. No speculative features [cite: 1].
*   **Surgical Edits Only:** Touch only what you must. Do not refactor adjacent code or format untouched lines [cite: 1].
*   **Orphan Management:** Remove imports/variables/functions that your changes made unused. Do not remove pre-existing dead code unless asked [cite: 1].
*   **Goal Verification:** Define success criteria (e.g., "Write tests for invalid inputs, then make them pass") and loop independently [cite: 1].

### Domain Skill Modifiers
*   **VIBE_CODER:** Extreme ownership, non-destructive editing, regression prevention.
*   **AI_PIPELINE:** Align geospatial tensors to `(Channels, Height, Width)`. Stick to `rasterio`, `h5py`, `numpy`, and `torch`. Enforce thermodynamic constraints.
*   **FRONTEND_UI:** Ensure MapLibre layers and flow animations are device-agnostic. Never hardcode English strings (use i18next).
*   **BACKEND_API:** Additive schema migrations only (EF Core MySQL). Serialize AI outputs into lightweight GeoJSON.

---

## 3. Technical Architecture & Data Flow

**Data Ingestion:** MOSDAC (INSAT-3D), JAXA Himawari-8/9, NASA GPM.
**Preprocessing:** EPSG:4326 Reprojection, 0.04° grid resampling, 4-Channel Tensor Stacking.
**ML Inference (Free GPU Worker):** YOLO-OBB (Localization) + ConvLSTM (Physics-Guided Trajectory) + Grad-CAM (XAI).
**API Layer (Hostinger Node.js/PHP):** GeoJSON webhook receiver, MySQL Datastore.
**Frontend:** Vite/React PWA, MapLibre GL, 9-Language Localization engine.

---

## 4. 22-Step Micro-Task Execution Plan

### Phase 1: Data Engineering
*   **Task 1:** MOSDAC INSAT-3D/3DR Automated Ingestion Worker (`h5py`).
*   **Task 2:** JAXA Himawari-8/9 & NASA GPM Ingestion Pipeline (`ftplib`, chunked reads).
*   **Task 3:** Geospatial Reprojection & Grid Registration (EPSG:4326, `rasterio`).
*   **Task 4:** Radiometric Calibration & 4-Channel Tensor Assembly (Float32).
*   **Task 5:** IMD Best Track Dataset Harmonization (SQLite/Parquet).

### Phase 2: Computer Vision Detection
*   **Task 6:** Oriented Bounding Box (OBB) Annotation Generator.
*   **Task 7:** Atmospheric Physics-Aware Data Augmentation Engine.
*   **Task 8:** YOLO-OBB Cyclone Eye Localization & Diameter Estimation.
*   **Task 9:** IMD Classification Head & Confidence Calibrator.

### Phase 3: Trajectory & Physics-Guided AI
*   **Task 10:** Spatiotemporal Sequence Matrix Builder.
*   **Task 11:** Spatiotemporal Forecaster (ConvLSTM + Bi-GRU).
*   **Task 12:** Atkinson-Holliday Physics Residual Loss Engine.
*   **Task 13:** Layer-Wise Grad-CAM Visual Explainability Module.

### Phase 4: Backend & Database
*   **Task 14:** Free-Tier Remote Inference Worker & Webhook Dispatcher.
*   **Task 15:** Additive Database Schema & Migration Architecture.
*   **Task 16:** Lightweight Node.js/PHP API Gateway.
*   **Task 17:** Gemini Pro Automated Multilingual Bulletin Generator.

### Phase 5: Dashboard & PWA
*   **Task 18:** Responsive Dashboard Shell & Glassmorphic UI Scaffold.
*   **Task 19:** MapLibre GL Vector Engine & Cyclone Path Visualization.
*   **Task 20:** 9-Language Regional Localization Engine (i18next).
*   **Task 21:** Progressive Web App (PWA) Offline Engine & Web Push.
*   **Task 22:** End-to-End Validation, Accuracy Benchmarking & SIH Pitch Suite.
