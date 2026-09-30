# CYCLO-NEXUS Master Plan v4.0 — Live, Honest, Free

Supersedes the execution order of `masterplan.md` (v3.0.0). v3 rules still apply: schema-first,
additive-only DB (`ADD COLUMN IF NOT EXISTS`), no heavy AI libraries on the Node backend,
dependency quarantine. **New rule: no synthetic or demo data on any live path.**

## Why v4
Verified on 2026-09-29:
- Live INSAT-3DS (MOSDAC) + NASA IMERG ingestion works end-to-end, including archive replay.
- The shipped YOLO / forecaster weights **do not detect real cyclones** (0.000 on Cyclone Remal,
  26 May 2024 12Z, with correct input). They were trained on synthetic spirals.
- Real-data inference payload is 77–83 MB (target < 35 MB).

So the platform needs (a) an authoritative data layer that is always right, (b) an AI layer that is
honest about what it can do, and (c) a path to retrain on real imagery.

## Architecture (target)

```
MOSDAC INSAT-3DS ─┐                         ┌─► FastAPI inference (YOLO-OBB + forecaster + physics detector)
NASA GPM IMERG ───┼─► pipeline runner ──────┤
                  │   (6×3-hourly window)   └─► signed webhook ─┐
JTWC (io* systems)┐                                             ▼
IBTrACS ACTIVE ───┴─► Node official-feed worker ───────► MySQL ◄── Express API ◄── React (Vercel)
                                                           ▲
                               pipeline heartbeat ─────────┘   /health → data freshness
```

Layers shown to users:
1. **Official** (JTWC warnings / IBTrACS provisional, with IMD referenced as the national authority) — positions, intensity, forecast track.
2. **Satellite analysis (AI)** — INSAT/IMERG-derived fix and rainfall for each official system, and
   *satellite watch areas*: persistent, organised deep convection over warm ocean that is not yet an official system (minor / pre-genesis). Always labelled experimental.

## Phases & progress

| # | Task | Status |
|---|------|--------|
| 1 | Blueprint Phase 1 (1.1–1.5) + replay-proof HMAC | ✅ done |
| 1b | Live MOSDAC + GES DISC workers, real 6×3 h window, frame cache, `--at` replay, `--dry-run`, detection flag, no fake frontend data | ✅ done |
| 2.1 | Remove dead routes/files (v3 2.1) | ✅ done |
| 2.2 | Zod `generated_at` accepts offsets (v3 2.2) | ✅ done |
| 2.3 | Migration 006: `source`, `status`, `source_url`, `last_update` columns; `pipeline_status` table | ✅ done |
| 2.4 | Official-feed worker (JTWC `io*` .tcw + IBTrACS ACTIVE NI) → cyclones/forecasts; in-process schedule + `POST /api/v1/internal/poll-telemetry` (CRON_SECRET) | ✅ done |
| 2.5 | Pipeline heartbeat → `/api/v1/health` reports data freshness; webhook accepts `source` | ✅ done |
| 3.1 | Physics-based satellite detector (cold-cloud cluster + rain core + persistence) in inference; YOLO used only when it fires | ✅ done — `WATCH_MIN_SCORE=0.95` from 3.3 |
| 3.2 | Pipeline publishes AI fixes linked to official systems, and watch areas; AI forecast gated by `AI_FORECAST_ENABLED` | ✅ done |
| 3.3 | Validation replay suite (Remal positive, quiet day negative) with pass/fail report | ✅ 20/22 real cases; threshold 0.95 → 8/14 storms, 0/6 false-alarm days (`docs/validation_report.md`) |
| 3.4 | Real-data training set builder (IBTrACS NI labels × MOSDAC archive) + Kaggle/Colab training notebook | ✅ toolkit done; YOLO training on team GPU pending |
| 3.5 | Multi-horizon forecaster: one head per lead time, Atkinson–Holliday loss, real-window builder + trainer (`forecaster/train_multi_horizon.py`); legacy weights still load | ✅ code + tests; training on team GPU pending |
| 4.1 | uint8 quantised tensor transport (< 35 MB), float32 still accepted | ✅ done |
| 5.1 | Frontend: official vs AI badges, multi-cyclone selector, watch-area layer, stale-data banner | ✅ done |
| 5.2 | React Router routes + mobile layout + map cooperative gestures (v3 3.1–3.2) | ✅ done |
| 5.3 | Pinpoint GPI inspector + backend wind-grid cache + wind particle canvas (v3 4.1–4.3) | ✅ done |
| 6.1 | `API_BASE` from `VITE_API_BASE_URL`, dynamic CORS (v3 5.1) | ✅ done |
| 6.2 | Inference Dockerfile (CPU torch), `vercel.json`, Oracle Always-Free VM setup (systemd units), deployment guide | ✅ written; deployment on team accounts pending |
| 7 | Full verification: tests, live cycle, replay suite, browser check | ✅ 115 Python tests pass; live publish cycle 30 Sep 2026 06:30 UTC ok (heartbeat recorded, 0 watch areas at 0.95) |

## Free deployment target
- Frontend → Vercel. API + MySQL → Hostinger (or TiDB Serverless).
- Pipeline + inference → Oracle Cloud Always-Free ARM VM in Mumbai/Hyderabad (co-located: no 80 MB
  transfer, Indian IP for MOSDAC, never sleeps). Fallback: Hugging Face Space + uint8 transport + cron ping.
- Monitoring: `/api/v1/health` freshness + UptimeRobot / Healthchecks.io.

## User actions required (cannot be done by the agent)
- Rotate MOSDAC password and webhook secret (were committed in source).
- Create Oracle Cloud / Vercel / Hostinger deployments with own accounts.
- Run retraining on Kaggle/Colab GPU with own account.

### Additions made during execution
- Template advisories (en/hi) replace Gemini (user choice); `/api/v1/cyclones/:id/advisory`.
- IBTrACS NI best tracks (1980+) imported to `besttrack_points`; `/api/v1/historical/*`.
- Wind grid cache `/api/v1/weather/wind-grid` (Open-Meteo, 2°, 3-hourly).
- Inference `/health`; uint8 transport → 15.3 MB real payload (was 83 MB).
- Frontend fake numbers found (people affected, model accuracy, movement, landfall, env panel) → Task 5.1 removes them.
