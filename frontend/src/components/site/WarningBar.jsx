import React from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, Satellite, WifiOff, Clock, ArrowRight } from 'lucide-react';
import { t } from '../../i18n/translations';
import { fill } from '../../i18n/strings_site';
import { useData } from '../../context/DataContext';
import { isWatch } from '../../types/cyclone';
import { catName, isActiveOfficial, rankSystems, seaName, showDemoBadge } from '../../utils/site';

/**
 * Site-wide warning strip shown above the navigation whenever there is something to act on:
 * one line per official system (strongest alert first), satellite watch areas, and data problems.
 * Renders nothing when all is clear.
 */
export default function WarningBar() {
  const { lang, systems, health, offline } = useData();
  const ranked = rankSystems(systems);
  const official = ranked.filter(isActiveOfficial);
  const watches = ranked.filter(isWatch);
  const satellite = health?.components?.find(c => c.component === 'satellite_pipeline');
  const official_feed = health?.components?.find(c => c.component === 'official_feed');
  const delayed = !offline && (satellite?.stale || official_feed?.stale);

  const rows = [];
  for (const s of official) {
    const level = s.alert_level || 'YELLOW';
    const name = s.cyclone_name || s.cyclone_id;
    rows.push(
      <div key={s.cyclone_id} className={`warn-row warn-${level.toLowerCase()}`} role="alert">
        <div className="site-container warn-inner">
          <AlertTriangle size={18} className="warn-icon" />
          <strong className="warn-level">{t(lang, `warn.level.${level}`)}</strong>
          {showDemoBadge(s) && <span className="demo-badge">{t(lang, 'demo.badge')}</span>}
          <span className="warn-text">
            {fill(t(lang, 'warn.storm'), { cat: catName(s, lang), name, sea: seaName(s, lang) })}
            {s.movement ? fill(t(lang, 'warn.moving'), { dir: s.movement.dir, speed: s.movement.speed }) : ''}.{' '}
            <span className="warn-follow">{t(lang, 'warn.follow')}</span>
          </span>
          <Link to="/alerts" className="warn-link">{t(lang, 'warn.advice')} <ArrowRight size={14} /></Link>
        </div>
      </div>,
    );
  }
  if (watches.length) {
    rows.push(
      <div key="watch" className="warn-row warn-watch" role="status">
        <div className="site-container warn-inner">
          <Satellite size={18} className="warn-icon" />
          <strong className="warn-level">{t(lang, 'warn.watchLabel')}</strong>
          <span className="warn-text">{fill(t(lang, 'warn.watch'), { sea: seaName(watches[0], lang) })}</span>
        </div>
      </div>,
    );
  }
  if (offline || delayed) {
    rows.push(
      <div key="data" className="warn-row warn-data" role="status">
        <div className="site-container warn-inner">
          {offline ? <WifiOff size={16} className="warn-icon" /> : <Clock size={16} className="warn-icon" />}
          <span className="warn-text">{t(lang, offline ? 'warn.offline' : 'warn.delayed')}</span>
          <a className="warn-link" href="https://mausam.imd.gov.in" target="_blank" rel="noopener noreferrer">IMD <ArrowRight size={14} /></a>
        </div>
      </div>,
    );
  }
  return rows.length ? <div className="warn-bar">{rows}</div> : null;
}
