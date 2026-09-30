/**
 * CYCLO-NEXUS Frontend Type Contracts
 * ════════════════════════════════════
 * Version: 1.0.0
 * Owner: ARCHITECT (locked)
 * Consumer: Agent ECHO (Read-Only)
 *
 * These types mirror schemas/telemetry_contract.py exactly.
 * Any divergence is a contract violation.
 */

// ── IMD 7-Tier Intensity Scale ──────────────────────────────────────

/**
 * @typedef {'D' | 'DD' | 'CS' | 'SCS' | 'VSCS' | 'ESCS' | 'SuCS'} IMDCategory
 */

/**
 * @typedef {Object} IMDWindRange
 * @property {IMDCategory} category
 * @property {number} minWindKmh
 * @property {number} maxWindKmh
 * @property {string} label
 */

/** @type {readonly IMDWindRange[]} */
export const IMD_SCALE = [
  { category: 'D',    minWindKmh: 31,  maxWindKmh: 49,  label: 'Depression' },
  { category: 'DD',   minWindKmh: 50,  maxWindKmh: 61,  label: 'Deep Depression' },
  { category: 'CS',   minWindKmh: 62,  maxWindKmh: 88,  label: 'Cyclonic Storm' },
  { category: 'SCS',  minWindKmh: 89,  maxWindKmh: 117, label: 'Severe Cyclonic Storm' },
  { category: 'VSCS', minWindKmh: 118, maxWindKmh: 166, label: 'Very Severe Cyclonic Storm' },
  { category: 'ESCS', minWindKmh: 167, maxWindKmh: 221, label: 'Extremely Severe Cyclonic Storm' },
  { category: 'SuCS', minWindKmh: 222, maxWindKmh: 999, label: 'Super Cyclonic Storm' },
];

/**
 * IMD category color mapping for UI rendering.
 * @type {Record<IMDCategory, string>}
 */
export const IMD_COLORS = {
  D:    '#60A5FA',  // Blue
  DD:   '#34D399',  // Green
  CS:   '#FBBF24',  // Yellow
  SCS:  '#FB923C',  // Orange
  VSCS: '#F87171',  // Red
  ESCS: '#C084FC',  // Purple
  SuCS: '#F472B6',  // Magenta
};

/**
 * A row of GET /api/v1/cyclones (master plan v4).
 * @typedef {Object} ActiveSystem
 * @property {string} cyclone_id
 * @property {string|null} cyclone_name
 * @property {'NIO'|'BOB'|'AS'} basin
 * @property {'OFFICIAL_JTWC'|'OFFICIAL_IBTRACS'|'AI_SATELLITE'} source
 * @property {'active'|'watch'|'dissipated'} status
 * @property {number|string} current_lat
 * @property {number|string} current_lon
 * @property {number} sustained_wind_kmh
 * @property {number} central_pressure_hpa
 * @property {IMDCategory} imd_category
 * @property {string} observation_time          ISO UTC
 * @property {string|null} source_url
 * @property {string|null} summary
 * @property {number|null} ai_min_cloud_top_k   satellite analysis (INSAT)
 * @property {number|null} ai_max_rain_mmhr     satellite analysis (IMERG)
 * @property {string|null} ai_fix_time
 * @property {number|null} detection_confidence
 * @property {{dir: string, speed: number, hours: number, bearing_deg: number}|null} movement
 * @property {'YELLOW'|'ORANGE'|'RED'|null} alert_level
 */

export const isOfficial = s => String(s?.source || '').startsWith('OFFICIAL_');
export const isWatch = s => s?.status === 'watch';

export const SOURCE_LABELS = {
  OFFICIAL_JTWC: 'JTWC warning',
  OFFICIAL_IBTRACS: 'IBTrACS best track',
  AI_SATELLITE: 'Satellite watch (experimental)',
};

export const ALERT_COLORS = { RED: '#ef4444', ORANGE: '#f97316', YELLOW: '#eab308' };
