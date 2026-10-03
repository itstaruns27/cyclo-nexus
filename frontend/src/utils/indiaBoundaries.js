/**
 * Country borders as officially recognised by the Government of India (Survey of India view):
 * the whole of Jammu & Kashmir and Ladakh, including the areas under Pakistani and Chinese
 * occupation, is shown as India. The CARTO basemap draws the de-facto lines (Line of Control,
 * Line of Actual Control) as international borders, so its country-boundary layers are hidden and
 * replaced by Natural Earth's India point-of-view outlines (public/geo/boundaries_in.geojson,
 * built by backend/scripts/build_geo.py).
 */
const BASEMAP_COUNTRY_LAYERS = ['boundary_country_outline', 'boundary_country_inner'];

export function applyIndiaBoundaries(map) {
  for (const id of BASEMAP_COUNTRY_LAYERS) {
    if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', 'none');
  }
  if (map.getSource('india-view-borders')) return;
  map.addSource('india-view-borders', { type: 'geojson', data: '/geo/boundaries_in.geojson' });
  // Under the labels, above the basemap fills
  const firstSymbol = map.getStyle().layers.find(l => l.type === 'symbol')?.id;
  map.addLayer({
    id: 'india-view-borders', type: 'line', source: 'india-view-borders',
    paint: {
      'line-color': ['case', ['==', ['get', 'iso'], 'IN'], '#cbd5e1', '#64748b'],
      'line-width': ['interpolate', ['linear'], ['zoom'], 2, 0.6, 6, 1.4],
      'line-opacity': 0.9,
    },
  }, firstSymbol);
}
