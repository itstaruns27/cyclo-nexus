/**
 * Storm profile — everything about one cyclone, past or active, for the storm detail page
 * ═════════════════════════════════════════════════════════════════════════════════════════
 *   GET /api/v1/storms/:id/profile?lang=en
 *     :id = IBTrACS SID (e.g. 2020136N10088, past storms since 1980) or an active cyclone_id
 *
 * Returns identity, life-cycle statistics, every track position (with JTWC wind radii where
 * measured), landfalls with place names, rapid intensification, ACE, time in each IMD grade,
 * rank among North Indian Ocean storms, people exposed per wind zone, recorded losses or similar-storm
 * losses, similar past storms, and — for active systems — forecasts and the advisory.
 * All values derive from IBTrACS / the official feed / the impact engine; nothing is invented.
 */

const express = require('express');
const router = express.Router();
const { pool } = require('../db/connection');
const { cacheMiddleware } = require('../middleware/cache');
const cycloneStore = require('../services/cyclone_store');
const impact = require('../services/impact');
const { buildAdvisory, computeMovement } = require('../services/advisory_generator');
const { getIMDCategory } = require('../services/imd_scale');

const KMH_PER_KT = 1.852;
const NM_KM = 1.852;
const GRADE_ORDER = ['D', 'DD', 'CS', 'SCS', 'VSCS', 'ESCS', 'SuCS'];
const SID_RE = /^\d{7}[NS]\d{5}$/;
const QUADS = ['ne', 'se', 'sw', 'nw'];

const gradeOf = kt => (kt == null ? null : getIMDCategory(kt * KMH_PER_KT));
const rankGrade = g => GRADE_ORDER.indexOf(g);

/** Normalised track point from a besttrack_points row. */
function fromBestTrack(r) {
  const radii = th => (r[`r${th}_ne`] == null ? null : QUADS.map(q => Math.round((Number(r[`r${th}_${q}`]) || 0) * NM_KM)));
  return {
    time: new Date(r.iso_time).toISOString(), lat: Number(r.lat), lon: Number(r.lon),
    wind_kt: r.kt == null ? null : Math.round(Number(r.kt)), pressure_hpa: r.pressure_hpa == null ? null : Number(r.pressure_hpa),
    grade: GRADE_ORDER.includes(r.grade) ? r.grade : (r.kt != null ? gradeOf(Number(r.kt)) : null),
    dist2land_km: r.dist2land_km == null ? null : Number(r.dist2land_km),
    speed_kmh: r.storm_speed_kt == null ? null : Math.round(Number(r.storm_speed_kt) * KMH_PER_KT),
    dir_deg: r.storm_dir_deg == null ? null : Math.round(Number(r.storm_dir_deg)),
    r34_km: radii(34), r50_km: radii(50), r64_km: radii(64),
    rmw_km: r.rmw_nm == null ? null : Math.round(Number(r.rmw_nm) * NM_KM),
    // impact.exposure() reads these raw fields
    kt: r.kt == null ? null : Number(r.kt),
    ...Object.fromEntries(['34', '50', '64'].flatMap(th => QUADS.map(q => [`r${th}_${q}`, r[`r${th}_${q}`]]))),
  };
}

function lifeCycle(points) {
  const km = (a, b) => impact.haversineKm(a.lat, a.lon, b.lat, b.lon);
  let distance = 0;
  for (let i = 1; i < points.length; i++) distance += km(points[i - 1], points[i]);
  const start = points[0].time; const end = points[points.length - 1].time;
  const hours = (new Date(end) - new Date(start)) / 3600e3;
  const withWind = points.filter(p => p.wind_kt != null);
  const peak = withWind.reduce((a, p) => (!a || p.wind_kt > a.wind_kt ? p : a), null);
  const withP = points.filter(p => p.pressure_hpa != null);
  const minP = withP.reduce((a, p) => (!a || p.pressure_hpa < a.pressure_hpa ? p : a), null);
  const grades = points.map(p => p.grade).filter(g => GRADE_ORDER.includes(g));
  const peakGrade = grades.sort((a, b) => rankGrade(b) - rankGrade(a))[0] || null;

  // Largest 24 h wind increase; rapid intensification = ≥ 30 kt in 24 h (standard definition)
  let ri = null;
  for (const p of withWind) {
    const t24 = new Date(p.time).getTime() + 24 * 3600e3;
    const q = withWind.find(x => Math.abs(new Date(x.time).getTime() - t24) < 1800e3);
    if (q && (!ri || q.wind_kt - p.wind_kt > ri.kt)) ri = { kt: Math.round(q.wind_kt - p.wind_kt), from: p.time, to: q.time };
  }

  // ACE (10⁴ kt²): Σ v² over 6-hourly steps at ≥ 35 kt; irregular tracks weight each point by its
  // interval to the next point (in 6 h units), which equals the standard sum for a 6-hourly track
  let ace = 0;
  for (let i = 0; i < withWind.length; i++) {
    const p = withWind[i]; const q = withWind[i + 1];
    if (p.wind_kt < 35) continue;
    const w = q ? (new Date(q.time) - new Date(p.time)) / (6 * 3600e3) : 1;
    ace += p.wind_kt ** 2 * Math.min(w, 2);
  }
  ace /= 1e4;

  // Hours spent in each IMD grade (each point represents the interval to the next point)
  const gradeHours = {};
  for (let i = 0; i < points.length - 1; i++) {
    const g = points[i].grade;
    if (!g) continue;
    gradeHours[g] = (gradeHours[g] || 0) + (new Date(points[i + 1].time) - new Date(points[i].time)) / 3600e3;
  }

  // Landfalls: sea → land transitions in the best track
  const landfalls = [];
  for (let i = 1; i < points.length; i++) {
    if (points[i].dist2land_km === 0 && points[i - 1].dist2land_km > 0) {
      const p = points[i];
      landfalls.push({ time: p.time, lat: p.lat, lon: p.lon, wind_kt: p.wind_kt, grade: p.grade, place: impact.placeLabel(p.lat, p.lon) });
    }
  }

  const sizes = points.filter(p => p.r34_km).map(p => p.r34_km.reduce((a, b) => a + b, 0) / 4);
  return {
    start, end, duration_h: Math.round(hours), distance_km: Math.round(distance),
    mean_speed_kmh: hours > 0 ? Math.round(distance / hours) : null,
    peak: peak ? { wind_kt: peak.wind_kt, wind_kmh: Math.round(peak.wind_kt * KMH_PER_KT), time: peak.time,
      lat: peak.lat, lon: peak.lon, place: impact.placeLabel(peak.lat, peak.lon) } : null,
    min_pressure: minP ? { hpa: minP.pressure_hpa, time: minP.time } : null,
    peak_grade: peakGrade,
    rapid_intensification: ri && ri.kt >= 30 ? ri : null,
    max_24h_intensification_kt: ri ? Math.round(ri.kt) : null,
    ace: Math.round(ace * 10) / 10,
    grade_hours: Object.fromEntries(Object.entries(gradeHours).map(([g, h]) => [g, Math.round(h)])),
    landfalls,
    max_gale_radius_km: sizes.length ? Math.round(Math.max(...sizes)) : null,
    genesis: { time: start, lat: points[0].lat, lon: points[0].lon, place: impact.placeLabel(points[0].lat, points[0].lon) },
  };
}

/** Gale-force (≥ 34 kt) radii per quadrant in km — measured where JTWC reported them, else typical. */
function withGale(p) {
  const { radii, measured } = impact.radiiKm({ ...p, kt: p.wind_kt ?? 0 });
  return { ...p, gale_km: radii[34].map(Math.round), gale_measured: measured };
}

/** Rank by peak wind among storms of the same sub-basin since 1980, and similar past storms. */
async function context(sid, basin, peakKt, month) {
  const [rows] = await pool.query(
    `SELECT sid, MAX(name) AS name, MAX(season) AS season, MAX(subbasin) AS subbasin, MAX(wind_kt) AS peak_kt,
            MIN(pressure_hpa) AS min_p, MIN(iso_time) AS start_time
       FROM besttrack_points GROUP BY sid HAVING MAX(wind_kt) IS NOT NULL`);
  const sameBasin = rows.filter(r => !basin || r.subbasin === basin);
  const stronger = sameBasin.filter(r => r.peak_kt > peakKt && r.sid !== sid).length;
  const similar = rows
    .filter(r => r.sid !== sid && r.subbasin === basin && Math.abs(r.peak_kt - peakKt) <= 15)
    .map(r => {
      const m = new Date(r.start_time).getUTCMonth();
      const dm = Math.min(Math.abs(m - month), 12 - Math.abs(m - month));
      return { ...r, score: Math.abs(r.peak_kt - peakKt) / 5 + dm - (r.name ? 1 : 0) - (impact.recordedFor(r.sid) ? 2 : 0) };
    })
    .sort((a, b) => a.score - b.score).slice(0, 6)
    .map(r => ({ sid: r.sid, name: r.name, season: r.season, peak_kt: r.peak_kt, peak_grade: gradeOf(r.peak_kt),
      min_pressure_hpa: r.min_p, recorded: impact.recordedFor(r.sid) }));
  return { rank_in_basin: stronger + 1, storms_in_basin: sameBasin.length, since: 1980, similar };
}

async function pastProfile(sid) {
  const [rows] = await pool.query(
    `SELECT iso_time, latitude AS lat, longitude AS lon, wind_kt AS kt, pressure_hpa, grade, dist2land_km,
            name, season, subbasin, r34_ne, r34_se, r34_sw, r34_nw, r50_ne, r50_se, r50_sw, r50_nw,
            r64_ne, r64_se, r64_sw, r64_nw, rmw_nm, roci_nm, storm_speed_kt, storm_dir_deg
       FROM besttrack_points WHERE sid = ? ORDER BY iso_time`, [sid]);
  if (!rows.length) return null;
  const points = rows.map(fromBestTrack);
  const life = lifeCycle(points);
  const basin = rows[0].subbasin;
  const ctx = await context(sid, basin, life.peak?.wind_kt ?? 0, new Date(life.start).getUTCMonth());
  const exposure = impact.exposure(points);
  return {
    kind: 'past', id: sid, sid, name: rows[0].name, season: rows[0].season,
    basin: basin === 'AS' ? 'AS' : basin === 'BB' ? 'BOB' : 'NIO',
    source: 'IBTrACS v04r01 (RSMC New Delhi / IMD intensities; JTWC wind radii)',
    life, track: points.map(({ kt, ...p }) => Object.fromEntries(Object.entries(p).filter(([k]) => !/^r\d\d_(ne|se|sw|nw)$/.test(k)))),
    exposure, recorded: impact.recordedFor(sid), analogs: null, context: ctx,
    forecasts: null, advisory: null, recorded_note: impact.recordedNote,
  };
}

async function activeProfile(id, lang) {
  const c = await cycloneStore.getById(id);
  if (!c) return null;
  const hist = (c.history || []).map(h => ({
    time: new Date(h.timestamp).toISOString(), lat: Number(h.latitude), lon: Number(h.longitude),
    wind_kt: h.sustained_wind_kmh == null ? null : Math.round(Number(h.sustained_wind_kmh) / KMH_PER_KT),
    pressure_hpa: h.central_pressure_hpa == null ? null : Number(h.central_pressure_hpa),
    grade: h.imd_category || null, dist2land_km: null,
  }));
  const now = {
    time: new Date(c.observation_time).toISOString(), lat: Number(c.current_lat), lon: Number(c.current_lon),
    wind_kt: Math.round(Number(c.sustained_wind_kmh) / KMH_PER_KT), pressure_hpa: Number(c.central_pressure_hpa),
    grade: c.imd_category, dist2land_km: null,
  };
  const points = hist.length && hist[hist.length - 1].time === now.time ? hist : [...hist, now];
  for (const p of points) p.kt = p.wind_kt;
  const life = lifeCycle(points);
  const bySource = {};
  for (const f of c.forecasts || []) {
    (bySource[f.source] = bySource[f.source] || []).push({
      hour: f.forecast_hour, lat: Number(f.predicted_lat), lon: Number(f.predicted_lon),
      wind_kmh: Number(f.predicted_wind_kmh), pressure_hpa: f.predicted_pressure_hpa == null ? null : Number(f.predicted_pressure_hpa),
      grade: f.predicted_imd_category, place: impact.placeLabel(Number(f.predicted_lat), Number(f.predicted_lon)),
      ...(f.source === 'AI_CONSENSUS' ? {
        cone_radius_km: f.cone_radius_km == null ? null : Number(f.cone_radius_km),
        verified_error_km: f.verified_error_km == null ? null : Number(f.verified_error_km),
        init_time: f.init_time, members: f.members ? String(f.members).split(',') : [],
      } : {}),
    });
  }
  for (const list of Object.values(bySource)) list.sort((a, b) => a.hour - b.hour);
  const officialSrc = Object.keys(bySource).find(s => s.startsWith('OFFICIAL_'));
  const fc = (bySource[officialSrc] || []).map(f => ({ lat: f.lat, lon: f.lon, kt: f.wind_kmh / KMH_PER_KT }));
  const nowPt = { lat: now.lat, lon: now.lon, kt: now.wind_kt };
  const peakKt = Math.max(now.wind_kt, ...fc.map(f => f.kt));
  const [peakRows] = await pool.query('SELECT sid, MAX(wind_kt) AS kt FROM besttrack_points WHERE sid IN (?) GROUP BY sid',
    [impact.recordedStorms.map(s => s.sid)]);
  const basin = c.basin === 'AS' ? 'AS' : 'BB';
  const isOfficial = String(c.source || '').startsWith('OFFICIAL_');
  return {
    kind: 'active', id: c.cyclone_id, sid: null, name: c.cyclone_name, season: new Date(c.observation_time).getUTCFullYear(),
    basin: c.basin || 'NIO', status: c.status, source: c.source, source_url: c.source_url || null,
    is_demo: c.external_id === 'DEMO', observation_time: now.time,
    now: { ...now, wind_kmh: Math.round(Number(c.sustained_wind_kmh)), place: impact.placeLabel(now.lat, now.lon),
      movement: computeMovement(c.history), detection_confidence: c.detection_confidence == null ? null : Number(c.detection_confidence) },
    life, track: points.map(p => withGale(p)).map(({ kt, ...p }) => p),
    exposure: impact.exposure([nowPt]),
    exposure_forecast: fc.length ? impact.exposure([nowPt, ...fc]) : null,
    recorded: null,
    analogs: impact.analogs(peakKt, Object.fromEntries(peakRows.map(r => [r.sid, r.kt]))),
    context: await context(null, basin, peakKt, new Date(now.time).getUTCMonth()),
    forecasts: bySource,
    advisory: isOfficial || c.status === 'watch' ? buildAdvisory(c, lang) : null,
    recorded_note: impact.recordedNote,
  };
}

router.get('/:id/profile', cacheMiddleware, async (req, res, next) => {
  try {
    const id = String(req.params.id);
    const lang = String(req.query.lang || 'en').slice(0, 5);
    const data = SID_RE.test(id) ? await pastProfile(id) : await activeProfile(id, lang);
    if (!data) return res.status(404).json({ success: false, error: 'Storm not found' });
    res.json({ success: true, data, timestamp: new Date().toISOString() });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
