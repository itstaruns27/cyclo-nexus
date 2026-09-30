-- 005_create_historical_tracks.sql
-- Owner: Agent DELTA | Task 15
-- Additive migration: CREATE only

CREATE TABLE IF NOT EXISTS historical_tracks (
    id                          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    cyclone_id                  VARCHAR(64) NOT NULL,
    timestamp                   DATETIME NOT NULL,
    latitude                    DECIMAL(7, 4) NOT NULL,
    longitude                   DECIMAL(7, 4) NOT NULL,
    sustained_wind_kmh          FLOAT NOT NULL,
    sustained_wind_knots        FLOAT NOT NULL,
    central_pressure_hpa        FLOAT NOT NULL,
    environmental_pressure_hpa  FLOAT NOT NULL DEFAULT 1010.0,
    imd_category                ENUM('D', 'DD', 'CS', 'SCS', 'VSCS', 'ESCS', 'SuCS') NOT NULL,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_hist_cyclone_time (cyclone_id, timestamp),
    CONSTRAINT fk_hist_cyclone FOREIGN KEY (cyclone_id)
        REFERENCES cyclones(cyclone_id) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
