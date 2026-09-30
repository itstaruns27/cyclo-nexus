/**
 * Cyclone Store — MySQL CRUD operations
 * ═════════════════════════════════════
 * Owner: Agent DELTA
 *
 * Two kinds of writers:
 *   - Official feed worker (source OFFICIAL_*) — see workers/ingest_worker.js
 *   - Satellite pipeline webhook (source AI_SATELLITE) — handled here. An AI fix linked to an
 *     official system only fills the ai_fix_* columns; it never overwrites official data.
 */

const { pool } = require('../db/connection');
const { getIMDCategory } = require('./imd_scale');

const ACTIVE_STATUSES = ['active', 'watch'];

class CycloneStore {
  async upsertFromWebhook(payload) {
    const conn = await pool.getConnection();
    try {
      await conn.beginTransaction();

      const meta = payload.metadata;
      const source = meta.source || 'AI_SATELLITE';
      const generatedAt = new Date(meta.generated_at);

      const currentEye = payload.features.find(f => f.properties.feature_type === 'current_eye');
      if (!currentEye) throw Object.assign(new Error('Missing current_eye feature'), { status: 400 });

      const [lon, lat] = currentEye.geometry.coordinates;
      const p = currentEye.properties;
      const obsTime = p.timestamp ? new Date(p.timestamp) : generatedAt;
      const confidence = p.detection_confidence ?? 0;
      const aiFix = [lat, lon, obsTime, confidence, p.min_cloud_top_k ?? null, p.max_rain_mmhr ?? null, p.method || null];

      let cycloneId = meta.cyclone_id;
      let linked = false;
      if (meta.link_cyclone_id) {
        const [rows] = await conn.query('SELECT cyclone_id FROM cyclones WHERE cyclone_id = ?', [meta.link_cyclone_id]);
        if (rows.length) {
          cycloneId = rows[0].cyclone_id;
          linked = true;
        }
      }

      if (linked) {
        // Attach the satellite analysis to the existing (official) system
        await conn.query(
          `UPDATE cyclones SET ai_fix_lat = ?, ai_fix_lon = ?, ai_fix_time = ?, ai_fix_confidence = ?,
             ai_min_cloud_top_k = ?, ai_max_rain_mmhr = ?, ai_method = ? WHERE cyclone_id = ?`,
          [...aiFix, cycloneId]
        );
      } else {
        const windKnots = p.sustained_wind_knots ?? 0;
        const windKmh = windKnots * 1.852;
        const obb = p.obb_params || { x_center: 0, y_center: 0, width: 0, height: 0, theta: 0 };
        await conn.query(
          `INSERT INTO cyclones (
             cyclone_id, cyclone_name, basin, current_lat, current_lon, sustained_wind_kmh, sustained_wind_knots,
             central_pressure_hpa, imd_category, obb_x_center, obb_y_center, obb_width, obb_height, obb_theta,
             detection_confidence, observation_time, inference_generated_at, source, status, summary,
             ai_fix_lat, ai_fix_lon, ai_fix_time, ai_fix_confidence, ai_min_cloud_top_k, ai_max_rain_mmhr, ai_method)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON DUPLICATE KEY UPDATE
             current_lat=VALUES(current_lat), current_lon=VALUES(current_lon),
             sustained_wind_kmh=VALUES(sustained_wind_kmh), sustained_wind_knots=VALUES(sustained_wind_knots),
             central_pressure_hpa=VALUES(central_pressure_hpa), imd_category=VALUES(imd_category),
             obb_x_center=VALUES(obb_x_center), obb_y_center=VALUES(obb_y_center), obb_width=VALUES(obb_width),
             obb_height=VALUES(obb_height), obb_theta=VALUES(obb_theta), detection_confidence=VALUES(detection_confidence),
             observation_time=VALUES(observation_time), inference_generated_at=VALUES(inference_generated_at),
             status=VALUES(status), summary=VALUES(summary),
             ai_fix_lat=VALUES(ai_fix_lat), ai_fix_lon=VALUES(ai_fix_lon), ai_fix_time=VALUES(ai_fix_time),
             ai_fix_confidence=VALUES(ai_fix_confidence), ai_min_cloud_top_k=VALUES(ai_min_cloud_top_k),
             ai_max_rain_mmhr=VALUES(ai_max_rain_mmhr), ai_method=VALUES(ai_method)`,
          [
            cycloneId, meta.cyclone_name || null, meta.basin, lat, lon, windKmh, windKnots,
            p.central_pressure_hpa ?? 1008, getIMDCategory(windKmh),
            obb.x_center, obb.y_center, obb.width, obb.height, obb.theta,
            confidence, obsTime, generatedAt, source, meta.status || 'watch', p.summary || null,
            ...aiFix,
          ]
        );
      }

      // Forecast nodes from this source replace only this source's previous forecast
      const forecasts = payload.features.filter(f => f.properties.feature_type === 'forecast_track'
        && f.geometry.type === 'Point');
      if (forecasts.length) {
        await conn.query('DELETE FROM forecast_tracks WHERE cyclone_id = ? AND source = ?', [cycloneId, source]);
        for (const f of forecasts) {
          const [fLon, fLat] = f.geometry.coordinates;
          const fWind = (f.properties.sustained_wind_knots ?? 0) * 1.852;
          await conn.query(
            `INSERT INTO forecast_tracks (cyclone_id, forecast_hour, predicted_lat, predicted_lon,
               predicted_wind_kmh, predicted_pressure_hpa, predicted_imd_category, confidence, generated_at, source)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
            [cycloneId, f.properties.forecast_hour, fLat, fLon, fWind, f.properties.central_pressure_hpa ?? 1008,
              getIMDCategory(fWind), confidence, generatedAt, source]
          );
        }
      }

      await conn.commit();
      return { cycloneId, linked };
    } catch (err) {
      await conn.rollback();
      throw err;
    } finally {
      conn.release();
    }
  }

  async getById(cycloneId) {
    const [cyclones] = await pool.query('SELECT * FROM cyclones WHERE cyclone_id = ?', [cycloneId]);
    if (!cyclones.length) return null;

    const [forecasts] = await pool.query(
      'SELECT * FROM forecast_tracks WHERE cyclone_id = ? ORDER BY source ASC, forecast_hour ASC',
      [cycloneId]
    );
    const history = await this.getHistory(cycloneId);
    return { ...cyclones[0], forecasts, history };
  }

  async getHistory(cycloneId) {
    const [history] = await pool.query(
      'SELECT timestamp, latitude, longitude, sustained_wind_kmh, central_pressure_hpa, imd_category FROM historical_tracks WHERE cyclone_id = ? ORDER BY timestamp ASC',
      [cycloneId]
    );
    return history;
  }

  async listActive() {
    // Official systems first, then satellite watch areas; only rows observed in the last 24 h
    const [rows] = await pool.query(
      `SELECT * FROM cyclones
        WHERE status IN (?) AND observation_time >= DATE_SUB(UTC_TIMESTAMP(), INTERVAL 24 HOUR)
        ORDER BY (source LIKE 'OFFICIAL_%') DESC, (status = 'active') DESC, sustained_wind_kmh DESC`,
      [ACTIVE_STATUSES]
    );
    return rows;
  }

  async getPipelineStatus() {
    const [rows] = await pool.query('SELECT * FROM pipeline_status ORDER BY component');
    return rows;
  }

  async recordHeartbeat({ component, status, message, last_data_time, details }) {
    await pool.query(
      `INSERT INTO pipeline_status (component, last_run_at, last_success_at, last_data_time, status, message, details)
       VALUES (?, UTC_TIMESTAMP(), IF(? = 'ok', UTC_TIMESTAMP(), NULL), ?, ?, ?, ?)
       ON DUPLICATE KEY UPDATE last_run_at=VALUES(last_run_at),
         last_success_at=IF(VALUES(status) = 'ok', VALUES(last_run_at), last_success_at),
         last_data_time=COALESCE(VALUES(last_data_time), last_data_time),
         status=VALUES(status), message=VALUES(message), details=VALUES(details)`,
      [component, status, last_data_time ? new Date(last_data_time) : null, status,
        message ? String(message).slice(0, 1000) : null, JSON.stringify(details || {})]
    );
  }
}

module.exports = new CycloneStore();
