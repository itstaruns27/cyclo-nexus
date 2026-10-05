-- 011_satellite_intensity.sql
-- Master plan v5, Task 2.3 — satellite (INSAT) intensity estimate per system, IMD 3-minute wind
-- Additive migration: ADD COLUMN IF NOT EXISTS only — NO DROP/TRUNCATE
ALTER TABLE cyclones ADD COLUMN IF NOT EXISTS ai_wind_kt FLOAT NULL;
ALTER TABLE cyclones ADD COLUMN IF NOT EXISTS ai_wind_band_kt FLOAT NULL;
ALTER TABLE cyclones ADD COLUMN IF NOT EXISTS ai_imd_category VARCHAR(8) NULL;
ALTER TABLE cyclones ADD COLUMN IF NOT EXISTS ai_eye TINYINT NULL;
