import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Anchor, Users, Building2, AlertTriangle, AlertOctagon, Info, Satellite, ShieldCheck, Wind, Gauge, Navigation, MapPin,
  ArrowRight, ExternalLink, Phone, FileCode2, Rss, Clock,
} from 'lucide-react';
import { t } from '../i18n/translations';
import { useData } from '../context/DataContext';
import { api, API_BASE } from '../services/api';
import { ALERT_COLORS, IMD_COLORS, IMD_SCALE, isOfficial, isWatch } from '../types/cyclone';
import { ago, catName, rankSystems, showDemoBadge } from '../utils/site';

const LEVEL_ICON = { RED: AlertOctagon, ORANGE: AlertTriangle, YELLOW: Info };
const EMERGENCY = ['112', '1078', '1070', '1077'];
const fmtObs = (iso, lang) => `${new Date(iso).toLocaleString(lang === 'hi' ? 'hi-IN' : 'en-IN',
  { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'UTC' })} UTC`;

function AlertCard({ adv, sys, lang }) {
  const level = adv.alert_level || 'YELLOW';
  const color = ALERT_COLORS[level];
  const Icon = LEVEL_ICON[level];
  const name = sys?.cyclone_name || adv.cyclone_id;
  const facts = sys ? [
    [Wind, t(lang, 'storm.point.wind'), `${Math.round(Number(sys.sustained_wind_kmh))} km/h`],
    [Gauge, t(lang, 'storm.point.pressure'), sys.central_pressure_hpa ? `${Math.round(Number(sys.central_pressure_hpa))} hPa` : '—'],
    [Navigation, t(lang, 'storm.kpi.movement'), sys.movement ? `${sys.movement.dir} · ${sys.movement.speed} km/h` : '—'],
    [MapPin, t(lang, 'storm.point.position'), `${Number(sys.current_lat).toFixed(1)}° N, ${Number(sys.current_lon).toFixed(1)}° E`],
  ] : [];
  return (
    <article className="alert-card" style={{ '--alert': color }}>
      <header className="ac-head">
        <span className="ac-level"><Icon size={18} /> {t(lang, `alertsX.level.${level}.name`)}</span>
        <div className="ac-title">
          <h2><Link to={`/storm/${encodeURIComponent(adv.cyclone_id)}`}>{name}</Link></h2>
          <span className="cat-badge big" style={{ '--cat': IMD_COLORS[sys?.imd_category] || '#94a3b8' }}>
            {sys?.imd_category}<em>{catName(sys, lang)}</em>
          </span>
          {showDemoBadge(sys) && <span className="chip demo">{t(lang, 'storm.demo')}</span>}
        </div>
        <span className="ac-time"><Clock size={14} /> {t(lang, 'alertsX.updated')} {fmtObs(adv.observation_time, lang)}</span>
      </header>

      {adv.fallback && <p className="muted-small">{t(lang, 'alertsPage.englishOnly')}</p>}
      <p className="ac-summary">{adv.threat_summary}</p>

      {facts.length > 0 && (
        <dl className="ac-facts">
          {facts.map(([FIcon, k, v]) => <div key={k}><dt><FIcon size={14} />{k}</dt><dd>{v}</dd></div>)}
        </dl>
      )}

      <h3 className="ac-who">{t(lang, 'alertsX.who')}</h3>
      <div className="ac-audience">
        <div><span className="aud-icon"><Anchor size={18} /></span><b>{t(lang, 'alertsPage.fishermen')}</b><p>{adv.directives_fishermen}</p></div>
        <div><span className="aud-icon"><Users size={18} /></span><b>{t(lang, 'alertsPage.public')}</b><p>{adv.directives_public}</p></div>
        <div><span className="aud-icon"><Building2 size={18} /></span><b>{t(lang, 'alertsPage.administration')}</b><p>{adv.directives_administration}</p></div>
      </div>

      <footer className="ac-actions">
        <Link className="btn-solid" to={`/storm/${encodeURIComponent(adv.cyclone_id)}`}>{t(lang, 'alertsX.details')} <ArrowRight size={16} /></Link>
        {adv.source_url && (
          <a className="btn-ghost" href={adv.source_url} target="_blank" rel="noopener noreferrer">{t(lang, 'panel.viewSource')} <ExternalLink size={14} /></a>
        )}
        <a className="btn-ghost" href={`${API_BASE}/alerts/${encodeURIComponent(adv.cyclone_id)}/cap.xml`} target="_blank" rel="noopener noreferrer">
          <FileCode2 size={14} /> {t(lang, 'alertsPage.capAlert')}
        </a>
      </footer>
      <p className="ac-disclaimer">{adv.disclaimer}</p>
    </article>
  );
}

function WatchCard({ adv, sys, lang }) {
  return (
    <article className="watch-card">
      <span className="wc-icon"><Satellite size={18} /></span>
      <div>
        <h3>{t(lang, 'alertsX.watchTitle')} · {fmtObs(adv.observation_time, lang)} {showDemoBadge(sys) && <span className="chip demo">{t(lang, 'storm.demo')}</span>}</h3>
        <p>{adv.threat_summary}</p>
        <p className="muted-small">{t(lang, 'alertsX.watchText')}</p>
      </div>
      <Link className="btn-ghost sm" to={`/storm/${encodeURIComponent(adv.cyclone_id)}`}>{t(lang, 'alertsX.details')}</Link>
    </article>
  );
}

export default function AlertsPage() {
  const { lang, systems, health } = useData();
  const [advisories, setAdvisories] = useState(null);
  const ranked = useMemo(() => rankSystems(systems), [systems]);

  useEffect(() => {
    let cancelled = false;
    setAdvisories(null);
    Promise.all(ranked.map(s => api.getAdvisory(s.cyclone_id, lang).catch(() => null)))
      .then(list => { if (!cancelled) setAdvisories(list.filter(Boolean)); });
    return () => { cancelled = true; };
  }, [lang, ranked.map(s => `${s.cyclone_id}@${s.observation_time}`).join(',')]); // eslint-disable-line react-hooks/exhaustive-deps

  const sysById = Object.fromEntries(systems.map(s => [s.cyclone_id, s]));
  const official = (advisories || []).filter(a => a.type === 'advisory');
  const watches = (advisories || []).filter(a => a.type === 'watch');
  const noOfficial = !systems.some(s => isOfficial(s) && !isWatch(s));
  const feed = health?.components?.find(c => c.component === 'official_feed');
  const tips = phase => t(lang, `home.tips.${phase}`) || [];

  return (
    <div className="alerts-page">
      <header className="alerts-hero">
        <div className="site-container">
          <h1>{t(lang, 'alertsX.title')}</h1>
          <p>{t(lang, 'alertsX.subtitle')}</p>
          {feed?.last_data_time && <span className="chip"><Clock size={13} /> {t(lang, 'alertsX.updated')} {ago(feed.last_data_time, lang)}</span>}
        </div>
      </header>

      <div className="site-container alerts-body">
        {advisories === null && systems.length > 0 && <p className="empty-note">{t(lang, 'alertsPage.loading')}</p>}

        {noOfficial && (
          <div className="all-clear">
            <span className="ac-ok"><ShieldCheck size={28} /></span>
            <div>
              <h2>{t(lang, 'alertsX.allClear')}</h2>
              <p>{t(lang, 'alertsX.allClearText')}</p>
            </div>
          </div>
        )}

        {official.map(a => <AlertCard key={a.cyclone_id} adv={a} sys={sysById[a.cyclone_id]} lang={lang} />)}
        {watches.map(a => <WatchCard key={a.cyclone_id} adv={a} sys={sysById[a.cyclone_id]} lang={lang} />)}

        <section className="alerts-block">
          <h2>{t(lang, 'alertsX.levels')}</h2>
          <div className="level-grid">
            {['RED', 'ORANGE', 'YELLOW'].map(l => {
              const Icon = LEVEL_ICON[l];
              const cats = l === 'RED' ? ['VSCS', 'ESCS', 'SuCS'] : l === 'ORANGE' ? ['CS', 'SCS'] : ['D', 'DD'];
              const min = IMD_SCALE.find(c => c.category === cats[0]).minWindKmh;
              return (
                <div key={l} className="level-tile" style={{ '--alert': ALERT_COLORS[l] }}>
                  <span className="lt-name"><Icon size={16} /> {t(lang, `alertsX.level.${l}.name`)}</span>
                  <p>{t(lang, `alertsX.level.${l}.text`)}</p>
                  <span className="lt-cats">{cats.join(' · ')} · ≥ {min} km/h</span>
                </div>
              );
            })}
          </div>
        </section>

        <section className="alerts-block">
          <h2>{t(lang, 'alertsX.prepare')}</h2>
          <p className="muted">{t(lang, 'alertsX.prepareText')}</p>
          <div className="prep-grid">
            {['before', 'during', 'after'].map((ph, i) => (
              <div key={ph} className="prep-card">
                <span className="prep-step">{i + 1}</span>
                <h3>{t(lang, `home.phase.${ph}`)}</h3>
                <ul>{tips(ph).map(x => <li key={x}>{x}</li>)}</ul>
              </div>
            ))}
          </div>
        </section>

        <section className="alerts-block">
          <h2>{t(lang, 'alertsX.emergency')}</h2>
          <div className="call-grid">
            {EMERGENCY.map(n => (
              <a key={n} href={`tel:${n}`} className="call-card">
                <Phone size={18} /><strong>{n}</strong><span>{t(lang, `home.help.n${n}`)}</span>
              </a>
            ))}
          </div>
        </section>

        <section className="alerts-block feeds">
          <h2>{t(lang, 'alertsX.feeds')}</h2>
          <a className="feed-link" href={`${API_BASE}/alerts/cap.atom`} target="_blank" rel="noopener noreferrer">
            <Rss size={16} /> {t(lang, 'alertsPage.capFeed')} <ExternalLink size={13} />
          </a>
        </section>
      </div>
    </div>
  );
}
