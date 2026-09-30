/**
 * Weather Routes
 *   GET /api/v1/weather/wind-grid        — cached 3° 10 m wind (u/v) over the North Indian Ocean map view
 *   GET /api/v1/weather/place?lat&lon     — nearest named town (GeoNames) with distance and bearing, for labelling
 *                                           any point the user picks (works at sea: "180 km SE of Puri")
 */

const express = require('express');
const router = express.Router();
const { getWindGrid } = require('../workers/wind_grid');
const { townsNear } = require('../services/impact');

const DIRS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
function bearing(lat1, lon1, lat2, lon2) {
  const r = Math.PI / 180;
  const y = Math.sin((lon2 - lon1) * r) * Math.cos(lat2 * r);
  const x = Math.cos(lat1 * r) * Math.sin(lat2 * r) - Math.sin(lat1 * r) * Math.cos(lat2 * r) * Math.cos((lon2 - lon1) * r);
  return DIRS[Math.round(((Math.atan2(y, x) / r + 360) % 360) / 45) % 8];
}

router.get('/wind-grid', (_req, res) => {
  const grid = getWindGrid();
  if (!grid) {
    return res.status(503).json({ success: false, error: 'Wind grid not available yet' });
  }
  res.set('Cache-Control', 'public, max-age=600');
  res.json({ success: true, data: grid, timestamp: new Date().toISOString() });
});

router.get('/place', (req, res) => {
  const lat = Number(req.query.lat); const lon = Number(req.query.lon);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
    return res.status(400).json({ success: false, error: 'lat and lon required' });
  }
  // Label with a place people know: the point's own town if within 5 km; otherwise the best of
  // score = 30·log10(population) − distance_km, so a 10× bigger town wins if it is < 30 km further
  // ("45 km SE of Chandrapur" rather than "33 km E of a village"). The search widens until a town
  // (≥ 1,000 people, GeoNames) is found.
  for (const km of [60, 150, 300, 600]) {
    const found = townsNear(lat, lon, km).sort((a, b) => a[1] - b[1]);
    if (!found.length) continue;
    const score = ([t, d]) => 30 * Math.log10(t[3]) - d;
    const pick = found[0][1] <= 5 ? found[0]
      : townsNear(lat, lon, found[0][1] + 150).reduce((best, x) => (score(x) > score(best) ? x : best), found[0]);
    const [t, d] = pick;
    return res.json({
      success: true,
      data: {
        name: t[0], country: t[4], population: t[3], distance_km: Math.round(d),
        // Direction of the picked point as seen from the town ("180 km SE of Puri")
        direction: bearing(t[1], t[2], lat, lon),
      },
    });
  }
  res.json({ success: true, data: null });
});

module.exports = router;
