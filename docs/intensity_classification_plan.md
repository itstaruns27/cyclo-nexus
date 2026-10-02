# Cyclone intensity classification: research and design (not implemented yet)

**Goal:** estimate the IMD intensity category of every system, D to SuCS, from INSAT-3DS + IMERG imagery alone, so Cyclo-Nexus can grade storms before an official bulletin exists and give a second opinion when one does.

## 1. The scale to classify (IMD, 3-minute sustained wind)

| Class | Name | km/h | knots |
|---|---|---|---|
| LPA | Low-pressure area | < 31 | < 17 |
| D | Depression | 31–49 | 17–27 |
| DD | Deep Depression | 50–61 | 28–33 |
| CS | Cyclonic Storm | 62–88 | 34–47 |
| SCS | Severe Cyclonic Storm | 89–117 | 48–63 |
| VSCS | Very Severe Cyclonic Storm | 118–166 | 64–89 |
| ESCS | Extremely Severe Cyclonic Storm | 167–221 | 90–119 |
| SuCS | Super Cyclonic Storm | ≥ 222 | ≥ 120 |

The project already maps wind to these classes (`schemas/imd_scale.py`, `backend/src/services/imd_scale.js`).

## 2. What the literature does

| Approach | Input | Reported accuracy | Notes |
|---|---|---|---|
| Dvorak technique / ADT | IR cloud pattern, eye–cloud temperature | Operational baseline | Manual (Dvorak) or automated (ADT); subjective / rule-based |
| CNN regression on single IR image (Pradhan et al. 2018, IEEE TIP 27:692–702) | 1 IR image | RMSE 10.18 kt | Classic deep-learning benchmark |
| CNNs on INSAT-3D IR (several Indian studies, 2023–2024) | INSAT-3D IR, 40+ NIO storms (2014–2023) | RMSE about 10–16 kt | Closest to our data |
| Multi-channel / multi-temporal CNNs (e.g. Remote Sensing 12(1):108, 2020) | IR + WV + time sequence | Better than single-image | Uses the trend, not only a snapshot |
| Physics-augmented deep learning (Mon. Wea. Rev. 149(7), 2021) | Imagery + physical predictors | Better than either alone | Same "physics-guided" idea as Cyclo-Nexus |
| Passive-microwave CNN (Mon. Wea. Rev. 147(6), 2019) | 37/89 GHz microwave | Strong | Microwave not in our live feed (future option) |

Direct class-only CNNs struggle because the strongest classes are rare. Regressing wind speed and then mapping to a class is the most accurate and robust design.

## 3. Proposed design for Cyclo-Nexus

1. **Input:** a storm-centred crop (about 10° × 10°, 128 px from the 512² store) of TIR1, WV, split-window and IMERG rain. Use the **last 3–6 frames** (6–15 h), so the model sees intensification and not just a snapshot.
2. **Model:** a small CNN or ConvLSTM encoder with two heads:
   - **regression:** max wind in knots (Huber loss), with an Atkinson–Holliday pressure head for consistency (same loss family as the forecaster)
   - **ordinal class:** CORAL / cumulative-link head, so "VSCS vs ESCS" counts as nearer than "D vs ESCS"

   The final class is the regression mapped to the IMD scale, cross-checked with the ordinal head.
3. **Labels:** IBTrACS `NEWDELHI_WIND` (IMD's own best track), 3-hourly rows matched to frames. These come straight from `data/training/frames.jsonl`, which the unified builder already writes.
4. **Imbalance:**
   - class-balanced sampling and loss weights
   - more frames around storm peaks (already done by the unified builder's peak-centred runs)
   - rotation augmentation, which is physically valid (no flips)
5. **Validation:**
   - hold out whole recent seasons (≥ 2024)
   - report wind RMSE / MAE (kt), exact-class accuracy, within-one-class accuracy, per-class recall and a confusion matrix
   - compare against a climatology/persistence baseline
6. **Product rule:** same as the rest of the platform. The official IMD/JTWC intensity always wins, and the AI class is shown as "satellite estimate" with its error bar.

## 4. Data already being collected

The unified set (`python -m data_pipeline.training.build_unified_set`) stores every frame with all active systems' wind, pressure and grade. The classifier needs **no extra download**.

## Sources

- Pradhan R. et al. (2018), *Tropical Cyclone Intensity Estimation Using a Deep Convolutional Neural Network*, IEEE TIP — https://pubmed.ncbi.nlm.nih.gov/29185987/
- INSAT-3D IR CNN studies — https://ieeexplore.ieee.org/document/10099964/ · https://ieeexplore.ieee.org/document/10434169/ · https://link.springer.com/chapter/10.1007/978-981-97-8836-1_30
- Multi-dimensional CNNs from geostationary data — https://doi.org/10.3390/rs12010108
- Physics-augmented deep learning — https://journals.ametsoc.org/view/journals/mwre/149/7/MWR-D-20-0333.1.xml
- Passive-microwave deep learning — https://journals.ametsoc.org/view/journals/mwre/147/6/mwr-d-18-0391.1.xml
- Rapid intensification over the NIO with attention models — https://link.springer.com/article/10.1007/s11069-025-07383-0
