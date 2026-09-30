/**
 * CYCLO-NEXUS Backend — Express.js Server
 * ════════════════════════════════════════
 * Owner: Agent DELTA (Tasks 14–17)
 * Skill: [SKILL:BACKEND_DATABASE]
 *
 * This server MUST NEVER run heavy PyTorch, rasterio, or HDF5 processing.
 * It serves solely as a high-speed data clearinghouse.
 */

require('dotenv').config({ path: require('path').join(__dirname, '..', '.env') });

const express = require('express');
const config = require('./config/env');
const { startScheduler } = require('./workers/ingest_worker');
const helmet = require('helmet');
const { corsMiddleware } = require('./config/cors');
const { compressionMiddleware } = require('./middleware/compression');
const { rateLimiter } = require('./middleware/rate_limiter');
const zlib = require('zlib');

// Route imports
const webhookRoutes = require('./routes/webhook');
const cycloneRoutes = require('./routes/cyclones');
const advisoryRoutes = require('./routes/advisory');
const healthRoutes = require('./routes/health');
const internalRoutes = require('./routes/internal');
const weatherRoutes = require('./routes/weather');
const historicalRoutes = require('./routes/historical');
const impactRoutes = require('./routes/impact');
const { startWindScheduler } = require('./workers/wind_grid');

const app = express();
const PORT = process.env.PORT || 3001;

// ── Global Middleware ──────────────────────────────────────────────

// Behind Hostinger/Passenger or another reverse proxy, use the real client IP for rate limiting
if (process.env.TRUST_PROXY) app.set('trust proxy', parseInt(process.env.TRUST_PROXY, 10) || 1);

// Security headers
app.use(helmet());

// CORS
app.use(corsMiddleware);

// Compression (gzip/brotli for responses)
app.use(compressionMiddleware);

// Rate limiting
app.use('/api/', rateLimiter);

// Zip Bomb Guard & Single-Pass Decompression
app.use((req, res, next) => {
  if (['POST', 'PUT', 'PATCH'].includes(req.method)) {
    let rawChunks = [];
    let length = 0;
    let rejected = false;
    const MAX_WIRE = 2 * 1024 * 1024; // 2MB wire limit

    // Respond 413 first and let the socket close afterwards; destroying the
    // request before responding resets the connection and the client never sees 413.
    const rejectTooLarge = () => {
      rejected = true;
      rawChunks = [];
      res.set('Connection', 'close');
      res.status(413).json({ error: 'Payload Too Large' });
    };

    // Fast path: honest clients declare their size up front
    if (Number(req.headers['content-length']) > MAX_WIRE) {
      rejectTooLarge();
      req.resume(); // drain without buffering
      return;
    }

    req.on('data', chunk => {
      if (rejected) return; // drain remaining chunks without buffering
      length += chunk.length;
      if (length > MAX_WIRE) return rejectTooLarge();
      rawChunks.push(chunk);
    });

    req.on('end', () => {
      if (rejected) return;
      const rawBuffer = Buffer.concat(rawChunks);
      
      const processBuffer = (err, decompressedBuffer) => {
        if (err) return res.status(400).json({ error: 'Decompression failed or payload too large' });
        
        req.rawBody = decompressedBuffer;
        if (req.headers['content-type'] && req.headers['content-type'].includes('application/json')) {
          try {
            req.body = JSON.parse(decompressedBuffer.toString('utf-8'));
          } catch (e) {
            return res.status(400).json({ error: 'Invalid JSON' });
          }
        } else {
            req.body = decompressedBuffer;
        }
        next();
      };

      if (req.headers['content-encoding'] === 'gzip') {
        zlib.gunzip(rawBuffer, { maxOutputLength: 10 * 1024 * 1024 }, processBuffer);
      } else {
        processBuffer(null, rawBuffer);
      }
    });
  } else {
    next();
  }
});

// ── Routes ────────────────────────────────────────────────────────

app.use('/api/v1/webhook', webhookRoutes);
app.use('/api/v1/cyclones', cycloneRoutes);
app.use('/api/v1/cyclones', advisoryRoutes);
app.use('/api/v1/health', healthRoutes);
app.use('/api/v1/internal', internalRoutes);
app.use('/api/v1/weather', weatherRoutes);
app.use('/api/v1/historical', historicalRoutes);
app.use('/api/v1/impact', impactRoutes);

// Unknown API paths → JSON 404 (instead of Express's HTML page)
app.use('/api/', (_req, res) => res.status(404).json({ success: false, error: 'Not found' }));

// ── Error Handler ─────────────────────────────────────────────────

app.use((err, _req, res, _next) => {
  console.error('[ERROR]', err.message);
  res.status(err.status || 500).json({
    success: false,
    error: process.env.NODE_ENV === 'production' ? 'Internal Server Error' : err.message,
    timestamp: new Date().toISOString(),
  });
});

// ── Start Server ──────────────────────────────────────────────────

// Only listen when run directly (tests import the app without binding a port)
if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`[Cyclo-Nexus] API Gateway running on port ${PORT}`);
    console.log(`[Cyclo-Nexus] Environment: ${process.env.NODE_ENV || 'development'}`);
    startScheduler(config.officialFeedIntervalMin);
    if (process.env.WIND_GRID_ENABLED !== 'false') startWindScheduler();
  });
}

module.exports = app;
