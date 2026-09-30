/**
 * In-memory TTL cache middleware.
 * Owner: Agent DELTA
 *
 * Caches GET responses for 30 seconds.
 * Cache is invalidated when new webhook POST is received.
 */

const NodeCache = require('node-cache');
const config = require('../config/env');

const cache = new NodeCache({
  stdTTL: config.cacheTtl,
  checkperiod: config.cacheTtl * 0.5,
  useClones: false,
});

/**
 * Cache middleware for GET endpoints.
 */
function cacheMiddleware(req, res, next) {
  if (req.method !== 'GET') return next();

  const key = req.originalUrl;
  const cached = cache.get(key);

  if (cached) {
    return res.json({
      ...cached,
      cached: true,
    });
  }

  // Override res.json to cache the response
  const originalJson = res.json.bind(res);
  res.json = (body) => {
    cache.set(key, { ...body, cached: false });
    return originalJson(body);
  };

  next();
}

/**
 * Invalidate all cached entries (called after webhook POST).
 */
function invalidateCache() {
  cache.flushAll();
}

module.exports = { cacheMiddleware, invalidateCache, cache };
