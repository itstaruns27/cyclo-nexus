/**
 * CORS configuration.
 * Owner: Agent DELTA
 *
 * Allows only origins listed in CORS_ORIGIN (comma-separated). Requests without an
 * Origin header (server-to-server: pipeline webhooks, cron) are not affected by CORS.
 */

const cors = require('cors');
const config = require('./env');

const corsMiddleware = cors({
  origin(origin, callback) {
    if (!origin || config.corsOrigins.includes(origin.replace(/\/$/, ''))) return callback(null, true);
    return callback(null, false);
  },
  methods: ['GET', 'POST'],
  allowedHeaders: [
    'Content-Type',
    'Content-Encoding',
    'Authorization',
    'X-CycloNexus-Version',
    'X-CycloNexus-Timestamp',
    'X-CycloNexus-Signature',
  ],
  maxAge: 86400,
});

module.exports = { corsMiddleware };
