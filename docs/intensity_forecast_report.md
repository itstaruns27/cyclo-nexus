# Intensity forecast and rapid-intensification probability — verification

Generated 2026-10-05 13:44 UTC by `python -m forecaster.guidance.intensity_model`.
Mean absolute error of the maximum sustained wind (kt, JTWC 1-minute). Start intensity = JTWC real-time (CARQ).
Model = gradient-boosted change per lead (inputs: every model's predicted change, trend, latitude, season, land along the track).
Rule = Phase-1 consensus intensity (current + AIFS/GFS change). Persistence = no change.

## Leave-one-season-out on 2018–2024 (each season predicted by a model that never saw it; includes the strong storms)

| Lead | Cases | Model | Rule | Persistence | Model, storms ≥ 64 kt | Rule, ≥ 64 kt |
|---|---|---|---|---|---|---|
| 12 h | 572 | **7.7** | 10.4 | 11.8 | **10.2** | 15.4 |
| 24 h | 496 | **11.8** | 16.7 | 19.7 | **15.3** | 23.5 |
| 36 h | 419 | **15.9** | 21.8 | 25.2 | **20.5** | 29.9 |
| 48 h | 349 | **18.1** | 25.9 | 29.1 | **20.1** | 32.9 |
| 72 h | 240 | **23.0** | 33.3 | 35.6 | **23.2** | 39.2 |

## Test seasons ≥ 2025 (never used)

| Lead | Cases | Model | Rule | Persistence |
|---|---|---|---|---|
| 12 h | 61 | **5.1** | 5.0 | 4.8 |
| 24 h | 49 | **4.5** | 5.4 | 7.3 |
| 36 h | 37 | **5.3** | 6.2 | 9.5 |
| 48 h | 29 | **7.0** | 7.2 | 9.4 |
| 72 h | 14 | **4.8** | 4.6 | 7.9 |

IMD official intensity error, long-period average 2019–23: 7.1 / 10.3 / 13.8 kt at 24 / 48 / 72 h (3-minute wind; indicative).

Tested and left out: sea-surface temperature (NOAA OISST) under the track and the gap to potential intensity (DeMaria–Kaplan) — leave-one-season-out errors changed by −0.4…+1.1 kt and RI skill fell (AUC 0.84 → 0.80).

## Rapid intensification (≥ 30 kt in 24 h)

Base rate 12.9% of 24-h cases (64 events, 2018–2024). Leave-one-season-out: ROC AUC **0.84**, Brier 0.092 vs 0.112 for always forecasting the base rate (skill 18%). Test seasons contain 0 RI case(s) — too few to score separately.

Reliability (leave-one-season-out):

| Forecast probability | Cases | Mean forecast | Observed frequency |
|---|---|---|---|
| (-0.001, 0.1] | 361 | 3% | 5% |
| (0.1, 0.25] | 70 | 16% | 24% |
| (0.25, 0.5] | 36 | 38% | 33% |
| (0.5, 1.0] | 29 | 66% | 59% |
