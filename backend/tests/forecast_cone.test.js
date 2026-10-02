/**
 * IMD cone of uncertainty — offline geometry tests.
 */

const { coneRadiusKm, buildConeRing, coneFeature } = require('../src/services/forecast_cone');

const KM_LAT = 110.57;

function inside([x, y], ring) {
  let hit = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) hit = !hit;
  }
  return hit;
}

describe('IMD cone radii', () => {
  it('uses the published radii and interpolates between lead times', () => {
    expect(coneRadiusKm(0)).toBe(0);
    expect(coneRadiusKm(12)).toBe(75);
    expect(coneRadiusKm(24)).toBe(150);
    expect(coneRadiusKm(30)).toBe(175);
    expect(coneRadiusKm(72)).toBe(350);
    expect(coneRadiusKm(96)).toBe(350);
  });
});

describe('cone ring', () => {
  // Steady eastward track along 15°N, about 9 km/h
  const nodes = [
    { hour: 0, lat: 15, lon: 85 }, { hour: 24, lat: 15, lon: 87 },
    { hour: 48, lat: 15, lon: 89 }, { hour: 72, lat: 15, lon: 91 },
  ];
  const ring = buildConeRing(nodes);

  it('is a closed ring that starts at the analysis position', () => {
    expect(ring[0]).toEqual([85, 15]);
    expect(ring[ring.length - 1]).toEqual(ring[0]);
  });

  it('contains every forecast position and its error circle, and nothing far outside it', () => {
    for (const p of nodes.slice(1)) {
      const r = coneRadiusKm(p.hour);
      expect(inside([p.lon, p.lat], ring)).toBe(true);
      expect(inside([p.lon, p.lat + (0.95 * r) / KM_LAT], ring)).toBe(true);
      expect(inside([p.lon, p.lat - (0.95 * r) / KM_LAT], ring)).toBe(true);
      expect(inside([p.lon, p.lat + (1.15 * r) / KM_LAT], ring)).toBe(false);
    }
    expect(inside([91 + (0.95 * 350) / (111.32 * Math.cos(15 * Math.PI / 180)), 15], ring)).toBe(true); // ahead of 72 h
    expect(inside([84, 15], ring)).toBe(false); // behind the analysis point
  });

  it('becomes the 72 h circle for a stationary storm', () => {
    const still = buildConeRing([{ hour: 0, lat: 15, lon: 88 }, { hour: 72, lat: 15, lon: 88 }]);
    expect(inside([88, 15 + 340 / KM_LAT], still)).toBe(true);
    expect(inside([88, 15 - 340 / KM_LAT], still)).toBe(true);
    expect(inside([88, 15 + 370 / KM_LAT], still)).toBe(false);
  });

  it('ignores points beyond 72 h and needs at least two nodes', () => {
    expect(buildConeRing([{ hour: 0, lat: 15, lon: 85 }])).toBeNull();
    const withLate = buildConeRing([...nodes, { hour: 120, lat: 25, lon: 95 }]);
    expect(withLate).toEqual(ring);
  });
});

describe('cone feature', () => {
  it('is built from the official forecast only', () => {
    const c = { cyclone_id: 'X', current_lat: 15, current_lon: 85, forecasts: [
      { source: 'AI_SATELLITE', forecast_hour: 24, predicted_lat: 16, predicted_lon: 86 },
    ] };
    expect(coneFeature(c)).toBeNull();
    c.forecasts.push({ source: 'OFFICIAL_JTWC', forecast_hour: 24, predicted_lat: 15, predicted_lon: 87 });
    const f = coneFeature(c);
    expect(f.geometry.type).toBe('Polygon');
    expect(f.properties).toMatchObject({ type: 'forecast_cone', source: 'OFFICIAL_JTWC', cyclone_id: 'X' });
  });
});
