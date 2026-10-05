# Satellite intensity estimate — validation

Generated 2026-10-05 15:10 UTC by `python -m forecaster.intensity.train fit`.

Estimates a storm's maximum sustained wind (IMD 3-minute, kt) and IMD class from the current INSAT image, the image
3–9 h earlier and IMERG rain — an automated Dvorak-style analysis (eye auto-centring, cloud-top rings, cold-cloud cover).

**INSAT data:** 1167 images of 73 storms (2018–2025), IMD best-track labels.
**Global pre-training:** NOAA HURSAT-B1, 1027 storms worldwide 2004–2015, 55145 images, JTWC/NHC 1-minute winds; on held-out storms RMSE 14.2 kt.

## Model selection — leave-one-season-out, 2018–2023

| Method | RMSE (kt) | MAE (kt) | Bias (kt) | Exact IMD class | Within one class |
|---|---|---|---|---|---|
| INSAT features (LightGBM) | 19.5 | 14.4 | -0.9 | 32% | 72% |
| 3-feature linear (Dvorak-like) | 22.5 | 18.1 | -0.8 | 24% | 64% |
| INSAT + global pre-trained model (LightGBM) | 18.0 | 13.1 | -0.8 | 33% | 78% |
| Global model, calibrated to IMD (linear) | 16.4 | 12.2 | -0.4 | 30% | 78% |
| Global model, quantile-mapped to IMD | 17.1 | 11.8 | -0.1 | 38% | 80% |
| CNN (HURSAT pre-trained, INSAT fine-tuned) | 13.7 | 9.9 | -0.4 | 40% | 86% |
| Blend: CNN + global model, quantile-mapped | 12.8 | 9.2 | -0.1 | 43% | 87% |

Chosen: **Blend: CNN + global model, quantile-mapped**.

CNN rows: out-of-fold predictions from leave-one-season-out over all 2018–25 seasons (`python -m forecaster.intensity.cnn cv`), so in this 2018–23 table each CNN fold had also seen 2024–25 — the 2024–25 test and the every-season table below never include the scored season in training.

## Test seasons 2024–25 (scored once; 230 images: Asna 2024, Dana 2024, Ditwah 2025, Fengal 2024, Montha 2025, Remal 2024, Senyar 2025, Shakhti 2025, Unnamed 2024, Unnamed 2025)

| Method | RMSE (kt) | MAE (kt) | Bias (kt) | Exact IMD class | Within one class |
|---|---|---|---|---|---|
| INSAT features (LightGBM) | 10.7 | 8.5 | +2.5 | 35% | 84% |
| 3-feature linear (Dvorak-like) | 14.8 | 12.4 | -0.9 | 41% | 72% |
| INSAT + global pre-trained model (LightGBM) | 10.5 | 8.4 | +2.4 | 39% | 83% |
| Global model, calibrated to IMD (linear) | 11.4 | 9.5 | +5.7 | 25% | 83% |
| Global model, quantile-mapped to IMD | 12.5 | 8.6 | +2.4 | 47% | 81% |
| CNN (HURSAT pre-trained, INSAT fine-tuned) | 9.6 | 7.2 | -0.0 | 51% | 87% |
| Blend: CNN + global model, quantile-mapped | 9.3 | 6.9 | +0.6 | 50% | 89% |

Note: 2024–25 had no storm above Severe Cyclonic Storm in IMD's best track, so the test is weak-storm heavy.

## Every season, leave-one-season-out (chosen method) — includes Fani, Amphan, Tauktae, Mocha, Biparjoy

| Method | RMSE (kt) | MAE (kt) | Bias (kt) | Exact IMD class | Within one class |
|---|---|---|---|---|---|
| All storms | 12.2 | 8.9 | -0.0 | 44% | 88% |
| Storms ≥ 64 kt (VSCS+) | 17.2 | 13.6 | -4.1 | 47% | 92% |

| Class | Images | MAE (kt) | Bias (kt) | Exact | Within one |
|---|---|---|---|---|---|
| D | 333 | 3.8 | +2.9 | 66% | 87% |
| DD | 187 | 6.5 | +2.4 | 27% | 94% |
| CS | 238 | 10.3 | -0.5 | 34% | 75% |
| SCS | 142 | 12.5 | -1.6 | 28% | 94% |
| VSCS | 158 | 13.6 | -1.6 | 46% | 94% |
| ESCS | 87 | 14.6 | -7.7 | 43% | 90% |
| SuCS | 22 | 10.4 | -7.8 | 68% | 91% |

Confusion matrix (rows = IMD best track, columns = estimate):

| | D | DD | CS | SCS | VSCS | ESCS | SuCS |
|---|---|---|---|---|---|---|---|
| D | 219 | 71 | 41 | 2 | 0 | 0 | 0 |
| DD | 68 | 51 | 57 | 11 | 0 | 0 | 0 |
| CS | 50 | 46 | 82 | 50 | 10 | 0 | 0 |
| SCS | 1 | 6 | 56 | 40 | 38 | 1 | 0 |
| VSCS | 0 | 1 | 9 | 44 | 73 | 31 | 0 |
| ESCS | 0 | 0 | 1 | 8 | 32 | 37 | 9 |
| SuCS | 0 | 0 | 0 | 0 | 2 | 5 | 15 |

80% of errors are within ±15 kt — shown on the site as the estimate's range. Published geostationary-IR methods: RMSE ≈ 10–16 kt (Pradhan et al. 2018: 10.2 kt with many more storms). Plan target: RMSE ≤ 12 kt on 2024–25.

**Shown on the site: yes** (needs test RMSE ≤ 12 kt and beating the Dvorak-like baseline).
