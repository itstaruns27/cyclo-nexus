import React, { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import { applyIndiaBoundaries } from '../../utils/indiaBoundaries';
import 'maplibre-gl/dist/maplibre-gl.css';
import { IMD_COLORS, SOURCE_COLOR } from '../../types/cyclone';
import { t } from '../../i18n/translations';

/**
 * Storm track map: observed track coloured by IMD grade, official / AI forecast tracks and the
 * forecast cone (active storms), landfall and formation markers, and — for the selected moment —
 * the gale-force wind area drawn from the storm's four quadrant radii.
 */
const EMPTY = { type: 'FeatureCollection', features: [] };
const R = Math.PI / 180;

/** Polygon of a 4-quadrant wind field: NE / SE / SW / NW radii in km around lat/lon. */
export function quadrantArea(lat, lon, radii) {
  const ring = [];
  for (let q = 0; q < 4; q++) {
    const r = radii[q] || 0;
    for (let a = q * 90; a <= q * 90 + 90; a += 6) {
      const dLat = (r * Math.cos(a * R)) / 111.2;
      const dLon = (r * Math.sin(a * R)) / (111.2 * Math.cos(lat * R));
      ring.push([lon + dLon, lat + dLat]);
    }
  }
  ring.push(ring[0]);
  return { type: 'Feature', geometry: { type: 'Polygon', coordinates: [ring] }, properties: {} };
}

function trackFeatures(points) {
  const feats = [];
  for (let i = 0; i < points.length - 1; i++) {
    const a = points[i]; const b = points[i + 1];
    feats.push({ type: 'Feature', geometry: { type: 'LineString', coordinates: [[a.lon, a.lat], [b.lon, b.lat]] },
      properties: { kind: 'seg', grade: a.grade || '' } });
  }
  points.forEach((p, i) => feats.push({ type: 'Feature', geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
    properties: { kind: 'pt', grade: p.grade || '', i } }));
  return { type: 'FeatureCollection', features: feats };
}

function markerEl(cls, label) {
  const el = document.createElement('div');
  el.className = `storm-mk ${cls}`;
  el.innerHTML = `<span></span><b>${label}</b>`;
  return el;
}

export default function StormMap({ points, forecastGeo, selected, galeArea, onSelect, landfalls, lang }) {
  const el = useRef(null);
  const map = useRef(null);
  const ready = useRef(false);
  const markers = useRef([]);
  const selectRef = useRef(onSelect);
  selectRef.current = onSelect;

  useEffect(() => {
    const m = new maplibregl.Map({
      container: el.current, style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [85, 16], zoom: 3.6, attributionControl: { compact: true },
      cooperativeGestures: window.matchMedia('(pointer: coarse)').matches,
    });
    map.current = m;
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    m.on('load', () => {
      applyIndiaBoundaries(m);
      for (const id of ['cone', 'fc', 'track', 'gale', 'sel']) m.addSource(id, { type: 'geojson', data: EMPTY });
      m.addLayer({ id: 'cone-fill', type: 'fill', source: 'cone', paint: { 'fill-color': SOURCE_COLOR,
        'fill-opacity': ['case', ['==', ['get', 'source'], 'AI_CONSENSUS'], 0.08, 0.12] } });
      m.addLayer({ id: 'cone-line', type: 'line', source: 'cone', paint: { 'line-color': SOURCE_COLOR, 'line-opacity': 0.5, 'line-width': 1 } });
      m.addLayer({ id: 'gale-fill', type: 'fill', source: 'gale', paint: { 'fill-color': '#38bdf8', 'fill-opacity': 0.16 } });
      m.addLayer({ id: 'gale-line', type: 'line', source: 'gale', paint: { 'line-color': '#7dd3fc', 'line-width': 1.5 } });
      m.addLayer({ id: 'fc-line', type: 'line', source: 'fc', layout: { 'line-cap': 'round' },
        paint: { 'line-color': SOURCE_COLOR, 'line-width': 2.5, 'line-dasharray': [2, 1.5] } });
      m.addLayer({ id: 'fc-pts', type: 'circle', source: 'fc', filter: ['==', ['geometry-type'], 'Point'],
        paint: { 'circle-radius': 4, 'circle-color': SOURCE_COLOR,
          'circle-stroke-width': 2, 'circle-stroke-color': '#0f172a' } });
      m.addLayer({ id: 'track-seg', type: 'line', source: 'track', filter: ['==', ['get', 'kind'], 'seg'], layout: { 'line-cap': 'round' },
        paint: { 'line-color': ['match', ['get', 'grade'], ...Object.entries(IMD_COLORS).flat(), '#94a3b8'], 'line-width': 3.5 } });
      m.addLayer({ id: 'track-pt', type: 'circle', source: 'track', filter: ['==', ['get', 'kind'], 'pt'],
        paint: { 'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 2.5, 7, 5], 'circle-color': ['match', ['get', 'grade'], ...Object.entries(IMD_COLORS).flat(), '#94a3b8'],
          'circle-stroke-width': 1, 'circle-stroke-color': '#0f172a' } });
      m.addLayer({ id: 'sel-pt', type: 'circle', source: 'sel',
        paint: { 'circle-radius': 8, 'circle-color': '#ffffff', 'circle-stroke-width': 3, 'circle-stroke-color': '#0f172a' } });
      m.on('click', 'track-pt', e => selectRef.current(e.features[0].properties.i));
      m.on('mouseenter', 'track-pt', () => { m.getCanvas().style.cursor = 'pointer'; });
      m.on('mouseleave', 'track-pt', () => { m.getCanvas().style.cursor = ''; });
      ready.current = true;
      m.fire('cnx-ready');
    });
    return () => { ready.current = false; m.remove(); };
  }, []);

  // Track, forecast, cone and markers
  useEffect(() => {
    const m = map.current;
    const apply = () => {
      m.getSource('track').setData(trackFeatures(points));
      const fcFeats = (forecastGeo?.features || []).filter(f => ['forecast_track', 'forecast_node'].includes(f.properties.type));
      m.getSource('fc').setData({ type: 'FeatureCollection', features: fcFeats });
      m.getSource('cone').setData({ type: 'FeatureCollection', features: (forecastGeo?.features || []).filter(f => f.properties.type === 'forecast_cone') });
      markers.current.forEach(mk => mk.remove());
      markers.current = [];
      if (points.length) {
        markers.current.push(new maplibregl.Marker({ element: markerEl('genesis', t(lang, 'storm.map.genesis')), anchor: 'left' })
          .setLngLat([points[0].lon, points[0].lat]).addTo(m));
      }
      for (const l of landfalls || []) {
        markers.current.push(new maplibregl.Marker({ element: markerEl('landfall', t(lang, 'storm.map.landfall')), anchor: 'left' })
          .setLngLat([l.lon, l.lat]).addTo(m));
      }
      const b = new maplibregl.LngLatBounds();
      points.forEach(p => b.extend([p.lon, p.lat]));
      fcFeats.forEach(f => (f.geometry.type === 'Point' ? b.extend(f.geometry.coordinates) : f.geometry.coordinates.forEach(c => b.extend(c))));
      if (!b.isEmpty()) m.fitBounds(b, { padding: 60, maxZoom: 6.5, duration: 0 });
    };
    if (ready.current) apply(); else m.once('cnx-ready', apply);
  }, [points, forecastGeo, landfalls, lang]);

  // Selected moment
  useEffect(() => {
    const m = map.current;
    const apply = () => {
      const p = points[selected];
      m.getSource('sel').setData(p ? { type: 'Feature', geometry: { type: 'Point', coordinates: [p.lon, p.lat] }, properties: {} } : EMPTY);
      m.getSource('gale').setData(galeArea || EMPTY);
    };
    if (ready.current) apply(); else m.once('cnx-ready', apply);
  }, [selected, galeArea, points]);

  return <div ref={el} className="storm-map" />;
}
