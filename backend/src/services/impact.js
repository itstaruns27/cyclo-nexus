/**
 * Impact engine — people exposed to a cyclone and what similar storms caused.
 * ════════════════════════════════════════════════════════════════════════
 * Population: GeoNames cities1000 (every town/city ≥ 1,000 people, CC-BY 4.0), filtered to the
 * North Indian Ocean region → backend/data/geonames_nio.json. Villages below 1,000 people are not
 * listed, so exposure is a LOWER BOUND of the true number of people affected.
 *
 * Wind zones around each track point (interpolated every ~25 km), by the point's wind speed:
 *   destructive core  ≥ 64 kt → within 60 km
 *   strong-wind zone  ≥ 34 kt → within 150 km (34–47 kt), 200 km (48–63 kt), 250 km (≥ 64 kt)
 * These are typical NIO radii (JTWC wind-radii climatology), not storm-specific wind fields.
 *
 * Recorded deaths / damage: backend/data/cyclone_impacts.json (approximate, cited per storm).
 */

const path = require('path');
const towns = require(path.join(__dirname, '..', '..', 'data', 'geonames_nio.json')).rows;
const recorded = require(path.join(__dirname, '..', '..', 'data', 'cyclone_impacts.json'));

const CELL = 1; // degrees; spatial index for the town list
const index = new Map();
for (const t of towns) {
  const key = `${Math.floor(t[1] / CELL)},${Math.floor(t[2] / CELL)}`;
  if (!index.has(key)) index.set(key, []);
  index.get(key).push(t);
}

const R = Math.PI / 180;
function haversineKm(lat1, lon1, lat2, lon2) {
  const a = Math.sin(((lat2 - lat1) * R) / 2) ** 2
    + Math.cos(lat1 * R) * Math.cos(lat2 * R) * Math.sin(((lon2 - lon1) * R) / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(a));
}

function galeRadiusKm(kt) {
  if (kt >= 64) return 250;
  if (kt >= 48) return 200;
  if (kt >= 34) return 150;
  return 0;
}
const coreRadiusKm = kt => (kt >= 64 ? 60 : 0);

/** Towns within `km` of a point. */
function townsNear(lat, lon, km) {
  const dLat = km / 111 + CELL; const dLon = km / (111 * Math.max(0.2, Math.cos(lat * R))) + CELL;
  const out = [];
  for (let a = Math.floor((lat - dLat) / CELL); a <= Math.floor((lat + dLat) / CELL); a++) {
    for (let b = Math.floor((lon - dLon) / CELL); b <= Math.floor((lon + dLon) / CELL); b++) {
      for (const t of index.get(`${a},${b}`) || []) {
        const d = haversineKm(lat, lon, t[1], t[2]);
        if (d <= km) out.push([t, d]);
      }
    }
  }
  return out;
}

/** Densify a track so zones are continuous between 6-hourly points (linear lat/lon/wind). */
function densify(points, stepKm = 25) {
  const out = [];
  for (let i = 0; i < points.length; i++) {
    const p = points[i];
    out.push(p);
    const q = points[i + 1];
    if (!q) break;
    const n = Math.floor(haversineKm(p.lat, p.lon, q.lat, q.lon) / stepKm);
    for (let k = 1; k < n; k++) {
      const f = k / n;
      out.push({ lat: p.lat + (q.lat - p.lat) * f, lon: p.lon + (q.lon - p.lon) * f, kt: p.kt + (q.kt - p.kt) * f });
    }
  }
  return out;
}

/**
 * People and towns inside the strong-wind zone and the destructive core of a track.
 * points: [{ lat, lon, kt }] (kt = sustained wind in knots; null/undefined → 0).
 */
function exposure(points) {
  const hit = new Map(); // town name|lat|lon → { town, zone, km }
  for (const p of densify(points.map(p => ({ lat: Number(p.lat), lon: Number(p.lon), kt: Number(p.kt) || 0 })))) {
    const gale = galeRadiusKm(p.kt);
    if (!gale) continue;
    const core = coreRadiusKm(p.kt);
    for (const [t, d] of townsNear(p.lat, p.lon, gale)) {
      const key = `${t[0]}|${t[1]}|${t[2]}`;
      const prev = hit.get(key);
      const inCore = d <= core || prev?.zone === 'core';
      hit.set(key, { t, zone: inCore ? 'core' : 'gale', km: Math.min(d, prev?.km ?? Infinity) });
    }
  }
  const all = [...hit.values()];
  const sum = list => list.reduce((s, h) => s + h.t[3], 0);
  const core = all.filter(h => h.zone === 'core');
  const byCountry = {};
  for (const h of all) byCountry[h.t[4]] = (byCountry[h.t[4]] || 0) + h.t[3];
  return {
    people_gale_zone: sum(all),
    people_core: sum(core),
    towns_gale_zone: all.length,
    towns_core: core.length,
    by_country: byCountry,
    largest_towns: all.sort((a, b) => b.t[3] - a.t[3]).slice(0, 12).map(h => ({
      name: h.t[0], country: h.t[4], population: h.t[3], zone: h.zone, min_distance_km: Math.round(h.km),
    })),
  };
}

const recordBySid = new Map(recorded.storms.map(s => [s.sid, s]));
const recordedFor = sid => recordBySid.get(sid) || null;

/** Recorded impacts of past storms with a similar peak wind (±20 kt), for "what could this cause". */
function analogs(peakKt, maxWindBySid) {
  const list = recorded.storms
    .map(s => ({ ...s, peak_wind_kt: maxWindBySid[s.sid] ?? null }))
    .filter(s => s.peak_wind_kt != null && Math.abs(s.peak_wind_kt - peakKt) <= 20);
  if (!list.length) return null;
  const pick = k => list.map(s => s[k]).filter(v => v != null);
  const range = arr => (arr.length ? [Math.min(...arr), Math.max(...arr)] : null);
  const median = arr => {
    if (!arr.length) return null;
    const v = [...arr].sort((x, y) => x - y); const m = Math.floor(v.length / 2);
    return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
  };
  // Median is what the public sees: one extreme event (e.g. Nargis 2008) must not define "typical"
  return {
    storms: list,
    deaths_range: range(pick('deaths')), damage_inr_range: range(pick('damage_inr')),
    deaths_median: median(pick('deaths')), damage_inr_median: median(pick('damage_inr')),
  };
}

module.exports = {
  exposure, analogs, recordedFor, townsNear, haversineKm, galeRadiusKm,
  recordedNote: recorded.note, recordedStorms: recorded.storms, TOWN_COUNT: towns.length,
};
