import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Wind, ThermometerSun, Droplets, Gauge, CloudRain, ArrowRight } from 'lucide-react';
import { t } from '../i18n/translations';
import { useData } from '../context/DataContext';
import { IMD_COLORS, isOfficial, isWatch } from '../types/cyclone';
import { fetchPointConditions } from '../services/weatherService';

const fmt = (v, digits, unit) => (v == null ? '—' : `${Number(v).toFixed(digits)} ${unit}`);

/** Forecast nodes of the preferred source: official first, AI only if no official track. */
export function pickForecast(geojson) {
  const nodes = (geojson?.features || []).filter(f => f.properties.type === 'forecast_node');
  const official = nodes.filter(n => String(n.properties.source).startsWith('OFFICIAL_'));
  const list = official.length ? official : nodes;
  return { nodes: list.sort((a, b) => a.properties.hour - b.properties.hour), official: official.length > 0 };
}

export default function BottomPanels({ cyclone, forecastGeoJSON }) {
  const { lang } = useData();
  const [cond, setCond] = useState(null);
  const [condError, setCondError] = useState(false);

  useEffect(() => {
    if (!cyclone) return undefined;
    let cancelled = false;
    setCond(null);
    setCondError(false);
    fetchPointConditions(Number(cyclone.current_lat), Number(cyclone.current_lon))
      .then(c => { if (!cancelled) setCond(c); })
      .catch(() => { if (!cancelled) setCondError(true); });
    return () => { cancelled = true; };
  }, [cyclone?.cyclone_id, cyclone?.current_lat, cyclone?.current_lon]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!cyclone) return null;
  const official = isOfficial(cyclone) && !isWatch(cyclone);
  const { nodes, official: officialTrack } = pickForecast(forecastGeoJSON);
  const base = new Date(cyclone.observation_time);
  const at = h => new Date(base.getTime() + h * 3600e3).toLocaleString(lang, {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'UTC',
  });
  const currentWind = Number(cyclone.sustained_wind_kmh) || 0;
  const peakWind = Math.max(currentWind, ...nodes.map(n => Number(n.properties.wind_kmh) || 0), 1);

  return (
    <div className="bottom-panels">
      {/* 1. Forecast track */}
      <div className="panel">
        <div className="panel-header">
          <h3>{officialTrack ? t(lang, 'forecastPage.official') : t(lang, 'forecast.title')}</h3>
          <Link className="view-link" to="/forecast">{t(lang, 'forecast.viewTable')} <ArrowRight size={14} /></Link>
        </div>
        {nodes.length === 0 ? (
          <p className="empty-note">{t(lang, 'forecastPage.none')}</p>
        ) : (
          <div className="forecast-table">
            <div className="forecast-row">
              <div className="forecast-dot" style={{ background: IMD_COLORS[cyclone.imd_category] || '#94a3b8' }} />
              <div className="forecast-label">{t(lang, 'forecast.current')}</div>
              <div className="forecast-time">{at(0)}</div>
              <div className="forecast-coords">{Number(cyclone.current_lat).toFixed(1)}° N, {Number(cyclone.current_lon).toFixed(1)}° E</div>
            </div>
            {nodes.map(n => (
              <div className="forecast-row" key={`${n.properties.source}-${n.properties.hour}`}>
                <div className="forecast-dot" style={{ background: IMD_COLORS[n.properties.category] || '#94a3b8' }} />
                <div className="forecast-label">+{n.properties.hour} {t(lang, 'forecast.hours')}</div>
                <div className="forecast-time">{at(n.properties.hour)}</div>
                <div className="forecast-coords">
                  {n.geometry.coordinates[1].toFixed(1)}° N, {n.geometry.coordinates[0].toFixed(1)}° E
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 2. Intensity */}
      <div className="panel">
        <div className="panel-header">
          <h3>{t(lang, 'intensity.title')}</h3>
        </div>
        {official ? (
          <>
            <div className="intensity-chart intensity-bars">
              <div className="chart-peak">
                <div className="peak-label">{t(lang, 'intensity.peak')}</div>
                <div className="peak-value">{peakWind.toFixed(0)} km/h</div>
              </div>
              {[{ hour: 0, wind: currentWind, cat: cyclone.imd_category },
                ...nodes.map(n => ({ hour: n.properties.hour, wind: Number(n.properties.wind_kmh) || 0, cat: n.properties.category }))]
                .map(b => (
                  <div key={b.hour} className="intensity-bar" title={`+${b.hour} h · ${b.wind.toFixed(0)} km/h · ${b.cat}`}
                    style={{ height: `${(b.wind / peakWind) * 100}%`, background: IMD_COLORS[b.cat] || '#94a3b8' }} />
                ))}
            </div>
            <div className="chart-summary">
              <div className="chart-summary-item">
                <Wind />
                <div className="cs-value">{currentWind.toFixed(0)} km/h</div>
                <div className="cs-label">{t(lang, 'intensity.windLabel')}</div>
              </div>
              <div className="chart-summary-item">
                <Gauge />
                <div className="cs-value">{Number(cyclone.central_pressure_hpa).toFixed(0)} hPa</div>
                <div className="cs-label">{t(lang, 'intensity.pressureLabel')}</div>
              </div>
              <div className="chart-summary-item">
                <div className="category-dot" style={{ background: IMD_COLORS[cyclone.imd_category] }} />
                <div className="cs-value">{cyclone.imd_category}</div>
                <div className="cs-label">{t(lang, 'intensity.category')}</div>
              </div>
            </div>
          </>
        ) : (
          <p className="empty-note">{t(lang, 'panel.watchNote')}</p>
        )}
      </div>

      {/* 3. Environmental conditions at the centre (Open-Meteo, live) */}
      <div className="panel">
        <div className="panel-header">
          <h3>{t(lang, 'env.atCentre')}</h3>
          <span className="muted-small">{t(lang, 'env.provider')}</span>
        </div>
        {condError ? (
          <p className="empty-note">{t(lang, 'env.unavailable')}</p>
        ) : (
          <div className="env-grid">
            <div className="env-item">
              <ThermometerSun />
              <div className="env-label">{t(lang, 'env.sst')}</div>
              <div className="env-value">{cond ? (cond.sstC == null ? t(lang, 'env.overLand') : fmt(cond.sstC, 1, '°C')) : '…'}</div>
            </div>
            <div className="env-item">
              <Droplets />
              <div className="env-label">{t(lang, 'env.humidity')}</div>
              <div className="env-value">{cond ? fmt(cond.humidityPct, 0, '%') : '…'}</div>
            </div>
            <div className="env-item">
              <CloudRain />
              <div className="env-label">{t(lang, 'env.rainToday')}</div>
              <div className="env-value">{cond ? fmt(cond.precipTodayMm, 1, 'mm') : '…'}</div>
            </div>
            <div className="env-item">
              <Gauge />
              <div className="env-label">{t(lang, 'env.pressure')}</div>
              <div className="env-value">{cond ? fmt(cond.mslpHpa, 0, 'hPa') : '…'}</div>
            </div>
            <div className="env-item">
              <Wind />
              <div className="env-label">{t(lang, 'env.surfaceWinds')}</div>
              <div className="env-value">{cond ? fmt(cond.windKmh, 0, 'km/h') : '…'}</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
