-- 003_create_advisories.sql
-- Owner: Agent DELTA | Task 15
-- Additive migration: CREATE only

CREATE TABLE IF NOT EXISTS advisories (
    id                          INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    cyclone_id                  VARCHAR(64) NOT NULL,
    alert_level                 ENUM('RED', 'ORANGE', 'YELLOW') NOT NULL,
    language_code               VARCHAR(5) NOT NULL DEFAULT 'en',
    threat_summary              TEXT NOT NULL,
    estimated_landfall_window   VARCHAR(64) NULL,
    evacuation_zones            JSON NULL,
    directives_fishermen        TEXT NULL,
    directives_public           TEXT NULL,
    directives_administration   TEXT NULL,
    generated_at                DATETIME NOT NULL,
    created_at                  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_advisory_cyclone (cyclone_id, language_code),
    CONSTRAINT fk_advisory_cyclone FOREIGN KEY (cyclone_id)
        REFERENCES cyclones(cyclone_id) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
