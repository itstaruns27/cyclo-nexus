/**
 * HMAC Signing/Verification Helpers
 * Owner: Agent DELTA
 */

const crypto = require('crypto');

/**
 * Compute HMAC-SHA256 signature.
 * @param {string} secret - Shared secret
 * @param {Buffer|string} data - Data to sign
 * @returns {string} Hex-encoded signature
 */
function computeHmac(secret, data) {
  return crypto.createHmac('sha256', secret).update(data).digest('hex');
}

/**
 * Constant-time HMAC comparison.
 * @param {string} a - First hex signature
 * @param {string} b - Second hex signature
 * @returns {boolean}
 */
function safeCompare(a, b) {
  try {
    const bufA = Buffer.from(a, 'hex');
    const bufB = Buffer.from(b, 'hex');
    if (bufA.length !== bufB.length) return false;
    return crypto.timingSafeEqual(bufA, bufB);
  } catch {
    return false;
  }
}

module.exports = { computeHmac, safeCompare };
