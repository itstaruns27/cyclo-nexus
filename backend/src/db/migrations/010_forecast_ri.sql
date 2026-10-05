-- 010_forecast_ri.sql
-- Master plan v5, Task 2.4 — chance of rapid intensification (≥ 30 kt in 24 h) with the AI consensus forecast
-- Additive migration: ADD COLUMN IF NOT EXISTS only — NO DROP/TRUNCATE
ALTER TABLE forecast_tracks ADD COLUMN IF NOT EXISTS ri_probability FLOAT NULL;
