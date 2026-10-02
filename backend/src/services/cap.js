/**
 * CAP 1.2 alerts (OASIS Common Alerting Protocol) + Atom index feed
 * ═════════════════════════════════════════════════════════════════
 * The format India's NDMA uses for SACHET and that Google Public Alerts / WMO alert hubs ingest.
 * Built only from the template advisory (advisory_generator.js), so CAP text and the website say
 * the same thing. Rules:
 *   - only official systems (source OFFICIAL_*, status active) become CAP alerts; satellite watch
 *     areas are not warnings and are never published as CAP
 *   - demo rows (external_id = 'DEMO') are status "Exercise", never "Actual"
 *   - one <info> block per language (en-IN, hi-IN)
 *   - <area>: circles of the strong-wind radius (impact.galeRadiusKm) at the current position and
 *     every official forecast point up to 72 h
 * Spec: https://docs.oasis-open.org/emergency/cap/v1.2/CAP-v1.2-os.html
 */

const { buildAdvisory } = require('./advisory_generator');
const { galeRadiusKm } = require('./impact');

const CAP_NS = 'urn:oasis:names:tc:emergency:cap:1.2';
const KMH_PER_KT = 1.852;
const VALID_HOURS = 12; // official bulletins are 6-hourly; an unrefreshed alert lapses after two cycles

const LANGS = [
  { code: 'en', cap: 'en-IN' },
  { code: 'hi', cap: 'hi-IN' },
];

const EVENT = {
  en: { D: 'Depression', DD: 'Deep Depression', CS: 'Cyclonic Storm', SCS: 'Severe Cyclonic Storm',
    VSCS: 'Very Severe Cyclonic Storm', ESCS: 'Extremely Severe Cyclonic Storm', SuCS: 'Super Cyclonic Storm' },
  hi: { D: 'अवदाब', DD: 'गहरा अवदाब', CS: 'चक्रवाती तूफान', SCS: 'गंभीर चक्रवाती तूफान',
    VSCS: 'अति गंभीर चक्रवाती तूफान', ESCS: 'अत्यंत गंभीर चक्रवाती तूफान', SuCS: 'महा चक्रवाती तूफान' },
};
const AREA = { BOB: 'Bay of Bengal and adjoining coasts', AS: 'Arabian Sea and adjoining coasts',
  NIO: 'North Indian Ocean and adjoining coasts' };

// Alert level → CAP urgency / responseType; IMD category → CAP severity
const BY_LEVEL = {
  RED: { urgency: 'Immediate', response: 'Evacuate' },
  ORANGE: { urgency: 'Expected', response: 'Prepare' },
  YELLOW: { urgency: 'Future', response: 'Monitor' },
};
const SEVERITY = { SuCS: 'Extreme', ESCS: 'Extreme', VSCS: 'Severe', SCS: 'Severe', CS: 'Moderate', DD: 'Minor', D: 'Minor' };

const HEADLINE = {
  en: (ev, name, level) => `${level} alert: ${ev}${name ? ` ${name}` : ''}`,
  hi: (ev, name, level) => `${{ RED: 'लाल', ORANGE: 'नारंगी', YELLOW: 'पीला' }[level]} चेतावनी: ${ev}${name ? ` ${name}` : ''}`,
};

function xml(s) {
  return String(s ?? '').replace(/[<>&'"]/g, ch => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;', "'": '&apos;', '"': '&quot;' }[ch]));
}

/** CAP dateTime: seconds precision, numeric offset, UTC written as "-00:00" (CAP 1.2 §3.3.2). */
function capTime(d) {
  return new Date(d).toISOString().slice(0, 19) + '-00:00';
}

function isCapEligible(c) {
  return String(c.source || '').startsWith('OFFICIAL_') && c.status === 'active';
}

/** "lat,lon radius_km" circles: now + official forecast points ≤ 72 h. */
function threatCircles(c) {
  const circle = (lat, lon, kmh) => {
    const r = galeRadiusKm(Number(kmh) / KMH_PER_KT) || 150;
    return `${Number(lat).toFixed(2)},${Number(lon).toFixed(2)} ${r}`;
  };
  const out = [circle(c.current_lat, c.current_lon, c.sustained_wind_kmh)];
  for (const f of c.forecasts || []) {
    if (!String(f.source || '').startsWith('OFFICIAL_') || f.forecast_hour <= 0 || f.forecast_hour > 72) continue;
    out.push(circle(f.predicted_lat, f.predicted_lon, f.predicted_wind_kmh));
  }
  return [...new Set(out)];
}

function identifier(c, senderId) {
  const t = new Date(c.observation_time).toISOString().replace(/[-:]/g, '').slice(0, 13);
  return `${senderId}.${String(c.cyclone_id).replace(/[\s,<&]/g, '_')}.${t}`;
}

/**
 * @param {object} c      cyclone row from cyclone_store.getById (with forecasts + history)
 * @param {object} opts   { sender, web, now }
 * @returns {string|null} CAP XML, or null when the system must not be published as CAP
 */
function buildCapAlert(c, { sender = 'cyclo-nexus', web = '', now = new Date() } = {}) {
  if (!isCapEligible(c)) return null;
  const sent = capTime(now);
  const obs = new Date(c.observation_time);
  const expires = capTime(new Date(Math.max(obs.getTime() + VALID_HOURS * 3600e3, now.getTime() + 3600e3)));
  const status = c.external_id === 'DEMO' ? 'Exercise' : 'Actual';
  const circles = threatCircles(c);

  const infos = LANGS.map(({ code, cap }) => {
    const adv = buildAdvisory(c, code);
    const level = adv.alert_level || 'YELLOW';
    const ev = EVENT[code][c.imd_category] || EVENT[code].D;
    const instruction = [adv.directives_public, adv.directives_fishermen, adv.directives_administration]
      .filter(Boolean).join('\n');
    return `  <info>
    <language>${cap}</language>
    <category>Met</category>
    <event>${xml(ev)}</event>
    <responseType>${BY_LEVEL[level].response}</responseType>
    <urgency>${BY_LEVEL[level].urgency}</urgency>
    <severity>${SEVERITY[c.imd_category] || 'Minor'}</severity>
    <certainty>Observed</certainty>
    <eventCode><valueName>IMD_CATEGORY</valueName><value>${xml(c.imd_category)}</value></eventCode>
    <effective>${sent}</effective>
    <onset>${capTime(obs)}</onset>
    <expires>${expires}</expires>
    <senderName>Cyclo-Nexus (auto-generated from ${xml(c.source.replace('OFFICIAL_', ''))} data; the official authority for India is IMD)</senderName>
    <headline>${xml(HEADLINE[code](ev, c.cyclone_name, level))}</headline>
    <description>${xml(adv.threat_summary)}</description>
    <instruction>${xml(instruction)}</instruction>${web ? `\n    <web>${xml(web)}</web>` : ''}
    <parameter><valueName>ALERT_LEVEL</valueName><value>${level}</value></parameter>
    <parameter><valueName>MAX_SUSTAINED_WIND_KMH</valueName><value>${Math.round(Number(c.sustained_wind_kmh))}</value></parameter>
    <parameter><valueName>CENTRAL_PRESSURE_HPA</valueName><value>${Math.round(Number(c.central_pressure_hpa))}</value></parameter>
    <area>
      <areaDesc>${xml(AREA[c.basin] || AREA.NIO)} (strong-wind zone now and along the official 72 h forecast track)</areaDesc>
${circles.map(x => `      <circle>${x}</circle>`).join('\n')}
    </area>
  </info>`;
  });

  return `<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="${CAP_NS}">
  <identifier>${xml(identifier(c, sender))}</identifier>
  <sender>${xml(sender)}</sender>
  <sent>${sent}</sent>
  <status>${status}</status>
  <msgType>Alert</msgType>
  <scope>Public</scope>
  <note>${xml(buildAdvisory(c, 'en').disclaimer)}</note>
${infos.join('\n')}
</alert>
`;
}

/** Atom 1.0 index of the current CAP alerts (the feed format alert aggregators poll). */
function buildCapFeed(cyclones, { selfUrl, alertUrl, now = new Date() }) {
  const entries = cyclones.filter(isCapEligible).map(c => {
    const adv = buildAdvisory(c, 'en');
    const ev = EVENT.en[c.imd_category] || EVENT.en.D;
    return `  <entry>
    <id>${xml(alertUrl(c.cyclone_id))}</id>
    <title>${xml(HEADLINE.en(ev, c.cyclone_name, adv.alert_level || 'YELLOW'))}</title>
    <updated>${new Date(c.observation_time).toISOString()}</updated>
    <summary>${xml(adv.threat_summary)}</summary>
    <link rel="alternate" type="application/cap+xml" href="${xml(alertUrl(c.cyclone_id))}"/>
  </entry>`;
  });
  return `<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <id>${xml(selfUrl)}</id>
  <title>Cyclo-Nexus cyclone alerts (CAP 1.2)</title>
  <updated>${new Date(now).toISOString()}</updated>
  <author><name>Cyclo-Nexus</name></author>
  <link rel="self" href="${xml(selfUrl)}"/>
${entries.join('\n')}
</feed>
`;
}

module.exports = { buildCapAlert, buildCapFeed, capTime, threatCircles, isCapEligible };
