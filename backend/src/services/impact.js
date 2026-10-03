/**
 * Impact engine — people exposed to a cyclone and what similar storms caused.
 * ════════════════════════════════════════════════════════════════════════
 * People: GHS-POP 2020 gridded population (EU JRC, CC-BY 4.0, ~1 km aggregated to 2.5' ≈ 4.6 km;
 * backend/scripts/build_geo.py), so villages and rural areas count and cities are not double counted;
 * countries per cell follow the Government of India's view of its boundaries (Natural Earth IND).
 * Town names: GeoNames cities1000 (every town/city ≥ 1,000 people, CC-BY 4.0), filtered to the
 * North Indian Ocean region → backend/data/geonames_nio.json. Villages below 1,000 people are not
 * listed, so exposure is a LOWER BOUND of the true number of people affected.
 *
 * Wind zones around each track point (interpolated every ~25 km), using the storm's real size:
 *   gale (≥ 34 kt) · storm-force (≥ 50 kt) · hurricane-force (≥ 64 kt, "destructive core")
 * Radii per quadrant (NE/SE/SW/NW) come from JTWC best-track wind radii in IBTrACS where measured
 * (most storms since 2001). Otherwise the median NIO radii for that intensity are used
 * (data/wind_radii_climatology.json, built from the same IBTrACS file). A town counts in the
 * strongest zone it falls in at any time.
 *
 * Recorded deaths / damage: backend/data/cyclone_impacts.json (approximate, cited per storm).
 */

const fs = require('fs');
const path = require('path');
const towns = require(path.join(__dirname, '..', '..', 'data', 'geonames_nio.json')).rows;
const recorded = require(path.join(__dirname, '..', '..', 'data', 'cyclone_impacts.json'));

// Population grid (float32 people per cell) and country index per cell
const GRID = require(path.join(__dirname, '..', '..', 'data', 'pop_grid.json'));
const readBin = (f, T) => {
  const b = fs.readFileSync(path.join(__dirname, '..', '..', 'data', f));
  return new T(b.buffer, b.byteOffset, b.byteLength / T.BYTES_PER_ELEMENT);
};
const POP = readBin('pop_grid.bin', Float32Array);
const CTRY = readBin('country_grid.bin', Uint8Array);
const ZONE = new Uint8Array(GRID.rows * GRID.cols); // scratch: strongest zone reached per cell

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

const NM = 1.852;
const climatology = require(path.join(__dirname, '..', '..', 'data', 'wind_radii_climatology.json')).bins;
const QUADS = ['ne', 'se', 'sw', 'nw'];
const THRESHOLDS = [34, 50, 64];

/** Median radius (km) of a wind threshold for a storm of `kt` (IMD 3-min wind ≈ 0.93 × JTWC 1-min). */
function climRadiusKm(kt, threshold) {
  const k1 = kt / 0.93;
  if (k1 < threshold) return 0;
  const keys = Object.keys(climatology).map(Number).sort((x, y) => x - y);
  const bin = Math.min(keys[keys.length - 1], Math.floor(k1 / 10) * 10);
  const row = climatology[bin];
  return row ? row[`r${threshold}_nm`] * NM : 0;
}

/** { 34: [ne, se, sw, nw], 50: [...], 64: [...] } in km — measured when available, else climatology. */
function radiiKm(p) {
  const measured = p.r34_ne != null;
  const out = {};
  for (const th of THRESHOLDS) {
    out[th] = QUADS.map(q => (measured ? (Number(p[`r${th}_${q}`]) || 0) * NM : climRadiusKm(p.kt, th)));
  }
  return { radii: out, measured };
}

/** Typical strong-wind (≥ 34 kt) radius for a wind speed — used by CAP alert circles. */
function galeRadiusKm(kt) {
  return Math.round(climRadiusKm(kt, 34)) || 0;
}

function bearingDeg(lat1, lon1, lat2, lon2) {
  const y = Math.sin((lon2 - lon1) * R) * Math.cos(lat2 * R);
  const x = Math.cos(lat1 * R) * Math.sin(lat2 * R) - Math.sin(lat1 * R) * Math.cos(lat2 * R) * Math.cos((lon2 - lon1) * R);
  return (Math.atan2(y, x) / R + 360) % 360;
}

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
      const kt = p.kt + (q.kt - p.kt) * f;
      const radii = {};
      for (const th of THRESHOLDS) radii[th] = p.radii[th].map((r, i) => r + (q.radii[th][i] - r) * f);
      out.push({ lat: p.lat + (q.lat - p.lat) * f, lon: p.lon + (q.lon - p.lon) * f, kt, radii });
    }
  }
  return out;
}

/** Mark grid cells inside this point's quadrant wind field with the strongest zone (1 gale, 2 storm, 3 core). */
function markCells(p, reach, touched) {
  const { west, north, cell_deg: d, rows, cols } = GRID;
  const kmLat = 111.2; const kmLon = 111.2 * Math.cos(p.lat * R);
  const r0 = Math.max(0, Math.floor((north - (p.lat + reach / kmLat)) / d));
  const r1 = Math.min(rows - 1, Math.floor((north - (p.lat - reach / kmLat)) / d));
  const c0 = Math.max(0, Math.floor((p.lon - reach / kmLon - west) / d));
  const c1 = Math.min(cols - 1, Math.floor((p.lon + reach / kmLon - west) / d));
  for (let r = r0; r <= r1; r++) {
    const dy = (north - (r + 0.5) * d - p.lat) * kmLat;
    for (let c = c0; c <= c1; c++) {
      const i = r * cols + c;
      if (ZONE[i] === 3 || POP[i] <= 0) continue;
      const dx = (west + (c + 0.5) * d - p.lon) * kmLon;
      const dist = Math.hypot(dx, dy);
      if (dist > reach) continue;
      const q = Math.floor(((Math.atan2(dx, dy) / R + 360) % 360) / 90) % 4; // NE, SE, SW, NW
      const z = dist <= p.radii[64][q] ? 3 : dist <= p.radii[50][q] ? 2 : dist <= p.radii[34][q] ? 1 : 0;
      if (z > ZONE[i]) {
        if (!ZONE[i]) touched.push(i);
        ZONE[i] = z;
      }
    }
  }
}

/** People per zone and per country from the marked cells; resets the scratch grid. */
function gridTotals(touched) {
  const out = { people_gale_zone: 0, people_storm_zone: 0, people_core: 0, by_country: {} };
  for (const i of touched) {
    const n = POP[i]; const z = ZONE[i];
    out.people_gale_zone += n;
    if (z >= 2) out.people_storm_zone += n;
    if (z >= 3) out.people_core += n;
    const cc = GRID.countries[CTRY[i]];
    if (cc) out.by_country[cc] = (out.by_country[cc] || 0) + n;
    ZONE[i] = 0;
  }
  for (const k of ['people_gale_zone', 'people_storm_zone', 'people_core']) out[k] = Math.round(out[k]);
  for (const k of Object.keys(out.by_country)) out.by_country[k] = Math.round(out.by_country[k]);
  return out;
}

/**
 * People and towns in the gale (≥ 34 kt), storm-force (≥ 50 kt) and hurricane-force (≥ 64 kt) zones.
 * points: [{ lat, lon, kt, r34_ne … r64_nw (nm, optional) }] (kt = sustained wind in knots).
 */
function exposure(points) {
  const RANK = { gale: 1, storm: 2, core: 3 };
  const hit = new Map(); // town key → { t, zone, km }
  const touched = [];
  let measured = 0;
  const pts = points.map(p => {
    const kt = Number(p.kt) || 0;
    const r = radiiKm({ ...p, kt });
    measured += r.measured;
    return { lat: Number(p.lat), lon: Number(p.lon), kt, radii: r.radii };
  });
  for (const p of densify(pts)) {
    const reach = Math.max(...p.radii[34]);
    if (!reach) continue;
    markCells(p, reach, touched);
    for (const [t, d] of townsNear(p.lat, p.lon, reach)) {
      const q = Math.floor(bearingDeg(p.lat, p.lon, t[1], t[2]) / 90) % 4;
      const zone = d <= p.radii[64][q] ? 'core' : d <= p.radii[50][q] ? 'storm' : d <= p.radii[34][q] ? 'gale' : null;
      if (!zone) continue;
      const key = `${t[0]}|${t[1]}|${t[2]}`;
      const prev = hit.get(key);
      const best = prev && RANK[prev.zone] >= RANK[zone] ? prev.zone : zone;
      hit.set(key, { t, zone: best, km: Math.min(d, prev?.km ?? Infinity) });
    }
  }
  const all = [...hit.values()];
  const atLeast = z => all.filter(h => RANK[h.zone] >= RANK[z]);
  return {
    ...gridTotals(touched),
    towns_gale_zone: all.length,
    towns_storm_zone: atLeast('storm').length,
    towns_core: atLeast('core').length,
    radii_source: measured
      ? `measured JTWC wind radii (${measured} of ${points.length} track points), typical radii elsewhere`
      : 'typical radii for the intensity (IBTrACS North Indian Ocean climatology)',
    largest_towns: all.sort((a, b) => b.t[3] - a.t[3]).slice(0, 12).map(h => ({
      name: h.t[0], country: h.t[4], population: h.t[3], zone: h.zone, min_distance_km: Math.round(h.km),
    })),
  };
}

const DIRS8 = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];

/**
 * A place people know for a point: the point's own town if within 5 km and ≥ 50,000 people; otherwise the best of
 * score = 30·log10(population) − distance_km, so a 10× bigger town wins if it is < 30 km further
 * ("45 km SE of Chandrapur" rather than "33 km E of a village"). Widens until a town is found.
 * Returns { name, country, population, distance_km, direction } (direction of the point from the town).
 */
function placeLabel(lat, lon) {
  for (const km of [60, 150, 300, 600]) {
    const found = townsNear(lat, lon, km).sort((a, b) => a[1] - b[1]);
    if (!found.length) continue;
    const score = ([t, d]) => 30 * Math.log10(t[3]) - d;
    const pick = found[0][1] <= 5 && found[0][0][3] >= 50000 ? found[0]
      : townsNear(lat, lon, found[0][1] + 150).reduce((best, x) => (score(x) > score(best) ? x : best), found[0]);
    const [t, d] = pick;
    return {
      name: t[0], country: t[4], population: t[3], distance_km: Math.round(d),
      direction: DIRS8[Math.round(bearingDeg(t[1], t[2], lat, lon) / 45) % 8],
    };
  }
  return null;
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
  exposure, analogs, recordedFor, townsNear, haversineKm, galeRadiusKm, placeLabel, radiiKm, bearingDeg,
  recordedNote: recorded.note, recordedStorms: recorded.storms, TOWN_COUNT: towns.length,
};
