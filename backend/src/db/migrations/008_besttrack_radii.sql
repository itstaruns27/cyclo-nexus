-- 008_besttrack_radii.sql
-- Storm size for impact estimates: JTWC wind radii per quadrant (nautical miles) from IBTrACS,
-- radius of maximum wind / outermost closed isobar, and storm motion.
-- Additive migration: ADD COLUMN only

ALTER TABLE besttrack_points ADD COLUMN IF NOT EXISTS r34_ne SMALLINT NULL;
ALTER TABLE besttrack_points ADD COLUMN IF NOT EXISTS r34_se SMALLINT NULL;
ALTER TABLE besttrack_points ADD COLUMN IF NOT EXISTS r34_sw SMALLINT NULL;
ALTER TABLE besttrack_points ADD COLUMN IF NOT EXISTS r34_nw SMALLINT NULL;
ALTER TABLE besttrack_points ADD COLUMN IF NOT EXISTS r50_ne SMALLINT NULL;
ALTER TABLE besttrack_points ADD COLUMN IF NOT EXISTS r50_se SMALLINT NULL;
ALTER TABLE besttrack_points ADD COLUMN IF NOT EXISTS r50_sw SMALLINT NULL;
ALTER TABLE besttrack_points ADD COLUMN IF NOT EXISTS r50_nw SMALLINT NULL;
ALTER TABLE besttrack_points ADD COLUMN IF NOT EXISTS r64_ne SMALLINT NULL;
ALTER TABLE besttrack_points ADD COLUMN IF NOT EXISTS r64_se SMALLINT NULL;
ALTER TABLE besttrack_points ADD COLUMN IF NOT EXISTS r64_sw SMALLINT NULL;
ALTER TABLE besttrack_points ADD COLUMN IF NOT EXISTS r64_nw SMALLINT NULL;
ALTER TABLE besttrack_points ADD COLUMN IF NOT EXISTS rmw_nm SMALLINT NULL;
ALTER TABLE besttrack_points ADD COLUMN IF NOT EXISTS roci_nm SMALLINT NULL;
ALTER TABLE besttrack_points ADD COLUMN IF NOT EXISTS storm_speed_kt FLOAT NULL;
ALTER TABLE besttrack_points ADD COLUMN IF NOT EXISTS storm_dir_deg FLOAT NULL
