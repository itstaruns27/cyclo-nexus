-- 006_sources_status_pipeline.sql
-- Master plan v4, Task 2.3
-- Additive migration: ADD COLUMN IF NOT EXISTS / CREATE TABLE IF NOT EXISTS only — NO DROP/TRUNCATE

-- Where a cyclone row came from: OFFICIAL_JTWC | OFFICIAL_IBTRACS | AI_SATELLITE
ALTER TABLE cyclones ADD COLUMN IF NOT EXISTS source VARCHAR(32) NOT NULL DEFAULT 'AI_SATELLITE';
-- active = named/numbered system, watch = pre-genesis area (invest / TCFA / satellite watch)
ALTER TABLE cyclones ADD COLUMN IF NOT EXISTS status VARCHAR(16) NOT NULL DEFAULT 'active';
ALTER TABLE cyclones ADD COLUMN IF NOT EXISTS external_id VARCHAR(64) NULL;
ALTER TABLE cyclones ADD COLUMN IF NOT EXISTS source_url VARCHAR(512) NULL;
ALTER TABLE cyclones ADD COLUMN IF NOT EXISTS summary TEXT NULL;

-- Latest satellite (INSAT + IMERG) analysis attached to the system
ALTER TABLE cyclones ADD COLUMN IF NOT EXISTS ai_fix_lat DECIMAL(7, 4) NULL;
ALTER TABLE cyclones ADD COLUMN IF NOT EXISTS ai_fix_lon DECIMAL(7, 4) NULL;
ALTER TABLE cyclones ADD COLUMN IF NOT EXISTS ai_fix_time DATETIME NULL;
ALTER TABLE cyclones ADD COLUMN IF NOT EXISTS ai_fix_confidence FLOAT NULL;
ALTER TABLE cyclones ADD COLUMN IF NOT EXISTS ai_min_cloud_top_k FLOAT NULL;
ALTER TABLE cyclones ADD COLUMN IF NOT EXISTS ai_max_rain_mmhr FLOAT NULL;
ALTER TABLE cyclones ADD COLUMN IF NOT EXISTS ai_method VARCHAR(32) NULL;

-- Forecast provenance, so official and AI tracks can coexist per cyclone
ALTER TABLE forecast_tracks ADD COLUMN IF NOT EXISTS source VARCHAR(32) NOT NULL DEFAULT 'AI_SATELLITE';

-- One row per pipeline component, updated every run (drives /api/v1/health freshness)
CREATE TABLE IF NOT EXISTS pipeline_status (
    component           VARCHAR(32) NOT NULL PRIMARY KEY,
    last_run_at         DATETIME NOT NULL,
    last_success_at     DATETIME NULL,
    last_data_time      DATETIME NULL,
    status              VARCHAR(16) NOT NULL,
    message             VARCHAR(1024) NULL,
    details             JSON NULL,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
