-- 009_forecast_consensus.sql
-- Master plan v5, Task 1.4 — AI consensus forecasts (source AI_CONSENSUS) next to the official track
-- Additive migration: ADD COLUMN IF NOT EXISTS only — NO DROP/TRUNCATE

-- Radius of the 67% uncertainty circle at this lead (km), from the consensus's own verified errors
ALTER TABLE forecast_tracks ADD COLUMN IF NOT EXISTS cone_radius_km FLOAT NULL;
-- Mean track error of the consensus at this lead on seasons it never saw (km) — shown next to the forecast
ALTER TABLE forecast_tracks ADD COLUMN IF NOT EXISTS verified_error_km FLOAT NULL;
-- Model run the forecast was built from, and which models contributed
ALTER TABLE forecast_tracks ADD COLUMN IF NOT EXISTS init_time DATETIME NULL;
ALTER TABLE forecast_tracks ADD COLUMN IF NOT EXISTS members VARCHAR(255) NULL;
