/**
 * Template advisory generator — offline tests.
 */

const { buildAdvisory, computeMovement, alertLevel } = require('../src/services/advisory_generator');

const official = {
  cyclone_id: 'JTWC-03B-2026', cyclone_name: 'MONTHA', basin: 'BOB', source: 'OFFICIAL_JTWC', status: 'active',
  current_lat: 15.2, current_lon: 87.4, sustained_wind_kmh: 95, central_pressure_hpa: 984, imd_category: 'SCS',
  observation_time: '2026-09-29T12:00:00Z',
  history: [
    { timestamp: '2026-09-29T06:00:00Z', latitude: 14.6, longitude: 87.8 },
    { timestamp: '2026-09-29T12:00:00Z', latitude: 15.2, longitude: 87.4 },
  ],
};

describe('alert levels (schemas/imd_scale.py thresholds)', () => {
  it('maps wind to YELLOW / ORANGE / RED', () => {
    expect(alertLevel(20)).toBeNull();
    expect(alertLevel(40)).toBe('YELLOW');
    expect(alertLevel(62)).toBe('ORANGE');
    expect(alertLevel(118)).toBe('RED');
  });
});

describe('movement', () => {
  it('computes bearing and speed from the last two positions >= 3 h apart', () => {
    const m = computeMovement(official.history);
    expect(m.dir).toBe('NNW'); // bearing ≈ 327°
    expect(m.hours).toBe(6);
    expect(m.speed).toBeGreaterThan(10);
    expect(m.speed).toBeLessThan(20);
  });

  it('returns null without enough history', () => {
    expect(computeMovement([official.history[1]])).toBeNull();
  });
});

describe('buildAdvisory', () => {
  it('builds an English ORANGE advisory from official numbers only', () => {
    const a = buildAdvisory(official, 'en');
    expect(a.alert_level).toBe('ORANGE');
    expect(a.threat_summary).toMatch(/Severe Cyclonic Storm "MONTHA"/);
    expect(a.threat_summary).toMatch(/15\.2°N, 87\.4°E/);
    expect(a.threat_summary).toMatch(/moved NNW/);
    expect(a.directives_fishermen).toMatch(/Bay of Bengal/);
    expect(a.disclaimer).toMatch(/India Meteorological Department/);
    expect(a.fallback).toBe(false);
  });

  it('builds Hindi text and falls back to English for unsupported languages', () => {
    expect(buildAdvisory(official, 'hi').threat_summary).toMatch(/गंभीर चक्रवाती तूफान/);
    const gu = buildAdvisory(official, 'gu');
    expect(gu.language).toBe('en');
    expect(gu.fallback).toBe(true);
  });

  it('builds regional-language advisories with every number filled in', () => {
    for (const lang of ['ta', 'te', 'ml', 'bn', 'or', 'kn', 'mr']) {
      const a = buildAdvisory(official, lang);
      expect(a.language).toBe(lang);
      expect(a.fallback).toBe(false);
      const text = [a.threat_summary, a.directives_fishermen, a.directives_public, a.directives_administration].join(' ');
      expect(text).not.toMatch(/\{\w+\}/);
      expect(a.threat_summary).toContain('MONTHA');
      expect(a.threat_summary).toContain('95');
    }
    expect(buildAdvisory(official, 'ta').threat_summary).toMatch(/தீவிரப் புயல்/);
  });

  it('never issues an alert level for satellite watch areas', () => {
    const a = buildAdvisory({ ...official, source: 'AI_SATELLITE', status: 'watch', cyclone_name: null }, 'en');
    expect(a.alert_level).toBeNull();
    expect(a.type).toBe('watch');
    expect(a.threat_summary).toMatch(/not an official warning/);
  });
});
