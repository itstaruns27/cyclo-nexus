-- 004_create_gradcam.sql
-- Owner: Agent DELTA | Task 15
-- Additive migration: CREATE only

CREATE TABLE IF NOT EXISTS gradcam_metadata (
    id                  INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    cyclone_id          VARCHAR(64) NOT NULL,
    heatmap_uri         VARCHAR(512) NOT NULL,
    target_layer        VARCHAR(256) NOT NULL,
    channel_index       TINYINT UNSIGNED NOT NULL,
    min_activation      FLOAT NOT NULL,
    max_activation      FLOAT NOT NULL,
    observation_time    DATETIME NOT NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_gradcam_cyclone (cyclone_id),
    CONSTRAINT fk_gradcam_cyclone FOREIGN KEY (cyclone_id)
        REFERENCES cyclones(cyclone_id) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
