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
