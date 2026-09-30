import React, { useEffect, useState } from 'react';
import { t } from '../i18n/translations';
import { useData } from '../context/DataContext';
import { api } from '../services/api';
import { IMD_COLORS, SOURCE_LABELS, isOfficial, isWatch } from '../types/cyclone';

function TrackTable({ system, geojson, lang }) {
  const nodes = (geojson?.features || []).filter(f => f.properties.type === 'forecast_node');
  const groups = nodes.reduce((acc, n) => {
    (acc[n.properties.source] = acc[n.properties.source] || []).push(n);
    return acc;
  }, {});
  const base = new Date(system.observation_time).getTime();
  const valid = h => new Date(base + h * 3600e3).toISOString().slice(5, 16).replace('T', ' ');

  if (!nodes.length) return <p className="empty-note">{t(lang, 'forecastPage.none')}</p>;
  return Object.entries(groups).map(([source, list]) => (
    <div key={source} className="track-group">
      <h4>{source === 'AI_SATELLITE' ? t(lang, 'forecastPage.ai') : `${t(lang, 'forecastPage.official')} · ${SOURCE_LABELS[source] || source}`}</h4>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>{t(lang, 'forecastPage.hour')}</th><th>{t(lang, 'forecastPage.valid')}</th>
              <th>{t(lang, 'forecastPage.position')}</th><th>{t(lang, 'forecastPage.wind')}</th><th>{t(lang, 'forecastPage.category')}</th>
            </tr>
          </thead>
          <tbody>
            {list.sort((a, b) => a.properties.hour - b.properties.hour).map(n => (
              <tr key={n.properties.hour}>
                <td>+{n.properties.hour} h</td>
                <td>{valid(n.properties.hour)}</td>
                <td>{n.geometry.coordinates[1].toFixed(1)}° N, {n.geometry.coordinates[0].toFixed(1)}° E</td>
                <td>{Number(n.properties.wind_kmh).toFixed(0)} km/h</td>
                <td><span className="cat-chip" style={{ background: IMD_COLORS[n.properties.category] }}>{n.properties.category}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  ));
}

export default function ForecastPage() {
  const { lang, systems } = useData();
  const official = systems.filter(s => isOfficial(s) && !isWatch(s));
  const [tracks, setTracks] = useState({});

  useEffect(() => {
    let cancelled = false;
    Promise.all(official.map(s => api.getCycloneForecast(s.cyclone_id).then(g => [s.cyclone_id, g]).catch(() => [s.cyclone_id, null])))
      .then(entries => { if (!cancelled) setTracks(Object.fromEntries(entries)); });
    return () => { cancelled = true; };
  }, [official.map(s => `${s.cyclone_id}@${s.observation_time}`).join(',')]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="page">
      <h2 className="page-title">{t(lang, 'forecastPage.title')}</h2>
      {official.length === 0 && <div className="panel"><p className="empty-note">{t(lang, 'forecastPage.noSystems')}</p></div>}
      {official.map(s => (
        <div className="panel" key={s.cyclone_id}>
          <div className="panel-header">
            <h3>{s.cyclone_name || s.cyclone_id} <span className="muted-small">· {s.imd_category} · {SOURCE_LABELS[s.source]}</span></h3>
          </div>
          <TrackTable system={s} geojson={tracks[s.cyclone_id]} lang={lang} />
        </div>
      ))}
    </div>
  );
}
