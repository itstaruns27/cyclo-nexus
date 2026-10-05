-- 012_satellite_heatmap.sql
-- Master plan v5, Task 3.5 — Grad-CAM explanation of the satellite intensity estimate (JPEG data URI, ~8 kB)
-- Additive migration: ADD COLUMN IF NOT EXISTS only — NO DROP/TRUNCATE
ALTER TABLE cyclones ADD COLUMN IF NOT EXISTS ai_heatmap MEDIUMTEXT NULL;
