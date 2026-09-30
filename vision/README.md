# Agent BRAVO: YOLO-OBB Computer Vision

> **Owner:** Agent BRAVO (Tasks 6–9)  
> **Skill:** [SKILL:YOLO_OBB_CV]  
> **Read Access:** Agent CHARLIE (OBB outputs)

## Tasks
- **T6:** OBB Annotation Generator — Convert cyclone eye annotations to YOLO-OBB format
- **T7:** Physics-Aware Augmentation — Rotation-safe transforms (no shear)
- **T8:** YOLO-OBB 4-Channel Adaptation — Modify first Conv2d layer for 4ch input
- **T9:** IMD Classification Head — 7-class head mapping to IMD scale

## Model Constraints (Google Colab T4)
- Batch size optimized for 15GB VRAM
- YOLO-OBB label format: `class_id x_c y_c w h θ` (normalized)
- Output OBB params: `(x_c, y_c, w, h, θ)` per `schemas/telemetry_contract.py`
- Eye diameter: pixel measurement × 4 km/pixel GSD

## Prohibited
- ❌ Saffir-Simpson scale (use IMD only)
- ❌ Affine shear augmentations
- ❌ Loading YOLO weights on web server
