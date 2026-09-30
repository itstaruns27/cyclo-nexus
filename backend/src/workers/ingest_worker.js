/**
 * Official Cyclone Feed Worker
 * ════════════════════════════
 * Master plan v4, Task 2.4 (v3 Micro-Task 2.3)
 *
 * Pulls authoritative tropical-cyclone data for the North Indian Ocean and upserts it into MySQL:
 *   1. JTWC RSS → warnings (.tcw: position, 1-min winds, forecast track) and
 *      Tropical Cyclone Formation Alerts (text: invest position, winds, pressure) → status 'watch'.
 *   2. IBTrACS ACTIVE (NI basin) → systems JTWC does not list (IBTrACS lags by days, so only
 *      rows observed within ACTIVE_WINDOW_H are treated as current).
 * Rows are written with source OFFICIAL_JTWC / OFFICIAL_IBTRACS and never touch AI rows.
 * Pure Node (global fetch) — no heavy dependencies (Hostinger constraint).
 */

const { pool } = require('../db/connection');
const { invalidateCache } = require('../middleware/cache');
const { getIMDCategory } = require('../services/imd_scale');
const cycloneStore = require('../services/cyclone_store');

const JTWC_RSS = 'https://www.metoc.navy.mil/jtwc/rss/jtwc.rss';
const IBTRACS_ACTIVE = 'https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.ACTIVE.list.v04r01.csv';
const USER_AGENT = 'Cyclo-Nexus/1.0 (MoES SIH26070 cyclone monitoring)';

// North Indian Ocean area of responsibility (generous margins around the 0–32N, 50–102E product box)
const NIO = { minLat: -5, maxLat: 35, minLon: 40, maxLon: 102 };
const ACTIVE_WINDOW_H = 12;
const KT_TO_KMH = 1.852;
// JTWC reports 1-minute winds; IMD categories use 3-minute winds (WMO conversion factor ≈ 0.93)
const ONE_MIN_TO_THREE_MIN = 0.93;

function inNio(lat, lon) {
  return lat >= NIO.minLat && lat <= NIO.maxLat && lon >= NIO.minLon && lon <= NIO.maxLon;
}

function basinFor(lon) {
  return lon < 78 ? 'AS' : 'BOB';
}

/** Atkinson–Holliday wind–pressure relation, used only when a bulletin gives no pressure. */
function pressureFromWind(windKt) {
  if (!windKt || windKt <= 0) return 1008;
  return Math.round(1010 - Math.pow(windKt / 6.7, 1 / 0.644));
}

async function fetchText(url, timeoutMs = 60000) {
  const res = await fetch(url, {
    headers: { 'User-Agent': USER_AGENT },
    signal: AbortSignal.timeout(timeoutMs),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status} for ${url}`);
  return res.text();
}

// ── JTWC ─────────────────────────────────────────────────────────

/** "292N" → 29.2, "1363E" → 136.3 (S / W negative). */
function parseLatLonToken(tok) {
  const m = /^(\d+)([NSEW])$/.exec(tok);
  if (!m) return NaN;
  const v = parseInt(m[1], 10) / 10;
  return m[2] === 'S' || m[2] === 'W' ? -v : v;
}

/** Parse a JMV 3.0 (.tcw) warning file. */
function parseTcw(text) {
  const lines = text.split(/\r?\n/);
  const header = lines.find(l => /^\d{10}\s+\w+/.test(l));
  if (!header) throw new Error('TCW header line not found');
  const [dtg, atcfId, ...rest] = header.trim().split(/\s+/);
  const name = rest[0] && !/^\d+$/.test(rest[0]) ? rest[0] : null;
  const obsTime = new Date(Date.UTC(+dtg.slice(0, 4), +dtg.slice(4, 6) - 1, +dtg.slice(6, 8), +dtg.slice(8, 10)));

  const points = [];
  for (const l of lines) {
    const m = /^T(\d{3})\s+(\d+[NS])\s+(\d+[EW])\s+(\d{3})/.exec(l.trim());
    if (m) {
      points.push({ hour: parseInt(m[1], 10), lat: parseLatLonToken(m[2]), lon: parseLatLonToken(m[3]), windKt: parseInt(m[4], 10) });
    }
  }
  if (!points.length || points[0].hour !== 0) throw new Error('TCW has no T000 position');

  const pres = /MINIMUM CENTRAL PRESSURE[^\n]*?IS\s+(\d{3,4})\s*MB/i.exec(text);
  const subj = /SUBJ:\s*(.+)/.exec(text);
  return {
    atcfId, name, obsTime, points,
    pressureHpa: pres ? parseInt(pres[1], 10) : null,
    title: subj ? subj[1].trim() : `${atcfId} ${name || ''}`.trim(),
  };
}

/** Parse a Tropical Cyclone Formation Alert text (invest). Returns null if cancelled/not locatable. */
function parseTcfa(text, issued) {
  if (/CANCELLATION|CANCELS REF/i.test(text)) return null;
  const inv = /INVEST\s+(\d{2}[A-Z])/i.exec(text);
  // Current position: "IS NOW LOCATED NEAR ..." when the alert reports movement, else the first "LOCATED NEAR"
  const POS = String.raw`LOCATED\s+NEAR\s+(\d+(?:\.\d+)?)([NS])\s+(\d+(?:\.\d+)?)([EW])`;
  const loc = new RegExp(String.raw`NOW\s+` + POS, 'i').exec(text) || new RegExp(POS, 'i').exec(text);
  if (!inv || !loc) return null;
  const lat = parseFloat(loc[1]) * (loc[2].toUpperCase() === 'S' ? -1 : 1);
  const lon = parseFloat(loc[3]) * (loc[4].toUpperCase() === 'W' ? -1 : 1);
  const wind = /SUSTAINED SURFACE WINDS ARE ESTIMATED AT\s+(\d+)(?:\s+TO\s+(\d+))?\s+KNOTS/i.exec(text);
  const pres = /SEA LEVEL PRESSURE IS ESTIMATED TO BE NEAR\s+(\d{3,4})\s*MB/i.exec(text);
  return {
    atcfId: inv[1].toUpperCase(),
    lat, lon,
    windKt: wind ? parseInt(wind[2] || wind[1], 10) : 25,
    pressureHpa: pres ? parseInt(pres[1], 10) : null,
    obsTime: issued || new Date(),
    summary: text.split(/RMKS\/\s*/i)[1]?.replace(/\s+/g, ' ').slice(0, 1000) || null,
  };
}

/** DTG like "29/1500Z" relative to the RSS pubDate month/year. */
function parseIssued(dtg, ref) {
  const m = /(\d{2})\/(\d{2})(\d{2})Z/.exec(dtg || '');
  if (!m) return null;
  const d = new Date(Date.UTC(ref.getUTCFullYear(), ref.getUTCMonth(), +m[1], +m[2], +m[3]));
  if (d - ref > 5 * 86400e3) d.setUTCMonth(d.getUTCMonth() - 1); // issued last month
  return d;
}

async function fetchJtwcSystems() {
  const rss = await fetchText(JTWC_RSS);
  const pub = /<lastBuildDate>([^<]+)<\/lastBuildDate>/.exec(rss);
  const ref = pub ? new Date(pub[1]) : new Date();
  const systems = [];

  const descriptions = [...rss.matchAll(/<description><!\[CDATA\[([\s\S]*?)\]\]><\/description>/g)].map(m => m[1]);
  for (const desc of descriptions) {
    // Each product block starts with <p><b>Title</b> ... Issued at DD/HHMMZ ... <ul>links</ul>
    const blocks = desc.split(/<p><b>/).slice(1);
    for (const block of blocks) {
      const title = (block.match(/^([^<]+)/) || [])[1]?.trim() || '';
      if (!title || /cancelled/i.test(block)) continue;
      const issued = parseIssued((block.match(/Issued at\s+([\d/]+Z)/) || [])[1], ref);
      const tcw = (block.match(/href='([^']+\.tcw)'/) || [])[1];
      const tcfaTxt = /Formation Alert/i.test(title) ? (block.match(/href='([^']+web\.txt)'/) || [])[1] : null;
      try {
        if (tcw && !/Formation Alert/i.test(title)) {
          const w = parseTcw(await fetchText(tcw));
          const p0 = w.points[0];
          if (!inNio(p0.lat, p0.lon)) continue;
          systems.push({ kind: 'warning', url: tcw.replace(/\.tcw$/, 'web.txt'), ...w });
        } else if (tcfaTxt) {
          const a = parseTcfa(await fetchText(tcfaTxt), issued);
          if (a && inNio(a.lat, a.lon)) systems.push({ kind: 'tcfa', url: tcfaTxt, title, ...a });
        }
      } catch (err) {
        console.warn(`[official-feed] skipped JTWC product "${title}": ${err.message}`);
      }
    }
  }
  return systems;
}

// ── IBTrACS ──────────────────────────────────────────────────────

async function fetchIbtracsActive(now = new Date()) {
  const csv = await fetchText(IBTRACS_ACTIVE, 120000);
  const lines = csv.split(/\r?\n/).filter(Boolean);
  const cols = lines[0].split(',');
  const idx = name => cols.indexOf(name);
  const I = {
    sid: idx('SID'), basin: idx('BASIN'), name: idx('NAME'), time: idx('ISO_TIME'), lat: idx('LAT'), lon: idx('LON'),
    wmoWind: idx('WMO_WIND'), wmoPres: idx('WMO_PRES'), ndWind: idx('NEWDELHI_WIND'), ndPres: idx('NEWDELHI_PRES'),
    usaWind: idx('USA_WIND'), usaPres: idx('USA_PRES'), atcf: idx('USA_ATCF_ID'),
  };
  const latest = new Map();
  for (const line of lines.slice(2)) {
    const f = line.split(',');
    if (f[I.basin] !== 'NI') continue;
    const t = new Date(f[I.time].replace(' ', 'T') + 'Z');
    const prev = latest.get(f[I.sid]);
    if (!prev || t > prev.obsTime) {
      const num = v => (v && v.trim() !== '' ? parseFloat(v) : null);
      latest.set(f[I.sid], {
        sid: f[I.sid], name: f[I.name] === 'UNNAMED' || f[I.name] === 'NOT_NAMED' ? null : f[I.name],
        obsTime: t, lat: num(f[I.lat]), lon: num(f[I.lon]), atcfId: f[I.atcf]?.trim() || null,
        // New Delhi (IMD) 3-min winds preferred, then WMO, then USA 1-min scaled to 3-min
        windKt3: num(f[I.ndWind]) ?? num(f[I.wmoWind]) ?? (num(f[I.usaWind]) != null ? num(f[I.usaWind]) * ONE_MIN_TO_THREE_MIN : null),
        pressureHpa: num(f[I.ndPres]) ?? num(f[I.wmoPres]) ?? num(f[I.usaPres]),
      });
    }
  }
  return [...latest.values()].filter(s => now - s.obsTime <= ACTIVE_WINDOW_H * 3600e3 && inNio(s.lat, s.lon));
}

// ── Persistence ─────────────────────────────────────────────────

async function upsertOfficial(conn, row, forecasts) {
  await conn.query(
    `INSERT INTO cyclones (
       cyclone_id, cyclone_name, basin, current_lat, current_lon, sustained_wind_kmh, sustained_wind_knots,
       central_pressure_hpa, imd_category, obb_x_center, obb_y_center, obb_width, obb_height, obb_theta,
       detection_confidence, observation_time, inference_generated_at, source, status, external_id, source_url, summary)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 0, 0, 0, 1.0, ?, UTC_TIMESTAMP(), ?, ?, ?, ?, ?)
     ON DUPLICATE KEY UPDATE
       cyclone_name=VALUES(cyclone_name), basin=VALUES(basin), current_lat=VALUES(current_lat), current_lon=VALUES(current_lon),
       sustained_wind_kmh=VALUES(sustained_wind_kmh), sustained_wind_knots=VALUES(sustained_wind_knots),
       central_pressure_hpa=VALUES(central_pressure_hpa), imd_category=VALUES(imd_category),
       observation_time=VALUES(observation_time), inference_generated_at=VALUES(inference_generated_at),
       source=VALUES(source), status=VALUES(status), external_id=VALUES(external_id),
       source_url=VALUES(source_url), summary=VALUES(summary)`,
    [row.id, row.name, basinFor(row.lon), row.lat, row.lon, row.windKt * KT_TO_KMH, row.windKt, row.pressureHpa,
      getIMDCategory(row.windKt3 * KT_TO_KMH), row.obsTime, row.source, row.status, row.externalId, row.url, row.summary]
  );

  // Track history: append the observed position once per timestamp
  await conn.query(
    `INSERT INTO historical_tracks (cyclone_id, timestamp, latitude, longitude, sustained_wind_kmh,
       sustained_wind_knots, central_pressure_hpa, imd_category)
     SELECT ?, ?, ?, ?, ?, ?, ?, ? FROM DUAL
     WHERE NOT EXISTS (SELECT 1 FROM historical_tracks WHERE cyclone_id = ? AND timestamp = ?)`,
    [row.id, row.obsTime, row.lat, row.lon, row.windKt * KT_TO_KMH, row.windKt, row.pressureHpa,
      getIMDCategory(row.windKt3 * KT_TO_KMH), row.id, row.obsTime]
  );

  if (forecasts) {
    await conn.query('DELETE FROM forecast_tracks WHERE cyclone_id = ? AND source = ?', [row.id, row.source]);
    for (const f of forecasts) {
      const kmh3 = f.windKt * ONE_MIN_TO_THREE_MIN * KT_TO_KMH;
      await conn.query(
        `INSERT INTO forecast_tracks (cyclone_id, forecast_hour, predicted_lat, predicted_lon, predicted_wind_kmh,
           predicted_pressure_hpa, predicted_imd_category, confidence, generated_at, source)
         VALUES (?, ?, ?, ?, ?, ?, ?, 1.0, ?, ?)`,
        [row.id, f.hour, f.lat, f.lon, f.windKt * KT_TO_KMH, pressureFromWind(f.windKt), getIMDCategory(kmh3),
          row.obsTime, row.source]
      );
    }
  }
}

function recordStatus(component, status, message, details, lastDataTime = null) {
  return cycloneStore.recordHeartbeat({ component, status, message, details, last_data_time: lastDataTime });
}

/** One full poll. Returns a summary; never throws (errors are recorded in pipeline_status). */
async function pollOfficialFeeds() {
  const summary = { jtwc: 0, ibtracs: 0, dissipated: 0, errors: [] };
  const seen = [];
  const rows = [];

  try {
    for (const s of await fetchJtwcSystems()) {
      if (s.kind === 'warning') {
        const p0 = s.points[0];
        rows.push({
          row: {
            id: `JTWC-${s.atcfId}-${s.obsTime.getUTCFullYear()}`, name: s.name, lat: p0.lat, lon: p0.lon,
            windKt: p0.windKt, windKt3: p0.windKt * ONE_MIN_TO_THREE_MIN,
            pressureHpa: s.pressureHpa ?? pressureFromWind(p0.windKt), obsTime: s.obsTime,
            source: 'OFFICIAL_JTWC', status: 'active', externalId: s.atcfId, url: s.url, summary: s.title,
          },
          forecasts: s.points.slice(1),
        });
      } else {
        rows.push({
          row: {
            id: `JTWC-INVEST-${s.atcfId}-${s.obsTime.getUTCFullYear()}`, name: `Invest ${s.atcfId}`, lat: s.lat, lon: s.lon,
            windKt: s.windKt, windKt3: s.windKt * ONE_MIN_TO_THREE_MIN,
            pressureHpa: s.pressureHpa ?? pressureFromWind(s.windKt), obsTime: s.obsTime,
            source: 'OFFICIAL_JTWC', status: 'watch', externalId: `INVEST-${s.atcfId}`, url: s.url,
            summary: s.summary || s.title,
          },
          forecasts: null,
        });
      }
    }
    summary.jtwc = rows.length;
  } catch (err) {
    summary.errors.push(`JTWC: ${err.message}`);
  }

  try {
    for (const s of await fetchIbtracsActive()) {
      // Skip systems JTWC already covers (within ~300 km)
      const dup = rows.some(r => Math.hypot(r.row.lat - s.lat, (r.row.lon - s.lon) * Math.cos(s.lat * Math.PI / 180)) < 2.7);
      if (dup) continue;
      const windKt3 = s.windKt3 ?? 20;
      rows.push({
        row: {
          id: `IBTRACS-${s.sid}`, name: s.name, lat: s.lat, lon: s.lon, windKt: windKt3, windKt3,
          pressureHpa: s.pressureHpa ?? pressureFromWind(windKt3), obsTime: s.obsTime,
          source: 'OFFICIAL_IBTRACS', status: 'active', externalId: s.sid,
          url: 'https://www.ncei.noaa.gov/products/international-best-track-archive', summary: 'IBTrACS provisional best track',
        },
        forecasts: null,
      });
      summary.ibtracs++;
    }
  } catch (err) {
    summary.errors.push(`IBTrACS: ${err.message}`);
  }

  const conn = await pool.getConnection();
  try {
    await conn.beginTransaction();
    for (const { row, forecasts } of rows) {
      await upsertOfficial(conn, row, forecasts);
      seen.push(row.id);
    }
    // Official systems no longer listed by any source are closed out (rows are kept — additive only)
    const feedsOk = summary.errors.length === 0;
    if (feedsOk) {
      const [res] = await conn.query(
        `UPDATE cyclones SET status = 'dissipated'
          WHERE source LIKE 'OFFICIAL_%' AND status <> 'dissipated' AND NOT (external_id <=> 'DEMO')
            ${seen.length ? 'AND cyclone_id NOT IN (?)' : ''}`,
        seen.length ? [seen] : []
      );
      summary.dissipated = res.affectedRows;
    }
    await conn.commit();
  } catch (err) {
    await conn.rollback();
    summary.errors.push(`DB: ${err.message}`);
  } finally {
    conn.release();
  }

  invalidateCache();
  const latest = rows.reduce((t, r) => (!t || r.row.obsTime > t ? r.row.obsTime : t), null);
  const status = summary.errors.length ? (rows.length ? 'degraded' : 'error') : 'ok';
  try {
    await recordStatus('official_feed', status, summary.errors.join('; ') || `${rows.length} official system(s)`,
      { ...summary, systems: seen }, latest);
  } catch (err) {
    console.error('[official-feed] could not record status:', err.message);
  }
  console.log(`[official-feed] ${status}: ${rows.length} system(s) ${JSON.stringify(summary)}`);
  return { status, systems: seen, ...summary };
}

let timer = null;
function startScheduler(intervalMinutes) {
  if (!intervalMinutes || intervalMinutes <= 0 || timer) return;
  const run = () => pollOfficialFeeds().catch(err => console.error('[official-feed] poll crashed:', err));
  run();
  timer = setInterval(run, intervalMinutes * 60e3);
  timer.unref();
}

module.exports = {
  pollOfficialFeeds, startScheduler,
  // exported for tests
  parseTcw, parseTcfa, parseIssued, pressureFromWind, inNio,
};
