/**
 * Track-forecast cone of uncertainty (IMD method)
 * ═══════════════════════════════════════════════
 * IMD draws a circle around each official forecast position whose radius is the average official
 * track-forecast error for that lead time, and the cone is the area those circles sweep
 * (Mohapatra et al., "Evaluation of Cone of Uncertainty in Tropical Cyclone Track Forecast over
 * North Indian Ocean Issued by India Meteorological Department", Tropical Cyclone Research and
 * Review). Radii are IMD's, from 2003–2008 errors: 35, 75, 115, 150 km at 6–24 h and 200, 250,
 * 300, 350 km at 36–72 h. Recent errors are smaller, so the cone is on the safe (wide) side.
 *
 * Geometry: the track is densified hourly in a local km plane; the boundary is the exact envelope
 * of the moving, growing circles — centre c(s), radius r(s), k = dr/ds:
 *     boundary = c + r · (−k·t ± √(1−k²)·n)     (t: unit tangent, n: unit normal)
 * closed by the final circle's forward arc. Where k ≥ 1 a circle lies inside the next one and
 * contributes no boundary point (slow or stationary storms).
 */

const IMD_CONE_KM = [[0, 0], [6, 35], [12, 75], [18, 115], [24, 150], [36, 200], [48, 250], [60, 300], [72, 350]];
const MAX_HOUR = 72;
const KM_PER_DEG_LAT = 110.57;

function coneRadiusKm(hour) {
  if (hour <= 0) return 0;
  if (hour >= MAX_HOUR) return IMD_CONE_KM[IMD_CONE_KM.length - 1][1];
  for (let i = 1; i < IMD_CONE_KM.length; i++) {
    const [h1, r1] = IMD_CONE_KM[i];
    if (hour <= h1) {
      const [h0, r0] = IMD_CONE_KM[i - 1];
      return r0 + ((r1 - r0) * (hour - h0)) / (h1 - h0);
    }
  }
  return 0;
}

/**
 * @param {{hour:number, lat:number, lon:number}[]} nodes  analysis (hour 0) + official forecast points
 * @returns {number[][]|null}  closed [lon, lat] ring, or null with fewer than two usable nodes
 */
function buildConeRing(nodes) {
  const pts = nodes
    .filter(p => p.hour >= 0 && p.hour <= MAX_HOUR && Number.isFinite(+p.lat) && Number.isFinite(+p.lon))
    .map(p => ({ hour: +p.hour, lat: +p.lat, lon: +p.lon }))
    .sort((a, b) => a.hour - b.hour)
    .filter((p, i, a) => i === 0 || p.hour > a[i - 1].hour);
  if (pts.length < 2) return null;

  const lat0 = pts[0].lat;
  const lon0 = pts[0].lon;
  const kmPerDegLon = 111.32 * Math.cos((lat0 * Math.PI) / 180);
  const toXY = p => [(p.lon - lon0) * kmPerDegLon, (p.lat - lat0) * KM_PER_DEG_LAT];
  const toLonLat = ([x, y]) => [+(lon0 + x / kmPerDegLon).toFixed(4), +(lat0 + y / KM_PER_DEG_LAT).toFixed(4)];

  // Hourly centres along the track
  const c = [];
  for (let i = 1; i < pts.length; i++) {
    const a = pts[i - 1];
    const b = pts[i];
    for (let h = a.hour; h < b.hour || (i === pts.length - 1 && h === b.hour); h++) {
      const f = (h - a.hour) / (b.hour - a.hour);
      c.push({ xy: toXY({ lat: a.lat + f * (b.lat - a.lat), lon: a.lon + f * (b.lon - a.lon) }), r: coneRadiusKm(h) });
    }
  }
  const unit = ([x, y]) => { const d = Math.hypot(x, y); return d > 1e-9 ? [x / d, y / d] : null; };

  const left = [];
  const right = [];
  let lastT = null;
  for (let i = 0; i < c.length; i++) {
    const prev = c[Math.max(0, i - 1)];
    const next = c[Math.min(c.length - 1, i + 1)];
    const d = [next.xy[0] - prev.xy[0], next.xy[1] - prev.xy[1]];
    const t = unit(d) || lastT;
    if (!t) continue;
    lastT = t;
    const ds = Math.hypot(...d);
    const k = ds > 1e-9 ? (next.r - prev.r) / ds : Infinity;
    if (k >= 1 || c[i].r === 0) continue; // nested inside the next circle, or the zero-radius analysis point
    const s = Math.sqrt(1 - k * k);
    const n = [-t[1], t[0]];
    const { xy: [x, y], r } = c[i];
    left.push([x + r * (-k * t[0] + s * n[0]), y + r * (-k * t[1] + s * n[1])]);
    right.push([x + r * (-k * t[0] - s * n[0]), y + r * (-k * t[1] - s * n[1])]);
  }

  // Forward arc of the final circle, from the left envelope round the front to the right envelope
  const end = c[c.length - 1];
  const t = lastT || [1, 0];
  const heading = Math.atan2(t[1], t[0]);
  const before = c[c.length - 2];
  const kEnd = (end.r - before.r) / Math.max(1e-9, Math.hypot(end.xy[0] - before.xy[0], end.xy[1] - before.xy[1]));
  // Full circle when no envelope precedes it (stationary storm); otherwise the arc between the envelope sides
  const phi = left.length ? Math.acos(-Math.max(-0.999, Math.min(0.999, kEnd))) : Math.PI;
  const arc = [];
  const STEPS = 36;
  for (let j = 0; j <= STEPS; j++) {
    const a = heading + phi - (2 * phi * j) / STEPS;
    arc.push([end.xy[0] + end.r * Math.cos(a), end.xy[1] + end.r * Math.sin(a)]);
  }

  const start = c[0].xy;
  const ring = [start, ...left, ...arc, ...right.reverse(), start].map(toLonLat);
  return ring;
}

/** GeoJSON Feature for the first official forecast of a cyclone row (getById shape), or null. */
function coneFeature(cyclone) {
  const official = (cyclone.forecasts || []).filter(f => String(f.source || '').startsWith('OFFICIAL_'));
  if (!official.length) return null;
  const source = official[0].source;
  const ring = buildConeRing([
    { hour: 0, lat: cyclone.current_lat, lon: cyclone.current_lon },
    ...official.filter(f => f.source === source)
      .map(f => ({ hour: f.forecast_hour, lat: f.predicted_lat, lon: f.predicted_lon })),
  ]);
  if (!ring) return null;
  return {
    type: 'Feature',
    geometry: { type: 'Polygon', coordinates: [ring] },
    properties: { type: 'forecast_cone', source, cyclone_id: cyclone.cyclone_id, method: 'IMD cone of uncertainty (2003–2008 mean official track errors)' },
  };
}

module.exports = { coneRadiusKm, buildConeRing, coneFeature, IMD_CONE_KM };
