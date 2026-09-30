/**
 * Rate limiting middleware.
 * Owner: Agent DELTA
 */

const rateLimit = require('express-rate-limit');

const rateLimiter = rateLimit({
  windowMs: 60 * 1000,   // 1 minute window
  max: 120,              // 120 requests per minute
  standardHeaders: true,
  legacyHeaders: false,
  message: {
    success: false,
    error: 'Rate limit exceeded. Please try again later.',
  },
});

module.exports = { rateLimiter };
