# AI_AGENT_SKILLS_DIRECTIVE.md

> **Operating System & Behavioral Constitution for Autonomous AI Coding Agents**  
> **Project:** CYCLO-NEXUS — Multimodal Satellite AI Platform for Tropical Cyclone Intelligence  
> **Target Event:** Smart India Hackathon (SIH)  
> **Execution Standard:** High-Precision Vibe Coding • Non-Destructive Refactoring • Zero-Regression Architecture

---

## Table of Contents
1. [Meta-Agent Constitution (Universal Guardrails)](#1-meta-agent-constitution-universal-guardrails)
2. [Skill 01: Core Vibe Coder & Surgical Surgery](#skill-01-core-vibe-coder--surgical-surgery)
3. [Skill 02: Geospatial & Multi-Spectral Satellite Data Ingestion](#skill-02-geospatial--multi-spectral-satellite-data-ingestion)
4. [Skill 03: YOLO-OBB & Computer Vision Detection](#skill-03-yolo-obb--computer-vision-detection)
5. [Skill 04: Physics-Guided Trajectory & Thermodynamic Modeling](#skill-04-physics-guided-trajectory--thermodynamic-modeling)
6. [Skill 05: Resource-Constrained Backend & Additive Database](#skill-05-resource-constrained-backend--additive-database)
7. [Skill 06: High-Performance PWA, MapLibre & Multilingual UI](#skill-06-high-performance-pwa-maplibre--multilingual-ui)
8. [Skill 07: Gemini Advisory Engine & Multi-Lingual Prompt Channelling](#skill-07-gemini-advisory-engine--multi-lingual-prompt-channelling)
9. [Prompt Injection Template (Tagging Matrix)](#9-prompt-injection-template-tagging-matrix)

---

## 1. Meta-Agent Constitution (Universal Guardrails)

These rules supersede any standard behavior. They must be active on every prompt across every platform (Gemini Pro, Claude, ChatGPT, Cursor, GitHub Copilot).

```
                             AGENT EXECUTION GATE
               ┌──────────────────────────────────────────────┐
               │         Read User Prompt & Context           │
               └──────────────────────┬───────────────────────┘
                                      │
                                      ▼
               ┌──────────────────────────────────────────────┐
               │    Ambiguity or Multiple Interpretations?    │
               └──────────────┬───────────────────────────────┘
                              │
               ┌──────────────┴──────────────┐
               │ YES                         │ NO
               ▼                             ▼
   ┌───────────────────────┐    ┌─────────────────────────────┐
   │ Stop & State Tradeoff │    │ State Verifiable Plan       │
   │ Ask Before Executing  │    │ Step 1 -> Check 1           │
   └───────────────────────┘    │ Step 2 -> Check 2           │
                                └──────────────┬──────────────┘
                                               │
                                               ▼
                                ┌─────────────────────────────┐
                                │   Surgical Implementation   │
                                │  Touch ONLY Required Lines  │
                                └──────────────┬──────────────┘
                                               │
                                               ▼
                                ┌─────────────────────────────┐
                                │ Automated Verification Loop │
                                └─────────────────────────────┘
```

### The Three Inviolable Laws
1. **The Law of Conservation of Code:** Never rewrite, reformat, or "clean up" working code that is outside the explicit scope of the prompt.
2. **The Law of Verifiable Goals:** Never output a code block without defining how that specific code must be verified.
3. **The Law of Zero Hallucination:** Never assume the existence of an API endpoint, satellite metadata field, library function, or file path. If unconfirmed, inspect or ask.

---

## Skill 01: Core Vibe Coder & Surgical Surgery

**Skill Identifier:** `[SKILL:VIBE_CODER]`  
**Domain:** Code editing discipline, dependency boundaries, diff minimization, execution loops.

### Operational Philosophy
"Vibe coding" is not sloppy coding; it is high-speed, intuitive engineering bounded by strict guardrails. The agent writes minimal code, verifies iteratively, and treats working code as immutable production infrastructure.

### Rules of Engagement

#### What You MUST Do
* **State Assumptions Explicitly:** If a task allows more than one technical pathway, outline the options briefly before writing code.
* **Keep Diffs Tiny:** Limit your output strictly to the targeted function, component, or file.
* **Remove Your Own Residue:** If your change makes a previously imported package, variable, or function obsolete, remove that orphan immediately.
* **Write Goal-Driven Micro-Plans:** Structure complex tasks using the verification loop pattern:
  ```
  1. [Actionable Task] -> verify: [Specific Test/Assertion]
  2. [Actionable Task] -> verify: [Specific Test/Assertion]
  ```

#### What You MUST NEVER Do
* **DO NOT Refactor Surrounding Code:** Do not touch adjacent comments, variable names, or formatting styles just because you would have written them differently.
* **DO NOT Over-Engineer:** Never write speculative wrapper classes, abstract factories, or configuration options for single-use routines.
* **DO NOT Write Infinite Try-Catch Blocks:** Do not hide underlying operational failures with generic `except Exception: pass` statements.
* **DO NOT Delete Pre-Existing Dead Code:** Focus only on your task. Mention unused code, but do not delete it unless commanded.

---

## Skill 02: Geospatial & Multi-Spectral Satellite Data Ingestion

**Skill Identifier:** `[SKILL:GEOSPATIAL_INGEST]`  
**Domain:** MOSDAC (INSAT-3D/3DR), JAXA Himawari-8/9, NASA GPM, HDF5, NetCDF4, GeoTIFF, coordinate registration.

### Operational Philosophy
Satellite data ingestion must be memory-bounded, numerically exact, and resilient to missing sensor packets. Calibration formulas must convert digital counts into physical Brightness Temperatures ($K$) without data corruption.

### Data Channels & Parameters
* **INSAT-3D/3DR TIR-1:** Central wavelength ~10.8 micrometers (Brightness Temperature).
* **INSAT-3D/3DR TIR-2:** Central wavelength ~12.0 micrometers (Split-Window computation).
* **INSAT-3D/3DR WV:** Central wavelength ~6.9 micrometers (Middle-tropospheric moisture).
* **JAXA Himawari-8/9 AHI Band 13:** Clean IR (~10.4 micrometers).
* **NASA GPM IMERG:** Half-hourly surface precipitation rate estimates (mm/hr).

### Rules of Engagement

#### What You MUST Do
* **Enforce Tensor Shape Discipline:** Standardize stacked multi-channel tensors to shape `(Channels, Height, Width)` using float32.
* **Normalize Carefully:** Keep brightness temperatures in standard ranges (180 K to 320 K) before min-max scaling to [0.0, 1.0].
* **Strict Coordinate Reference System (CRS):** Enforce WGS84 (`EPSG:4326`) across all satellite grids. North Indian Ocean bounding box:
  $$\text{Latitude: } 0.0^\circ\text{N} \to 32.0^\circ\text{N}, \quad \text{Longitude: } 50.0^\circ\text{E} \to 102.0^\circ\text{E}$$
* **Chunked Streaming:** Read large HDF5/NetCDF files in memory-bounded slices via `h5py` and `netCDF4`.

#### What You MUST NEVER Do
* **DO NOT Confuse Radiance and Reflectance:** Never mix visible channel albedo (%) directly with infrared brightness temperature (K) without explicit radiometric transformation.
* **DO NOT Drop Spatial Metadata:** Never strip affine transform matrices or projection metadata when converting rasters to NumPy arrays.
* **DO NOT Use Heavy Geospatial Servers:** Do not introduce GeoServer or complex GIS daemons. Keep transformations local using `rasterio` and `GDAL` lightweight bindings.

---

## Skill 03: YOLO-OBB & Computer Vision Detection

**Skill Identifier:** `[SKILL:YOLO_OBB_CV]`  
**Domain:** Ultralytics YOLOv8/v11-OBB, Rotated Bounding Boxes, Eyewall/CDO feature extraction, IMD categorization.

### Operational Philosophy
Tropical cyclones are asymmetric, spiraling fluid vortices. Standard axis-aligned boxes incorporate massive noise. The vision system must accurately predict the rotated orientation angle (theta), locate the eye center $(x_c, y_c)$, compute eye diameter, and classify the storm against IMD guidelines.

### IMD Classification Scale
```
┌──────────────────────────────────────┬───────────────────┬───────────────────┐
│ Category                             │ Short Code        │ Sustained Winds   │
├──────────────────────────────────────┼───────────────────┼───────────────────┤
│ Depression                           │ D                 │ 31–49 km/h        │
│ Deep Depression                      │ DD                │ 50–61 km/h        │
│ Cyclonic Storm                       │ CS                │ 62–88 km/h        │
│ Severe Cyclonic Storm                │ SCS               │ 89–117 km/h       │
│ Very Severe Cyclonic Storm           │ VSCS              │ 118–166 km/h      │
│ Extremely Severe Cyclonic Storm      │ ESCS              │ 167–221 km/h      │
│ Super Cyclonic Storm                 │ SuCS              │ >= 222 km/h       │
└──────────────────────────────────────┴───────────────────┴───────────────────┘
```

### Rules of Engagement

#### What You MUST Do
* **Preserve 4-Channel Convolution:** When loading YOLO backbones, adapt the first layer (`Conv2d`) to take in 4 channels instead of 3, copying or averaging weights across the first three channels and initializing the fourth cleanly.
* **Rotated Box Output Format:** Ensure all OBB predictions emit 5-parameter coordinates:
  $$[x_c, y_c, w, h, \theta]$$
  where $\theta \in [-\pi/2, \pi/2]$ or $[0, 2\pi]$ depending on the underlying label format.
* **Eye Diameter Computation:** Convert pixel eye measurements into metric distances (km) using the ground sample distance (~4 km/pixel).

#### What You MUST NEVER Do
* **DO NOT Use Saffir-Simpson Scale:** Never categorize storms as "Category 1-5" without explicitly stating and computing the official IMD scale equivalents.
* **DO NOT Use Synthetic Shearing in Augmentations:** Never apply affine shear transforms during training that violate fluid mechanics and Coriolis rotational physics.
* **DO NOT Load Massive Models on Web Workers:** Keep the YOLO-OBB weights decoupled from the presentation and web tier.

---

## Skill 04: Physics-Guided Trajectory & Thermodynamic Modeling

**Skill Identifier:** `[SKILL:PHYSICS_AI_TRAJECTORY]`  
**Domain:** Spatio-temporal sequences (ConvLSTM, Bi-GRU), Atkinson-Holliday relationship, Grad-CAM XAI.

### Operational Philosophy
Pure machine learning easily outputs non-physical anomalies (e.g., predicting sustained winds of 180 km/h while simultaneously predicting standard atmospheric pressure of 1008 hPa). The network must be constrained by geophysical thermodynamics.

### Core Mathematical Formulations
1. **Atkinson-Holliday Empirical Wind-Pressure Relationship:**
   $$\Delta P = P_{env} - P_c = 0.018 \cdot (V_{max})^{1.5}$$
   *(where $P_{env}$ is ambient peripheral pressure $\approx 1010\text{ hPa}$, $P_c$ is minimum central pressure in $\text{hPa}$, and $V_{max}$ is in knots).*

2. **Physics-Constrained Loss Formulation:**
   $$\mathcal{L}_{total} = \mathcal{L}_{MSE}(\mathbf{Y}_{traj}, \hat{\mathbf{Y}}_{traj}) + \alpha \cdot \mathcal{L}_{Huber}(V_{pred}, V_{true}) + \beta \cdot \max\left(0, \left|\Delta P_{pred} - 0.018 \cdot (V_{pred})^{1.5}\right| - \tau\right)$$

### Rules of Engagement

#### What You MUST Do
* **Vectorize Sequence Preparation:** Build 6-step temporal sequence matrices $[t-15\text{h}, t_0]$ at 3-hour intervals with strict zero-leakage checks.
* **Layer-Wise Grad-CAM Hooks:** Safely attach PyTorch forward and backward hooks to the last convolutional feature layer to export spatial salience heatmaps without breaking model evaluation loops.
* **Include Uncertainty Cones:** Output both deterministic $(\Delta x, \Delta y)$ coordinates and standard deviation envelopes ($\sigma_x, \sigma_y$) representing the forecast cone of uncertainty for 6h, 12h, 24h, 48h, and 72h.

#### What You MUST NEVER Do
* **DO NOT Leak Future Data:** Ensure chronological slicing during dataset creation. Never shuffle temporal sequences across the time axis.
* **DO NOT Block Execution on GPU Tensors:** Convert inference outputs immediately to plain Python primitives or NumPy arrays before serialization to prevent GPU memory leaks.

---

## Skill 05: Resource-Constrained Backend & Additive Database

**Skill Identifier:** `[SKILL:BACKEND_DATABASE]`  
**Domain:** Hostinger Business Hosting (Node.js/PHP), MySQL/MariaDB, Entity Framework Core, RESTful GeoJSON endpoints.

### Operational Philosophy
The server runs on a shared, resource-bounded hosting environment. It must never perform deep learning inference. It serves solely as a high-speed data clearinghouse, receiving serialized inference payloads, managing state, and serving the PWA.

### Rules of Engagement

#### What You MUST Do
* **Additive Database Migrations Only:** When modifying MySQL tables, use non-destructive schema migrations:
  ```sql
  ALTER TABLE cyclone_telemetry ADD COLUMN IF NOT EXISTS eye_diameter_km FLOAT NULL;
  ```
* **Verify EF Core Migrations History:** Always check and preserve the `__EFMigrationsHistory` table state before applying changes.
* **GeoJSON Payload Serialization:** Expose all geographic trajectory paths, eye points, and cones of uncertainty using valid RFC 7946 GeoJSON specifications (`FeatureCollection`, `Point`, `Polygon`).
* **In-Memory Caching:** Cache active cyclone metadata endpoints with short-lived TTLs (30 to 60 seconds) to withstand sudden traffic spikes during disaster alerts.

#### What You MUST NEVER Do
* **DO NOT Execute Heavy Python/PyTorch on Hostinger:** Never attempt to invoke model inference, GDAL re-projections, or heavy HDF5 reads directly inside the Hostinger web server process.
* **DO NOT Run Destructive DDL:** Never execute `DROP TABLE`, `DROP COLUMN`, or `TRUNCATE` in database migration scripts.
* **DO NOT Send Uncompressed Imagery:** Never stream raw GeoTIFF files or uncompressed arrays to clients; convert all spatial overlays into compressed WebP or vector tiles.

---

## Skill 06: High-Performance PWA, MapLibre & Multilingual UI

**Skill Identifier:** `[SKILL:FRONTEND_PWA_MAP]`  
**Domain:** React, Tailwind CSS, MapLibre GL, `i18next`, Service Workers, Web Push, Glassmorphic UI.

### Operational Philosophy
During an escalating disaster, first responders operate on low-bandwidth, battery-depleted mobile devices in high-stress environments. The interface must be minimal, dark-themed, ultra-legible, installable as a PWA, and strictly localized into regional coastal languages.

### Supported Language Matrix
```
1. en: English      4. or: Odia (ଓଡ଼ିଆ)        7. ml: Malayalam (മലയാളം)
2. hi: Hindi (हिन्दी) 5. ta: Tamil (தமிழ்)       8. mr: Marathi (मराठी)
3. bn: Bengali (বাংলা) 6. te: Telugu (తెలుగు)     9. gu: Gujarati (ગુજરાતી)
```

### Rules of Engagement

#### What You MUST Do
* **Zero Hardcoded Strings:** Every visual label, tooltip, unit indicator, and alert banner must use the `useTranslation()` hook from `react-i18next`:
  ```jsx
  // CORRECT:
  <span>{t('telemetry.central_pressure')}: {data.pressure} hPa</span>
  // FORBIDDEN:
  <span>Central Pressure: {data.pressure} hPa</span>
  ```
* **Manage MapLibre GL Lifecycles:** Initialize the MapLibre canvas inside a React `useEffect` hook and properly trigger `map.remove()` on component unmount to prevent WebGL context destruction errors.
* **Touch-First Accessibility:** Ensure all interactive touch targets (sliders, buttons, language selectors) have minimum dimensions of 48px x 48px.
* **Stable Animations:** Ensure background atmospheric flow animations adjust smoothly across all screen viewports without causing layout shifts.

#### What You MUST NEVER Do
* **DO NOT Force Global Re-renders:** Layer overlays (such as toggling wind particles or Grad-CAM heatmaps) must not cause the entire telemetry dashboard to re-render.
* **DO NOT Block Offline Boot:** The Service Worker must cache the foundational shell, translation JSON catalogs, and offline vector basemaps so the app opens reliably during zero-network field conditions.
* **DO NOT Overload Desktop Views on Mobile:** Never display massive multi-column data tables on mobile layouts; collapse secondary sensor readings into clean, expandable drawers.

---

## Skill 07: Gemini Advisory Engine & Multi-Lingual Prompt Channelling

**Skill Identifier:** `[SKILL:GEMINI_ADVISORY]`  
**Domain:** Google Gemini Pro API, automated disaster bulletins, structured JSON generation, NDRF/SDMA alerting.

### Operational Philosophy
Emergency management agencies require instantly actionable instructions, not ambiguous summaries. The Gemini Pro integration must translate numerical telemetry directly into clear, urgent disaster warnings without hallucinations or formatting errors.

### Rules of Engagement

#### What You MUST Do
* **Enforce Structured JSON Output:** Use Gemini's structured response configuration to enforce rigid JSON returns:
  ```json
  {
    "alert_level": "RED | ORANGE | YELLOW",
    "threat_summary": "string",
    "estimated_landfall_window": "ISO-8601 string",
    "coastal_evacuation_priority": ["zone_id_1", "zone_id_2"],
    "actionable_directives": {
      "fishermen": "string",
      "general_public": "string",
      "district_administration": "string"
    }
  }
  ```
* **Ground Alerts in Numerical Thresholds:** Base alert severity strictly on sustained wind speeds:
  * $V_{max} \ge 118\text{ km/h}$ (VSCS+): Red Alert (Mandatory immediate coastal evacuation).
  * $62 \le V_{max} < 118\text{ km/h}$ (CS/SCS): Orange Alert (Halt maritime operations, secure infrastructure).
  * $31 \le V_{max} < 62\text{ km/h}$ (D/DD): Yellow Alert (Continuous tracking, advisory for fishermen).

#### What You MUST NEVER Do
* **DO NOT Output Unparsed Markdown in API Chains:** Do not permit the LLM to wrap output inside backticks (```json ... ```) if the downstream service expects raw JSON.
* **DO NOT Speculate Beyond Model Vectors:** Gemini must never invent casualty estimates, unverified geographic landmarks, or landfall times not supported by the upstream forecasting model.

---

## 9. Prompt Injection Template (Tagging Matrix)

Copy and prepend this block to your agent prompts to immediately invoke the exact operating constraints required for the task.

```markdown
### SYSTEM DIRECTIVE APPLIED
Active Skill Tags: [SKILL:VIBE_CODER] + [INSERT_SPECIFIC_SKILL_HERE]
Constitution: Read and strictly obey MUST_FOLLOW_RULES from AI_AGENT_SKILLS_DIRECTIVE.md.

Task Reference: Task #[X] — [Task Name from 22-Step Execution Plan]
Execution Mode: Surgical implementation, non-destructive diffs, goal-driven verification.

Context & Boundaries:
- Target File: [Path to file]
- Forbidden Actions: Do not modify adjacent files, do not change existing function signatures, do not remove pre-existing comments.
- Verification Criteria: [Define exactly how to verify this code runs successfully]

Task Description:
[Insert detailed instruction here]
```

---

## Verification & Compliance Checklist

Before emitting code to the user or writing to disk, the agent must silently check:

- [ ] Does every modified line trace directly back to the user's explicit instructions?
- [ ] Are all scientific equations verified against atmospheric thermodynamics (e.g., Atkinson-Holliday)?
- [ ] Are all coordinates adhering to standard WGS84 (`EPSG:4326`) conventions?
- [ ] Have all UI text components avoided hardcoded strings, utilizing `i18next` keys instead?
- [ ] Is heavy deep learning inference strictly separated from the Hostinger web server code?
- [ ] Are database schema modifications purely additive without destructive DDL commands?
