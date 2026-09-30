/**
 * Formatters — Wind speed, pressure, coordinate formatting utilities
 * Owner: Agent ECHO | STUB
 */

export function formatWindSpeed(kmh) {
  return `${Math.round(kmh)} km/h`;
}

export function formatPressure(hpa) {
  return `${Math.round(hpa)} hPa`;
}

export function formatCoordinate(lat, lon) {
  const latDir = lat >= 0 ? 'N' : 'S';
  const lonDir = lon >= 0 ? 'E' : 'W';
  return `${Math.abs(lat).toFixed(2)}°${latDir}, ${Math.abs(lon).toFixed(2)}°${lonDir}`;
}

export function formatConfidence(value) {
  return `${(value * 100).toFixed(1)}%`;
}
