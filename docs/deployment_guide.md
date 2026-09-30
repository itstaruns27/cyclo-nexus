# CYCLO-NEXUS Deployment Guide (v4 — free stack)

```
Oracle Always-Free VM (Mumbai/Hyderabad)          Hostinger                     Vercel
┌──────────────────────────────────────┐   HMAC   ┌──────────────────────┐ HTTPS ┌──────────────┐
│ cyclonexus-pipeline (every 30 min)   │ ───────► │ Express API + MySQL  │ ◄──── │ React (Vite) │
│   MOSDAC INSAT-3DS + NASA IMERG      │ webhooks │ official-feed worker │       └──────────────┘
│ cyclonexus-inference (127.0.0.1:8000)│          │ (JTWC + IBTrACS)     │
└──────────────────────────────────────┘          └──────────────────────┘
                                   free cron (cron-job.org) → POST /api/v1/internal/poll-telemetry
```

Why the pipeline and the inference service share one VM: the 6-frame input window never crosses the
internet, the VM has an Indian IP for MOSDAC, and Always-Free VMs do not sleep. Hugging Face Spaces
is the fallback for inference (see §4).

## 0. Accounts & secrets (you)

| Item | Where |
|---|---|
| MOSDAC login | https://mosdac.gov.in (data download enabled) |
| NASA Earthdata login + approve **NASA GESDISC DATA ARCHIVE** | https://urs.earthdata.nasa.gov/profile → Applications |
| `WEBHOOK_SECRET` (same on VM and backend) | `node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"` |
| `CRON_SECRET` (backend only) | same command |

Rotate any secret that was ever committed to the repository before going live.

## 1. Backend — Hostinger (Node.js + MySQL)

1. hPanel → Databases → create a MySQL database and user.
2. hPanel → Advanced → Node.js → create an app: Node 18+, application root `backend`, startup file `src/server.js`.
3. Upload `backend/` (without `node_modules`), then in the app terminal: `npm ci --omit=dev`.
4. Create `backend/.env` from `backend/.env.example`:
   - `DB_*`, `WEBHOOK_SECRET`, `CRON_SECRET`
   - `CORS_ORIGIN=https://<your-vercel-domain>,https://<custom-domain>`
   - `TRUST_PROXY=1`, `NODE_ENV=production`
5. `npm run migrate` (creates/extends tables; additive only).
6. Load historical best tracks once (the CSV comes from NOAA NCEI IBTrACS, file `ibtracs.NI.list.v04r01.csv`):
   `node scripts/import_ibtracs.js /path/to/ibtracs.NI.list.v04r01.csv`
7. Restart the app and check `https://<api-domain>/api/v1/health`.

Passenger may put an idle app to sleep, so schedule the official feed externally as well:
cron-job.org → every 30 min → `POST https://<api-domain>/api/v1/internal/poll-telemetry`
with header `Authorization: Bearer <CRON_SECRET>`.

## 2. Pipeline + inference — Oracle Cloud Always-Free VM

1. Create an Always-Free VM (Ampere A1, 4 OCPU / 24 GB, Ubuntu 22.04+) in **ap-mumbai-1** or **ap-hyderabad-1**.
2. `git clone <repo> && cd <repo>` — copy `vision/weights/vision_best.pt` and `forecaster/weights/forecaster_best.pt` onto the VM (they are git-ignored).
3. `bash deploy/oracle/setup.sh`
4. Edit `/etc/cyclonexus/pipeline.env` (credentials, `WEBHOOK_SECRET`, `BACKEND_API_URL`).
5. `sudo systemctl enable --now cyclonexus-inference cyclonexus-pipeline`
6. `journalctl -u cyclonexus-pipeline -f` — first cycle downloads 6 INSAT frames (~25 MB each); later cycles fetch one.

The pipeline posts a signed heartbeat every cycle; `/api/v1/health` marks it `stale` after 90 minutes
and the website shows a "data delayed" banner.

## 3. Frontend — Vercel

1. Import the repository; **Root Directory** = `frontend` (framework: Vite). `frontend/vercel.json` adds the SPA rewrite.
2. Environment variable: `VITE_API_BASE_URL=https://<api-domain>` (no trailing `/api/v1`).
3. Deploy; open `/forecast` directly to confirm the rewrite (should load, not 404).

## 4. Fallback: inference on Hugging Face Spaces

1. Create a Space with the **Docker** SDK; push `inference/`, `forecaster/`, `vision/weights/`, `.dockerignore` and
   `inference/Dockerfile` (as the Space's `Dockerfile`, building from the repository root).
2. Space secret `INFERENCE_API_KEY=<random>`; on the pipeline host set the same `INFERENCE_API_KEY` and
   `INFERENCE_URL=https://<space>.hf.space/predict`.
3. Keep `TENSOR_TRANSPORT=uint8` (real windows are ~15 MB instead of ~80 MB).

Local image test: `docker build -f inference/Dockerfile -t cyclonexus-inference .` then
`docker run -p 7860:7860 cyclonexus-inference` and `curl localhost:7860/health`.

## 5. Monitoring (free)

- UptimeRobot: HTTP keyword monitor on `/api/v1/health` for `"stale":false` (or alert on `degraded`).
- `/status` page on the website shows every component, last success and latest data time.

## 6. Local development

```bash
# MySQL/MariaDB running locally (e.g. XAMPP), then:
cd backend && npm install && npm run migrate && node scripts/import_ibtracs.js && npm run dev
.venv/Scripts/python -m uvicorn inference.serve:app --port 8000          # from repo root
.venv/Scripts/python -m data_pipeline.ingestion.live_pipeline_runner      # one live cycle
cd frontend && npm install && npm run dev                                # http://localhost:5173
```
