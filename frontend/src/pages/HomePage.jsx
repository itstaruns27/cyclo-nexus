import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ShieldCheck, Eye, AlertTriangle, ArrowRight, MapPin, LocateFixed, Wind, CloudRain, Gauge, Waves,
  Satellite, Cpu, BadgeCheck, MessageSquareText, Phone, Navigation,
} from 'lucide-react';
import CycloneMap from '../components/CycloneMap';
import AreaCheck from '../components/site/AreaCheck';
import ImpactSection from '../components/site/ImpactSection';
import { t } from '../i18n/translations';
import { fill } from '../i18n/strings_site';
import { useData } from '../context/DataContext';
import { ALERT_COLORS, isWatch } from '../types/cyclone';
import { fetchPointConditions } from '../services/weatherService';
import { catName, compass, formationChance, haversineKm, isActiveOfficial, rankSystems, seaName, showDemoBadge, useForecast } from '../utils/site';

const PUBLIC_TABS = ['satellite', 'windFlow', 'rainfall', 'seaTemp'];
const EMERGENCY = ['112', '1078', '1070', '1077'];
const HOW_ICONS = [Satellite, Cpu, BadgeCheck, MessageSquareText];

// ── Hero: the one answer most visitors need ────────────────────────────────

const BASIN_POINTS = { BOB: [15.0, 88.0], AS: [15.0, 65.0] };
const SCALE = ['none', 'YELLOW', 'ORANGE', 'RED'];

/** Indicative new-cyclone chance at the centre of each sea (refreshed with the system list). */
function useBasinChance(systems) {
  const [chance, setChance] = useState({});
  const key = systems.map(s => s.cyclone_id).join(',');
  useEffect(() => {
    let cancelled = false;
    Promise.all(Object.entries(BASIN_POINTS).map(([b, [lat, lon]]) => fetchPointConditions(lat, lon)
      .then(c => [b, formationChance(c, lat, lon, systems).level]).catch(() => [b, null])))
      .then(list => { if (!cancelled) setChance(Object.fromEntries(list)); });
    return () => { cancelled = true; };
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  return chance;
}

function Hero({ lead, lang, loaded }) {
  const { systems } = useData();
  const chance = useBasinChance(systems);
  let state = 'clear';
  if (lead && isActiveOfficial(lead)) state = 'storm';
  else if (lead && isWatch(lead)) state = 'watch';
  const Icon = { clear: ShieldCheck, watch: Eye, storm: AlertTriangle }[state];
  const level = state === 'storm' ? lead.alert_level || 'YELLOW' : 'none';
  const accent = state === 'storm' ? ALERT_COLORS[level] : undefined;
  const officialCount = systems.filter(isActiveOfficial).length;

  let title; let text;
  if (!loaded) { title = t(lang, 'home.loading'); text = ''; }
  else if (state === 'storm') {
    title = lead.cyclone_name
      ? fill(t(lang, 'home.stormTitle'), { name: lead.cyclone_name })
      : fill(t(lang, 'home.stormTitleUnnamed'), { cat: catName(lead, lang) });
    text = fill(t(lang, 'home.stormText'), { cat: catName(lead, lang), sea: seaName(lead, lang), follow: t(lang, 'warn.follow') });
  } else if (state === 'watch') {
    title = t(lang, 'home.watchTitle');
    text = fill(t(lang, 'home.watchText'), { sea: seaName(lead, lang) });
  } else {
    title = t(lang, 'home.clearTitle');
    text = t(lang, 'home.clearText');
  }

  const basinCell = b => {
    const here = systems.filter(s => s.basin === b);
    const st = here.some(isActiveOfficial) ? 'storm' : here.length ? 'watch' : 'calm';
    return (
      <div key={b}>
        <dt>{t(lang, `site.sea.${b}`)}</dt>
        <dd className={`basin-${st}`}>{t(lang, `home.basin.${st}`)}</dd>
        {st === 'calm' && (
          <small>{t(lang, 'home.fact.chanceIn')}: <b className={`lvl-${chance[b] || 'na'}`}>
            {chance[b] ? t(lang, `pin.level.${chance[b]}`) : '…'}</b></small>
        )}
      </div>
    );
  };

  return (
    <section className={`hero hero-${state}`} style={accent ? { '--accent': accent } : undefined}>
      <div className="site-container hero-inner">
        <div className="hero-copy">
          <span className="eyebrow">
            <span className="pulse-dot" /> {t(lang, 'home.eyebrow')}
            {showDemoBadge(lead) && <span className="demo-badge">{t(lang, 'demo.badge')}</span>}
          </span>
          <div className="hero-status">
            <span className="hero-icon"><Icon size={30} /></span>
            <h1>{title}</h1>
          </div>
          {text && <p className="hero-text">{text}</p>}

          {loaded && (
            <div className="alert-scale" aria-label={t(lang, 'scale.title')}>
              <span className="alert-scale-title">{t(lang, 'scale.title')}</span>
              <div className="alert-scale-steps">
                {SCALE.map(l => (
                  <span key={l} className={`step step-${l.toLowerCase()}${l === level ? ' current' : ''}`}>
                    {t(lang, `scale.${l}`)}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="hero-actions">
            <a href="#safety" className="btn-solid">{t(lang, 'home.whatToDo')} <ArrowRight size={16} /></a>
            <a href="#area" className="btn-ghost"><MapPin size={16} /> {t(lang, 'home.checkArea')}</a>
          </div>
        </div>

        {loaded && (
          <div className="hero-panel">
            <div className="radar" aria-hidden="true"><span /></div>
            {state === 'storm' ? (
              <dl className="hero-facts">
                <div><dt>{t(lang, 'home.fact.alert')}</dt><dd style={{ color: accent }}>{t(lang, `warn.level.${level}`)}</dd></div>
                <div><dt>{t(lang, 'home.fact.wind')}</dt><dd>{Math.round(Number(lead.sustained_wind_kmh))} km/h</dd></div>
                <div><dt>{t(lang, 'home.fact.moving')}</dt><dd>{lead.movement ? `${lead.movement.dir} · ${lead.movement.speed} km/h` : '—'}</dd></div>
                <div><dt>{t(lang, 'home.fact.where')}</dt><dd>{seaName(lead, lang)}</dd></div>
              </dl>
            ) : (
              <dl className="hero-facts">
                <div><dt>{t(lang, 'home.fact.alert')}</dt><dd className="basin-calm">{t(lang, 'scale.none')}</dd></div>
                <div><dt>{t(lang, 'home.fact.storms')}</dt><dd>{officialCount}</dd></div>
                {['BOB', 'AS'].map(basinCell)}
              </dl>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

// ── Page ───────────────────────────────────────────────────────────────────

function Section({ id, title, text, children, tone }) {
  return (
    <section id={id} className={`section${tone ? ` section-${tone}` : ''}`}>
      <div className="site-container">
        <div className="section-head">
          <h2>{title}</h2>
          {text && <p>{text}</p>}
        </div>
        {children}
      </div>
    </section>
  );
}

export default function HomePage() {
  const { lang, systems, loaded, selected } = useData();
  const lead = rankSystems(systems)[0] || null;
  const forecast = useForecast(selected);
  const tips = phase => t(lang, `home.tips.${phase}`) || [];
  const activePhase = lead && isActiveOfficial(lead) ? 'during' : 'before';

  return (
    <>
      <Hero lead={lead} lang={lang} loaded={loaded} />

      <Section id="map" title={t(lang, 'home.mapTitle')} text={t(lang, 'home.mapText')}>
        <div className="map-frame">
          <CycloneMap forecastGeoJSON={forecast} systems={systems} selected={selected} tabs={PUBLIC_TABS} legend={false} inspector="public" />
        </div>
      </Section>

      <Section id="area" title={t(lang, 'home.areaTitle')} text={t(lang, 'home.areaText')} tone="soft">
        <AreaCheck systems={systems} lang={lang} />
      </Section>

      <Section id="impact" title={t(lang, lead && isActiveOfficial(lead) ? 'impact.titleActive' : 'impact.title')}
        text={t(lang, lead && isActiveOfficial(lead) ? 'impact.textActive' : 'impact.text')}>
        <ImpactSection lead={lead} lang={lang} />
      </Section>

      <Section id="safety" title={t(lang, 'home.safetyTitle')} text={t(lang, 'home.safetyText')} tone="soft">
        <div className="grid-3">
          {['before', 'during', 'after'].map((phase, i) => (
            <article key={phase} className={`tip-card${phase === activePhase ? ' tip-active' : ''}`}>
              <span className="tip-step">{i + 1}</span>
              <h3>{t(lang, `home.phase.${phase}`)}</h3>
              <ul>{tips(phase).map(tip => <li key={tip}>{tip}</li>)}</ul>
            </article>
          ))}
        </div>
      </Section>

      <Section id="help" title={t(lang, 'home.helpTitle')} text={t(lang, 'home.helpText')}>
        <div className="grid-4">
          {EMERGENCY.map(n => (
            <a key={n} href={`tel:${n}`} className="call-card">
              <Phone size={18} />
              <strong>{n}</strong>
              <span>{t(lang, `home.help.n${n}`)}</span>
            </a>
          ))}
        </div>
      </Section>

      <Section id="how" title={t(lang, 'home.howTitle')} tone="soft">
        <div className="grid-4">
          {(t(lang, 'home.how') || []).map((step, i) => {
            const Icon = HOW_ICONS[i];
            return (
              <article key={step.t} className="how-card">
                <span className="how-icon"><Icon size={20} /></span>
                <h3>{step.t}</h3>
                <p>{step.d}</p>
              </article>
            );
          })}
        </div>
      </Section>

      <section className="section">
        <div className="site-container">
          <div className="cta-band">
            <div>
              <h2>{t(lang, 'home.expertTitle')}</h2>
              <p>{t(lang, 'home.expertText')}</p>
            </div>
            <Link to="/expert" className="btn-light">{t(lang, 'home.openExpert')} <ArrowRight size={16} /></Link>
          </div>
        </div>
      </section>
    </>
  );
}
