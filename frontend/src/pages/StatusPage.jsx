import React from 'react';
import { CheckCircle2, AlertTriangle, XCircle } from 'lucide-react';
import { t } from '../i18n/translations';
import { useData } from '../context/DataContext';

const SOURCES = [
  { name: 'ISRO MOSDAC — INSAT-3DS Imager L1C', use: 'Infrared / water-vapour imagery, every 30 min', url: 'https://mosdac.gov.in' },
  { name: 'NASA GPM IMERG Early (GES DISC)', use: 'Satellite rainfall rate, half-hourly (~4–6 h latency)', url: 'https://gpm.nasa.gov/data/imerg' },
  { name: 'JTWC', use: 'Official warnings, forecast tracks, formation alerts', url: 'https://www.metoc.navy.mil/jtwc/jtwc.html' },
  { name: 'NOAA IBTrACS', use: 'Best tracks (history) and provisional active storms', url: 'https://www.ncei.noaa.gov/products/international-best-track-archive' },
  { name: 'Open-Meteo', use: 'Point weather, sea-surface temperature, 10 m wind grid', url: 'https://open-meteo.com' },
  { name: 'NASA GIBS', use: 'Map imagery layers (true colour, rainfall, SST)', url: 'https://www.earthdata.nasa.gov/gibs' },
  { name: 'India Meteorological Department', use: 'Official authority for cyclone warnings in India', url: 'https://mausam.imd.gov.in' },
];

const fmt = (iso, lang) => (iso ? new Date(iso).toLocaleString(lang, { timeZone: 'UTC', dateStyle: 'medium', timeStyle: 'short' }) + ' UTC' : t(lang, 'statusPage.never'));

function StatusIcon({ ok, warn }) {
  if (ok) return <CheckCircle2 size={16} className="ok" />;
  if (warn) return <AlertTriangle size={16} className="warn" />;
  return <XCircle size={16} className="bad" />;
}

export default function StatusPage() {
  const { lang, health, offline } = useData();
  return (
    <div className="page">
      <h2 className="page-title">{t(lang, 'statusPage.title')}</h2>
      <div className="panel">
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>{t(lang, 'statusPage.component')}</th><th>{t(lang, 'statusPage.status')}</th>
                <th>{t(lang, 'statusPage.lastSuccess')}</th><th>{t(lang, 'statusPage.lastData')}</th><th>{t(lang, 'statusPage.message')}</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>{t(lang, 'statusPage.api')}</td>
                <td><StatusIcon ok={!offline} /> {offline ? 'offline' : health?.status}</td>
                <td colSpan={2}>{health ? fmt(health.timestamp, lang) : '—'}</td>
                <td>{t(lang, 'statusPage.database')}: {health?.database || '—'}</td>
              </tr>
              {(health?.components || []).map(c => (
                <tr key={c.component}>
                  <td>{t(lang, `banner.${c.component}`)}</td>
                  <td><StatusIcon ok={c.status === 'ok' && !c.stale} warn={c.status === 'degraded' || (c.status === 'ok' && c.stale)} />{' '}
                    {c.status}{c.stale ? ` · ${t(lang, 'statusPage.stale')}` : ''}</td>
                  <td>{fmt(c.last_success_at, lang)}</td>
                  <td>{c.last_data_time ? fmt(c.last_data_time, lang) : '—'}</td>
                  <td className="wrap">{c.message || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <h3 className="section-title">{t(lang, 'statusPage.sources')}</h3>
      <div className="panel">
        <ul className="source-list">
          {SOURCES.map(s => (
            <li key={s.name}>
              <a href={s.url} target="_blank" rel="noopener noreferrer"><strong>{s.name}</strong></a>
              <span>{s.use}</span>
            </li>
          ))}
        </ul>
      </div>

      <h3 className="section-title">{t(lang, 'statusPage.validation')}</h3>
      <div className="panel"><p className="empty-note">{t(lang, 'statusPage.validationText')}</p></div>
    </div>
  );
}
