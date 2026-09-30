# 🌀 CYCLO-NEXUS: Master Implementation & Deployment Blueprint (v3.0.0 — Architect Edition)

**Project:** CYCLO-NEXUS — AI Cyclone Tracking Platform (MoES SIH26070)
**Role for Executing Agent:** Principal Systems Architect and Lead SRE.

## 🛑 STRICT EXECUTION DIRECTIVES (READ CAREFULLY)

You are executing a highly fragile, multi-boundary system upgrade. This architecture utilizes a modular, zero-cost production stack (Vercel for frontend, Hostinger for Node/MySQL backend, Hugging Face Spaces for AI inference) designed to support up to 10,000 monthly active users on a custom domain. Any deviation from these constraints will result in catastrophic production failures.

1. **Micro-Task Isolation:** You must implement exactly ONE micro-task at a time. After outputting the code for a micro-task, you must output its **Verification Task** and **STOP**. Do NOT proceed to the next task until the user explicitly says "PASS".
2. **Schema-First:** Import types from `schemas/` or `frontend/src/types/` before writing logic.
3. **No Cross-Boundary Writes:** Modify only the files relevant to the specific micro-task assigned.
4. **Additive-Only DB:** No `DROP` or `TRUNCATE`. Use `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`.
5. **Dependency Quarantine:** New pip packages go to the pipeline/inference `requirements.txt`.
6. **Hostinger Constraints:** The following libraries are strictly PROHIBITED on the Node.js backend to prevent deployment failures: `torch`, `tensorflow`, `rasterio`, `h5py`, `gdal`, `opencv-python`.

---

## PHASE 1: Data Pipeline Hardening (P0 Blockers)

### Micro-Task 1.1: Tensor Zlib Compression & Base64 Serialization
* **Target:** `data_pipeline/ingestion/live_pipeline_runner.py`
* **Implementation:** Ensure the `(6, 4, 1024, 1024)` numpy tensor is contiguous. Compress it using `zlib.compress(tensor_f32.tobytes(), level=6)`. Encode the result using `base64.b64encode().decode("ascii")`. Update the HTTP POST payload to send `{"tensor_b64": "...", "tensor_shape": [6, 4, 1024, 1024], "tensor_dtype": "float32"}`.
* **Verification Task 1.1:** Write a standalone Python snippet that generates a random `(6, 4, 1024, 1024)` float32 numpy array, compresses it, and prints the final Base64 string length in megabytes. Verify it is under 35 MB.

### Micro-Task 1.2: Strict Pydantic Schema Enforcement
* **Target:** `inference/schemas.py`
* **Implementation:** Update `InferenceRequest`. Replace the nested list with `tensor_b64: str`, `tensor_shape: List[int]`, `tensor_dtype: str`. Add `@validator` methods that hard-fail if `tensor_shape != [6, 4, 1024, 1024]` or `tensor_dtype != "float32"`.
* **Verification Task 1.2:** Write a quick test using `InferenceRequest(tensor_b64="...", tensor_shape=[1,1], tensor_dtype="float64")` and catch the `ValidationError` to prove the guard works.

### Micro-Task 1.3: Safe Tensor Deserialization & Reshape
* **Target:** `inference/serve.py`
* **Implementation:** In the `/predict` route, decode the base64 string, then `zlib.decompress()`. Implement a strict byte-length guard (`EXPECTED_BYTES = 6 * 4 * 1024 * 1024 * 4`). If `len(raw_bytes) != 100663296`, raise an `HTTPException(422)`. Reconstruct via `np.frombuffer(raw_bytes, dtype=np.float32).reshape(6, 4, 1024, 1024)`. Map to `torch.device("cuda" if torch.cuda.is_available() else "cpu")`.
* **Verification Task 1.3:** Send the payload generated in 1.1 to the local FastAPI `/predict` endpoint. Confirm HTTP 200 and successful model inference output.

### Micro-Task 1.4: HMAC Secret Generation & Pipeline Gzip
* **Target:** `backend/.env`, `data_pipeline/.env`, `data_pipeline/ingestion/live_pipeline_runner.py`
* **Implementation:** Generate a 256-bit hex string for `WEBHOOK_SECRET` in both `.env` files. In `live_pipeline_runner.py`, serialize the webhook JSON, generate the HMAC-SHA256 signature, then apply `gzip.compress(level=6)`. Set headers `Content-Encoding: gzip` and `X-CycloNexus-Signature`.
* **Verification Task 1.4:** Print the compressed byte length and the generated signature in the pipeline logs before dispatch.

### Micro-Task 1.5: Node.js Zip Bomb Guard & Single-Pass Decompression
* **Target:** `backend/src/server.js`, `backend/src/middleware/webhook_auth.js`
* **Implementation:** Remove `express.json()`. Implement a custom middleware that reads the incoming stream up to a hard 2MB wire limit. Decompress the buffer using `zlib.gunzip({ maxOutputLength: 10 * 1024 * 1024 })` (10MB limit). Assign `req.rawBody = decompressedBuffer` and `req.body = JSON.parse(decompressedBuffer)`. In `webhook_auth.js`, apply `crypto.timingSafeEqual` against `req.rawBody`.
* **Verification Task 1.5:** Fire a mocked valid signed gzip request to `localhost:3001/api/v1/webhook/inference`. Verify HTTP 200. Fire a 3MB mocked garbage payload and verify HTTP 413.

---

## PHASE 2: Backend Cleanup & Ingestion Automation (P1 Debt)

### Micro-Task 2.1: Dead Route Elimination
* **Target:** `backend/` directory, `frontend/` directory.
* **Implementation:** Delete `backend/server.js`, `backend/routes/api.js`, `backend/webhook.js`, `backend/src/routes/forecast.js`, and `frontend/src/hooks/useCycloneData.js`. In `backend/src/server.js`, remove the `forecastRoutes` require and mount.
* **Verification Task 2.1:** Start the Express server. Run `curl http://localhost:3001/api/v1/cyclones/1/forecast`. Confirm it hits the real handler in `cyclones.js`, not a 404 or stub.

### Micro-Task 2.2: Zod Timestamp & Auth Hardening
* **Target:** `backend/src/utils/validators.js`
* **Implementation:** Update the schema `generated_at` field to `z.string().datetime({ offset: true })`. 
* **Verification Task 2.2:** Run a Node script parsing `{"generated_at": "2026-09-29T16:40:31+05:30"}` through the schema. Confirm `safeParse` is true.

### Micro-Task 2.3: NOAA Ingestion Worker & Secure Cron Trigger
* **Target:** `backend/src/workers/ingest_worker.js`, `backend/src/routes/internal.js`, `backend/src/server.js`
* **Implementation:** Write the worker to fetch NOAA IBTrACS GeoJSON wrapped in a `try/catch`. Upsert active storms to MySQL. Create `internal.js` with `POST /api/v1/internal/poll-telemetry` protected by a `CRON_SECRET` header to manually trigger this worker, preventing Hostinger Passenger sleep cycles.
* **Verification Task 2.3:** Run `curl -X POST http://localhost:3001/api/v1/internal/poll-telemetry -H "Authorization: Bearer <CRON_SECRET>"`. Confirm DB tables are populated.

---

## PHASE 3: Client Interactivity & Mobile-First Polish (Modules D & E)

### Micro-Task 3.1: React Router Integration & Global Layout
* **Target:** `frontend/src/App.jsx`, `frontend/src/components/Sidebar.jsx`
* **Implementation:** Install `react-router-dom`. Replace local `useState` tab state with actual routes (`/`, `/forecast`, `/historical`). Wire `Sidebar.jsx` `NavLink` components to these routes to preserve state on browser refresh.
* **Verification Task 3.1:** Load `http://localhost:5173/forecast` directly in the browser. Confirm it loads the forecast view with the Sidebar "Forecast" item highlighted.

### Micro-Task 3.2: Mobile Responsive Unlock & Map Gestures
* **Target:** `frontend/src/index.css`, `frontend/src/components/Header.jsx`, `frontend/src/components/CycloneMap.jsx`
* **Implementation:** Remove `overflow: hidden; height: 100vh;` from `index.css`; replace with `min-height: 100vh; overflow-x: hidden;`. Add a hamburger menu in `Header.jsx` to toggle a mobile sidebar drawer. Add `cooperativeGestures: true` to the MapLibre instantiation.
* **Verification Task 3.2:** Open Chrome DevTools (iPhone 12). Scroll the page vertically over the map. Confirm the page scrolls instead of the map zooming. Verify the hamburger menu works.

---

## PHASE 4: Geospatial Engines & Visualization (Modules A, B, C)

### Micro-Task 4.1: Pinpoint GPI Engine (Map Click)
* **Target:** `frontend/src/services/weatherService.js`, `CycloneMap.jsx`, `WeatherInspector.jsx`
* **Implementation:** Implement `map.on('click')` to capture coordinates. Fetch Open-Meteo current weather for that exact point. Implement the GPI formula ($SST \ge 26.5^\circ\text{C}$, $\Delta P = \max(0, 1013 - P_{mslp})$, $V_{10m} > 35\text{ km/h}$). Render `WeatherInspector.jsx` dynamically.
* **Verification Task 4.1:** Click a random ocean point in the local UI. Verify the network tab shows 1 API call and the UI renders the GPI score.

### Micro-Task 4.2: Backend Wind Grid Cache (API Exhaustion Fix)
* **Target:** `backend/src/workers/ingest_worker.js`, `backend/src/routes/weather.js`
* **Implementation:** Add a sub-routine to the ingest worker to fetch a 1.0° coarse wind grid (~1,500 points) from Open-Meteo once every 3 hours. Save this as a JSON file or DB cache. Create `GET /api/v1/weather/wind-grid` to serve it to the frontend.
* **Verification Task 4.2:** Hit `http://localhost:3001/api/v1/weather/wind-grid`. Confirm it returns the cached wind matrix instantly.

### Micro-Task 4.3: ISRO-Style Wind Canvas
* **Target:** `frontend/src/components/WindParticleCanvas.jsx`
* **Implementation:** Fetch the cached backend grid. Create an HTML5 Canvas overlay on MapLibre. Implement the advection loop (4,000 particles desktop / 1,500 mobile) utilizing `rgba(0,0,0,0.96)` for trailing frames.
* **Verification Task 4.3:** Monitor Chrome DevTools Performance. Confirm the canvas maintains >45 FPS and successfully pauses on `map.on('movestart')`.

### Micro-Task 4.4: Turf.js Impact Engine & UI Thread Fix
* **Target:** `frontend/src/services/impactEngine.js`, `StatCards.jsx`
* **Implementation:** Use a simplified coastal district GeoJSON. Wrap `turf.buffer` and `turf.intersect` inside a `useMemo` hook in the main tracking component to calculate fractional population exposure without blocking the React render cycle.
* **Verification Task 4.4:** Run a React profiler trace while switching between active cyclones. Confirm the render pass does not exceed 16ms (60 FPS).

---

## PHASE 5: Zero-Cost Production Deployment

### Micro-Task 5.1: Dynamic API Base & Production CORS
* **Target:** `frontend/src/services/api.js`, `backend/src/config/cors.js`
* **Implementation:** Safely map `API_BASE`: `const baseUrl = import.meta.env.VITE_API_BASE_URL; export const API_BASE = baseUrl ? baseUrl.replace(/\/$/, '') + '/api/v1' : '/api/v1';`. Allow dynamic Origins in Express matching `process.env.CORS_ORIGIN`.
* **Verification Task 5.1:** Build frontend with `VITE_API_BASE_URL=https://<your-custom-domain> npm run build`. Search the output JS chunk to ensure the production domain was injected.

### Micro-Task 5.2: Hugging Face CPU Container Setup
* **Target:** `inference/Dockerfile`, `inference/serve.py`
* **Implementation:** Write a Dockerfile using `python:3.10-slim`. Use `pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu`. Expose `7860`.
* **Verification Task 5.2:** Run `docker build -t inference-test ./inference`. Ensure the build completes without pulling the 5GB CUDA runtime.

### Micro-Task 5.3: Vercel Frontend Configuration
* **Target:** `vercel.json`
* **Implementation:** Add SPA rewrite rule `/(.*) -> /index.html` to support React Router on Vercel infrastructure.
* **Verification Task 5.3:** Deploy to Vercel via CLI. Verify navigating directly to `/forecast` returns 200 OK, not 404.

---

**Initialization Request for Agent:**
Acknowledge receipt of this blueprint. Confirm you understand the strict single-task execution policy. Output the implementation code for **Micro-Task 1.1** and its verification task, then WAIT for the user to say "PASS".