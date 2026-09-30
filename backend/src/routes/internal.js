/**
 * Internal Routes — cron-triggered jobs
 * ═════════════════════════════════════
 * Master plan v4, Task 2.4 (v3 Micro-Task 2.3)
 *   POST /api/v1/internal/poll-telemetry  (Authorization: Bearer <CRON_SECRET>)
 * Lets an external free cron (cron-job.org / GitHub Actions) run the official-feed
 * worker, which also wakes a sleeping Hostinger Passenger process.
 */

const crypto = require('crypto');
const express = require('express');
const router = express.Router();
const config = require('../config/env');
const { pollOfficialFeeds } = require('../workers/ingest_worker');

function requireCronSecret(req, res, next) {
  const secret = config.cronSecret;
  if (!secret || secret.length < 32) {
    return res.status(503).json({ success: false, error: 'CRON_SECRET not configured' });
  }
  const header = req.headers.authorization || '';
  const token = header.startsWith('Bearer ') ? header.slice(7) : '';
  const a = crypto.createHash('sha256').update(token).digest();
  const b = crypto.createHash('sha256').update(secret).digest();
  if (!crypto.timingSafeEqual(a, b)) {
    return res.status(401).json({ success: false, error: 'Unauthorized' });
  }
  next();
}

let running = null;

router.post('/poll-telemetry', requireCronSecret, async (_req, res, next) => {
  try {
    // Coalesce overlapping triggers into a single poll
    running = running || pollOfficialFeeds().finally(() => { running = null; });
    const result = await running;
    res.status(result.status === 'error' ? 502 : 200).json({ success: result.status !== 'error', ...result });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
