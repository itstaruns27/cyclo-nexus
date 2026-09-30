/**
 * Wind Grid Cache (master plan v4, Task 5.3 / v3 Micro-Task 4.2)
 * ═════════════════════════════════════════════════════════════
 * Fetches current 10 m wind over the North Indian Ocean map view (20–130°E, 20°S–40°N) from
 * Open-Meteo (free, no key) on a 3° grid,
 * converts to u/v components, and caches it in memory + on disk. Refreshed every 3 hours
 * by the scheduler, so browsers never call Open-Meteo for the particle layer.
 * 3° keeps usage ≈ 777 locations × 8/day, inside Open-Meteo's free daily limit (10k).
 * The box is wider than the NIO analysis domain so the particle layer fills a wide map.
 */

const fs = require('fs');
const path = require('path');

const BBOX = { minLat: -20, maxLat: 40, minLon: 20, maxLon: 130 };
const STEP = 3;
const CHUNK = 150;
const CACHE_FILE = path.join(__dirname, '..', '..', 'cache', 'wind_grid.json');
const REFRESH_MS = 3 * 3600e3;
const CHUNK_PAUSE_MS = 20000;
const sleep = ms => new Promise(r => setTimeout(r, ms));

let grid = null;

function loadFromDisk() {
  try {
    grid = JSON.parse(fs.readFileSync(CACHE_FILE, 'utf8'));
  } catch {
    grid = null;
  }
}

async function fetchChunk(points) {
  const params = new URLSearchParams({
    latitude: points.map(p => p.lat).join(','),
    longitude: points.map(p => p.lon).join(','),
    current: 'wind_speed_10m,wind_direction_10m',
    wind_speed_unit: 'ms',
  });
  const res = await fetch(`https://api.open-meteo.com/v1/forecast?${params}`, {
    signal: AbortSignal.timeout(60000),
  });
  if (!res.ok) throw new Error(`Open-Meteo HTTP ${res.status}`);
  const body = await res.json();
  return Array.isArray(body) ? body : [body];
}

async function refreshWindGrid() {
  const lats = [];
  for (let lat = BBOX.maxLat; lat >= BBOX.minLat; lat -= STEP) lats.push(lat);
  const lons = [];
  for (let lon = BBOX.minLon; lon <= BBOX.maxLon; lon += STEP) lons.push(lon);
  const points = lats.flatMap(lat => lons.map(lon => ({ lat, lon })));

  const results = [];
  // Open-Meteo's free tier counts every location and allows ~600 per minute, so pace the chunks
  // (150 locations every 20 s ≈ 450/min) and back off once if throttled anyway.
  for (let i = 0; i < points.length; i += CHUNK) {
    if (i) await sleep(CHUNK_PAUSE_MS);
    const chunk = points.slice(i, i + CHUNK);
    try {
      results.push(...await fetchChunk(chunk));
    } catch (err) {
      if (!/HTTP 429/.test(err.message)) throw err;
      await sleep(65000);
      results.push(...await fetchChunk(chunk));
    }
  }
  if (results.length !== points.length) throw new Error(`expected ${points.length} points, got ${results.length}`);

  const u = []; const v = [];
  let observed = null;
  for (const r of results) {
    const speed = r.current?.wind_speed_10m;
    const dir = r.current?.wind_direction_10m;
    if (speed == null || dir == null) { u.push(0); v.push(0); continue; }
    // Meteorological direction = where wind comes FROM
    const rad = (dir * Math.PI) / 180;
    u.push(+(-speed * Math.sin(rad)).toFixed(2));
    v.push(+(-speed * Math.cos(rad)).toFixed(2));
    observed = observed || r.current.time;
  }

  grid = {
    generated_at: new Date().toISOString(),
    valid_time: observed ? `${observed}Z` : null,
    source: 'Open-Meteo (best-match NWP), 10 m wind',
    bbox: BBOX, step_deg: STEP, nx: lons.length, ny: lats.length, unit: 'm/s',
    // Row-major, row 0 = northernmost latitude
    u, v,
  };
  fs.mkdirSync(path.dirname(CACHE_FILE), { recursive: true });
  fs.writeFileSync(CACHE_FILE, JSON.stringify(grid));
  console.log(`[wind-grid] refreshed ${points.length} points (valid ${grid.valid_time})`);
  return grid;
}

function getWindGrid() {
  if (!grid) loadFromDisk();
  return grid;
}

let timer = null;
function startWindScheduler() {
  if (timer) return;
  loadFromDisk();
  const sameBox = grid && grid.step_deg === STEP && JSON.stringify(grid.bbox) === JSON.stringify(BBOX);
  const stale = !sameBox || Date.now() - new Date(grid.generated_at).getTime() > REFRESH_MS;
  const run = () => refreshWindGrid().catch(err => console.error('[wind-grid] refresh failed:', err.message));
  if (stale) run();
  timer = setInterval(run, REFRESH_MS);
  timer.unref();
}

module.exports = { getWindGrid, refreshWindGrid, startWindScheduler };
