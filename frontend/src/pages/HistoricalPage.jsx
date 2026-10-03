import React, { useEffect, useMemo, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { Link } from 'react-router-dom';
import { Search, ChevronLeft, ChevronRight, ArrowRight, Wind } from 'lucide-react';
import { t } from '../i18n/translations';
import { useData } from '../context/DataContext';
import { api, API_BASE } from '../services/api';
import { IMD_COLORS, IMD_SCALE } from '../types/cyclone';

/**
 * Past storms (IBTrACS North Indian Ocean, 1980 → today): search any storm by name, browse a season
 * as cards, see all of the season's tracks on one map. Every storm opens its full page (/storm/:sid).
 */
const EMPTY = { type: 'FeatureCollection', features: [] };
const KMH = 1.852;
const basinName = (b, lang) => t(lang, `storm.basin.${b === 'AS' ? 'AS' : b === 'BB' ? 'BOB' : 'NIO'}`);
const fmt = (iso, lang) => new Date(iso).toLocaleDateString(lang === 'hi' ? 'hi-IN' : 'en-IN', { day: 'numeric', month: 'short', timeZone: 'UTC' });
const catLabel = g => IMD_SCALE.find(c => c.category === g)?.label || '';

function useStormSearch(q) {
  const [res, setRes] = useState([]);
  useEffect(() => {
    if (q.trim().length < 2) { setRes([]); return undefined; }
    const id = setTimeout(() => {
      fetch(`${API_BASE}/historical/search?q=${encodeURIComponent(q.trim())}`).then(r => r.json()).then(b => setRes(b.data || [])).catch(() => setRes([]));
    }, 220);
    return () => clearTimeout(id);
  }, [q]);
  return res;
}

export default function HistoricalPage() {
  const { lang } = useData();
  const [seasons, setSeasons] = useState([]);
  const [season, setSeason] = useState(null);
  const [storms, setStorms] = useState([]);
  const [tracks, setTracks] = useState({});
  const [hover, setHover] = useState(null);
  const [q, setQ] = useState('');
  const results = useStormSearch(q);
  const mapEl = useRef(null);
  const map = useRef(null);
  const ready = useRef(false);

  useEffect(() => {
    api.getSeasons().then(s => { setSeasons(s); setSeason((s.find(x => x.storms >= 3) || s[0])?.season ?? null); }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!season) return;
    setStorms([]);
    setTracks({});
    api.getStorms(season).then(list => {
      setStorms(list);
      Promise.all(list.map(s => api.getStorm(s.sid).then(d => [s.sid, d]).catch(() => [s.sid, null])))
        .then(pairs => setTracks(Object.fromEntries(pairs.filter(p => p[1]))));
    }).catch(() => {});
  }, [season]);

  useEffect(() => {
    const m = new maplibregl.Map({
      container: mapEl.current, style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [80, 15], zoom: 3.3, attributionControl: { compact: true },
      cooperativeGestures: window.matchMedia('(pointer: coarse)').matches,
    });
    map.current = m;
    m.on('load', () => {
      m.addSource('tracks', { type: 'geojson', data: EMPTY });
      m.addLayer({ id: 'seg', type: 'line', source: 'tracks', layout: { 'line-cap': 'round' },
        paint: { 'line-color': ['match', ['get', 'grade'], ...Object.entries(IMD_COLORS).flat(), '#64748b'],
          'line-width': ['case', ['get', 'hl'], 4.5, 2.2], 'line-opacity': ['case', ['get', 'dim'], 0.25, 0.95] } });
      ready.current = true;
      m.fire('cnx-ready');
    });
    return () => { ready.current = false; m.remove(); };
  }, []);

  const geo = useMemo(() => {
    const feats = [];
    for (const [sid, d] of Object.entries(tracks)) {
      const pts = d.points;
      for (let i = 0; i < pts.length - 1; i++) {
        feats.push({ type: 'Feature', properties: { sid, grade: pts[i].grade || '', hl: hover === sid, dim: hover != null && hover !== sid },
          geometry: { type: 'LineString', coordinates: [[Number(pts[i].longitude), Number(pts[i].latitude)], [Number(pts[i + 1].longitude), Number(pts[i + 1].latitude)]] } });
      }
    }
    return { type: 'FeatureCollection', features: feats };
  }, [tracks, hover]);

  useEffect(() => {
    const m = map.current;
    const apply = () => m.getSource('tracks')?.setData(geo);
    if (ready.current) apply(); else m?.once('cnx-ready', apply);
  }, [geo]);

  const idx = seasons.findIndex(s => s.season === season);
  const kt = s => s.max_wind_kt || 0;
  const strongest = storms.length ? [...storms].sort((a, b) => kt(b) - kt(a))[0] : null;

  return (
    <div className="history-page">
      <header className="alerts-hero">
        <div className="site-container">
          <h1>{t(lang, 'historicalPage.title')}</h1>
          <p>{t(lang, 'historicalPage.subtitle')}</p>
          <div className="storm-search">
            <Search size={18} />
            <input value={q} onChange={e => setQ(e.target.value)} placeholder={t(lang, 'hist2.search')} aria-label={t(lang, 'hist2.search')} />
            {results.length > 0 && (
              <ul className="search-results">
                {results.map(r => (
                  <li key={r.sid}>
                    <Link to={`/storm/${r.sid}`}>
                      <span className="sr-dot" style={{ background: IMD_COLORS[r.peak_grade] || '#94a3b8' }} />
                      <b>{r.name}</b><em>{r.season}</em>
                      <span>{r.peak_grade || '—'} · {r.max_wind_kt ? `${Math.round(r.max_wind_kt * KMH)} km/h` : '—'} · {basinName(r.subbasin, lang)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </header>

      <div className="site-container history-body">
        <div className="season-bar">
          <button type="button" className="icon-btn" disabled={idx >= seasons.length - 1} onClick={() => setSeason(seasons[idx + 1].season)} aria-label="Previous season"><ChevronLeft size={18} /></button>
          <select className="season-select" value={season ?? ''} onChange={e => setSeason(Number(e.target.value))} aria-label={t(lang, 'historicalPage.season')}>
            {seasons.map(s => <option key={s.season} value={s.season}>{s.season} · {s.storms} {t(lang, 'historicalPage.storms')}</option>)}
          </select>
          <button type="button" className="icon-btn" disabled={idx <= 0} onClick={() => setSeason(seasons[idx - 1].season)} aria-label="Next season"><ChevronRight size={18} /></button>
          {storms.length > 0 && (
            <div className="season-stats">
              <span><b>{storms.length}</b> {t(lang, 'hist.systems')}</span>
              <span><b>{storms.filter(s => kt(s) >= 34).length}</b> {t(lang, 'hist.cyclones')}</span>
              <span><b>{storms.filter(s => kt(s) >= 64).length}</b> {t(lang, 'hist.severe')}</span>
              {strongest && <span>{t(lang, 'hist.strongest')}: <b>{strongest.name || t(lang, 'historicalPage.unnamed')}</b></span>}
            </div>
          )}
        </div>

        <div className="history-grid">
          <div className="storm-cards">
            {storms.map(s => (
              <Link key={s.sid} to={`/storm/${s.sid}`} className={`storm-card${hover === s.sid ? ' hl' : ''}`}
                style={{ '--cat': IMD_COLORS[s.peak_grade] || '#94a3b8' }}
                onMouseEnter={() => setHover(s.sid)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(s.sid)} onBlur={() => setHover(null)}>
                <span className="sc-bar" />
                <div className="stc-main">
                  <strong>{s.name || t(lang, 'historicalPage.unnamed')}</strong>
                  <span>{fmt(s.start_time, lang)} → {fmt(s.end_time, lang)} · {basinName(s.subbasin, lang)}</span>
                </div>
                <div className="stc-side">
                  {s.peak_grade && <span className="cat-badge" style={{ '--cat': IMD_COLORS[s.peak_grade] }} title={catLabel(s.peak_grade)}>{s.peak_grade}</span>}
                  <span className="stc-wind"><Wind size={13} /> {s.max_wind_kt ? `${Math.round(s.max_wind_kt * KMH)} km/h` : '—'}</span>
                </div>
                <ArrowRight size={16} className="stc-go" />
              </Link>
            ))}
          </div>
          <div className="history-map-card">
            <div ref={mapEl} className="history-map" />
            <ul className="map-key">
              {IMD_SCALE.map(c => <li key={c.category}><i style={{ background: IMD_COLORS[c.category] }} />{c.category}</li>)}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
