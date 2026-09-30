import React from 'react';
import { Wind, Satellite, AlertTriangle, Clock } from 'lucide-react';
import { t } from '../i18n/translations';
import { useData } from '../context/DataContext';
import { isOfficial, isWatch, ALERT_COLORS } from '../types/cyclone';

const ALERT_RANK = { RED: 3, ORANGE: 2, YELLOW: 1 };

function formatAge(iso, lang) {
  if (!iso) return t(lang, 'stats.unknown');
  const minutes = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (minutes < 90) return `${minutes} min`;
  return `${(minutes / 60).toFixed(1)} h`;
}

export default function StatCards() {
  const { lang, systems, health } = useData();
  const official = systems.filter(s => isOfficial(s) && !isWatch(s));
  const watches = systems.filter(isWatch);
  const highest = systems.reduce((best, s) => (ALERT_RANK[s.alert_level] > (ALERT_RANK[best] || 0) ? s.alert_level : best), null);
  const satellite = health?.components?.find(c => c.component === 'satellite_pipeline');

  return (
    <div className="stat-cards">
      <div className="stat-card">
        <div className="stat-icon blue"><Wind /></div>
        <div className="stat-info">
          <p>{t(lang, 'stats.officialSystems')}</p>
          <h3>{official.length}</h3>
          <div className="stat-change neutral">{t(lang, 'stats.officialSub')}</div>
        </div>
      </div>

      <div className="stat-card">
        <div className="stat-icon purple"><Satellite /></div>
        <div className="stat-info">
          <p>{t(lang, 'stats.watchAreas')}</p>
          <h3>{watches.length}</h3>
          <div className="stat-change neutral">{t(lang, 'stats.watchSub')}</div>
        </div>
      </div>

      <div className="stat-card">
        <div className="stat-icon red"><AlertTriangle /></div>
        <div className="stat-info">
          <p>{t(lang, 'stats.highestAlert')}</p>
          <h3 style={{ color: highest ? ALERT_COLORS[highest] : undefined }}>{highest || t(lang, 'stats.noAlert')}</h3>
          <div className="stat-change neutral">{t(lang, 'stats.alertSub')}</div>
        </div>
      </div>

      <div className="stat-card">
        <div className="stat-icon green"><Clock /></div>
        <div className="stat-info">
          <p>{t(lang, 'stats.dataAge')}</p>
          <h3 className={satellite?.stale ? 'text-warn' : undefined}>{formatAge(satellite?.last_data_time, lang)}</h3>
          <div className="stat-change neutral">{t(lang, 'stats.ageSub')}</div>
        </div>
      </div>
    </div>
  );
}
