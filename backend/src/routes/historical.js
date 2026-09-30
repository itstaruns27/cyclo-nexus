/**
 * Historical Routes — IBTrACS North Indian Ocean best tracks
 *   GET /api/v1/historical/seasons           — seasons with storm counts
 *   GET /api/v1/historical/storms?season=Y   — storm summaries for a season
 *   GET /api/v1/historical/storms/:sid       — full track of one storm
 */

const express = require('express');
const router = express.Router();
const { pool } = require('../db/connection');
const { cacheMiddleware } = require('../middleware/cache');

const GRADE_ORDER = ['D', 'DD', 'CS', 'SCS', 'VSCS', 'ESCS', 'SuCS'];

router.get('/seasons', cacheMiddleware, async (_req, res, next) => {
  try {
    const [rows] = await pool.query(
      'SELECT season, COUNT(DISTINCT sid) AS storms FROM besttrack_points GROUP BY season ORDER BY season DESC'
    );
    res.json({ success: true, data: rows, timestamp: new Date().toISOString() });
  } catch (err) {
    next(err);
  }
});

router.get('/storms', cacheMiddleware, async (req, res, next) => {
  try {
    const season = parseInt(req.query.season, 10);
    if (!season) return res.status(400).json({ success: false, error: 'season query parameter required' });
    const [rows] = await pool.query(
      `SELECT sid, MAX(name) AS name, MAX(subbasin) AS subbasin, MIN(iso_time) AS start_time, MAX(iso_time) AS end_time,
              MAX(wind_kt) AS max_wind_kt, MIN(pressure_hpa) AS min_pressure_hpa,
              GROUP_CONCAT(DISTINCT grade) AS grades
         FROM besttrack_points WHERE season = ? GROUP BY sid ORDER BY start_time`,
      [season]
    );
    const data = rows.map(r => {
      const grades = String(r.grades || '').split(',').filter(g => GRADE_ORDER.includes(g));
      const peak = grades.sort((a, b) => GRADE_ORDER.indexOf(b) - GRADE_ORDER.indexOf(a))[0] || null;
      return { ...r, grades: undefined, peak_grade: peak };
    });
    res.json({ success: true, data, timestamp: new Date().toISOString() });
  } catch (err) {
    next(err);
  }
});

router.get('/storms/:sid', cacheMiddleware, async (req, res, next) => {
  try {
    const [rows] = await pool.query(
      `SELECT iso_time, latitude, longitude, grade, wind_kt, pressure_hpa, dist2land_km, name, subbasin, season
         FROM besttrack_points WHERE sid = ? ORDER BY iso_time`,
      [req.params.sid]
    );
    if (!rows.length) return res.status(404).json({ success: false, error: 'Storm not found' });
    res.json({
      success: true,
      data: {
        sid: req.params.sid, name: rows[0].name, season: rows[0].season, subbasin: rows[0].subbasin,
        points: rows.map(({ name, subbasin, season, ...p }) => p),
      },
      timestamp: new Date().toISOString(),
    });
  } catch (err) {
    next(err);
  }
});

module.exports = router;
