/**
 * Webhook Routes (HMAC-signed, gzip)
 * ══════════════════════════════════
 * Owner: Agent DELTA | Task 14
 *   POST /api/v1/webhook/inference  — satellite pipeline detections (GeoJSON)
 *   POST /api/v1/webhook/heartbeat  — pipeline run status (drives /health freshness)
 */

const express = require('express');
const router = express.Router();
const { verifyWebhookSignature } = require('../middleware/webhook_auth');
const { invalidateCache } = require('../middleware/cache');
const { validateWebhookPayload, validateHeartbeat } = require('../utils/validators');
const cycloneStore = require('../services/cyclone_store');

router.post('/inference', verifyWebhookSignature, async (req, res, next) => {
  try {
    const validation = validateWebhookPayload(req.body);
    if (!validation.success) {
      return res.status(400).json({
        success: false,
        error: 'Payload validation failed',
        details: validation.errors,
      });
    }

    const result = await cycloneStore.upsertFromWebhook(req.body);
    invalidateCache();

    res.status(200).json({
      success: true,
      message: 'Inference payload accepted',
      cyclone_id: result.cycloneId,
      linked: result.linked,
      timestamp: new Date().toISOString(),
    });
  } catch (err) {
    next(err);
  }
});

router.post('/heartbeat', verifyWebhookSignature, async (req, res, next) => {
  try {
    const validation = validateHeartbeat(req.body);
    if (!validation.success) {
      return res.status(400).json({ success: false, error: 'Heartbeat validation failed', details: validation.errors });
    }
    await cycloneStore.recordHeartbeat(validation.data);
    invalidateCache();
    res.status(200).json({ success: true, timestamp: new Date().toISOString() });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
