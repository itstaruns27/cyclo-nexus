# Track guidance and consensus — verification

Generated 2026-10-05 12:41 UTC by `python -m forecaster.guidance.consensus`.

**Truth:** JTWC best track (IBTrACS v04 USA_*), cases where the system is ≥ 25 kt at the start and at the verifying time.
**Fitted on:** seasons ≤ 2024 (625 forecast cases). **Tested on:** seasons ≥ 2025 (73 cases, never used for fitting): Unnamed (IO012025), Unnamed (IO012026), Shakhti (IO022025), Montha (IO032025), Senyar (IO042025), Ditwah (IO052025).

Errors are great-circle distances (km) between forecast and best-track centre; numbers in brackets are case counts.
Models: IFS = ECMWF HRES; AIFS = ECMWF's AI model; -ENSM = ensemble mean; GFS = NCEP; UKM, CMC, NGX = UK, Canada, US Navy.
"(raw)" = the model's own track; otherwise the track is moved towards the real-time storm position by a fraction fitted per model (listed below).

## Test seasons (≥ 2025) — all available cases

| Model | 12 h | 24 h | 36 h | 48 h | 72 h | 96 h | 120 h |
|---|---|---|---|---|---|---|---|
| AIFS (raw) | 59 (50) | 57 (39) | 68 (28) | 88 (22) | 133 (13) | 116 (5) | 190 (1) |
| AIFS | 59 (50) | 58 (39) | 67 (28) | 89 (22) | 136 (13) | 127 (5) | 195 (1) |
| IFS-ENSM (raw) | 57 (59) | 63 (48) | 80 (34) | 102 (27) | 141 (14) | 126 (6) | 186 (1) |
| IFS-ENSM | 53 (59) | 62 (48) | 79 (34) | 103 (27) | 147 (14) | 136 (6) | 201 (1) |
| Cyclo-Nexus consensus | 53 (61) | 58 (49) | 73 (37) | 109 (29) | 139 (14) | 110 (7) | — |
| Equal-weight consensus | 49 (61) | 68 (49) | 84 (37) | 111 (29) | 138 (14) | 88 (7) | 106 (2) |
| IFS (raw) | 63 (52) | 70 (36) | 71 (29) | 111 (24) | 138 (11) | 122 (3) | 299 (1) |
| IFS | 61 (52) | 73 (36) | 74 (29) | 113 (24) | 143 (11) | 132 (3) | 327 (1) |
| UKM | 67 (29) | 68 (22) | 112 (16) | 120 (14) | 186 (8) | 117 (4) | 76 (1) |
| UKM (raw) | 66 (29) | 68 (22) | 111 (16) | 120 (14) | 185 (8) | 106 (4) | 60 (1) |
| NGX (raw) | 100 (30) | 109 (25) | 105 (19) | 126 (16) | 147 (8) | 231 (4) | 128 (2) |
| AEMN (raw) | 61 (60) | 93 (48) | 112 (36) | 141 (28) | 171 (13) | 124 (6) | 119 (2) |
| NGX | 76 (30) | 106 (25) | 114 (19) | 142 (16) | 164 (8) | 278 (4) | 208 (2) |
| AEMN | 62 (60) | 91 (48) | 111 (36) | 142 (28) | 168 (13) | 114 (6) | 109 (2) |
| CEMN | 64 (32) | 94 (26) | 125 (20) | 169 (16) | 176 (8) | 76 (4) | 92 (2) |
| CMC | 77 (32) | 99 (26) | 129 (20) | 169 (16) | 179 (8) | 127 (4) | 194 (2) |
| NEMN (raw) | 92 (27) | 104 (23) | 137 (18) | 175 (14) | 249 (7) | 200 (4) | 272 (2) |
| NEMN | 67 (27) | 100 (23) | 134 (18) | 178 (14) | 221 (7) | 174 (4) | 207 (2) |
| GFS | 65 (55) | 98 (46) | 140 (36) | 182 (28) | 212 (13) | 132 (5) | 110 (1) |
| GFS (raw) | 69 (55) | 106 (46) | 148 (36) | 183 (28) | 209 (13) | 136 (5) | 88 (1) |
| CMC (raw) | 78 (32) | 106 (26) | 148 (20) | 187 (16) | 195 (8) | 122 (4) | 214 (2) |
| CEMN (raw) | 78 (32) | 115 (26) | 156 (20) | 198 (16) | 207 (8) | 108 (4) | 119 (2) |
| Persistence | 81 (49) | 153 (37) | 236 (29) | 288 (21) | 358 (10) | 431 (5) | 889 (1) |

## Test seasons — homogeneous sample (Cyclo-Nexus consensus, Persistence, IFS, GFS, AIFS)

| Model | 12 h | 24 h | 36 h | 48 h | 72 h | 96 h | 120 h |
|---|---|---|---|---|---|---|---|
| Cyclo-Nexus consensus | 40 (36) | 45 (24) | 70 (19) | 92 (15) | 124 (6) | 106 (1) | — |
| Persistence | 80 (36) | 112 (24) | 168 (19) | 231 (15) | 323 (6) | 589 (1) | — |
| IFS | 52 (36) | 61 (24) | 76 (19) | 123 (15) | 138 (6) | 182 (1) | — |
| GFS | 61 (36) | 72 (24) | 110 (19) | 151 (15) | 177 (6) | 92 (1) | — |
| AIFS | 50 (36) | 52 (24) | 69 (19) | 87 (15) | 132 (6) | 132 (1) | — |
| Equal-weight consensus | 37 (36) | 54 (24) | 78 (19) | 93 (15) | 81 (6) | 57 (1) | — |

## Intensity error (kt), test seasons

| Model | 12 h | 24 h | 48 h | 72 h |
|---|---|---|---|---|
| Cyclo-Nexus consensus | 5 (49) | 5 (37) | 7 (21) | 4 (10) |
| Persistence | 5 (49) | 7 (37) | 8 (21) | 8 (10) |
| IFS | 6 (41) | 7 (26) | 6 (17) | 4 (7) |
| GFS | 4 (46) | 4 (37) | 6 (21) | 3 (10) |
| AIFS | 11 (38) | 12 (27) | 9 (16) | 5 (9) |
| IFS-ENSM | 6 (47) | 5 (36) | 5 (19) | 2 (10) |

## Training seasons (≤ 2024) — for reference

| Model | 12 h | 24 h | 36 h | 48 h | 72 h | 96 h | 120 h |
|---|---|---|---|---|---|---|---|
| AIFS (raw) | 39 (28) | 45 (22) | 59 (17) | 79 (11) | 61 (3) | — | — |
| AIFS | 36 (28) | 44 (22) | 59 (17) | 82 (11) | 66 (3) | — | — |
| IFS-ENSM | 41 (133) | 61 (111) | 74 (90) | 90 (72) | 111 (44) | 125 (28) | 154 (24) |
| IFS-ENSM (raw) | 43 (133) | 62 (111) | 75 (90) | 90 (72) | 110 (44) | 123 (28) | 152 (24) |
| IFS | 44 (132) | 60 (110) | 75 (90) | 90 (71) | 117 (44) | 140 (14) | 177 (11) |
| IFS (raw) | 45 (133) | 61 (110) | 76 (90) | 90 (71) | 118 (44) | 139 (14) | 174 (11) |
| Cyclo-Nexus consensus | 50 (305) | 71 (247) | 93 (195) | 118 (149) | 201 (57) | 367 (21) | — |
| Equal-weight consensus | 50 (306) | 71 (248) | 94 (196) | 119 (150) | 167 (88) | 233 (36) | 165 (23) |
| UKM | 54 (63) | 60 (49) | 87 (34) | 126 (24) | 229 (9) | 475 (4) | 486 (2) |
| UKM (raw) | 56 (63) | 63 (49) | 90 (34) | 128 (24) | 233 (9) | 478 (4) | 485 (2) |
| CEMN | 60 (123) | 89 (98) | 114 (74) | 132 (55) | 194 (30) | 275 (13) | 381 (8) |
| CMC | 62 (122) | 92 (98) | 124 (73) | 142 (55) | 201 (30) | 363 (13) | 298 (8) |
| CMC (raw) | 71 (122) | 100 (98) | 129 (73) | 147 (55) | 205 (30) | 378 (13) | 312 (8) |
| CEMN (raw) | 75 (123) | 107 (98) | 131 (74) | 148 (55) | 203 (30) | 284 (13) | 398 (8) |
| NVGM | 68 (178) | 98 (164) | 122 (148) | 152 (134) | 227 (103) | 341 (78) | 508 (52) |
| AEMN | 56 (262) | 81 (208) | 113 (158) | 155 (114) | 258 (56) | 401 (22) | 217 (13) |
| NEMN | 71 (125) | 106 (99) | 129 (74) | 155 (55) | 216 (30) | 214 (12) | 203 (7) |
| NEMN (raw) | 88 (125) | 116 (99) | 136 (74) | 156 (55) | 212 (30) | 209 (12) | 192 (7) |
| NVGM (raw) | 72 (178) | 102 (164) | 125 (148) | 157 (134) | 232 (103) | 341 (78) | 510 (52) |
| GFS | 58 (262) | 82 (207) | 113 (156) | 157 (113) | 287 (54) | 366 (21) | 183 (10) |
| AEMN (raw) | 59 (262) | 81 (208) | 115 (158) | 157 (114) | 259 (56) | 405 (22) | 218 (13) |
| GFS (raw) | 61 (262) | 82 (207) | 115 (156) | 159 (113) | 292 (54) | 370 (21) | 194 (10) |
| NGX | 78 (119) | 114 (95) | 153 (71) | 191 (53) | 286 (28) | 289 (11) | 317 (6) |
| NGX (raw) | 80 (119) | 117 (95) | 156 (71) | 191 (53) | 288 (28) | 296 (11) | 317 (6) |
| Persistence | 79 (570) | 155 (494) | 238 (417) | 324 (347) | 529 (238) | 758 (158) | 949 (111) |

## Consensus settings (forecaster/weights/consensus.json)

Primary members (equal weights, used whenever both are available): AIFS, IFS-ENSM. Otherwise all available members are blended with the fitted weights below.

Relative weight per lead (higher = trusted more):

| Member | 12 h | 24 h | 36 h | 48 h | 72 h | 96 h | 120 h |
|---|---|---|---|---|---|---|---|
| IFS | 0.10 | 0.10 | 0.10 | 0.11 | 0.00 | 0.00 | 0.00 |
| AIFS | 0.10 | 0.20 | 0.25 | 0.00 | 0.00 | 0.00 | 0.00 |
| IFS-ENSM | 0.14 | 0.10 | 0.10 | 0.10 | 0.00 | 0.00 | 0.00 |
| GFS | 0.11 | 0.09 | 0.08 | 0.10 | 0.11 | 0.50 | 0.00 |
| AEMN | 0.11 | 0.10 | 0.09 | 0.10 | 0.13 | 0.50 | 0.00 |
| UKM | 0.11 | 0.13 | 0.10 | 0.11 | 0.00 | 0.00 | 0.00 |
| CMC | 0.09 | 0.08 | 0.08 | 0.14 | 0.19 | 0.00 | 0.00 |
| CEMN | 0.10 | 0.09 | 0.09 | 0.16 | 0.27 | 0.00 | 0.00 |
| NGX | 0.07 | 0.05 | 0.05 | 0.07 | 0.11 | 0.00 | 0.00 |
| NVGM | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| NEMN | 0.07 | 0.06 | 0.06 | 0.10 | 0.18 | 0.00 | 0.00 |

Shift towards the real-time position (fraction of the start-point difference): IFS 0.25, AIFS 0.25, IFS-ENSM 0.25, GFS 0.50, AEMN 0.50, UKM 0.25, CMC 0.75, CEMN 1.00, NGX 0.75, NVGM 0.75, NEMN 1.00


Cone radius (67% of 2023–24 consensus errors; NHC's definition): 12 h 42 km, 24 h 63 km, 36 h 82 km, 48 h 98 km, 72 h 171 km.
Share of unseen-season positions inside the cone (target ≈ 67%): 12 h 51%, 24 h 65%, 36 h 70%, 48 h 55%, 72 h 86%.

## Comparison with the official forecast (IMD)

| | 24 h | 48 h | 72 h |
|---|---|---|---|
| **Cyclo-Nexus consensus, unseen seasons** | **58** | **109** | **139** |
| IMD official, LPA 2019–23 | 72 | 112 | 156 |
| IMD official, 2024 | 56 | 110 | 174 |

IMD verifies against its own best track and includes depressions; the consensus is verified against JTWC's best track — so the comparison is indicative, not like-for-like.

**Task 1.3 acceptance (≤ official error at 48–72 h): PASS.** The AI consensus forecast may be shown on the site (AI_FORECAST_ENABLED).

## Best on unseen seasons, per lead

- 12 h: **Equal-weight consensus** 49 km
- 24 h: **Cyclo-Nexus consensus** 58 km
- 36 h: **AIFS** 67 km
- 48 h: **AIFS** 89 km
- 72 h: **AIFS** 136 km
- 96 h: **CEMN** 76 km
- 120 h: **UKM** 76 km
