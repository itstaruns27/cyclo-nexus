/**
 * Demo scenario for presentations — NOT real data.
 * ═══════════════════════════════════════════════
 * Inserts a scripted cyclone ("ARNAB", Very Severe Cyclonic Storm in the Bay of Bengal heading for
 * the Odisha coast) plus a satellite watch area in the Arabian Sea into the LOCAL database, so every
 * page (warning bar, home, advisories, impact, expert panel) can be shown working end to end.
 *
 *   node scripts/demo_cyclone.js start    # (re)insert, with times relative to now
 *   node scripts/demo_cyclone.js stop     # remove every demo row
 *   node scripts/demo_cyclone.js status
 *
 * Demo rows carry external_id = 'DEMO': the official-feed poller never dissipates them and the
 * website labels them "Demo scenario". The list API shows systems observed in the last 24 h, so
 * run `start` again on the day you record. Always run `stop` before any real deployment.
 */

require('dotenv').config({ path: require('path').join(__dirname, '..', '.env') });
const { pool } = require('../src/db/connection');
const { getIMDCategory } = require('../src/services/imd_scale');

const KT = 1.852;
const H = 3600e3;
// Atkinson–Holliday wind–pressure relation, environmental pressure 1010 hPa
const pressureFor = kt => Math.round(1010 - (kt / 6.7) ** (1 / 0.644));
const IDS = ['DEMO-ARNAB', 'DEMO-WATCH-AS'];

// [hoursAgo, lat, lon, wind_kt] — observed track (6-hourly)
const TRACK = [
  [72, 11.4, 89.9, 25], [66, 11.9, 89.7, 28], [60, 12.4, 89.4, 30], [54, 12.9, 89.2, 35],
  [48, 13.5, 89.0, 40], [42, 14.1, 88.8, 45], [36, 14.7, 88.6, 50], [30, 15.3, 88.4, 55],
  [24, 15.8, 88.2, 60], [18, 16.3, 88.0, 65], [12, 16.8, 87.8, 70], [6, 17.2, 87.6, 72], [0, 17.6, 87.4, 76],
];
// [hour, lat, lon, wind_kt] — landfall near Puri around +30 h
const FORECAST = {
  OFFICIAL_JTWC: [[12, 18.5, 86.9, 85], [24, 19.3, 86.3, 90], [36, 20.1, 85.7, 65], [48, 21.0, 85.2, 40], [72, 22.4, 84.5, 25]],
  AI_CONSENSUS: [[12, 18.6, 86.8, 82], [24, 19.5, 86.1, 88], [36, 20.3, 85.5, 60], [48, 21.2, 85.0, 38], [72, 22.6, 84.3, 24]],
};
// AI consensus extras per lead: [cone radius km, verified typical error km] (forecaster/weights/consensus.json)
const CONSENSUS_EXTRA = { 12: [42, 53], 24: [63, 58], 36: [82, 73], 48: [98, 109], 72: [171, 139] };

async function stop() {
  for (const table of ['forecast_tracks', 'historical_tracks', 'cyclones']) {
    await pool.query(`DELETE FROM ${table} WHERE cyclone_id IN (?)`, [IDS]);
  }
  console.log('Demo scenario removed.');
}

async function start() {
  await stop();
  const now = Math.floor((Date.now() - 20 * 60e3) / (3 * H)) * 3 * H; // latest 3-hourly synoptic time
  const [, lat, lon, kt] = TRACK[TRACK.length - 1];
  const kmh = kt * KT;
  await pool.query(
    `INSERT INTO cyclones (cyclone_id, cyclone_name, basin, current_lat, current_lon, sustained_wind_kmh, sustained_wind_knots,
       central_pressure_hpa, imd_category, obb_x_center, obb_y_center, obb_width, obb_height, obb_theta, detection_confidence,
       observation_time, inference_generated_at, source, status, external_id, source_url, summary,
       ai_fix_lat, ai_fix_lon, ai_fix_time, ai_fix_confidence, ai_min_cloud_top_k, ai_max_rain_mmhr, ai_method)
     VALUES (?, 'ARNAB', 'BOB', ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 1.0, ?, UTC_TIMESTAMP(), 'OFFICIAL_JTWC', 'active', 'DEMO', NULL,
       'Expected to cross the Odisha coast near Puri in about 30 hours as a Very Severe Cyclonic Storm (official forecast).', ?, ?, ?, 0.94, 187.4, 64.2, 'physics_dav_v1')`,
    ['DEMO-ARNAB', lat, lon, kmh, kt, pressureFor(kt), getIMDCategory(kmh), new Date(now),
      lat + 0.15, lon - 0.1, new Date(now - 1.5 * H)]);

  for (const [ago, la, lo, w] of TRACK) {
    await pool.query(
      `INSERT INTO historical_tracks (cyclone_id, timestamp, latitude, longitude, sustained_wind_kmh, sustained_wind_knots,
         central_pressure_hpa, imd_category) VALUES ('DEMO-ARNAB', ?, ?, ?, ?, ?, ?, ?)`,
      [new Date(now - ago * H), la, lo, w * KT, w, pressureFor(w), getIMDCategory(w * KT)]);
  }
  for (const [source, list] of Object.entries(FORECAST)) {
    for (const [h, la, lo, w] of list) {
      await pool.query(
        `INSERT INTO forecast_tracks (cyclone_id, forecast_hour, predicted_lat, predicted_lon, predicted_wind_kmh,
           predicted_pressure_hpa, predicted_imd_category, confidence, generated_at, source,
           cone_radius_km, verified_error_km, init_time, members, ri_probability)
         VALUES ('DEMO-ARNAB', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        [h, la, lo, w * KT, pressureFor(w), getIMDCategory(w * KT), source === 'AI_CONSENSUS' ? 0 : 1.0, new Date(now), source,
          ...(source === 'AI_CONSENSUS' ? [...CONSENSUS_EXTRA[h], new Date(now - 6 * H), 'AIFS,IFS-ENSM,IFS,GFS,UKM', 0.12] : [null, null, null, null, null])]);
    }
  }

  // Satellite watch area (experimental layer) in the Arabian Sea
  await pool.query(
    `INSERT INTO cyclones (cyclone_id, cyclone_name, basin, current_lat, current_lon, sustained_wind_kmh, sustained_wind_knots,
       central_pressure_hpa, imd_category, obb_x_center, obb_y_center, obb_width, obb_height, obb_theta, detection_confidence,
       observation_time, inference_generated_at, source, status, external_id, summary,
       ai_fix_lat, ai_fix_lon, ai_fix_time, ai_fix_confidence, ai_min_cloud_top_k, ai_max_rain_mmhr, ai_method)
     VALUES ('DEMO-WATCH-AS', NULL, 'AS', 12.8, 65.6, 0, 0, 1006, 'D', 0, 0, 0, 0, 0, 0.97, ?, UTC_TIMESTAMP(), 'AI_SATELLITE',
       'watch', 'DEMO', 'Demo scenario: organised deep convection over warm water (SST 29.4 °C): coldest cloud top 196 K, peak rain 31 mm/h.',
       12.8, 65.6, ?, 0.97, 196.0, 31.0, 'physics_dav_v1')`,
    [new Date(now), new Date(now)]);

  console.log(`Demo scenario inserted: ARNAB (VSCS, ${Math.round(kmh)} km/h, ${lat}N ${lon}E) + Arabian Sea watch area,`
    + ` observed ${new Date(now).toISOString().slice(0, 16)}Z. Refresh the website (API cache: 30 s).`);
}

async function status() {
  const [rows] = await pool.query('SELECT cyclone_id, status, observation_time FROM cyclones WHERE cyclone_id IN (?)', [IDS]);
  console.log(rows.length ? rows : 'No demo rows.');
}

const cmd = process.argv[2];
const run = { start, stop, status }[cmd];
if (!run) {
  console.log('Usage: node scripts/demo_cyclone.js start | stop | status');
  process.exit(1);
}
run().catch(err => { console.error(err.message); process.exitCode = 1; }).finally(() => pool.end());
