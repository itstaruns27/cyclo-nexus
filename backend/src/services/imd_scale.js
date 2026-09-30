/**
 * IMD cyclonic-disturbance scale (3-minute sustained winds, km/h).
 * Mirrors schemas/imd_scale.py. Below 31 km/h is a low-pressure area; the DB enum
 * starts at D, so weaker systems are reported as D.
 */
function getIMDCategory(windKmh) {
  if (windKmh >= 222) return 'SuCS';
  if (windKmh >= 167) return 'ESCS';
  if (windKmh >= 118) return 'VSCS';
  if (windKmh >= 89) return 'SCS';
  if (windKmh >= 62) return 'CS';
  if (windKmh >= 50) return 'DD';
  return 'D';
}

module.exports = { getIMDCategory };
