import React, { useEffect, useState } from 'react';
import { X, CheckCircle2, XCircle } from 'lucide-react';
import { t } from '../i18n/translations';
import { useData } from '../context/DataContext';
import { fetchPointConditions, genesisIndicators } from '../services/weatherService';

/** Point-conditions panel shown after clicking the map (v3 Micro-Task 4.1). One Open-Meteo request pair per click. */
export default function WeatherInspector({ lngLat, onClose }) {
  const { lang } = useData();
  const [state, setState] = useState({ loading: true });

  useEffect(() => {
    let cancelled = false;
    setState({ loading: true });
    fetchPointConditions(lngLat.lat, lngLat.lng)
      .then(cond => { if (!cancelled) setState({ cond, gi: genesisIndicators(cond) }); })
      .catch(() => { if (!cancelled) setState({ error: true }); });
    return () => { cancelled = true; };
  }, [lngLat.lat, lngLat.lng]);

  return (
    <div className="weather-inspector" role="dialog" aria-label={t(lang, 'inspector.title')}>
      <div className="wi-header">
        <strong>{t(lang, 'inspector.title')}</strong>
        <span className="muted-small">{lngLat.lat.toFixed(2)}° N, {lngLat.lng.toFixed(2)}° E</span>
        <button onClick={onClose} aria-label="Close"><X size={16} /></button>
      </div>
      {state.loading && <p className="muted-small">{t(lang, 'inspector.loading')}</p>}
      {state.error && <p className="muted-small">{t(lang, 'inspector.error')}</p>}
      {state.gi && (
        <>
          {state.gi.overLand ? (
            <p className="wi-land">{t(lang, 'inspector.land')}</p>
          ) : (
            <>
              <div className="wi-score">{state.gi.met} {t(lang, 'inspector.met')}</div>
              <div className="wi-sub">{t(lang, 'inspector.genesis')}</div>
            </>
          )}
          <ul className="wi-checks">
            {state.gi.checks.map(c => (
              <li key={c.key} className={c.ok ? 'ok' : 'no'}>
                {c.ok ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
                <span>{t(lang, `inspector.${c.key}`)}</span>
                <strong>{c.value == null ? '—' : `${Number(c.value).toFixed(1)} ${c.unit}`}</strong>
                <em>{c.threshold}</em>
              </li>
            ))}
          </ul>
          <p className="muted-small">{t(lang, 'inspector.note')} Open-Meteo · {state.cond.time || ''}</p>
        </>
      )}
    </div>
  );
}
