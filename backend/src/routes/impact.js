/**
 * Impact Routes (see services/impact.js for the method and its limits)
 *   GET /api/v1/impact/cyclone/:id   — active system: people exposed now and along the forecast track + similar past storms
 *   GET /api/v1/impact/storm/:sid    — past storm (IBTrACS): track statistics, exposure, recorded deaths/damage
 *   GET /api/v1/impact/major         — major recorded cyclones with exposure (for the impact overview)
 *   GET /api/v1/impact/near?lat&lon  — cyclone history and population around a point ("check my area")
 *   GET /api/v1/impact/climatology   — storms per month / decade / peak grade, 1980–present
 */

const express = require('express');
const router = express.Router();
const { pool } = require('../db/connection');
const { cacheMiddleware } = require('../middleware/cache');
const cycloneStore = require('../services/cyclone_store');
const impact = require('../services/impact');

const KMH_PER_KT = 1.852;
const GRADE_ORDER = ['D', 'DD', 'CS', 'SCS', 'VSCS', 'ESCS', 'SuCS'];
const ok = (res, data) => res.json({ success: true, data, timestamp: new Date().toISOString() });

async function trackOf(sid) {
  const [rows] = await pool.query(
    `SELECT iso_time, latitude AS lat, longitude AS lon, wind_kt AS kt, pressure_hpa, grade, dist2land_km, name, season, subbasin,
            r34_ne, r34_se, r34_sw, r34_nw, r50_ne, r50_se, r50_sw, r50_nw, r64_ne, r64_se, r64_sw, r64_nw,
            rmw_nm, roci_nm, storm_speed_kt, storm_dir_deg
       FROM besttrack_points WHERE sid = ? ORDER BY iso_time`, [sid]);
  return rows;
}

function trackStats(rows) {
  let distance = 0;
  for (let i = 1; i < rows.length; i++) {
    distance += impact.haversineKm(Number(rows[i - 1].lat), Number(rows[i - 1].lon), Number(rows[i].lat), Number(rows[i].lon));
  }
  const winds = rows.map(r => r.kt).filter(v => v != null);
  const pressures = rows.map(r => r.pressure_hpa).filter(v => v != null);
  const grades = rows.map(r => r.grade).filter(g => GRADE_ORDER.includes(g));
  const landfall = rows.find((r, i) => i > 0 && r.dist2land_km === 0 && rows[i - 1].dist2land_km > 0);
  return {
    start: rows[0].iso_time, end: rows[rows.length - 1].iso_time,
    duration_h: Math.round((new Date(rows[rows.length - 1].iso_time) - new Date(rows[0].iso_time)) / 3600e3),
    distance_km: Math.round(distance),
    peak_wind_kt: winds.length ? Math.max(...winds) : null,
    min_pressure_hpa: pressures.length ? Math.min(...pressures) : null,
    peak_grade: grades.sort((a, b) => GRADE_ORDER.indexOf(b) - GRADE_ORDER.indexOf(a))[0] || null,
    landfall: landfall ? { time: landfall.iso_time, lat: Number(landfall.lat), lon: Number(landfall.lon), wind_kt: landfall.kt } : null,
  };
}

let peakBySidCache = null;
async function peakBySid() {
  if (peakBySidCache) return peakBySidCache;
  const sids = impact.recordedStorms.map(s => s.sid);
  const [rows] = await pool.query('SELECT sid, MAX(wind_kt) AS kt FROM besttrack_points WHERE sid IN (?) GROUP BY sid', [sids]);
  peakBySidCache = Object.fromEntries(rows.map(r => [r.sid, r.kt]));
  return peakBySidCache;
}

router.get('/storm/:sid', cacheMiddleware, async (req, res, next) => {
  try {
    const rows = await trackOf(req.params.sid);
    if (!rows.length) return res.status(404).json({ success: false, error: 'Storm not found' });
    ok(res, {
      sid: req.params.sid, name: rows[0].name, season: rows[0].season,
      stats: trackStats(rows),
      exposure: impact.exposure(rows),
      recorded: impact.recordedFor(req.params.sid),
      recorded_note: impact.recordedNote,
    });
  } catch (err) { next(err); }
});

router.get('/cyclone/:id', cacheMiddleware, async (req, res, next) => {
  try {
    const c = await cycloneStore.getById(req.params.id);
    if (!c) return res.status(404).json({ success: false, error: 'Cyclone not found' });
    const current = { lat: c.current_lat, lon: c.current_lon, kt: Number(c.sustained_wind_kmh) / KMH_PER_KT };
    const bySource = {};
    for (const f of c.forecasts || []) (bySource[f.source] = bySource[f.source] || []).push(f);
    const src = Object.keys(bySource).find(s => s.startsWith('OFFICIAL_')) || Object.keys(bySource)[0];
    const forecast = (bySource[src] || []).sort((a, b) => a.forecast_hour - b.forecast_hour)
      .map(f => ({ lat: f.predicted_lat, lon: f.predicted_lon, kt: Number(f.predicted_wind_kmh) / KMH_PER_KT, hour: f.forecast_hour }));
    const peakKt = Math.max(current.kt, ...forecast.map(f => f.kt));
    ok(res, {
      cyclone_id: c.cyclone_id, name: c.cyclone_name,
      exposure_now: impact.exposure([current]),
      exposure_forecast: forecast.length ? impact.exposure([current, ...forecast]) : null,
      forecast_source: src || null,
      forecast_hours: forecast.length ? forecast[forecast.length - 1].hour : 0,
      peak_wind_kt: Math.round(peakKt),
      analogs: impact.analogs(peakKt, await peakBySid()),
      recorded_note: impact.recordedNote,
    });
  } catch (err) { next(err); }
});

let majorCache = null;
router.get('/major', cacheMiddleware, async (_req, res, next) => {
  try {
    if (!majorCache) {
      majorCache = [];
      for (const s of impact.recordedStorms) {
        const rows = await trackOf(s.sid);
        const st = rows.length ? trackStats(rows) : null;
        majorCache.push({ ...s, peak_wind_kt: st?.peak_wind_kt ?? null, peak_grade: st?.peak_grade ?? null,
          // headline figure: people in the storm-force (≥ 50 kt) zone, closest to reported "people affected"
          ...(rows.length ? (({ people_gale_zone, people_storm_zone }) => ({ people_gale_zone, people_storm_zone }))(impact.exposure(rows)) : {}) });
      }
      majorCache.sort((a, b) => b.season - a.season);
    }
    const totals = majorCache.reduce((t, s) => ({ deaths: t.deaths + (s.deaths || 0), damage_inr: t.damage_inr + (s.damage_inr || 0) }), { deaths: 0, damage_inr: 0 });
    ok(res, { storms: majorCache, totals, note: impact.recordedNote });
  } catch (err) { next(err); }
});

router.get('/near', cacheMiddleware, async (req, res, next) => {
  try {
    const lat = Number(req.query.lat); const lon = Number(req.query.lon);
    const radius = Math.min(Number(req.query.radius) || 150, 400);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return res.status(400).json({ success: false, error: 'lat and lon required' });
    const dLat = radius / 111; const dLon = radius / (111 * Math.max(0.2, Math.cos((lat * Math.PI) / 180)));
    const [rows] = await pool.query(
      `SELECT sid, name, season, iso_time, latitude, longitude, wind_kt, grade FROM besttrack_points
        WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?`,
      [lat - dLat, lat + dLat, lon - dLon, lon + dLon]);
    const storms = new Map();
    for (const r of rows) {
      const d = impact.haversineKm(lat, lon, Number(r.latitude), Number(r.longitude));
      if (d > radius) continue;
      const s = storms.get(r.sid) || { sid: r.sid, name: r.name || impact.recordedFor(r.sid)?.name || null, season: r.season, closest_km: Infinity, max_wind_kt: null, time: r.iso_time };
      if (d < s.closest_km) { s.closest_km = Math.round(d); s.time = r.iso_time; }
      if (r.wind_kt != null && (s.max_wind_kt == null || r.wind_kt > s.max_wind_kt)) s.max_wind_kt = r.wind_kt;
      storms.set(r.sid, s);
    }
    const list = [...storms.values()].sort((a, b) => new Date(b.time) - new Date(a.time));
    const cyclonic = list.filter(s => (s.max_wind_kt || 0) >= 34);
    const people = impact.townsNear(lat, lon, 50).reduce((sum, [t]) => sum + t[3], 0);
    const [minSeason] = (await pool.query('SELECT MIN(season) AS s FROM besttrack_points'))[0];
    ok(res, {
      radius_km: radius, since: minSeason.s,
      storms: list.length, cyclonic_storms: cyclonic.length,
      last: list[0] || null,
      strongest: [...list].sort((a, b) => (b.max_wind_kt || 0) - (a.max_wind_kt || 0))[0] || null,
      recent: list.slice(0, 5),
      people_within_50km: people,
    });
  } catch (err) { next(err); }
});

router.get('/climatology', cacheMiddleware, async (_req, res, next) => {
  try {
    const [rows] = await pool.query(
      `SELECT sid, MIN(season) AS season, MIN(MONTH(iso_time)) AS month, MAX(subbasin) AS basin, MAX(wind_kt) AS kt
         FROM besttrack_points GROUP BY sid`);
    const byMonth = Array(12).fill(0); const byDecade = {}; const byBasin = {}; const byStrength = { D: 0, CS: 0, SCS: 0, VSCS: 0 };
    for (const r of rows) {
      byMonth[r.month - 1]++;
      const dec = `${Math.floor(r.season / 10) * 10}s`;
      byDecade[dec] = (byDecade[dec] || 0) + 1;
      byBasin[r.basin] = (byBasin[r.basin] || 0) + 1;
      const kt = r.kt || 0;
      byStrength[kt >= 64 ? 'VSCS' : kt >= 48 ? 'SCS' : kt >= 34 ? 'CS' : 'D']++;
    }
    const seasons = new Set(rows.map(r => r.season)).size;
    ok(res, { storms: rows.length, seasons, per_year: +(rows.length / seasons).toFixed(1), by_month: byMonth, by_decade: byDecade, by_basin: byBasin, by_strength: byStrength });
  } catch (err) { next(err); }
});

module.exports = router;
