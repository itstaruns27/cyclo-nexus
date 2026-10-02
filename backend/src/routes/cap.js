/**
 * CAP Routes — Common Alerting Protocol 1.2 output
 * ════════════════════════════════════════════════
 *   GET /api/v1/alerts/cap.atom        Atom index of current CAP alerts (official systems only)
 *   GET /api/v1/alerts/:id/cap.xml     one CAP alert (en-IN + hi-IN info blocks); 404 for watch areas
 * Sender id comes from CAP_SENDER (default "cyclo-nexus"); the <web> link from PUBLIC_SITE_URL.
 */

const express = require('express');
const router = express.Router();
const cycloneStore = require('../services/cyclone_store');
const { buildCapAlert, buildCapFeed } = require('../services/cap');

const SENDER = process.env.CAP_SENDER || 'cyclo-nexus';
const SITE = process.env.PUBLIC_SITE_URL || '';

function base(req) {
  return `${req.protocol}://${req.get('host')}${req.baseUrl}`;
}

function sendXml(res, type, body) {
  res.set('Content-Type', `${type}; charset=utf-8`);
  res.set('Cache-Control', 'public, max-age=60');
  res.send(body);
}

router.get('/cap.atom', async (req, res, next) => {
  try {
    const rows = await cycloneStore.listActive();
    const b = base(req);
    sendXml(res, 'application/atom+xml', buildCapFeed(rows, {
      selfUrl: `${b}/cap.atom`,
      alertUrl: id => `${b}/${encodeURIComponent(id)}/cap.xml`,
    }));
  } catch (err) {
    next(err);
  }
});

router.get('/:id/cap.xml', async (req, res, next) => {
  try {
    const cyclone = await cycloneStore.getById(req.params.id);
    const body = cyclone && buildCapAlert(cyclone, { sender: SENDER, web: SITE ? `${SITE.replace(/\/$/, '')}/alerts` : '' });
    if (!body) {
      return res.status(404).json({ success: false, error: 'No CAP alert: system not found or not an official warning' });
    }
    sendXml(res, 'application/cap+xml', body);
  } catch (err) {
    next(err);
  }
});

module.exports = router;
