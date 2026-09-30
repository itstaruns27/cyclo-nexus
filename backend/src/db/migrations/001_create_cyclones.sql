-- 001_create_cyclones.sql
-- Owner: Agent DELTA | Task 15
-- Additive migration: CREATE only — NO DROP/TRUNCATE

CREATE TABLE IF NOT EXISTS cyclones (
    id                          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    cyclone_id                  VARCHAR(64) NOT NULL UNIQUE,
    cyclone_name                VARCHAR(128) NULL,
    basin                       ENUM('NIO', 'BOB', 'AS') NOT NULL DEFAULT 'NIO',

    -- Current state
    current_lat                 DECIMAL(7, 4) NOT NULL,
    current_lon                 DECIMAL(7, 4) NOT NULL,
    sustained_wind_kmh          FLOAT NOT NULL,
    sustained_wind_knots        FLOAT NOT NULL,
    central_pressure_hpa        FLOAT NOT NULL,
    environmental_pressure_hpa  FLOAT NOT NULL DEFAULT 1010.0,
    imd_category                ENUM('D', 'DD', 'CS', 'SCS', 'VSCS', 'ESCS', 'SuCS') NOT NULL,

    -- OBB parameters
    obb_x_center                FLOAT NOT NULL,
    obb_y_center                FLOAT NOT NULL,
    obb_width                   FLOAT NOT NULL,
    obb_height                  FLOAT NOT NULL,
    obb_theta                   FLOAT NOT NULL,

    -- Eye metrics
    eye_diameter_km             FLOAT NULL,
    eyewall_thickness_km        FLOAT NULL,
    eye_symmetry_score          FLOAT NULL,
    detection_confidence        FLOAT NOT NULL,

    -- Timestamps
    observation_time            DATETIME NOT NULL,
    inference_generated_at      DATETIME NOT NULL,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Indexes
    INDEX idx_location (current_lat, current_lon),
    INDEX idx_cyclone_id (cyclone_id),
    INDEX idx_observation_time (observation_time),
    INDEX idx_imd_category (imd_category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
