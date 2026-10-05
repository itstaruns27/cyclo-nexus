import React from 'react';
import { Link } from 'react-router-dom';
import { MapPin, Wind, Activity, Navigation, Clock, Satellite, CloudRain, AlertOctagon, ExternalLink } from 'lucide-react';
import { t } from '../i18n/translations';
import { fill } from '../i18n/strings_site';
import { useData } from '../context/DataContext';
import { showDemoBadge } from '../utils/site';
import { IMD_COLORS, IMD_SCALE, ALERT_COLORS, SOURCE_LABELS, isOfficial, isWatch } from '../types/cyclone';

const fmtTime = (iso, lang) => (iso ? new Date(iso).toLocaleString(lang, {
  day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'UTC', timeZoneName: 'short',
}) : '—');

function Row({ icon: Icon, label, value }) {
  return (
    <div className="detail-row">
      <Icon />
      <span className="label">{label}</span>
      <span className="value">{value}</span>
    </div>
  );
}

export default function CycloneDetails() {
  const { lang, systems, selected: c, select } = useData();

  if (!c) {
    return (
      <div className="cyclone-panel no-data-panel">
        <div className="no-data">
          <Activity />
          <h4>{t(lang, 'noData')}</h4>
          <p>{t(lang, 'noDataSub')}</p>
        </div>
      </div>
    );
  }

  const official = isOfficial(c) && !isWatch(c);
  const color = official ? (IMD_COLORS[c.imd_category] || '#94a3b8') : '#a855f7';
  const catLabel = IMD_SCALE.find(s => s.category === c.imd_category)?.label || c.imd_category;
  const title = c.cyclone_name || (official ? c.cyclone_id : t(lang, 'source.watch'));

  return (
    <div className="cyclone-panel">
      {systems.length > 1 && (
        <div className="system-tabs" role="tablist" aria-label={t(lang, 'panel.systems')}>
          {systems.map(s => (
            <button key={s.cyclone_id} role="tab" aria-selected={s.cyclone_id === c.cyclone_id}
              className={`system-tab${s.cyclone_id === c.cyclone_id ? ' active' : ''}${isWatch(s) ? ' watch' : ''}`}
              onClick={() => select(s.cyclone_id)}>
              {s.cyclone_name || (isWatch(s) ? t(lang, 'source.watch') : s.cyclone_id)}
            </button>
          ))}
        </div>
      )}

      <div className="cyclone-panel-header">
        <div className="cyclone-panel-live">
          <span className={`source-badge ${official ? 'official' : 'watch'}`}>
            {official ? t(lang, 'source.official') : `${t(lang, 'source.watch')} · ${t(lang, 'source.experimental')}`}
          </span>
          <span className="muted-small">{SOURCE_LABELS[c.source] || c.source}</span>
        </div>
        <h2 className="cyclone-name">{title}{showDemoBadge(c) && <span className="demo-badge">{t(lang, 'demo.badge')}</span>}</h2>
        {official && (
          <div className="cyclone-category-badge" style={{ backgroundColor: color + '22', color }}>
            {c.imd_category} · {catLabel}
          </div>
        )}
      </div>

      <div className="cyclone-panel-body">
        <Row icon={MapPin} label={t(lang, 'panel.location')}
          value={`${Number(c.current_lat).toFixed(1)}° N, ${Number(c.current_lon).toFixed(1)}° E${official ? '' : ' (±300 km)'}`} />
        <Row icon={Clock} label={t(lang, 'panel.observed')} value={fmtTime(c.observation_time, lang)} />
        {official && (
          <>
            <Row icon={Wind} label={t(lang, 'panel.windSpeed')} value={`${Number(c.sustained_wind_kmh).toFixed(0)} km/h`} />
            <Row icon={Activity} label={t(lang, 'panel.pressure')} value={`${Number(c.central_pressure_hpa).toFixed(0)} hPa`} />
            <Row icon={Navigation} label={t(lang, 'panel.movement')}
              value={c.movement ? `${c.movement.dir} · ${c.movement.speed} km/h` : t(lang, 'panel.noMovement')} />
          </>
        )}
        {!official && c.detection_confidence != null && (
          <Row icon={Satellite} label={t(lang, 'panel.score')} value={Number(c.detection_confidence).toFixed(2)} />
        )}
        {(c.ai_min_cloud_top_k != null || c.ai_max_rain_mmhr != null) && (
          <div className="satellite-box">
            <div className="satellite-box-title"><Satellite size={14} /> {t(lang, 'panel.satellite')}</div>
            <div className="satellite-box-grid">
              <span>{t(lang, 'panel.coldestTop')}</span>
              <strong>{c.ai_min_cloud_top_k != null ? `${Number(c.ai_min_cloud_top_k).toFixed(0)} K` : '—'}</strong>
              <span><CloudRain size={12} /> {t(lang, 'panel.peakRain')}</span>
              <strong>{c.ai_max_rain_mmhr != null ? `${Number(c.ai_max_rain_mmhr).toFixed(0)} mm/h` : '—'}</strong>
            </div>
            {c.ai_wind_kt != null && (
              <p className="satellite-est">{fill(t(lang, 'storm.kpi.satEst'), {
                w: Math.round(Number(c.ai_wind_kt) * 1.852), b: c.ai_wind_band_kt != null ? Math.round(Number(c.ai_wind_band_kt) * 1.852) : '—',
                g: c.ai_imd_category || '—' })}</p>
            )}
          </div>
        )}

        {!official && <p className="watch-note">{t(lang, 'panel.watchNote')}</p>}

        {c.alert_level && (
          <div className="alert-banner" style={{ borderColor: ALERT_COLORS[c.alert_level] }}>
            <div className="alert-banner-icon" style={{ color: ALERT_COLORS[c.alert_level] }}><AlertOctagon /></div>
            <div className="alert-banner-content">
              <h4 style={{ color: ALERT_COLORS[c.alert_level] }}>{c.alert_level}</h4>
              <p>{c.summary || t(lang, 'alert.alertText')}</p>
            </div>
          </div>
        )}
      </div>

      <div className="cyclone-panel-actions">
        {official && <Link className="btn btn-primary" to="/alerts">{t(lang, 'panel.viewAdvisory')} →</Link>}
        <Link className="btn btn-outline" to={`/storm/${encodeURIComponent(c.cyclone_id)}`}>{t(lang, 'alertsX.details')}</Link>
        <Link className="btn btn-outline" to="/forecast">{t(lang, 'panel.viewForecast')}</Link>
        {c.source_url && (
          <a className="btn btn-outline" href={c.source_url} target="_blank" rel="noopener noreferrer"
            title={t(lang, 'panel.viewSource')}>
            <ExternalLink size={16} />
          </a>
        )}
      </div>
    </div>
  );
}
