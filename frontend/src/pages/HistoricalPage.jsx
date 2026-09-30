import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { t } from '../i18n/translations';
import { useData } from '../context/DataContext';
import { api } from '../services/api';
import { IMD_COLORS } from '../types/cyclone';
import { compact, inr } from '../utils/site';

const EMPTY = { type: 'FeatureCollection', features: [] };

function trackGeoJSON(storm) {
  if (!storm) return EMPTY;
  const coords = storm.points.map(p => [Number(p.longitude), Number(p.latitude)]);
  return {
    type: 'FeatureCollection',
    features: [
      { type: 'Feature', geometry: { type: 'LineString', coordinates: coords }, properties: { kind: 'line' } },
      ...storm.points.map(p => ({ type: 'Feature', geometry: { type: 'Point', coordinates: [Number(p.longitude), Number(p.latitude)] },
        properties: { kind: 'point', grade: p.grade || '', time: p.iso_time, wind: p.wind_kt } })),
    ],
  };
}

const nf = (n, lang) => (n == null ? '—' : Number(n).toLocaleString(lang === 'hi' ? 'hi-IN' : 'en-IN'));

/** Track statistics, exposure and recorded losses of one past storm (backend /impact/storm/:sid). */
function StormImpact({ d, lang }) {
  const st = d.stats; const e = d.exposure; const r = d.recorded;
  const kmh = kt => (kt == null ? '—' : `${Math.round(kt * 1.852)} km/h`);
  return (
    <div className="panel storm-impact">
      <div className="panel-header"><h3>{d.name || r?.name || t(lang, 'historicalPage.unnamed')} ({d.season}) · {t(lang, 'hist.details')}</h3></div>
      <div className="impact-kv">
        <div><span>{t(lang, 'hist.duration')}</span><strong>{Math.round(st.duration_h / 24 * 10) / 10} {t(lang, 'hist.days')}</strong></div>
        <div><span>{t(lang, 'hist.distance')}</span><strong>{nf(st.distance_km, lang)} km</strong></div>
        <div><span>{t(lang, 'hist.peakWind')}</span><strong>{kmh(st.peak_wind_kt)}</strong></div>
        <div><span>{t(lang, 'hist.minPressure')}</span><strong>{st.min_pressure_hpa ?? '—'} hPa</strong></div>
        <div><span>{t(lang, 'hist.peakGrade')}</span><strong>{st.peak_grade || '—'}</strong></div>
        <div><span>{t(lang, 'hist.landfall')}</span><strong>{st.landfall ? `${st.landfall.lat.toFixed(1)}° N, ${st.landfall.lon.toFixed(1)}° E · ${kmh(st.landfall.wind_kt)}` : t(lang, 'hist.noLandfall')}</strong></div>
        <div><span>{t(lang, 'impact.x.peopleGale')}</span><strong>{compact(e.people_gale_zone, lang)}</strong></div>
        <div><span>{t(lang, 'impact.x.peopleCore')}</span><strong>{compact(e.people_core, lang)}</strong></div>
        <div><span>{t(lang, 'impact.deaths')}</span><strong>{r ? nf(r.deaths, lang) : t(lang, 'hist.notRecorded')}</strong></div>
        <div><span>{t(lang, 'impact.loss')}</span><strong>{r ? inr(r.damage_inr, lang) : t(lang, 'hist.notRecorded')}</strong></div>
      </div>
      {e.largest_towns.length > 0 && (
        <p className="impact-towns">
          <span>{t(lang, 'impact.towns')}:</span>
          {e.largest_towns.slice(0, 8).map(tn => <span key={`${tn.name}-${tn.min_distance_km}`} className={`town-chip ${tn.zone}`}>{tn.name}</span>)}
        </p>
      )}
      <p className="muted-small method-note">
        {r ? <>{r.deaths_note ? `${r.deaths_note}. ` : ''}<a href={r.source} target="_blank" rel="noopener noreferrer">{t(lang, 'impact.x.source')}</a> · </> : null}
        {t(lang, 'hist.exposureNote')}
      </p>
    </div>
  );
}

export default function HistoricalPage() {
  const { lang } = useData();
  const [seasons, setSeasons] = useState([]);
  const [season, setSeason] = useState(null);
  const [storms, setStorms] = useState([]);
  const [storm, setStorm] = useState(null);
  const [error, setError] = useState(null);
  const [impact, setImpact] = useState(null);
  const mapEl = useRef(null);
  const map = useRef(null);

  useEffect(() => {
    api.getSeasons().then(s => { setSeasons(s); setSeason((s.find(x => x.storms >= 3) || s[0])?.season ?? null); }).catch(e => setError(e.message));
  }, []);

  useEffect(() => {
    if (!season) return;
    setStorm(null);
    api.getStorms(season).then(setStorms).catch(e => setError(e.message));
  }, [season]);

  useEffect(() => {
    map.current = new maplibregl.Map({
      container: mapEl.current, style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [82, 15], zoom: 3.4, attributionControl: { compact: true },
      cooperativeGestures: window.matchMedia('(pointer: coarse)').matches,
    });
    map.current.on('load', () => {
      map.current.addSource('track', { type: 'geojson', data: EMPTY });
      map.current.addLayer({ id: 'track-line', type: 'line', source: 'track', filter: ['==', ['get', 'kind'], 'line'],
        paint: { 'line-color': '#f97316', 'line-width': 2.5 } });
      map.current.addLayer({ id: 'track-points', type: 'circle', source: 'track', filter: ['==', ['get', 'kind'], 'point'],
        paint: { 'circle-radius': 4, 'circle-stroke-width': 1, 'circle-stroke-color': '#fff',
          'circle-color': ['match', ['get', 'grade'], ...Object.entries(IMD_COLORS).flat(), '#94a3b8'] } });
    });
    return () => map.current.remove();
  }, []);

  const openStorm = async sid => {
    setImpact(null);
    api.getStormImpact(sid).then(setImpact).catch(() => {});
    const s = await api.getStorm(sid).catch(() => null);
    setStorm(s);
    const src = map.current?.getSource('track');
    if (src && s) {
      src.setData(trackGeoJSON(s));
      const b = new maplibregl.LngLatBounds();
      s.points.forEach(p => b.extend([Number(p.longitude), Number(p.latitude)]));
      map.current.fitBounds(b, { padding: 40, maxZoom: 6, duration: 800 });
    }
  };

  const fmtDate = iso => new Date(iso).toISOString().slice(0, 10);

  return (
    <div className="page">
      <h2 className="page-title">{t(lang, 'historicalPage.title')}</h2>
      <p className="page-subtitle">{t(lang, 'historicalPage.subtitle')}</p>
      {error && <p className="empty-note">{error}</p>}
      {storms.length > 0 && (() => {
        const kt = s => s.max_wind_kt || 0;
        const strongest = [...storms].sort((a, b) => kt(b) - kt(a))[0];
        return (
          <div className="season-summary">
            <div><strong>{storms.length}</strong><span>{t(lang, 'hist.systems')}</span></div>
            <div><strong>{storms.filter(s => kt(s) >= 34).length}</strong><span>{t(lang, 'hist.cyclones')}</span></div>
            <div><strong>{storms.filter(s => kt(s) >= 64).length}</strong><span>{t(lang, 'hist.severe')}</span></div>
            <div><strong>{strongest.name || t(lang, 'historicalPage.unnamed')}</strong>
              <span>{t(lang, 'hist.strongest')}{strongest.max_wind_kt ? ` · ${Math.round(strongest.max_wind_kt * 1.852)} km/h` : ''}</span></div>
          </div>
        );
      })()}
      <div className="historical-grid">
        <div className="panel">
          <div className="panel-header">
            <label>
              {t(lang, 'historicalPage.season')}{' '}
              <select className="lang-select" value={season ?? ''} onChange={e => setSeason(Number(e.target.value))}>
                {seasons.map(s => <option key={s.season} value={s.season}>{s.season} ({s.storms} {t(lang, 'historicalPage.storms')})</option>)}
              </select>
            </label>
          </div>
          <div className="table-scroll">
            <table className="data-table clickable">
              <thead>
                <tr>
                  <th>{t(lang, 'historicalPage.dates')}</th><th>Name</th><th>{t(lang, 'historicalPage.basin')}</th>
                  <th>{t(lang, 'historicalPage.peak')}</th><th>{t(lang, 'historicalPage.maxWind')}</th>
                </tr>
              </thead>
              <tbody>
                {storms.map(s => (
                  <tr key={s.sid} onClick={() => openStorm(s.sid)} className={storm?.sid === s.sid ? 'selected' : ''}>
                    <td>{fmtDate(s.start_time)} → {fmtDate(s.end_time)}</td>
                    <td>{s.name || t(lang, 'historicalPage.unnamed')}</td>
                    <td>{s.subbasin === 'AS' ? 'Arabian Sea' : s.subbasin === 'BB' ? 'Bay of Bengal' : s.subbasin || '—'}</td>
                    <td>{s.peak_grade ? <span className="cat-chip" style={{ background: IMD_COLORS[s.peak_grade] }}>{s.peak_grade}</span> : '—'}</td>
                    <td>{s.max_wind_kt != null ? `${Math.round(s.max_wind_kt * 1.852)} km/h` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="panel map-panel">
          <div className="panel-header">
            <h3>{storm ? `${storm.name || t(lang, 'historicalPage.unnamed')} (${storm.season}) · ${storm.points.length} ${t(lang, 'historicalPage.points')}`
              : t(lang, 'historicalPage.select')}</h3>
          </div>
          <div ref={mapEl} className="historical-map" />
        </div>
      </div>
      {impact && <StormImpact d={impact} lang={lang} />}
    </div>
  );
}
