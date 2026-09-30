# CYCLO-NEXUS: Comprehensive Platform Upgrade & Technical Master Plan
**Document Version:** 1.0.0  
**Date:** September 2026  
**Status:** Approved for Implementation Architecture  
**Target Repository:** `cyclonegaurd` (Phase 5 Backend, Phase 6 Frontend, GIS & Inference Engine)

---

## Table of Contents
1. [User Q&A: Full Questions & Technical Diagnostics](#1-user-qa-full-questions--technical-diagnostics)
   - [Q1: Mock vs. Live Data in Current Deployment](#q1-is-the-data-completely-mock-and-not-live-data)
   - [Q2: Algorithms for Affected Areas, Population at Risk & Impact Parameters](#q2-is-there-any-algorithm-to-showcase-which-areas-are-affected-and-people-in-danger)
   - [Q3: Non-Clickable Interface Elements & Missing Handlers](#q3-why-is-everything-not-clickable-on-the-site)
   - [Q4: Mobile Responsiveness Breakdown](#q4-why-is-the-site-not-responsive-for-mobile-users)
   - [Q5: ISRO SCORPIO / MOSDAC-Style Animated Wind Vector Particles](#q5-why-are-we-not-using-an-isro-scorpio--mosdac-style-animated-wind-map)
   - [Q6: Pinpoint Meteorological Inspection & Storm Formation Probability (Even Without Cyclones)](#q6-showing-live-area-details-and-cyclone-probability-when-clicking-any-location)
   - [Q7: Satellite API Status & Integration Reality](#q7-are-we-taking-these-data-from-satellite-apis-or-not)
2. [Exact Strategy & Architectural Blueprint](#2-exact-strategy--architectural-blueprint)
   - [Module A: ISRO SCORPIO-Style WebGL/Canvas Wind Streamline Particle Engine](#module-a-isro-scorpio-style-animated-wind-particle-engine)
   - [Module B: Live Pinpoint Weather & Cyclogenesis Potential Index (GPI) Engine](#module-b-live-pinpoint-weather--cyclogenesis-potential-index-gpi-engine)
   - [Module C: Geospatial Impact & Population Vulnerability Engine (Turf.js)](#module-c-geospatial-impact--population-vulnerability-engine)
   - [Module D: Interactive Navigation, Tab Switching & Component Interactivity](#module-d-interactive-navigation-tab-switching--component-interactivity)
   - [Module E: Mobile-First Responsive Overhaul & Touch Optimization](#module-e-mobile-first-responsive-overhaul--touch-optimization)
   - [Module F: Automated Satellite & NWP Data Ingestion Pipeline](#module-f-automated-satellite--nwp-data-ingestion-pipeline)
3. [Risk Management: Potential Pitfalls & Technical Mitigations](#3-risk-management-potential-pitfalls--technical-mitigations)
4. [Step-by-Step Implementation Roadmap](#4-step-by-step-implementation-roadmap)

---

## 1. User Q&A: Full Questions & Technical Diagnostics

### Q1: Is the data completely mock and not live data?
**Answer: YES, what currently renders on the frontend is fallback mock data.**
* **Current Code Diagnostic:**
  * In [frontend/src/services/api.js](file:///d:/cyclonegaurd/frontend/src/services/api.js#L4-L26), the client implements a fallback object: `DEMO_CYCLONE` (`Cyclone Vayun`, Lat 15.2, Lon 86.4, SCS category, 105 km/h sustained wind) and `DEMO_GEOJSON`.
  * The frontend polls `GET /api/v1/cyclones`. While the Node.js Express backend and MySQL service are online, the database table `active_cyclones` contains zero records because an active satellite ingestion pipeline or live inference trigger has not posted incoming real-time telemetry to the webhook (`POST /api/v1/webhook/inference`).
  * When the backend responds with an empty list `[]`, the frontend invokes its fallback guard to avoid rendering a blank white screen, displaying the mock cyclone.

---

### Q2: Is there any algorithm to showcase which areas are affected and people in danger?
**Answer: NO, not in the current frontend build — the metrics are static UI placeholder values.**
* **Current Code Diagnostic:**
  * The numbers shown in the stat cards (e.g., "2.8M People in Warning Zone", "4 Coastal Districts") in [frontend/src/components/StatCards.jsx](file:///d:/cyclonegaurd/frontend/src/components/StatCards.jsx) are static constants.
* **The Required Scientific Algorithm:**
  1. **Hazard Swath Generation:** Given the eye track coordinates $[(lon_t, lat_t)]$ and forecasted radii of 34-kt (gale), 50-kt (storm), and 64-kt (hurricane) winds, construct a dynamic buffer envelope polygon using geospatial math (`turf.buffer` / `turf.convex`).
  2. **Landfall & District Intersection:** Perform polygon-in-polygon and line-intersection tests between the hazard swath and coastal administrative district polygons (Census of India / GADM coastal GeoJSON).
  3. **Population Exposure Calculation:**
     $$\text{Total People at Risk} = \sum_{d \in \text{Impacted Districts}} \text{Population}_d \times \frac{\text{Area}(\text{Swath} \cap \text{District}_d)}{\text{Area}(\text{District}_d)}$$
  4. **Landfall ETA:** Compute distance from current eye location to the intersection point along the coast divided by forecast translation speed $V_t$.

---

### Q3: Why is everything not clickable on the site?
**Answer: Navigation links and buttons were constructed as visual interface templates without event handlers, active tab state, or routing.**
* **Current Code Diagnostic:**
  * **Sidebar Navigation:** [frontend/src/components/Sidebar.jsx](file:///d:/cyclonegaurd/frontend/src/components/Sidebar.jsx#L30-L36) renders plain `<div>` elements for each link (`Live Monitoring`, `Cyclone Tracking`, `Forecast`, `Historical`, `Alerts`, `Reports`, `Settings`) without `onClick` callbacks or routing links.
  * **Header Controls:** Notification bell, Export button, Search bar, and Profile button lack state-driven modal triggers.
  * **Bottom Panels:** Tab switching between Overview, Wind Swath, Impact Analysis, and Evacuation Advisories was hardcoded to a static layout without active sub-view toggling.

---

### Q4: Why is the site not responsive for mobile users?
**Answer: The layout locks the viewport height and clips overflow, while missing a mobile drawer menu.**
* **Current Code Diagnostic:**
  * In [frontend/src/index.css](file:///d:/cyclonegaurd/frontend/src/index.css#L75-L91), `body` and `.app-layout` enforce `height: 100vh; overflow: hidden;`. On mobile browsers (iOS Safari and Android Chrome with dynamic URL bars), this breaks touch scrolling and prevents users from scrolling down to view dashboard panels.
  * At `@media (max-width: 1024px)`, `.sidebar` is hidden via `display: none;`, but **no mobile hamburger toggle button or slide-over drawer** was built into the header. As a result, mobile users lose all navigation.
  * The MapLibre GL canvas consumes all touch events without a gesture-scroll overlay, trapping user swipe actions inside the map container.
  * The header actions bar overflows horizontally on screens narrower than 420px.

---

### Q5: Why are we not using an ISRO SCORPIO / MOSDAC-style animated wind map?
**Answer: The map currently renders standard vector layers and static tiles, without a WebGL particle vector field.**
* **Current Code Diagnostic:**
  * [frontend/src/components/CycloneMap.jsx](file:///d:/cyclonegaurd/frontend/src/components/CycloneMap.jsx) loads base vector cartography and toggles raster satellite tiles from NASA GIBS.
* **How ISRO SCORPIO / MOSDAC Operates:**
  * ISRO SCORPIO, MOSDAC, and Windy use 2D numerical weather grids ($u$ = zonal/east-west wind velocity, $v$ = meridional/north-south wind velocity) at 10m or 850 hPa levels.
  * A continuous WebGL shader or HTML5 Canvas loop animates thousands of particle trajectories interpolated over the $(u, v)$ vector grid, color-coded by wind magnitude:
    $$\text{Speed} = \sqrt{u^2 + v^2}$$
  * This creates fluid streamlines indicating circulation centers, wind shear, and gale bands in real time.

---

### Q6: Showing live area details and cyclone probability when clicking any location?
**Answer: This feature is not yet hooked up because the frontend was restricted to active cyclone queries only.**
* **The Solution & Strategy:**
  * Enable an interactive point-and-click listener on the map (`map.on('click')`).
  * On every map click, query live meteorological data for that exact coordinate $(lat, lon)$:
    * Mean Sea Level Pressure (MSLP in hPa)
    * 10m Wind Speed (km/h & knots) and Wind Direction (degrees)
    * Air Temperature (°C) & Sea Surface Temperature (SST in °C)
    * Relative Humidity (%) & Dew Point
  * Execute a **Genesis Potential Index (GPI)** calculation to evaluate storm/depression probability:
    * $\text{SST} \ge 26.5^\circ\text{C}$ (essential ocean thermal energy)
    * $\text{Pressure} < 1008\text{ hPa}$ (low-pressure perturbation)
    * $\text{Vertical Wind Shear} < 15\text{ knots}$ (favorable storm intensification)
    * $\text{Coriolis / Latitude} > 5^\circ\text{N}$ (sufficient planetary vorticity)
  * Output a live **Storm / Cyclogenesis Risk Index** (Low, Moderate, High, Severe) with immediate hazard warnings for fishermen and coastal residents.

---

### Q7: Are we taking these data from satellite APIs or not?
**Answer: Only satellite imagery tiles are currently live; meteorological tracks and telemetry are not yet connected to a streaming satellite API.**

| Component | Current Implementation | Source | Live Status |
| :--- | :--- | :--- | :--- |
| **Satellite Imagery Layer** | NASA GIBS WMTS Tiles | NASA EPSDIS GIBS API (`VIIRS_SNPP` & `AIRS`) | **LIVE** |
| **Cyclone Track & Eye Center** | Fallback JSON (`DEMO_CYCLONE`) | Hardcoded in `api.js` | **MOCK (Awaiting Webhook)** |
| **Atmospheric Grids (Wind/Pressure)** | Stat card placeholders | Hardcoded in JSX | **MOCK** |
| **Model Predictions (Vision & Track)** | FastAPI microservice on port 8000 | PyTorch (`yolo_4ch_best.pt` & `forecaster_best.pt`) | **READY FOR LIVE INPUT** |

---

## 2. Exact Strategy & Architectural Blueprint

### Module A: ISRO SCORPIO-Style Animated Wind Particle Engine

```
┌────────────────────────────────────────────────────────┐
│            MapLibre GL Map Canvas (Base Layer)         │
└──────────────────────────┬─────────────────────────────┘
                           │ Synchronized Viewport (pan/zoom)
┌──────────────────────────▼─────────────────────────────┐
│       HTML5 Canvas Overlay / WebGL Particle Engine      │
│  - 3,500 - 5,000 animated particles                     │
│  - Interpolates (u, v) wind vectors from GFS grid      │
│  - Particle aging, fading trails, speed color ramp     │
└──────────────────────────┬─────────────────────────────┘
                           │ Streamed Data (JSON/ArrayBuffer)
┌──────────────────────────▼─────────────────────────────┐
│  Live Wind Vector API (NOAA GFS / Open-Meteo Marine)   │
│  Grid: 0.25° x 0.25° over Indian Ocean (0°N-30°N, 50°E-100°E)
└────────────────────────────────────────────────────────┘
```

#### Technical Implementation Details:
1. **Engine Architecture:**
   * Implement a synchronized custom Canvas overlay using requestAnimationFrame.
   * Maintain an active particle array: each particle has $\{x, y, age, maxAge\}$.
   * In each animation frame (target 60 FPS):
     1. Clear canvas with semi-transparent alpha (`rgba(0, 0, 0, 0.96)`) to produce fluid vector trails.
     2. Map current canvas pixel coordinates $(px, py)$ to geographical coordinates $(lon, lat)$ via MapLibre's `map.unproject()`.
     3. Bilinearly interpolate $u$ and $v$ from the wind vector data grid.
     4. Update particle position:
        $$x_{next} = x + u \times \text{speedFactor}, \quad y_{next} = y - v \times \text{speedFactor}$$
     5. Color particle according to wind magnitude (Cyan: <20 km/h; Yellow: 40–60 km/h; Orange: 60–90 km/h; Red/Magenta: >100 km/h).
     6. Reset particle if it exceeds `maxAge` or exits the viewport bounds.
2. **Performance Optimization:**
   * Dynamic particle scaling: 5,000 particles on desktop, 2,000 particles on mobile devices.
   * Pause the particle loop during rapid map zooming and resume immediately upon `moveend`.

---

### Module B: Live Pinpoint Weather & Cyclogenesis Potential Index (GPI) Engine

#### 1. Interactive Pinpoint Interaction:
* Bind a click listener on the MapLibre map:
  ```javascript
  map.on('click', async (e) => {
    const { lng, lat } = e.lngLat;
    dropInspectionMarker([lng, lat]);
    await fetchLiveLocationTelemetry(lng, lat);
  });
  ```
* Display a pulsating target pin at the clicked coordinate.

#### 2. Live Meteorological Data Fetching:
* Query the high-resolution Open-Meteo Marine and Weather API (free, open-access, zero-key, updated hourly from NOAA GFS / ECMWF):
  ```
  https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current=temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m,wind_direction_10m,wind_gusts_10m&marine=sea_surface_temperature
  ```
* Metrics retrieved in real-time:
  * **Mean Sea Level Pressure (MSLP):** Normal (1012 hPa) down to severe depression (<995 hPa).
  * **10m Sustained Wind:** Speed in km/h, knots, and Beaufort scale.
  * **Wind Gusts:** Peak instantaneous gust speeds.
  * **Wind Direction:** Cardinal compass heading (e.g., ENE 68°).
  * **Air Temperature & SST:** Ocean heat content verification (>26.5°C threshold).

#### 3. Cyclogenesis Potential Index (GPI) Formulation:
* Even when no named cyclone is present, calculate the live risk score:
  ```javascript
  function calculateCyclogenesisProbability(data) {
    const { sst, pressure, windSpeed, windGust, lat } = data;
    
    // 1. Thermal score (Sea Surface Temp > 26.5°C)
    let thermalScore = sst >= 26.5 ? Math.min(1.0, (sst - 26.0) / 4.0) : 0.05;
    
    // 2. Pressure deficit score (Baseline 1012 hPa)
    let pressureDeficit = Math.max(0, 1013 - pressure);
    let pressureScore = Math.min(1.0, pressureDeficit / 25.0); // 1013 -> 988 hPa
    
    // 3. Dynamic vorticity score (Wind speed & gusts)
    let windScore = Math.min(1.0, windSpeed / 75.0);
    
    // 4. Coriolis factor (Depressions rarely form within 4 degrees of the equator)
    let coriolisFactor = Math.abs(lat) < 4.0 ? 0.1 : Math.min(1.0, Math.abs(lat) / 10.0);
    
    // Weighted Genesis Index (0 to 100%)
    const rawIndex = (thermalScore * 0.35 + pressureScore * 0.40 + windScore * 0.25) * coriolisFactor;
    return Math.round(rawIndex * 100);
  }
  ```
* **Alert Categories:**
  * **0% – 20%:** Green / Calm Ocean State (Normal Conditions)
  * **21% – 45%:** Yellow / Atmospheric Disturbance (Monitor Cloud Banding)
  * **46% – 70%:** Orange / Low Pressure Area / Depression Forming (Fishermen Warning)
  * **71% – 100%:** Red / Deep Depression / Severe Cyclone Threat (Imminent Gale Warning)

---

### Module C: Geospatial Impact & Population Vulnerability Engine

#### 1. Real-Time Hazard Cone Calculation:
* Utilizing `@turf/turf` (or spatial polygon routines):
  * Take the multi-step forecasted eye positions from the model ($T+6\text{h}$, $T+12\text{h}$, $T+24\text{h}$, $T+48\text{h}$, $T+72\text{h}$).
  * Compute an expanding uncertainty cone:
    $$R_{\text{cone}}(t) = R_{\text{gale}} + \epsilon \cdot t$$
    where $\epsilon = 3.5\text{ km/hour}$ of forecast horizon.
  * Construct the bounding GeoJSON polygon enclosing the outer wind radii.

#### 2. Coastal District Intersection & Impact Aggregation:
* Store GeoJSON polygons of Indian coastal districts (Odisha, Andhra Pradesh, Tamil Nadu, West Bengal, Kerala, Karnataka, Goa, Maharashtra, Gujarat) with 2021/2026 projected census population counts.
* Perform spatial intersection:
  ```javascript
  const impactedDistricts = coastalDistricts.features.filter(district => {
    return turf.booleanIntersects(hazardConePolygon, district.geometry);
  });
  
  const totalPopulationAtRisk = impactedDistricts.reduce((sum, d) => sum + d.properties.population, 0);
  ```
* Output dynamically calculated live cards:
  * **Impacted Coastal Districts:** Exact list (e.g., Jagatsinghpur, Kendrapara, Puri, Srikakulam).
  * **Estimated Vulnerable Population:** Dynamically computed from intersected polygons.
  * **Landfall ETA:** Projected day, hour, and location based on line-intersection of track with coastline.
  * **Storm Surge Threat:** Calculated using bathymetry slope and central pressure deficit:
    $$\text{Surge Height (m)} \approx 0.01 \cdot (1010 - P_{\text{central}}) \times \text{BathymetryFactor}$$

---

### Module D: Interactive Navigation, Tab Switching & Component Interactivity

#### 1. Active Tab Navigation State:
* Upgrade `App.jsx` to maintain active view state:
  `const [activeTab, setActiveTab] = useState('dashboard');`
* Connect all 8 sidebar items:
  1. **`dashboard`:** Main operational command center (Map + Key Metrics + Overview).
  2. **`liveMonitoring`:** Fullscreen live satellite and wind streamline particle visualizer.
  3. **`cycloneTracking`:** Deep eye telemetry, OBB bounding box inspector, pressure/wind time-series.
  4. **`forecast`:** Multi-horizon forecast cone, track error margins, and model comparison table.
  5. **`historical`:** Search past Bay of Bengal and Arabian Sea cyclones (Amphan, Fani, Biparjoy, Michaung).
  6. **`alerts`:** Active IMD bulletins, red/orange/yellow district-level alerts, emergency contacts.
  7. **`reports`:** Exportable PDF and CSV incident summaries for disaster relief agencies.
  8. **`settings`:** Language switcher, wind units (km/h vs. knots), map base style toggles.

#### 2. Interactive Header & Bottom Panels:
* Wire notification bell to an Alerts Modal with real-time emergency advisories.
* Wire Export button to an automated browser print/PDF generator for situation reports.
* Enable tab switching in [BottomPanels.jsx](file:///d:/cyclonegaurd/frontend/src/components/BottomPanels.jsx):
  * **Tab 1:** Meteorological Telemetry
  * **Tab 2:** Affected Area & Population Impact Analysis (live calculated)
  * **Tab 3:** NDMA / IMD Evacuation Advisories
  * **Tab 4:** Regional Disaster Management Helplines

---

### Module E: Mobile-First Responsive Overhaul & Touch Optimization

#### 1. Layout & Scroll Architecture:
* In `index.css`:
  * Remove `height: 100vh; overflow: hidden;` from mobile media queries (`max-width: 1024px`).
  * Set `body { min-height: 100vh; overflow-y: auto; overflow-x: hidden; }`.
  * Convert `.app-layout` to a fluid column layout on mobile screens.

#### 2. Mobile Drawer Navigation:
* Add a hamburger menu button to `Header.jsx` visible only on screens `< 1024px`.
* Implement a slide-in navigation drawer with backdrop overlay for mobile screens:
  ```
  ┌────────────────────────────────────────────────────────┐
  │ [=] CYCLO-NEXUS [Live]     [Lang: EN v] [Alert Bell]   │ Header
  └────────────────────────────────────────────────────────┘
  ┌────────────────────────────────────────────────────────┐
  │  Stat Cards Carousel (Swipable on mobile)               │
  └────────────────────────────────────────────────────────┘
  ┌────────────────────────────────────────────────────────┐
  │  Interactive Map (Touch gesture enabled, height: 420px)│
  │  [Tap anywhere for Live Point Weather & Risk]          │
  └────────────────────────────────────────────────────────┘
  ┌────────────────────────────────────────────────────────┐
  │  Floating Bottom Sheet: Clicked Location / Cyclone     │
  │  Pressure: 1002 hPa | Wind: 62 km/h | Risk: 58%        │
  └────────────────────────────────────────────────────────┘
  ```

#### 3. Map Touch Handling:
* Enable `cooperativeGestures: true` or custom two-finger drag prompts on MapLibre so that single-finger scrolling allows moving past the map on mobile devices without getting stuck.

---

### Module F: Automated Satellite & NWP Data Ingestion Pipeline

```
  ┌──────────────────────────────────────────────────────────┐
  │         External Atmospheric Data Providers              │
  │  - NASA GIBS (Satellite True Color & Precipitation)       │
  │  - Open-Meteo / NOAA GFS (Wind Vectors & MSLP Grids)     │
  │  - IMD RSMC / IBTrACS (Official Active Cyclone Bulletins)│
  └────────────────────────────┬─────────────────────────────┘
                               │ HTTP Polling (Every 15 mins)
  ┌────────────────────────────▼─────────────────────────────┐
  │       CYCLO-NEXUS Node.js Backend Background Worker      │
  │       File: `backend/src/workers/ingest_worker.js`       │
  │  - Checks for active storms in NIO (North Indian Ocean)  │
  │  - Pulls current coordinates, pressure, and winds        │
  │  - Automatically triggers inference pipeline if new data │
  └────────────────────────────┬─────────────────────────────┘
                               │ Upsert Query
  ┌────────────────────────────▼─────────────────────────────┐
  │           MySQL Database (`active_cyclones`)             │
  │  - Replaces DEMO_CYCLONE fallback with real live tracks  │
  └──────────────────────────────────────────────────────────┘
```

---

## 3. Risk Management: Potential Pitfalls & Technical Mitigations

| Risk / Failure Mode | Impact | Engineering Mitigation |
| :--- | :--- | :--- |
| **1. GPU/Canvas lag from wind particles on low-end mobile devices** | Frame rate drops below 20 FPS, UI stuttering | Detect hardware concurrency & mobile user agent. Throttle particle count to 1,500 on mobile, reduce canvas resolution factor to `window.devicePixelRatio * 0.75`, and pause particles during panning. |
| **2. Public weather API rate limiting (HTTP 429)** | Point-and-click weather inspector fails when users click repeatedly | Implement a client-side coordinate cache (quantized to 0.1° lat/lon, ~11 km) with a 15-minute TTL. Rapid clicks within the same grid cell return instantaneous cached telemetry without network calls. |
| **3. Offline / network disconnect during disaster scenario** | Users in coastal storm areas lose connectivity | Register Service Worker for offline asset caching (PWA). Cache the last-known cyclone coordinates, wind field, and coastal emergency contacts in `localStorage` / `IndexedDB`. |
| **4. MapLibre canvas pan/zoom coordinate de-synchronization** | Wind particles drift or jitter out of place when zooming | Render wind particles on a dedicated MapLibre `custom` layer or sync via `map.on('render')`, transforming particle world coordinates using MapLibre's internal projection matrix instead of DOM overlays. |
| **5. Large coastal district GeoJSON bundle slowing mobile initial load** | Bundle size grows by 5–10MB, delaying initial dashboard render | Simplify district boundary polygons using Douglas-Peucker tolerance (`0.02°`), compressing the India coastal boundaries GeoJSON to under 120 KB, and load asynchronously via dynamic `import()`. |
| **6. User clicks outside oceanic / coastal domain (e.g. Himalayas or Europe)** | Inapplicable marine parameters (SST null, cyclogenesis formula invalid) | Detect coordinate bounding box. If coordinates fall outside the North Indian Ocean basin ($0^\circ-35^\circ\text{N}$, $45^\circ-105^\circ\text{E}$), display terrestrial weather mode and hide marine cyclogenesis metrics. |

---

## 4. Step-by-Step Implementation Roadmap

```
PHASE 1: Clickability & Multi-Page View Navigation (Immediate)
├── Wire `App.jsx` tab state to all 8 sidebar items
├── Build dedicated sub-views for Live Monitoring, Historical, Alerts, and Settings
├── Wire Header search, notification drawer, and report export
└── Add mobile slide-in navigation drawer with hamburger toggle

PHASE 2: Interactive Pinpoint Weather & Cyclogenesis Engine
├── Add click listener to MapLibre GL canvas
├── Build `weatherService.js` to query live atmospheric data (MSLP, Wind, Gusts, Temp, SST)
├── Implement the scientific Genesis Potential Index (GPI) algorithm
└── Render the live telemetry floating card / inspector panel

PHASE 3: ISRO SCORPIO-Style Animated Wind Particle Layer
├── Build `WindParticleLayer.js` utilizing Canvas 2D / WebGL
├── Ingest 0.25° wind vector grid ($u, v$ components) for the Indian Ocean
├── Implement speed-based color mapping and streamline fade trails
└── Add toggle control: [Satellite View | Animated Wind Streamlines | Hazard Cone]

PHASE 4: Real Geospatial Impact & Population Vulnerability Engine
├── Integrate simplified coastal district boundaries GeoJSON
├── Build `@turf/turf` hazard cone buffer and polygon intersection algorithms
├── Calculate live affected coastal districts and exposed population counts
└── Replace hardcoded stat card values with dynamic geospatial results

PHASE 5: Mobile-First Responsive Polish & Backend Ingestion Worker
├── Clean up `index.css` layout constraints and enable fluid vertical scrolling
├── Implement cooperative gesture control for mobile map interactions
└── Build automated backend worker (`ingest_worker.js`) to sync live IMD/RSMC storm tracks
```

---
*This plan serves as the definitive engineering roadmap for CYCLO-NEXUS, directly resolving every identified gap, fulfilling all architectural requirements, and matching operational standards established by ISRO SCORPIO, MOSDAC, and the India Meteorological Department (IMD).*
