import React from 'react';
import { Wind, Droplets, Gauge, CloudRain, Waves, Cloud, Umbrella } from 'lucide-react';
import { t } from '../../i18n/translations';
import { weatherInfo } from '../../utils/weatherCodes';

const DIRS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
const dirName = deg => (deg == null ? '' : DIRS[Math.round(deg / 45) % 8]);
const f = (v, d, u) => (v == null ? '—' : `${Number(v).toFixed(d)}${u}`);

/**
 * Weather report for one point (Open-Meteo, live): conditions now + 3-day forecast.
 * compact → map-click panel; otherwise the full "Check your area" version.
 */
export default function WeatherReport({ cond, lang, compact = false }) {
  if (!cond) return null;
  const now = weatherInfo(cond.weatherCode, lang);
  const NowIcon = now.Icon;
  const items = [
    [Droplets, t(lang, 'area.humidity'), f(cond.humidityPct, 0, '%')],
    [Wind, t(lang, 'home.wind'), `${f(cond.windKmh, 0, ' km/h')} ${dirName(cond.windDirDeg)}`],
    [Wind, t(lang, 'wx.gusts'), f(cond.gustKmh, 0, ' km/h')],
    [CloudRain, t(lang, 'home.rain'), f(cond.precipTodayMm, 1, ' mm')],
    [Gauge, t(lang, 'home.pressure'), f(cond.mslpHpa, 0, ' hPa')],
    cond.sstC != null ? [Waves, t(lang, 'home.seaTemp'), f(cond.sstC, 1, ' °C')] : [Cloud, t(lang, 'wx.clouds'), f(cond.cloudPct, 0, '%')],
  ];

  return (
    <div className={`wx${compact ? ' wx-compact' : ''}`}>
      <div className="wx-now">
        <NowIcon size={compact ? 34 : 46} className="wx-icon" />
        <div>
          <div className="wx-temp">{f(cond.temperatureC, 0, '°')}<span>C</span></div>
          <div className="wx-desc">{now.label}</div>
          <div className="wx-feels">{t(lang, 'wx.feels')} {f(cond.feelsLikeC, 0, '°C')}</div>
        </div>
      </div>

      <div className="wx-grid">
        {items.map(([Icon, label, value]) => (
          <div key={label} className="wx-item"><Icon size={15} /><span>{label}</span><strong>{value}</strong></div>
        ))}
      </div>

      {cond.outlook?.length > 0 && (
        <div className="wx-days">
          {cond.outlook.map((d, i) => {
            const w = weatherInfo(d.code, lang);
            const DayIcon = w.Icon;
            const label = i === 0 ? t(lang, 'wx.today')
              : new Date(`${d.date}T12:00:00`).toLocaleDateString(lang, { weekday: 'short' });
            return (
              <div key={d.date} className="wx-day" title={w.label}>
                <strong>{label}</strong>
                <DayIcon size={22} className="wx-icon" />
                <span className="wx-range">{f(d.maxTempC, 0, '°')} / {f(d.minTempC, 0, '°')}</span>
                {!compact && <span><Umbrella size={13} /> {f(d.rainChancePct, 0, '%')} · {f(d.rainMm, 0, ' mm')}</span>}
                {!compact && <span><Wind size={13} /> {f(d.gustKmh, 0, ' km/h')}</span>}
              </div>
            );
          })}
        </div>
      )}
      <p className="wx-src">{t(lang, 'wx.source')}</p>
    </div>
  );
}
