-- 007_besttrack_points.sql
-- Master plan v4: official historical best tracks (IBTrACS North Indian Ocean) for the Historical page
-- Additive migration: CREATE only

CREATE TABLE IF NOT EXISTS besttrack_points (
    id              INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    sid             VARCHAR(16) NOT NULL,
    season          SMALLINT UNSIGNED NOT NULL,
    name            VARCHAR(64) NULL,
    subbasin        VARCHAR(4) NULL,
    iso_time        DATETIME NOT NULL,
    latitude        DECIMAL(7, 4) NOT NULL,
    longitude       DECIMAL(7, 4) NOT NULL,
    grade           VARCHAR(8) NULL,
    wind_kt         FLOAT NULL,
    pressure_hpa    FLOAT NULL,
    dist2land_km    FLOAT NULL,
    UNIQUE KEY uq_sid_time (sid, iso_time),
    INDEX idx_season (season),
    INDEX idx_sid (sid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
