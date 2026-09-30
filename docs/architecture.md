# CYCLO-NEXUS System Architecture

See the full implementation plan:
[implementation_plan.md](file:///C:/Users/tarun%20sharma/.gemini/antigravity-ide/brain/129f2a6b-69c8-43d8-9be1-43d3584b33fb/implementation_plan.md)

## Quick Reference

```
Colab (T4 GPU)           Hostinger (Node.js)        Browser (PWA)
┌──────────────┐         ┌───────────────────┐      ┌──────────────┐
│ YOLO-OBB     │──POST──▶│ Webhook Receiver  │──GET─│ React + i18n │
│ ConvLSTM     │ GeoJSON │ MySQL Datastore   │      │ MapLibre GL  │
│ Grad-CAM     │  HMAC   │ Gemini Advisory   │      │ Offline PWA  │
└──────────────┘         └───────────────────┘      └──────────────┘
```

## Data Flow
1. Satellite data → MOSDAC/JAXA/GPM pipelines → 4-ch tensor (C,H,W)=(4,1024,1024)
2. YOLO-OBB → Eye detection + IMD classification → OBB params (xc,yc,w,h,θ)
3. ConvLSTM/Bi-GRU → 72h forecast track with uncertainty cones
4. Grad-CAM → Spatial attention heatmaps (XAI)
5. Colab webhook → Hostinger MySQL → REST API → MapLibre GL visualization
6. Gemini Pro → Multilingual emergency bulletins
