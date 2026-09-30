/**
 * Backend API client.
 * API base: VITE_API_BASE_URL (e.g. https://api.example.in) + /api/v1, or same-origin /api/v1
 * (Vite dev proxy / reverse proxy). Only real backend data is ever returned — callers get
 * [] / null when there is nothing, and an exception when the API is unreachable.
 */

const baseUrl = import.meta.env.VITE_API_BASE_URL;
export const API_BASE = baseUrl ? baseUrl.replace(/\/$/, '') + '/api/v1' : '/api/v1';

async function getJson(path, { allow404 = false } = {}) {
  const res = await fetch(`${API_BASE}${path}`);
  if (allow404 && res.status === 404) return null;
  // 503 still carries a JSON body (health / wind grid not ready) that callers interpret
  if (!res.ok && res.status !== 503) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export const api = {
  /** @returns {Promise<import('../types/cyclone').ActiveSystem[]>} */
  async getActiveCyclones() {
    const body = await getJson('/cyclones');
    return Array.isArray(body.data) ? body.data : [];
  },

  async getCycloneForecast(cycloneId) {
    const body = await getJson(`/cyclones/${encodeURIComponent(cycloneId)}/forecast`, { allow404: true });
    return body?.data && Array.isArray(body.data.features) ? body.data : null;
  },

  async getAdvisory(cycloneId, lang) {
    const body = await getJson(`/cyclones/${encodeURIComponent(cycloneId)}/advisory?lang=${encodeURIComponent(lang)}`,
      { allow404: true });
    return body?.data || null;
  },

  /** Health includes per-component freshness; returned even when the API reports 503. */
  async getHealth() {
    return getJson('/health');
  },

  async getWindGrid() {
    const body = await getJson('/weather/wind-grid');
    return body?.success ? body.data : null;
  },

  async getSeasons() {
    return (await getJson('/historical/seasons')).data || [];
  },

  async getStorms(season) {
    return (await getJson(`/historical/storms?season=${encodeURIComponent(season)}`)).data || [];
  },

  /** Impact (services/impact.js on the backend): exposure, recorded losses, local history, climatology. */
  async getCycloneImpact(id) {
    return (await getJson(`/impact/cyclone/${encodeURIComponent(id)}`, { allow404: true }))?.data || null;
  },
  async getStormImpact(sid) {
    return (await getJson(`/impact/storm/${encodeURIComponent(sid)}`, { allow404: true }))?.data || null;
  },
  async getMajorImpacts() {
    return (await getJson('/impact/major')).data;
  },
  async getNear(lat, lon, radius = 150) {
    return (await getJson(`/impact/near?lat=${lat.toFixed(3)}&lon=${lon.toFixed(3)}&radius=${radius}`)).data;
  },
  /** Nearest named town to a point (GeoNames): { name, country, distance_km, direction } or null. */
  async getPlace(lat, lon) {
    return (await getJson(`/weather/place?lat=${lat.toFixed(3)}&lon=${lon.toFixed(3)}`)).data;
  },
  async getClimatology() {
    return (await getJson('/impact/climatology')).data;
  },

  async getStorm(sid) {
    return (await getJson(`/historical/storms/${encodeURIComponent(sid)}`, { allow404: true }))?.data || null;
  },
};
