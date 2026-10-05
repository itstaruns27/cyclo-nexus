/**
 * Cyclone API Routes — GET /api/v1/cyclones
 * ═════════════════════════════════════════
 * Owner: Agent DELTA
 */

const express = require('express');
const router = express.Router();
const cycloneStore = require('../services/cyclone_store');
const geojsonSerializer = require('../services/geojson_serializer');
const { cacheMiddleware } = require('../middleware/cache');
const { computeMovement, alertLevel } = require('../services/advisory_generator');

// GET /api/v1/cyclones — List active official systems and satellite watch areas
router.get('/', cacheMiddleware, async (_req, res, next) => {
  try {
    const rows = await cycloneStore.listActive();
    const cyclones = await Promise.all(rows.map(async c => {
      const history = await cycloneStore.getHistory(c.cyclone_id);
      const official = String(c.source).startsWith('OFFICIAL_');
      return {
        ...c,
        movement: computeMovement(history),
        alert_level: official && c.status === 'active' ? alertLevel(Number(c.sustained_wind_kmh)) : null,
      };
    }));
    res.json({
      success: true,
      data: cyclones,
      timestamp: new Date().toISOString(),
      cached: false,
    });
  } catch (err) {
    next(err);
  }
});

// GET /api/v1/cyclones/:id — Get specific cyclone details
router.get('/:id', cacheMiddleware, async (req, res, next) => {
  try {
    const cyclone = await cycloneStore.getById(req.params.id);
    if (!cyclone) {
      return res.status(404).json({ success: false, error: 'Cyclone not found' });
    }

    res.json({
      success: true,
      data: cyclone,
      timestamp: new Date().toISOString(),
      cached: false,
    });
  } catch (err) {
    next(err);
  }
});

// GET /api/v1/cyclones/:id/forecast — Get GeoJSON forecast
// Grad-CAM image of the satellite intensity estimate (what the CNN looked at), JPEG
router.get('/:id/heatmap', async (req, res, next) => {
  try {
    const img = await cycloneStore.getHeatmap(req.params.id);
    if (!img) return res.status(404).json({ success: false, error: 'No satellite heatmap for this system' });
    res.set('Cache-Control', 'public, max-age=600').type('image/jpeg').send(img);
  } catch (err) {
    next(err);
  }
});

router.get('/:id/forecast', cacheMiddleware, async (req, res, next) => {
  try {
    const cyclone = await cycloneStore.getById(req.params.id);
    if (!cyclone) {
      return res.status(404).json({ success: false, error: 'Cyclone not found' });
    }

    const geojson = geojsonSerializer.buildForecast(cyclone);
    res.json({
      success: true,
      data: geojson,
      timestamp: new Date().toISOString(),
      cached: false,
    });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
