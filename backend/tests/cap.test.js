/**
 * CAP 1.2 alert + Atom feed — offline tests.
 */

const { buildCapAlert, buildCapFeed, capTime, threatCircles } = require('../src/services/cap');

const NOW = new Date('2026-09-29T13:00:00Z');
const official = {
  cyclone_id: 'JTWC-03B-2026', cyclone_name: 'MONTHA', basin: 'BOB', source: 'OFFICIAL_JTWC', status: 'active',
  current_lat: 15.2, current_lon: 87.4, sustained_wind_kmh: 130, central_pressure_hpa: 975, imd_category: 'VSCS',
  observation_time: '2026-09-29T12:00:00Z', external_id: '03B',
  history: [
    { timestamp: '2026-09-29T06:00:00Z', latitude: 14.6, longitude: 87.8 },
    { timestamp: '2026-09-29T12:00:00Z', latitude: 15.2, longitude: 87.4 },
  ],
  forecasts: [
    { source: 'OFFICIAL_JTWC', forecast_hour: 24, predicted_lat: 17.0, predicted_lon: 86.5, predicted_wind_kmh: 150 },
    { source: 'OFFICIAL_JTWC', forecast_hour: 96, predicted_lat: 21.0, predicted_lon: 85.0, predicted_wind_kmh: 60 },
    { source: 'AI_SATELLITE', forecast_hour: 24, predicted_lat: 18.0, predicted_lon: 88.0, predicted_wind_kmh: 140 },
  ],
};

const tag = (x, name) => [...x.matchAll(new RegExp(`<${name}>([^<]*)</${name}>`, 'g'))].map(m => m[1]);

describe('CAP alert', () => {
  const x = buildCapAlert(official, { sender: 'cyclo-nexus', web: 'https://example.org/alerts', now: NOW });

  it('is a CAP 1.2 document with the required alert elements', () => {
    expect(x).toContain('<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">');
    expect(tag(x, 'identifier')[0]).toBe('cyclo-nexus.JTWC-03B-2026.20260929T1200');
    expect(tag(x, 'status')).toEqual(['Actual']);
    expect(tag(x, 'msgType')).toEqual(['Alert']);
    expect(tag(x, 'scope')).toEqual(['Public']);
  });

  it('writes times with a numeric UTC offset, never "Z"', () => {
    expect(capTime('2026-09-29T12:00:00.000Z')).toBe('2026-09-29T12:00:00-00:00');
    expect(tag(x, 'sent')[0]).toBe('2026-09-29T13:00:00-00:00');
    expect(tag(x, 'expires')[0]).toBe('2026-09-30T00:00:00-00:00');
  });

  it('has English and Hindi info blocks mapped from the RED alert level', () => {
    expect(tag(x, 'language')).toEqual(['en-IN', 'hi-IN']);
    expect(tag(x, 'urgency')).toEqual(['Immediate', 'Immediate']);
    expect(tag(x, 'responseType')).toEqual(['Evacuate', 'Evacuate']);
    expect(tag(x, 'severity')).toEqual(['Severe', 'Severe']);
    expect(tag(x, 'headline')[0]).toBe('RED alert: Very Severe Cyclonic Storm MONTHA');
    expect(tag(x, 'headline')[1]).toContain('लाल चेतावनी');
    expect(x).toContain('<value>RED</value>');
  });

  it('covers the current position and official forecast points up to 72 h only', () => {
    expect(threatCircles(official)).toEqual(['15.20,87.40 161', '17.00,86.50 185']);
    expect(tag(x, 'circle')).toEqual(['15.20,87.40 161', '17.00,86.50 185', '15.20,87.40 161', '17.00,86.50 185']);
  });

  it('escapes XML special characters', () => {
    const y = buildCapAlert({ ...official, cyclone_name: 'A&B <x>' }, { now: NOW });
    expect(y).toContain('A&amp;B &lt;x&gt;');
    expect(y).not.toContain('A&B <x>');
  });

  it('publishes demo rows as Exercise and never publishes watch areas', () => {
    expect(tag(buildCapAlert({ ...official, external_id: 'DEMO' }, { now: NOW }), 'status')).toEqual(['Exercise']);
    expect(buildCapAlert({ ...official, source: 'AI_SATELLITE', status: 'watch' }, { now: NOW })).toBeNull();
    expect(buildCapAlert({ ...official, status: 'dissipated' }, { now: NOW })).toBeNull();
  });
});

describe('CAP Atom feed', () => {
  it('lists only official active systems with links to their CAP files', () => {
    const watch = { ...official, cyclone_id: 'AI-WATCH-1', source: 'AI_SATELLITE', status: 'watch' };
    const feed = buildCapFeed([official, watch], {
      selfUrl: 'https://api.example.org/api/v1/alerts/cap.atom',
      alertUrl: id => `https://api.example.org/api/v1/alerts/${id}/cap.xml`,
      now: NOW,
    });
    expect(feed).toContain('<feed xmlns="http://www.w3.org/2005/Atom">');
    expect((feed.match(/<entry>/g) || []).length).toBe(1);
    expect(feed).toContain('href="https://api.example.org/api/v1/alerts/JTWC-03B-2026/cap.xml"');
    expect(feed).not.toContain('AI-WATCH-1');
  });
});
