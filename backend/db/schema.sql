-- Task 15: MySQL Database Schemas
-- ══════════════════════════════
-- Owner: Agent DELTA | Skill: [SKILL:NODEJS_BACKEND]
--
-- DDL schema for cyclone telemetry persistence and multi-lingual
-- safety advisory generation.

CREATE TABLE IF NOT EXISTS cyclones (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255),
    center_lat DECIMAL(9, 6),
    center_lon DECIMAL(9, 6),
    v_max_knots FLOAT,
    imd_category VARCHAR(50),
    timestamp DATETIME
);

CREATE TABLE IF NOT EXISTS advisories (
    id VARCHAR(36) PRIMARY KEY,
    cyclone_id VARCHAR(36),
    language VARCHAR(10),
    content TEXT,
    issued_at DATETIME,
    FOREIGN KEY (cyclone_id) REFERENCES cyclones(id) ON DELETE CASCADE
);
