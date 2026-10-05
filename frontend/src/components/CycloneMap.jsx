import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import { applyIndiaBoundaries } from '../utils/indiaBoundaries';
import 'maplibre-gl/dist/maplibre-gl.css';
import { t } from '../i18n/translations';
import { useData } from '../context/DataContext';
import { isOfficial, isWatch, IMD_COLORS, CONSENSUS_COLOR } from '../types/cyclone';
import WindParticleCanvas from './WindParticleCanvas';
import WeatherInspector from './WeatherInspector';
import CycloneChancePanel from './site/CycloneChancePanel';

const MAP_TABS = ['satellite', 'predictedTrack', 'windFlow', 'rainfall', 'seaTemp'];
const EMPTY = { type: 'FeatureCollection', features: [] };
const WATCH_RADIUS_KM = 300;

// NASA GIBS WMTS layers (free, no key). Rain and SST use time 'default' = latest published
// (daily products lag ~2 days, so a fixed 'yesterday' date 404s); rain is the 30-min IMERG layer.
const GIBS_LAYERS = {
  satellite: {
    url: 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_SNPP_CorrectedReflectance_TrueColor/default/{time}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg',
    maxzoom: 9, opacity: 0.75,
  },
  rainfall: {
    url: 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/IMERG_Precipitation_Rate_30min/default/default/GoogleMapsCompatible_Level6/{z}/{y}/{x}.png',
    maxzoom: 6, opacity: 0.85,
  },
  seaTemp: {
    url: 'https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/GHRSST_L4_MUR_Sea_Surface_Temperature/default/default/GoogleMapsCompatible_Level7/{z}/{y}/{x}.png',
    maxzoom: 7, opacity: 0.8,
  },
};

function gibsDate() {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - 1); // daily composites are complete for yesterday
  return d.toISOString().split('T')[0];
}

/** 64-vertex polygon approximating a circle of radius km (for watch-area uncertainty). */
function circlePolygon(lat, lon, km) {
  const coords = [];
  for (let i = 0; i <= 64; i++) {
    const a = (i / 64) * 2 * Math.PI;
    const dLat = (km / 111.32) * Math.cos(a);
    const dLon = (km / (111.32 * Math.cos((lat * Math.PI) / 180))) * Math.sin(a);
    coords.push([lon + dLon, lat + dLat]);
  }
  return { type: 'Polygon', coordinates: [coords] };
}

function systemsGeoJSON(systems) {
  const features = [];
  for (const s of systems) {
    const lat = Number(s.current_lat); const lon = Number(s.current_lon);
    const watch = isWatch(s) || !isOfficial(s);
    if (watch) {
      features.push({ type: 'Feature', geometry: circlePolygon(lat, lon, WATCH_RADIUS_KM),
        properties: { kind: 'watch_area', cyclone_id: s.cyclone_id } });
    }
    features.push({ type: 'Feature', geometry: { type: 'Point', coordinates: [lon, lat] },
      properties: { kind: watch ? 'watch_point' : 'official_point', cyclone_id: s.cyclone_id,
        name: s.cyclone_name || s.cyclone_id, category: s.imd_category, wind_kmh: Math.round(s.sustained_wind_kmh) } });
  }
  return { type: 'FeatureCollection', features };
}

/** Spinning cyclone symbol (demo): spiral arms + eye, sized and coloured by intensity. */
function stormElement(s, onClick) {
  const official = isOfficial(s) && !isWatch(s);
  const wind = Number(s.sustained_wind_kmh) || 0;
  const size = official ? Math.round(46 + Math.min(wind, 200) * 0.28) : 40;
  const color = official ? (IMD_COLORS[s.imd_category] || '#ef4444') : '#a855f7';
  const spin = official ? Math.max(1.6, 6 - wind / 40) : 7; // stronger storm spins faster
  const el = document.createElement('div');
  el.className = `storm-marker${official ? '' : ' watch'}`;
  el.style.setProperty('--size', `${size}px`);
  el.style.setProperty('--color', color);
  el.style.setProperty('--spin', `${spin}s`);
  el.title = s.cyclone_name || (official ? s.cyclone_id : 'Possible new storm');
  const arm = 'M50 50 C 50 28, 68 14, 92 18 C 74 22, 60 34, 58 50 Z';
  el.innerHTML = `
    <span class="storm-pulse"></span>
    <svg class="storm-spiral" viewBox="0 0 100 100" aria-hidden="true">
      <defs><radialGradient id="g-${s.cyclone_id}"><stop offset="0" stop-color="#fff" stop-opacity=".95"/>
        <stop offset=".55" stop-color="${color}" stop-opacity=".9"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></radialGradient></defs>
      <circle cx="50" cy="50" r="46" fill="url(#g-${s.cyclone_id})" opacity=".35"/>
      ${[0, 120, 240].map(r => `<path d="${arm}" fill="${color}" transform="rotate(${r} 50 50)" opacity=".92"/>`).join('')}
      <circle cx="50" cy="50" r="${official ? 8 : 6}" fill="#0f172a" stroke="#fff" stroke-width="3"/>
    </svg>
    ${official ? `<span class="storm-label">${s.cyclone_name || s.cyclone_id}</span>` : ''}`;
  el.addEventListener('click', e => { e.stopPropagation(); onClick(s.cyclone_id); });
  return el;
}

export default function CycloneMap({ forecastGeoJSON, systems, selected, tabs = MAP_TABS, legend = true, inspector = 'expert' }) {
  const { lang, health, offline, select } = useData();
  const container = useRef(null);
  const [map, setMap] = useState(null);
  const [activeTab, setActiveTab] = useState(tabs[0]);
  const [inspect, setInspect] = useState(null);
  const [rainTime, setRainTime] = useState(null);

  // Rain: pin every tile to the newest IMERG half-hour GIBS has (DescribeDomains), so all tiles show
  // the same moment and the map can say which moment that is (IMERG Early runs ~4–6 h behind real time).
  useEffect(() => {
    if (!map) return undefined;
    let cancelled = false;
    const now = new Date();
    const from = new Date(now.getTime() - 3 * 86400e3).toISOString().slice(0, 10);
    fetch('https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/wmts.cgi?SERVICE=WMTS&REQUEST=DescribeDomains&VERSION=1.0.0'
      + `&LAYER=IMERG_Precipitation_Rate_30min&TILEMATRIXSET=2km&TIME=${from}/${now.toISOString().slice(0, 19)}Z`)
      .then(r => r.text())
      .then(xml => {
        const m = xml.match(/\/(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ)\/PT30M/);
        if (!m || cancelled) return;
        const src = map.getSource('gibs-rainfall');
        if (src?.setTiles) src.setTiles([GIBS_LAYERS.rainfall.url.replace('/default/default/', `/default/${m[1]}/`)]);
        setRainTime(m[1]);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [map]);

  // Create the map once
  useEffect(() => {
    const touch = window.matchMedia('(pointer: coarse)').matches;
    const m = new maplibregl.Map({
      container: container.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [80.0, 14.0],
      zoom: 3.6,
      // The visible area never leaves the wind grid (backend wind_grid.js BBOX: 20–130°E, 20°S–40°N),
      // so the particle layer always covers the whole map on any screen width.
      maxBounds: [[20, -20], [130, 40]],
      attributionControl: { compact: true },
      cooperativeGestures: touch, // one-finger page scroll on phones; two fingers pan the map
    });
    m.addControl(new maplibregl.NavigationControl(), 'top-left');
    m.addControl(new maplibregl.FullscreenControl(), 'bottom-right');

    m.on('load', () => {
      applyIndiaBoundaries(m);
      const date = gibsDate();
      for (const [key, cfg] of Object.entries(GIBS_LAYERS)) {
        m.addSource(`gibs-${key}`, { type: 'raster', tiles: [cfg.url.replace('{time}', date)], tileSize: 256,
          maxzoom: cfg.maxzoom, attribution: 'NASA GIBS' });
        m.addLayer({ id: `gibs-${key}`, type: 'raster', source: `gibs-${key}`,
          layout: { visibility: key === 'satellite' ? 'visible' : 'none' }, paint: { 'raster-opacity': cfg.opacity } });
      }

      m.addSource('systems', { type: 'geojson', data: EMPTY });
      m.addSource('tracks', { type: 'geojson', data: EMPTY });

      m.addLayer({ id: 'watch-area', type: 'fill', source: 'systems', filter: ['==', ['get', 'kind'], 'watch_area'],
        paint: { 'fill-color': '#a855f7', 'fill-opacity': 0.12 } });
      m.addLayer({ id: 'watch-area-line', type: 'line', source: 'systems', filter: ['==', ['get', 'kind'], 'watch_area'],
        paint: { 'line-color': '#a855f7', 'line-width': 1.5, 'line-dasharray': [2, 2] } });
      m.addLayer({ id: 'forecast-cone', type: 'fill', source: 'tracks', filter: ['==', ['get', 'type'], 'forecast_cone'],
        paint: { 'fill-color': ['case', ['==', ['get', 'source'], 'AI_CONSENSUS'], CONSENSUS_COLOR, '#f97316'],
          'fill-opacity': ['case', ['==', ['get', 'source'], 'AI_CONSENSUS'], 0.08, 0.13] } });
      m.addLayer({ id: 'forecast-cone-line', type: 'line', source: 'tracks', filter: ['==', ['get', 'type'], 'forecast_cone'],
        paint: { 'line-color': ['case', ['==', ['get', 'source'], 'AI_CONSENSUS'], CONSENSUS_COLOR, '#f97316'], 'line-width': 1, 'line-opacity': 0.55 } });
      m.addLayer({ id: 'history-line', type: 'line', source: 'tracks', filter: ['==', ['get', 'type'], 'history_track'],
        paint: { 'line-color': '#cbd5e1', 'line-width': 2 } });
      m.addLayer({ id: 'official-track', type: 'line', source: 'tracks',
        filter: ['all', ['==', ['get', 'type'], 'forecast_track'], ['!', ['in', ['get', 'source'], ['literal', ['AI_SATELLITE', 'AI_CONSENSUS']]]]],
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': '#f97316', 'line-width': 3, 'line-dasharray': [3, 2] } });
      m.addLayer({ id: 'consensus-track', type: 'line', source: 'tracks',
        filter: ['all', ['==', ['get', 'type'], 'forecast_track'], ['==', ['get', 'source'], 'AI_CONSENSUS']],
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': CONSENSUS_COLOR, 'line-width': 2.5, 'line-dasharray': [1.5, 1.5] } });
      m.addLayer({ id: 'ai-track', type: 'line', source: 'tracks',
        filter: ['all', ['==', ['get', 'type'], 'forecast_track'], ['==', ['get', 'source'], 'AI_SATELLITE']],
        paint: { 'line-color': '#a855f7', 'line-width': 2, 'line-dasharray': [1, 2] } });
      m.addLayer({ id: 'forecast-nodes', type: 'circle', source: 'tracks', filter: ['==', ['get', 'type'], 'forecast_node'],
        paint: {
          'circle-radius': 5,
          'circle-color': ['match', ['get', 'category'],
            'D', '#60a5fa', 'DD', '#34d399', 'CS', '#fbbf24', 'SCS', '#fb923c', 'VSCS', '#f87171', 'ESCS', '#c084fc',
            'SuCS', '#f472b6', '#94a3b8'],
          'circle-stroke-width': 1.5, 'circle-stroke-color': '#ffffff',
        } });
      m.addLayer({ id: 'watch-point', type: 'circle', source: 'systems', filter: ['==', ['get', 'kind'], 'watch_point'],
        paint: { 'circle-radius': 6, 'circle-opacity': 0, 'circle-stroke-opacity': 0 } }); // drawn by animated markers
      m.addLayer({ id: 'official-point', type: 'circle', source: 'systems', filter: ['==', ['get', 'kind'], 'official_point'],
        paint: { 'circle-radius': 10, 'circle-opacity': 0, 'circle-stroke-opacity': 0 } }); // drawn by animated markers

      for (const layer of ['official-point', 'watch-point']) {
        m.on('click', layer, e => {
          e.preventDefault();
          select(e.features[0].properties.cyclone_id);
        });
        m.on('mouseenter', layer, () => { m.getCanvas().style.cursor = 'pointer'; });
        m.on('mouseleave', layer, () => { m.getCanvas().style.cursor = ''; });
      }
      m.on('click', e => {
        if (e.defaultPrevented) return;
        setInspect({ lng: e.lngLat.lng, lat: e.lngLat.lat });
      });
      setMap(m);
    });

    // Keep the map canvas matched to its (flex-sized) container
    const ro = new ResizeObserver(() => m.resize());
    ro.observe(container.current);
    return () => { ro.disconnect(); setMap(null); m.remove(); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // All active systems
  useEffect(() => {
    if (map?.style) map.getSource('systems')?.setData(systemsGeoJSON(systems || []));
  }, [map, systems]);

  // Animated storm markers
  useEffect(() => {
    if (!map) return undefined;
    const markers = (systems || []).map(s => new maplibregl.Marker({ element: stormElement(s, select) })
      .setLngLat([Number(s.current_lon), Number(s.current_lat)]).addTo(map));
    return () => markers.forEach(m => m.remove());
  }, [map, systems]); // eslint-disable-line react-hooks/exhaustive-deps

  // Tracks of the selected system
  useEffect(() => {
    if (!map?.style) return;
    map.getSource('tracks')?.setData(forecastGeoJSON || EMPTY);
  }, [map, forecastGeoJSON]);

  // Fly to the selected system
  useEffect(() => {
    if (!map?.style || !selected) return;
    map.flyTo({ center: [Number(selected.current_lon), Number(selected.current_lat)], zoom: 4.8, duration: 1200 });
  }, [map, selected?.cyclone_id]); // eslint-disable-line react-hooks/exhaustive-deps

  // Tabs: one GIBS layer at a time (none for track-only / wind views)
  useEffect(() => {
    if (!map?.style) return;
    for (const key of Object.keys(GIBS_LAYERS)) {
      map.setLayoutProperty(`gibs-${key}`, 'visibility', key === activeTab ? 'visible' : 'none');
    }
  }, [map, activeTab]);

  const satellite = health?.components?.find(c => c.component === 'satellite_pipeline');
  const status = offline ? 'offline' : satellite && !satellite.stale ? 'live' : 'delayed';

  return (
    <div className="map-section">
      <div className="map-tabs" role="tablist">
        {tabs.map(tab => (
          <button key={tab} role="tab" aria-selected={activeTab === tab}
            className={`map-tab${activeTab === tab ? ' active' : ''}`} onClick={() => setActiveTab(tab)}>
            {t(lang, `map.${tab}`)}
          </button>
        ))}
      </div>
      <div className="map-container">
        <div ref={container} className="map-canvas" />
        <WindParticleCanvas map={map} active={activeTab === 'windFlow'} />
        {inspect && (inspector === 'public'
          ? <CycloneChancePanel lngLat={inspect} onClose={() => setInspect(null)} />
          : <WeatherInspector lngLat={inspect} onClose={() => setInspect(null)} />)}
        {activeTab === 'rainfall' && (
          <div className="rain-key">
            <strong>{t(lang, 'map.rainNow')}</strong>
            {rainTime && <span>{new Date(rainTime).toLocaleString(lang === 'hi' ? 'hi-IN' : 'en-IN', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'UTC' })} UTC · NASA IMERG</span>}
            <div className="rain-scale"><i /><b>0.5</b><b>2</b><b>10</b><b>50 mm/h</b></div>
            <small>{t(lang, 'map.rainNote')}</small>
          </div>
        )}
        {legend && <div className="map-legend">
          <div className="map-legend-item"><div className="map-legend-dot" style={{ background: '#ef4444' }} /><span>{t(lang, 'map.currentPos')}</span></div>
          <div className="map-legend-item"><div className="map-legend-line" style={{ background: '#cbd5e1' }} /><span>{t(lang, 'map.history')}</span></div>
          <div className="map-legend-item"><div className="map-legend-line" style={{ background: '#f97316' }} /><span>{t(lang, 'map.officialTrack')}</span></div>
          <div className="map-legend-item"><div className="map-legend-dot" style={{ background: '#f97316', opacity: 0.35, borderRadius: 2 }} /><span>{t(lang, 'map.cone')}</span></div>
          <div className="map-legend-item"><div className="map-legend-line" style={{ background: CONSENSUS_COLOR }} /><span>{t(lang, 'map.aiTrack')}</span></div>
          <div className="map-legend-item"><div className="map-legend-dot" style={{ background: '#a855f7', opacity: 0.6 }} /><span>{t(lang, 'map.watchArea')}</span></div>
          <div className="map-legend-hint">{t(lang, 'map.clickHint')}</div>
        </div>}
        {status !== 'delayed' && (
          <div className={`map-status ${status}`}>
            <div className="live-dot" />
            <span>{status === 'live' ? t(lang, 'map.liveData') : t(lang, `map.${status}`)}</span>
          </div>
        )}
      </div>
    </div>
  );
}
