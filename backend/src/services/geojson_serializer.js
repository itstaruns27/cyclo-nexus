/**
 * GeoJSON Serializer — Builds RFC 7946 FeatureCollections
 * ═══════════════════════════════════════════════════════
 * Owner: Agent DELTA
 *
 * Feature `properties.type` values:
 *   current_position  — latest position (official where available)
 *   history_track     — LineString of observed positions
 *   forecast_node     — forecast point, with `source` (OFFICIAL_* | AI_SATELLITE)
 *   forecast_track    — LineString per forecast source
 *   ai_fix            — latest satellite (INSAT + IMERG) analysis position
 *   forecast_cone     — IMD cone of uncertainty around the official forecast (services/forecast_cone.js)
 */

const { coneFeature } = require('./forecast_cone');

const lonLat = (lon, lat) => [Number(lon), Number(lat)];

class GeoJSONSerializer {
  buildForecast(cycloneData) {
    if (!cycloneData) return null;

    const c = cycloneData;
    const features = [];

    features.push({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: lonLat(c.current_lon, c.current_lat) },
      properties: {
        type: 'current_position',
        cyclone_id: c.cyclone_id,
        name: c.cyclone_name,
        source: c.source,
        status: c.status,
        wind_kmh: c.sustained_wind_kmh,
        pressure: c.central_pressure_hpa,
        category: c.imd_category,
        timestamp: c.observation_time,
      },
    });

    const history = (c.history || []).map(h => lonLat(h.longitude, h.latitude));
    if (history.length >= 2) {
      features.push({
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: history },
        properties: { type: 'history_track', cyclone_id: c.cyclone_id },
      });
    }

    const cone = coneFeature(c);
    if (cone) features.push(cone);

    const bySource = new Map();
    for (const f of c.forecasts || []) {
      const src = f.source || 'AI_SATELLITE';
      if (!bySource.has(src)) bySource.set(src, []);
      bySource.get(src).push(f);
    }
    for (const [source, list] of bySource) {
      const coordinates = [lonLat(c.current_lon, c.current_lat)];
      for (const f of list) {
        coordinates.push(lonLat(f.predicted_lon, f.predicted_lat));
        features.push({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: lonLat(f.predicted_lon, f.predicted_lat) },
          properties: {
            type: 'forecast_node',
            source,
            hour: f.forecast_hour,
            wind_kmh: f.predicted_wind_kmh,
            pressure: f.predicted_pressure_hpa,
            category: f.predicted_imd_category,
          },
        });
      }
      features.push({
        type: 'Feature',
        geometry: { type: 'LineString', coordinates },
        properties: { type: 'forecast_track', source, cyclone_id: c.cyclone_id },
      });
    }

    if (c.ai_fix_lat != null && c.ai_fix_lon != null) {
      features.push({
        type: 'Feature',
        geometry: { type: 'Point', coordinates: lonLat(c.ai_fix_lon, c.ai_fix_lat) },
        properties: {
          type: 'ai_fix',
          cyclone_id: c.cyclone_id,
          timestamp: c.ai_fix_time,
          confidence: c.ai_fix_confidence,
          min_cloud_top_k: c.ai_min_cloud_top_k,
          max_rain_mmhr: c.ai_max_rain_mmhr,
          method: c.ai_method,
        },
      });
    }

    return { type: 'FeatureCollection', features };
  }
}

module.exports = new GeoJSONSerializer();
