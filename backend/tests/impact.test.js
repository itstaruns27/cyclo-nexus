const impact = require('../src/services/impact');

describe('impact exposure', () => {
  test('a very severe storm crossing the Odisha coast puts Bhubaneswar and Puri in the core', () => {
    const e = impact.exposure([{ lat: 17.4, lon: 87.4, kt: 75 }, { lat: 19.9, lon: 85.8, kt: 68 }, { lat: 22.4, lon: 84.6, kt: 22 }]);
    const core = e.largest_towns.filter(t => t.zone === 'core').map(t => t.name);
    expect(core).toEqual(expect.arrayContaining(['Bhubaneswar', 'Puri']));
    expect(e.people_core).toBeGreaterThan(1e6);
    expect(e.people_gale_zone).toBeGreaterThanOrEqual(e.people_core);
  });

  test('a depression (< 34 kt) exposes nobody', () => {
    expect(impact.exposure([{ lat: 19.8, lon: 85.8, kt: 25 }]).people_gale_zone).toBe(0);
  });

  test('a storm far out at sea exposes nobody', () => {
    expect(impact.exposure([{ lat: 12, lon: 90, kt: 90 }]).people_gale_zone).toBe(0);
  });
});

describe('impact analogs', () => {
  test('median is used for the typical storm and ignores the extreme tail', () => {
    const peaks = Object.fromEntries(impact.recordedStorms.map(s => [s.sid, 90]));
    const a = impact.analogs(90, peaks);
    expect(a.deaths_range[1]).toBeGreaterThan(a.deaths_median);
    expect(a.deaths_median).toBeLessThan(10000);
  });

  test('no recorded storm of that strength → null', () => {
    expect(impact.analogs(20, {})).toBeNull();
  });
});

describe('exposure with measured wind radii (quadrants)', () => {
  const { exposure, placeLabel } = require('../src/services/impact');
  // Puri ≈ 19.80°N 85.83°E. A storm 60 km SW of Puri with gale winds only in its NE quadrant reaches it;
  // the same storm with gale winds only in the SW quadrant must not.
  const base = { lat: 19.4, lon: 85.4, kt: 60, r50_ne: 0, r50_se: 0, r50_sw: 0, r50_nw: 0, r64_ne: 0, r64_se: 0, r64_sw: 0, r64_nw: 0 };
  const names = e => e.largest_towns.map(t => t.name);

  it('counts towns only inside the quadrant that has gale-force winds', () => {
    const ne = exposure([{ ...base, r34_ne: 60, r34_se: 0, r34_sw: 0, r34_nw: 0 }]);
    const sw = exposure([{ ...base, r34_ne: 0, r34_se: 0, r34_sw: 60, r34_nw: 0 }]);
    expect(names(ne)).toContain('Puri');
    expect(names(sw)).not.toContain('Puri');
    expect(ne.radii_source).toMatch(/measured/);
  });

  it('falls back to typical radii when none were measured', () => {
    const e = exposure([{ lat: 19.4, lon: 85.4, kt: 60 }]);
    expect(e.people_gale_zone).toBeGreaterThan(0);
    expect(e.radii_source).toMatch(/typical/);
  });

  it('names places people know', () => {
    expect(placeLabel(19.81, 85.83).name).toBe('Puri');
  });
});

describe('people within a radius (population grid)', () => {
  it('counts a metro on land and nobody in the open sea', () => {
    expect(impact.peopleWithin(13.08, 80.27, 50)).toBeGreaterThan(8e6); // Chennai
    expect(impact.peopleWithin(15, 88, 50)).toBe(0); // central Bay of Bengal
  });
});
