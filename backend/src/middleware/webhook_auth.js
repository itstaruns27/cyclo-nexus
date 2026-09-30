/**
 * HMAC-SHA256 Webhook Authentication Middleware
 * ═════════════════════════════════════════════
 * Owner: Agent DELTA
 * Enforces strict crypto-signature validation to reject spoofed telemetry.
 */

const crypto = require('crypto');
const config = require('../config/env');

function verifyWebhookSignature(req, res, next) {
  const signature = req.headers['x-cyclonexus-signature'];
  const timestamp = req.headers['x-cyclonexus-timestamp'];

  if (!signature || !timestamp) {
    return res.status(401).json({ success: false, error: 'Missing auth headers' });
  }

  // Reject requests older than 5 minutes
  if (Math.abs(Date.now() - new Date(timestamp).getTime()) > 300_000) {
    return res.status(401).json({ success: false, error: 'Stale timestamp' });
  }

  const secret = config.webhookSecret || process.env.WEBHOOK_SECRET;
  if (!secret || secret.length < 32 || secret === 'CHANGE_ME_TO_A_LONG_RANDOM_STRING') {
    return res.status(500).json({ success: false, error: 'Misconfigured secret' });
  }

  // Sign "<timestamp>.<body>" so the timestamp cannot be swapped to replay an old body
  const expectedSig = crypto
    .createHmac('sha256', secret)
    .update(`${timestamp}.`)
    .update(req.rawBody)
    .digest('hex');

  try {
    if (!crypto.timingSafeEqual(Buffer.from(signature, 'hex'), Buffer.from(expectedSig, 'hex'))) {
      return res.status(401).json({ success: false, error: 'Invalid signature' });
    }
  } catch (err) {
    return res.status(401).json({ success: false, error: 'Malformed signature' });
  }

  next();
}

module.exports = { verifyWebhookSignature };
