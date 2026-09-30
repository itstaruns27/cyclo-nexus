/**
 * Import IBTrACS North Indian Ocean best tracks into `besttrack_points`.
 *
 * Usage:
 *   node scripts/import_ibtracs.js [path/to/ibtracs.NI.list.v04r01.csv] [--since 1980]
 * Default path: ../data/static/ibtracs.NI.list.v04r01.csv
 * Idempotent (INSERT IGNORE on (sid, iso_time)); safe to re-run after refreshing the CSV.
 * Grade/wind/pressure prefer the RSMC New Delhi (IMD) values, then WMO.
 */

require('dotenv').config({ path: require('path').join(__dirname, '..', '.env') });

const fs = require('fs');
const path = require('path');
const readline = require('readline');
const { pool } = require('../src/db/connection');

async function main() {
  const args = process.argv.slice(2);
  const sinceIdx = args.indexOf('--since');
  const since = sinceIdx >= 0 ? parseInt(args[sinceIdx + 1], 10) : 1980;
  const file = args.find((a, i) => !a.startsWith('--') && args[i - 1] !== '--since')
    || path.join(__dirname, '..', '..', 'data', 'static', 'ibtracs.NI.list.v04r01.csv');

  const rl = readline.createInterface({ input: fs.createReadStream(file), crlfDelay: Infinity });
  let cols = null;
  let lineNo = 0;
  let batch = [];
  let total = 0;

  const flush = async () => {
    if (!batch.length) return;
    const [res] = await pool.query(
      `INSERT IGNORE INTO besttrack_points
         (sid, season, name, subbasin, iso_time, latitude, longitude, grade, wind_kt, pressure_hpa, dist2land_km)
       VALUES ?`, [batch]);
    total += res.affectedRows;
    batch = [];
  };

  for await (const line of rl) {
    lineNo++;
    if (lineNo === 1) { cols = line.split(','); continue; }
    if (lineNo === 2) continue; // units row
    const f = line.split(',');
    const get = name => f[cols.indexOf(name)]?.trim() ?? '';
    const season = parseInt(get('SEASON'), 10);
    if (!(season >= since)) continue;
    const num = v => (v === '' ? null : parseFloat(v));
    const name = get('NAME');
    batch.push([
      get('SID'), season, name === 'NOT_NAMED' || name === 'UNNAMED' ? null : name, get('SUBBASIN') || null,
      get('ISO_TIME'), num(get('LAT')), num(get('LON')), get('NEWDELHI_GRADE') || null,
      num(get('NEWDELHI_WIND')) ?? num(get('WMO_WIND')), num(get('NEWDELHI_PRES')) ?? num(get('WMO_PRES')),
      num(get('DIST2LAND')),
    ]);
    if (batch.length >= 1000) await flush();
  }
  await flush();
  console.log(`Imported ${total} new best-track points (seasons >= ${since}) from ${file}`);
  await pool.end();
}

main().catch(err => {
  console.error('Import failed:', err.message);
  process.exit(1);
});
