# Satellite Watch Detector — Validation Report (physics_dav_v1)

Date: 30 Sep 2026 · Case set: `data/validation/cases.jsonl` (built by `build_case_set`, scored by `evaluate_detector`)

## Case set
20 of the 22 planned cases completed: 14 storm cases (IBTrACS North Indian Ocean, 2024–2025) and
6 storm-free days. The last cases failed because `mosdac.gov.in` stopped resolving (network/DNS
drop on 29 Sep 2026, 17:09 UTC); re-run `build_case_set` to add them — it is resumable.

A storm case is a **hit** when a candidate lies within 500 km of the best-track centre.
`max` is the highest candidate score anywhere in the frame (on storm-free days, that is the false-alarm score).

## Threshold sweep

| `WATCH_MIN_SCORE` | Storms detected (POD) | Storm-free days with a false alarm |
|---|---|---|
| 0.60 (previous) | 10 / 14 (71%) | 4 / 6 |
| 0.90 | 9 / 14 (64%) | 2 / 6 |
| **0.95 (chosen)** | **8 / 14 (57%)** | **0 / 6** |

Position error of hits: 101–463 km (median ≈ 330 km). Infrared finds the cold cloud
centre, not the circulation centre, so the ±300 km watch radius stays and official positions
always take priority.

## Decision
`WATCH_MIN_SCORE=0.95`. The requirement was high detection with at most one false-alarm day in eight;
0.60 and 0.90 break it, and 0.95 meets it. The missed cases are mostly early depressions
(weak, disorganised convection), which the official JTWC/IBTrACS layer still covers.

## Caveats
- Only 6 negative days — false-alarm rate is uncertain; add more negatives before relying on it.
- Retrained YOLO weights (Task 3.4) must be re-scored on this set before being switched on.

## Retrained models on real INSAT + IMERG data (3 Oct 2026)

Unified training set: 1,245 real frames (2018–2025, 74 storms), stored 512² uint8.
Split by season: train 2018–2022, model selection 2023, **test 2024–2025 (never seen)**.

### YOLO-OBB detector (yolo11s-obb, 512 px, best epoch 12 of 42, early stopping)

Held-out 2024–2025 frames: 230 storm instances, 55 storm-free frames. A hit is a box within 300 km of the best-track centre.

| Confidence | Storms found | Median centre error | Storm-free frames with a false alarm |
|---|---|---|---|
| 0.25 | 79% | 66 km | 33 / 55 |
| 0.5 | 67% | 63 km | 16 / 55 |
| 0.6 | 57% | 59 km | 8 / 55 |
| **0.7 (production default)** | 29% | 48 km | 3 / 55 |
| 0.8 | 6% | 34 km | 0 / 55 |

Old (synthetic-trained) weights: 0.000 on Remal. The physics detector (threshold 0.95) stays the primary watch signal: 8/14 storms, 0/6 false-alarm days, but 101–463 km centre error. YOLO adds precise extra candidates at 0.7, still subject to the SST and land checks.

### Track / intensity model (forecaster/track_model.py, ensemble of 5)

Storm-centred 6 × 3 h crops + recent motion → correction to persistence. Test: 133 windows (2024–2025).

| Track error (km) | 6 h | 12 h | 24 h | 48 h | 72 h |
|---|---|---|---|---|---|
| Persistence | 38 | 74 | 153 | 325 | 513 |
| Motion-only model | 37 | 72 | 151 | 318 | 476 |
| **Satellite + motion model** | 37 | 73 | 148 | 297 | 517 |

- **Track:** the satellite model improves on persistence by 3% at 24 h and 9% at 48 h.
- **Intensity:** wind error is about the same as persistence (8.5 vs 8.3 kt at 24 h).
- The full-domain ConvLSTM (`train_multi_horizon.py`) collapsed to a constant prediction on real data and is not used.
- Official JTWC / IMD forecasts remain more accurate, so `AI_FORECAST_ENABLED` stays `false`.

## AI consensus track and intensity forecast (5 Oct 2026)

Full tables: [`docs/guidance_report.md`](guidance_report.md) (regenerate with `python -m forecaster.guidance.consensus`).

- **Data:** 57 JTWC-numbered North Indian Ocean systems 2018–2026; ECMWF open-data tropical-cyclone tracks
  (AIFS, IFS HRES, IFS 51-member ensemble, AIFS ensemble; from Jan 2023) and UCAR RAL ATCF a-decks
  (GFS, GEFS, UKMET, CMC, NAVGEM; 2018 →). Truth: JTWC best track, cases ≥ 25 kt at start and verifying time.
- **Fitting:** seasons ≤ 2024 only (member set, per-model position shift, fallback weights, cone).
  **Test:** 2025–26 storms, used once.

| Unseen 2025–26 storms | 24 h | 48 h | 72 h |
|---|---|---|---|
| AI consensus track error | **58 km** | **109 km** | **139 km** |
| IMD official, long-period average 2019–23 (indicative) | 72 km | 112 km | 156 km |
| Persistence | 153 km | 288 km | 358 km |
| AI consensus intensity error | 5 kt | 7 kt | 4 kt |
| Persistence intensity error | 7 kt | 8 kt | 8 kt |

- **Cone** (67% of 2023–24 consensus errors): 63 / 98 / 171 km at 24 / 48 / 72 h; 2025–26 positions inside it:
  65% / 55% / 86% (target 67%).
- **Decision:** passes the Task 1.3 check (≤ IMD official average at 48–72 h) → may be shown, labelled
  "AI consensus (experimental)", next to the official forecast when `AI_FORECAST_ENABLED=true`.
- **Caveats:** small test sample (29 cases at 48 h, 14 at 72 h); 2025–26 storms were mostly weak, so intensity
  errors are lower than in 2023–24 (10 / 13 / 16 kt at 24 / 48 / 72 h in 2018–24, against IMD's 7 / 10 / 14 kt);
  IMD verifies against its own best track.
