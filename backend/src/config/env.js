/**
 * Environment configuration loader.
 * Owner: Agent DELTA
 */

const config = {
  port: parseInt(process.env.PORT || '3001', 10),
  nodeEnv: process.env.NODE_ENV || 'development',
  db: {
    host: process.env.DB_HOST || 'localhost',
    port: parseInt(process.env.DB_PORT || '3306', 10),
    user: process.env.DB_USER || 'root',
    password: process.env.DB_PASSWORD || '',
    database: process.env.DB_NAME || 'cyclonexus_db',
  },
  webhookSecret: process.env.WEBHOOK_SECRET || '',
  // Comma-separated list of allowed browser origins, e.g. "https://cyclonexus.in,https://www.cyclonexus.in"
  corsOrigins: (process.env.CORS_ORIGIN || 'http://localhost:5173')
    .split(',').map(s => s.trim().replace(/\/$/, '')).filter(Boolean),
  cacheTtl: parseInt(process.env.CACHE_TTL || '30', 10),
  cronSecret: process.env.CRON_SECRET || '',
  // In-process official-feed polling interval (minutes); 0 disables (use the cron route instead)
  officialFeedIntervalMin: parseFloat(process.env.OFFICIAL_FEED_INTERVAL_MIN || '30'),
};

module.exports = config;
