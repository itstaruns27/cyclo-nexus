/**
 * MySQL Connection Pool
 * ═════════════════════
 * Owner: Agent DELTA
 */

const mysql = require('mysql2/promise');
const config = require('../config/env');

const pool = mysql.createPool({
  host: config.db.host,
  port: config.db.port,
  user: config.db.user,
  password: config.db.password,
  database: config.db.database,
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0,
  charset: 'utf8mb4',
  // All DATETIME columns hold UTC; without this mysql2 converts JS Dates using the host's local zone
  timezone: 'Z',
});

module.exports = { pool };
