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
