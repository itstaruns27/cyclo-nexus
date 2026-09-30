/**
 * Health Check Route — GET /api/v1/health
 * Owner: Agent DELTA
 *
 * Reports API + database health and the freshness of each data component
 * (official_feed, satellite_pipeline). `stale: true` means the component's last
 * successful run is older than its threshold, so the UI can warn users.
 */

const express = require('express');
const router = express.Router();
const cycloneStore = require('../services/cyclone_store');

// Max minutes since last successful run before a component is considered stale
const STALE_AFTER_MIN = {
  official_feed: 90,
  satellite_pipeline: 90,
};

router.get('/', async (_req, res) => {
  const now = Date.now();
  let database = 'ok';
  let components = [];
  try {
    const rows = await cycloneStore.getPipelineStatus();
    // Expected components that have never reported are shown as stale, not silently omitted
    for (const name of Object.keys(STALE_AFTER_MIN)) {
      if (!rows.some(r => r.component === name)) {
        rows.push({ component: name, status: 'error', message: 'No run recorded yet' });
      }
    }
    components = rows.map(c => {
      const lastOk = c.last_success_at ? new Date(c.last_success_at).getTime() : null;
      const limit = STALE_AFTER_MIN[c.component] ?? 120;
      return {
        component: c.component,
        status: c.status,
        message: c.message,
        last_run_at: c.last_run_at,
        last_success_at: c.last_success_at,
        last_data_time: c.last_data_time,
        minutes_since_success: lastOk ? Math.round((now - lastOk) / 60000) : null,
        stale: !lastOk || now - lastOk > limit * 60000,
      };
    });
  } catch (err) {
    database = 'error';
  }

  const degraded = database !== 'ok' || components.some(c => c.stale || c.status !== 'ok');
  res.status(database === 'ok' ? 200 : 503).json({
    success: database === 'ok',
    status: database !== 'ok' ? 'unhealthy' : degraded ? 'degraded' : 'healthy',
    service: 'cyclonexus-api',
    version: '1.1.0',
    database,
    components,
    timestamp: new Date().toISOString(),
  });
});

module.exports = router;
