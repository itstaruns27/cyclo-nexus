/**
 * Database Migration Runner
 * ═════════════════════════
 * Owner: Agent DELTA | Task 15
 *
 * Runs SQL migration files in order. Tracks applied migrations
 * in a `_migrations` table (lightweight alternative to EF Core).
 *
 * Usage: node src/db/migrate.js
 */

require('dotenv').config({ path: require('path').join(__dirname, '..', '..', '.env') });

const fs = require('fs');
const path = require('path');
const { pool } = require('./connection');

const ADD_COLUMN_RE = /^ALTER\s+TABLE\s+`?(\w+)`?\s+ADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\s+`?(\w+)`?\s+/i;

/** Split a migration file into statements (no semicolons inside string literals in our migrations). */
function splitStatements(sql) {
  return sql
    .split('\n')
    .filter(line => !line.trim().startsWith('--'))
    .join('\n')
    .split(/;\s*(?:\r?\n|$)/)
    .map(s => s.trim())
    .filter(Boolean);
}

/**
 * MariaDB supports `ADD COLUMN IF NOT EXISTS`; MySQL 8 does not. On MySQL, check
 * information_schema and run the plain `ADD COLUMN` only when the column is missing.
 */
async function runStatement(connection, stmt, isMariaDB) {
  const m = stmt.match(ADD_COLUMN_RE);
  if (!m || isMariaDB) return connection.query(stmt);
  const [rows] = await connection.query(
    `SELECT 1 FROM information_schema.COLUMNS
      WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? AND COLUMN_NAME = ?`,
    [m[1], m[2]]
  );
  if (rows.length) return null;
  return connection.query(stmt.replace(/\s+IF\s+NOT\s+EXISTS/i, ''));
}

const MIGRATIONS_DIR = path.join(__dirname, 'migrations');

async function ensureMigrationsTable(connection) {
  await connection.execute(`
    CREATE TABLE IF NOT EXISTS _migrations (
      id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
      filename VARCHAR(255) NOT NULL UNIQUE,
      applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
  `);
}

async function getAppliedMigrations(connection) {
  const [rows] = await connection.execute(
    'SELECT filename FROM _migrations ORDER BY id'
  );
  return new Set(rows.map(r => r.filename));
}

async function runMigrations() {
  const connection = await pool.getConnection();

  try {
    await ensureMigrationsTable(connection);
    const applied = await getAppliedMigrations(connection);
    const [[{ v }]] = await connection.query('SELECT VERSION() AS v');
    const isMariaDB = /mariadb/i.test(v);

    // Get migration files sorted alphabetically
    const files = fs.readdirSync(MIGRATIONS_DIR)
      .filter(f => f.endsWith('.sql'))
      .sort();

    let count = 0;
    for (const file of files) {
      if (applied.has(file)) {
        console.log(`[SKIP] ${file} (already applied)`);
        continue;
      }

      const sql = fs.readFileSync(path.join(MIGRATIONS_DIR, file), 'utf-8');
      console.log(`[RUN]  ${file}`);

      // Execute each statement of the migration in order
      for (const stmt of splitStatements(sql)) {
        await runStatement(connection, stmt, isMariaDB);
      }

      // Record migration
      await connection.execute(
        'INSERT INTO _migrations (filename) VALUES (?)',
        [file]
      );

      count++;
      console.log(`[DONE] ${file}`);
    }

    console.log(`\n✓ ${count} migration(s) applied. ${applied.size + count} total.`);
  } catch (err) {
    console.error('[MIGRATION ERROR]', err.message);
    process.exit(1);
  } finally {
    connection.release();
    await pool.end();
  }
}

runMigrations();
