# Agent CHARLIE: Spatiotemporal Trajectory Forecaster

> **Owner:** Agent CHARLIE (Tasks 10–13)  
> **Skill:** [SKILL:PHYSICS_AI_TRAJECTORY]  
> **Read Access:** Agent DELTA (serialized outputs)

## Tasks
- **T10:** Spatiotemporal Sequence Matrix Builder — 6-step (t-15h → t0) at 3h cadence
- **T11:** ConvLSTM + Bi-GRU Forecaster — Predict tracks for +6h, +12h, +24h, +48h, +72h
- **T12:** Atkinson-Holliday Physics Residual Loss — ΔP = 0.018 × V_max^1.5
- **T13:** Layer-Wise Grad-CAM XAI — Spatial attention heatmaps

## Key Physics

```
L_total = L_MSE(Y_traj, Ŷ_traj) + α·L_Huber(V_pred, V_true) + β·max(0, |ΔP_pred - 0.018·V_pred^1.5| - τ)
```

## Constraints
- ❌ No future data leakage — strict chronological splits
- ❌ No GPU tensor serialization — convert to NumPy/Python before JSON export
- ✅ Output uncertainty cones (σ_lat, σ_lon) for all forecast horizons
