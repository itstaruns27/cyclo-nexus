/**
 * Advisory Routes — GET /api/v1/cyclones/:id/advisory?lang=en
 * ══════════════════════════════════════════════════════════
 * Owner: Agent DELTA | Task 17
 * Deterministic template advisories built from the stored official data.
 */

const express = require('express');
const router = express.Router();
const { cacheMiddleware } = require('../middleware/cache');
const cycloneStore = require('../services/cyclone_store');
const { buildAdvisory } = require('../services/advisory_generator');

router.get('/:id/advisory', cacheMiddleware, async (req, res, next) => {
  try {
    const cyclone = await cycloneStore.getById(req.params.id);
    if (!cyclone) {
      return res.status(404).json({ success: false, error: 'Cyclone not found' });
    }
    const lang = String(req.query.lang || 'en').slice(0, 5);
    res.json({
      success: true,
      data: buildAdvisory(cyclone, lang),
      timestamp: new Date().toISOString(),
      cached: false,
    });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
