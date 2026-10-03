# Cyclo-Nexus — Master Plan v5 (completion plan)

**Date:** 3 Oct 2026 · **Supersedes:** `masterplan_v4.md` · **Branch:** `feat/cap-cone-offline-training` (PR to `main` pending)

**Problem statement (SIH26070, MoES):** *"Develop an AI/ML-based system for identification, classification and prediction of different tropical cyclone patterns using multi-source satellite data."*

**Goal of this plan:** finish every remaining piece so the platform:
- runs live on free hosting without supervision;
- covers **identification, classification and prediction** with measured, published accuracy;
- matches or beats existing services wherever that is realistically possible.

**Rules carried over from v4:**
- No synthetic data on any live path.
- Official data (IMD / JTWC / IBTrACS) is always shown first; AI output is always labelled.
- An AI feature goes live only after it beats its baseline on seasons it never saw (2024–2026).
- Secrets live only in `.env`.
- Ask before new downloads or account actions.

---

## 1. Where we are (verified 3 Oct 2026)

| Area | Status | Evidence |
|---|---|---|
| Live data: INSAT-3DS (MOSDAC), GPM IMERG (GES DISC), JTWC + IBTrACS | ✅ working | live runs; MOSDAC search truncation fixed |
| Physics detector (DAV + cold cloud + rain + SST + land) | ✅ validated | 8/14 storms, 0/6 false-alarm days (`docs/validation_report.md`) |
| YOLO-OBB detector, retrained on 1,245 real frames | ✅ trained, not yet combined with the physics detector | held-out 2024–25: 67% found at conf 0.5, 29% at conf 0.7 (48 km median error, 3/55 false alarms) |
| Storm-centred track model (5-model ensemble) | ✅ trained, **not wired into pipeline** | 48 h: 297 km vs 325 km persistence (−9%) |
| Full-domain ConvLSTM forecaster | ❌ collapsed to a constant output | replaced by the track model; do not use |
| Intensity classification from imagery | ❌ not built | design in `docs/intensity_classification_plan.md` |
| Impact engine (GHS-POP 2020 grid, JTWC quadrant radii, India-view countries) | ✅ | Phailin 1.08 vs 1.32 crore reported |
| Website: home, alerts, storm pages, past storms, expert panel, 9 languages, offline PWA, CAP 1.2 feed, IMD cone, India official boundaries | ✅ | browser-tested desktop + phone |
| Tests | ✅ 38 backend + 115 Python | |
| Deployment (Oracle VM + Hostinger + Vercel + cron) | ❌ written, not deployed | `docs/deployment_guide.md` |
| Secrets previously committed (MOSDAC, JAXA, webhook) | ⚠️ must be rotated | team action |

---

## 2. Accuracy targets (what "highest accuracy" means, measured on unseen 2024–2026 seasons)

| Capability | Baseline / existing service | Today | Target at completion |
|---|---|---|---|
| **Identification**: storms found (≥ D) | Physics detector 57% | YOLO 29–67% | **≥ 70% found, ≤ 5% false-alarm frames, centre error ≤ 60 km** |
| Early genesis lead time | IMD naming time | not measured | **flag 12–24 h before official Depression** in ≥ 50% of cases |
| **Classification**: wind error | Dvorak / ADT ≈ 10–15 kt | none | **RMSE ≤ 10–12 kt; exact IMD class ≥ 60%; within one class ≥ 90%** |
| **Prediction**: track, 24 / 48 / 72 h | Persistence 153 / 325 / 513 km; IMD official ≈ 60–90 km at 24 h | 148 / 297 / 517 km | **AI consensus ≈ official: ≤ 90 / 160 / 250 km** |
| Prediction: intensity, 24 h | Persistence 8.3 kt | 8.5 kt | **≤ 6–7 kt** |
| Impact exposure vs reported "affected" | — | within ~×2 | **within ±50% on 6+ documented storms** |

No system reaches 100%. These targets match published research and official services, and every number above gets re-measured and written into `docs/validation_report.md`.

---

## 3. Work plan

Work is grouped in phases. Each task lists what it delivers, how it's done, its acceptance check and its owner. **Agent** means Claude does it; **Team** means it needs your account, GPU or decision.

### Phase 0 — Close out the current branch (½ day)
| # | Task | Acceptance | Owner |
|---|---|---|---|
| 0.1 | Open and merge PR `feat/cap-cone-offline-training` → `main` (or install `gh` CLI so the agent can) | merged, CI green | Team |
| 0.2 | Fix leftovers: "people living in towns" subtitle (all 9 languages), localised compass directions (NNW → regional words) | no English fragments in regional UI | Agent |
| 0.3 | Commit regenerated data notes: `pop_grid.bin` provenance, `data/static/geo` kept out of git | README data section updated | Agent |

### Phase 1 — Prediction to official-level accuracy (4–5 days)
| # | Task | How | Acceptance | Owner |
|---|---|---|---|---|
| 1.1 | **Satellite steering winds** | INSAT-3DS atmospheric motion vectors (MOSDAC) + ASCAT/OSCAT scatterometer winds around each storm, as track-model inputs | track model 48 h error −15% or better vs today | Agent (+ Team: free EUMETSAT/Copernicus Marine account if needed) |
| 1.2 | **AI weather-model guidance** | Pull ECMWF AIFS open data + GFS every 6 h and extract storm tracks (vortex tracker) | AIFS/GFS track errors reported on 2024–26 storms | Agent (downloads approved) |
| 1.3 | **Consensus forecaster** | Bias-corrected, error-weighted blend of official + AIFS + GFS + our track model, trained on 2018–2023 | ≤ official error on 2024–26 at 48–72 h, or documented gap | Agent |
| 1.4 | Wire the track model / consensus into the live pipeline | `inference/serve.py` + `live_pipeline_runner` publish `AI_CONSENSUS` forecasts; forecast cone from its own ensemble spread | live storm page shows the labelled AI forecast | Agent |
| 1.5 | Turn `AI_FORECAST_ENABLED` on only if 1.3 passes | feature flag + validation report entry | report states pass/fail | Agent |

### Phase 2 — Classification (IMD 7 classes) (3 days)
| # | Task | How | Acceptance | Owner |
|---|---|---|---|---|
| 2.1 | Intensity estimator | Storm-centred 6-frame CNN regression of wind (kt) + ordinal IMD-class head, from the existing 1,245-frame store (no new download) | RMSE ≤ 12 kt on 2024–25 | Agent (local RTX 4060) |
| 2.2 | Environment inputs | Satellite SST (GHRSST), ocean heat content (Copernicus Marine), mid-level humidity / shear | intensity 24 h forecast ≤ 7 kt | Agent |
| 2.3 | Show it on the site | "Satellite intensity estimate" with error bar on storm pages, expert panel and watch areas; official class always primary | browser check | Agent |
| 2.4 | Rapid-intensification flag | Classifier probability of ≥ 30 kt / 24 h | probability calibration plot in report | Agent |

### Phase 3 — Identification and more training data (3 days, mostly downloads + GPU)
| # | Task | How | Acceptance | Owner |
|---|---|---|---|---|
| 3.1 | More storms | INSAT-3D 2014–2017 frames through the unified builder (~15 GB) | store ≥ 1,800 frames | Agent |
| 3.2 | Global pretraining | NOAA GridSat-B1 IR storm crops (1980+, ~5–10 GB) → pretrain YOLO + intensity CNN, fine-tune on INSAT | YOLO ≥ 70% found at ≤ 5% false alarms | Agent |
| 3.3 | Detector fusion | Physics detector score + YOLO box + SST/land gate → one calibrated "watch probability" | beats both detectors alone on 2024–26 | Agent |
| 3.4 | Genesis lead-time study | Compare first watch time with first IMD Depression time for every 2024–26 system | lead-time histogram in report | Agent |
| 3.5 | Grad-CAM in the expert panel | explain YOLO / intensity predictions on demand | heat-map shown for active system | Agent |

### Phase 4 — Alerts and reach (2–3 days)
| # | Task | Acceptance | Owner |
|---|---|---|---|
| 4.1 | Register the CAP 1.2 feed with NDMA SACHET (after deployment) | feed listed / accepted | Team |
| 4.2 | Web-push notifications (PWA) for alert level changes, by chosen district | opt-in push received on a phone | Agent |
| 4.3 | SMS / WhatsApp gateway (provider-agnostic; free test tier) | test message sent to a team number | Team account + Agent |
| 4.4 | Native-speaker review of the 7 regional translations, especially advisories | sign-off noted in `docs/` | Team |
| 4.5 | Storm-surge indication (INCOIS bulletins link + simple surge-risk flag from wind and bathymetry) | shown with "indicative" label | Agent |

### Phase 5 — Deployment and operations (1–2 days)
| # | Task | Acceptance | Owner |
|---|---|---|---|
| 5.1 | **Rotate secrets** (MOSDAC, JAXA, webhook, CRON) | old values revoked | Team |
| 5.2 | Create accounts: Oracle Cloud (Mumbai/Hyderabad), Vercel, cron-job.org; Hostinger Node + MySQL | accounts ready | Team |
| 5.3 | Deploy per `docs/deployment_guide.md`: pipeline + inference on Oracle VM (systemd), API + DB on Hostinger, site on Vercel, 30-min cron | public URL live, `/health` green | Agent (guided) + Team |
| 5.4 | `npm run demo:stop` before go-live; set `VITE_HIDE_DEMO_BADGE` only for recordings | no DEMO rows in production | Agent |
| 5.5 | Monitoring: uptime check on `/health`, heartbeat alerts to the team email, weekly validation job | alert received when a feed is stale | Agent |
| 5.6 | Backups: nightly MySQL dump; weights versioned | restore tested once | Agent |

### Phase 6 — Final verification and submission (1–2 days)
| # | Task | Acceptance | Owner |
|---|---|---|---|
| 6.1 | Full test pass (Python, backend, frontend build) + browser checks desktop/phone in 3 languages | all green | Agent |
| 6.2 | Re-run all validation (detector, classifier, track, impact) on 2024–26 → final `docs/validation_report.md` | every target in §2 reported as met / not met | Agent |
| 6.3 | End-to-end live test: real cycle → website → CAP feed → push | screenshots in report | Agent |
| 6.4 | Update README, PPT (measured results), demo video | files in `docs/ppt` | Agent |
| 6.5 | Tag release `v1.0` | tag on `main` | Team |

---

## 4. Timeline (working mostly autonomously)

| Day | Work |
|---|---|
| 1 | Phase 0 + start Phase 3.1 downloads in the background |
| 2–5 | Phase 1 (prediction) |
| 6–8 | Phase 2 (classification) |
| 9–10 | Phase 3.2–3.5 (detector fusion, pretraining, lead time) |
| 11–12 | Phase 4 (alerts) |
| 13 | Phase 5 (deployment — needs team accounts on day 1–2 to avoid waiting) |
| 14 | Phase 6 (verification, docs, release) |

**Total: about 2–3 weeks.** For the submission, Phases 0, 1.4, 2.1–2.3, 5 and 6 alone (about 7 days) give a complete identification + classification + prediction story.

---

## 5. Needed from the team (in order)

1. Merge the open PR, or allow installing `gh` (GitHub CLI, ~13 MB).
2. Rotate the MOSDAC, JAXA and webhook secrets.
3. Create free accounts: Oracle Cloud, Vercel, cron-job.org, Copernicus Marine / EUMETSAT. Credentials go in `.env`; the agent never sees or prints them.
4. Hostinger Node app + MySQL details.
5. Native-speaker reviewers for Tamil, Telugu, Malayalam, Bengali, Odia, Kannada and Marathi.
6. SMS/WhatsApp provider choice (optional).

## 6. Risks and how they are handled

| Risk | Mitigation |
|---|---|
| MOSDAC outages or archive gaps | resumable builders, phase-1 cache, gap-filling rules, official feed always independent |
| AI models don't reach targets | feature flags keep them off; official data stays primary; honest report |
| Free-tier limits (Oracle RAM, Hostinger) | uint8 transport, single-server inference, caching |
| Translation mistakes in safety text | native review before official use; English always one tap away |
| Boundary depiction | India-view boundaries (Natural Earth IND) on all maps; keep in sync if the Survey of India updates |

## 7. Definition of done

- The live site updates every 30 minutes from real data, with no manual steps.
- Every AI output on the site has a published accuracy number from unseen seasons.
- Identification, classification and prediction are all live, labelled, and compared against official data.
- Alerts reach people in 9 languages via web, push and CAP, with SMS optional.
- `docs/validation_report.md`, the README and the PPT all show the same measured numbers.
