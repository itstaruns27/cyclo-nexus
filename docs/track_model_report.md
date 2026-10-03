# Storm-centred track model — held-out test

Train seasons < 2023, model selection on 2023, test seasons ≥ 2024 (never seen in training or selection). Ensemble of 5 models.

| Method | 6 h | 12 h | 24 h | 48 h | 72 h |
|---|---|---|---|---|---|
| persistence — track error (km) | 38 | 74 | 153 | 325 | 513 |
| motion-only ensemble — track error (km) | 37 | 72 | 151 | 318 | 476 |
| satellite + motion ensemble — track error (km) | 37 | 73 | 148 | 297 | 517 |
| no change (persistence) — wind error (kt) | 2.3 | 4.7 | 8.3 | 12.4 | 10.4 |
| motion-only ensemble — wind error (kt) | 2.8 | 4.6 | 8.3 | 12.1 | 11.2 |
| satellite + motion ensemble — wind error (kt) | 2.4 | 4.4 | 8.5 | 12.0 | 11.2 |
| test cases | 133 | 130 | 124 | 86 | 41 |

Best: **satellite + motion ensemble**, mean 6–48 h track error +5.9% vs persistence (positive = better).
