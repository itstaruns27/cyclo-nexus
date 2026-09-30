-- 002_create_forecasts.sql
-- Owner: Agent DELTA | Task 15
-- Additive migration: CREATE only

CREATE TABLE IF NOT EXISTS forecast_tracks (
    id                      INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    cyclone_id              VARCHAR(64) NOT NULL,
    forecast_hour           TINYINT UNSIGNED NOT NULL,
    predicted_lat           DECIMAL(7, 4) NOT NULL,
    predicted_lon           DECIMAL(7, 4) NOT NULL,
    predicted_wind_kmh      FLOAT NOT NULL,
    predicted_pressure_hpa  FLOAT NOT NULL,
    predicted_imd_category  ENUM('D', 'DD', 'CS', 'SCS', 'VSCS', 'ESCS', 'SuCS') NOT NULL,
    sigma_lat               FLOAT NOT NULL DEFAULT 0.0,
    sigma_lon               FLOAT NOT NULL DEFAULT 0.0,
    confidence              FLOAT NOT NULL DEFAULT 0.0,
    cone_geojson            JSON NULL,
    generated_at            DATETIME NOT NULL,
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_cyclone_forecast (cyclone_id, forecast_hour),
    CONSTRAINT fk_forecast_cyclone FOREIGN KEY (cyclone_id)
        REFERENCES cyclones(cyclone_id) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
