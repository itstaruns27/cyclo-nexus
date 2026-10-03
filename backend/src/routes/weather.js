/**
 * Weather Routes
 *   GET /api/v1/weather/wind-grid        — cached 3° 10 m wind (u/v) over the North Indian Ocean map view
 *   GET /api/v1/weather/place?lat&lon     — nearest named town (GeoNames) with distance and bearing, for labelling
 *                                           any point the user picks (works at sea: "180 km SE of Puri")
 */

const express = require('express');
const router = express.Router();
const { getWindGrid } = require('../workers/wind_grid');
const { placeLabel } = require('../services/impact');

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
  res.json({ success: true, data: placeLabel(lat, lon) });
});

module.exports = router;
