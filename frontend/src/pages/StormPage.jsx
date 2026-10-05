import React, { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  ArrowLeft, Wind, Gauge, Award, Clock, Route as RouteIcon, MapPin, Zap, Users, AlertOctagon, Building2,
  HeartCrack, IndianRupee, Download, ChevronDown, Anchor, Landmark, Info, ExternalLink,
} from 'lucide-react';
import { t } from '../i18n/translations';
import { fill } from '../i18n/strings_site';
import { useData } from '../context/DataContext';
import { api } from '../services/api';
import { IMD_COLORS, IMD_SCALE, ALERT_COLORS } from '../types/cyclone';
import { compact, inr } from '../utils/site';
import IntensityCharts, { GradeTimeline } from '../components/storm/IntensityCharts';
import StormMap, { quadrantArea } from '../components/storm/StormMap';

const KMH = 1.852;
const loc = lang => (lang === 'hi' ? 'hi-IN' : 'en-IN');
const kmh = kt => (kt == null ? null : Math.round(kt * KMH));
const catLabel = g => IMD_SCALE.find(c => c.category === g)?.label || g || '—';
const fmtDate = (iso, lang) => new Date(iso).toLocaleDateString(loc(lang), { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
const fmtDT = (iso, lang) => `${new Date(iso).toLocaleString(loc(lang), { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'UTC' })} UTC`;
const placeText = (p, at) => (p && p.distance_km <= 400 ? `${p.distance_km <= 5 ? 'at' : `${p.distance_km} km ${p.direction} of`} ${p.name}`
  : at ? `at ${Math.abs(at.lat).toFixed(1)}° ${at.lat >= 0 ? 'N' : 'S'}, ${at.lon.toFixed(1)}° E` : '');
const COUNTRY = { IN: 'India', BD: 'Bangladesh', MM: 'Myanmar', LK: 'Sri Lanka', PK: 'Pakistan', OM: 'Oman', YE: 'Yemen', SO: 'Somalia', TH: 'Thailand', MV: 'Maldives', IR: 'Iran', AE: 'UAE', SA: 'Saudi Arabia', NP: 'Nepal', BT: 'Bhutan', DJ: 'Djibouti' };

function CatBadge({ grade, big }) {
  if (!grade) return null;
  return <span className={`cat-badge${big ? ' big' : ''}`} style={{ '--cat': IMD_COLORS[grade] }}>{grade}<em>{catLabel(grade)}</em></span>;
}

function Kpi({ icon: Icon, label, value, sub }) {
  return (
    <div className="kpi">
      <span className="kpi-label"><Icon size={15} />{label}</span>
      <strong className="kpi-value">{value ?? '—'}</strong>
      {sub && <span className="kpi-sub">{sub}</span>}
    </div>
  );
}

function Section({ id, title, sub, children, tone }) {
  return (
    <section id={id} className={`storm-section${tone ? ` ${tone}` : ''}`}>
      <div className="site-container">
        <div className="ss-head"><h2>{title}</h2>{sub && <p>{sub}</p>}</div>
        {children}
      </div>
    </section>
  );
}

function ZoneCard({ cls, icon: Icon, title, sub, people, towns, lang }) {
  return (
    <div className={`zone-card ${cls}`}>
      <span className="zone-icon"><Icon size={18} /></span>
      <div className="zone-title">{title}</div>
      <strong>{compact(people, lang)}</strong>
      <span className="zone-people">{t(lang, 'storm.impact.people')} · {fill(t(lang, 'storm.impact.towns'), { n: (towns || 0).toLocaleString(loc(lang)) })}</span>
      <span className="zone-sub">{sub}</span>
    </div>
  );
}

function Exposure({ exp, lang }) {
  if (!exp) return null;
  const countries = Object.entries(exp.by_country || {}).sort((a, b) => b[1] - a[1]).slice(0, 5);
  const maxC = countries[0]?.[1] || 1;
  return (
    <>
      <div className="zone-grid">
        <ZoneCard cls="gale" icon={Wind} title={t(lang, 'storm.impact.gale')} sub={t(lang, 'storm.impact.galeSub')}
          people={exp.people_gale_zone} towns={exp.towns_gale_zone} lang={lang} />
        <ZoneCard cls="storm" icon={AlertOctagon} title={t(lang, 'storm.impact.storm')} sub={t(lang, 'storm.impact.stormSub')}
          people={exp.people_storm_zone} towns={exp.towns_storm_zone} lang={lang} />
        <ZoneCard cls="core" icon={Zap} title={t(lang, 'storm.impact.core')} sub={t(lang, 'storm.impact.coreSub')}
          people={exp.people_core} towns={exp.towns_core} lang={lang} />
      </div>
      <div className="impact-split">
        {countries.length > 0 && (
          <div className="card">
            <h3>{t(lang, 'storm.impact.byCountry')}</h3>
            <ul className="bar-list">
              {countries.map(([c, n]) => (
                <li key={c}>
                  <span>{COUNTRY[c] || c}</span>
                  <i><b style={{ width: `${(n / maxC) * 100}%` }} /></i>
                  <em>{compact(n, lang)}</em>
                </li>
              ))}
            </ul>
          </div>
        )}
        {exp.largest_towns?.length > 0 && (
          <div className="card">
            <h3>{t(lang, 'storm.impact.topTowns')}</h3>
            <ul className="town-list">
              {exp.largest_towns.slice(0, 10).map(tn => (
                <li key={`${tn.name}-${tn.min_distance_km}`}>
                  <span className={`zone-dot ${tn.zone}`} title={t(lang, `storm.impact.zone.${tn.zone}`)} />
                  <span className="tn-name">{tn.name}</span>
                  <span className="tn-meta">{compact(tn.population, lang)} · {tn.min_distance_km} km · {t(lang, `storm.impact.zone.${tn.zone}`)}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </>
  );
}

function PointCard({ p, lang }) {
  if (!p) return null;
  const galeMean = p.gale_km ? Math.round(p.gale_km.reduce((a, b) => a + b, 0) / 4) : null;
  const rows = [
    [t(lang, 'storm.point.time'), fmtDT(p.time, lang)],
    [t(lang, 'storm.point.position'), `${p.lat.toFixed(1)}° N, ${p.lon.toFixed(1)}° E`],
    [t(lang, 'storm.point.wind'), p.wind_kt != null ? `${kmh(p.wind_kt)} km/h (${Math.round(p.wind_kt)} kt)` : '—'],
    [t(lang, 'storm.point.pressure'), p.pressure_hpa != null ? `${Math.round(p.pressure_hpa)} hPa` : '—'],
    [t(lang, 'storm.point.category'), p.grade ? <CatBadge grade={p.grade} /> : '—'],
    [t(lang, 'storm.point.motion'), p.speed_kmh != null ? `${p.speed_kmh} km/h · ${p.dir_deg}°` : '—'],
    [t(lang, 'storm.point.gale'), galeMean ? `${galeMean} km (${t(lang, p.gale_measured ? 'storm.map.radiiMeasured' : 'storm.map.radiiTypical')})` : '—'],
    [t(lang, 'storm.point.land'), p.dist2land_km != null ? `${Math.round(p.dist2land_km)} km` : '—'],
  ];
  return (
    <div className="card point-card">
      <h3>{t(lang, 'storm.map.at')}</h3>
      <dl>{rows.map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>
    </div>
  );
}

function ForecastTable({ list, lang, ai }) {
  return (
    <div className={`card fc-card${ai ? ' ai' : ''}`}>
      <table className="clean-table">
        <thead><tr><th>{t(lang, 'storm.fc.hour')}</th><th>{t(lang, 'storm.fc.near')}</th><th>{t(lang, 'storm.fc.wind')}</th><th>{t(lang, 'storm.fc.cat')}</th>
          {ai && <th>{t(lang, 'storm.fc.typErr')}</th>}</tr></thead>
        <tbody>
          {list.map(f => (
            <tr key={f.hour}>
              <td>+{f.hour} h</td>
              <td>{f.place ? `${f.place.distance_km} km ${f.place.direction} of ${f.place.name}` : `${f.lat.toFixed(1)}°N ${f.lon.toFixed(1)}°E`}</td>
              <td>{Math.round(f.wind_kmh)} km/h</td>
              <td>{f.grade ? <CatBadge grade={f.grade} /> : '—'}</td>
              {ai && <td>{f.verified_error_km != null ? `± ${Math.round(f.verified_error_km)} km` : '—'}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function downloadCsv(d) {
  const head = ['time_utc', 'lat', 'lon', 'wind_kt', 'wind_kmh', 'pressure_hpa', 'imd_grade', 'speed_kmh', 'direction_deg', 'dist2land_km',
    'gale_radius_ne_km', 'gale_radius_se_km', 'gale_radius_sw_km', 'gale_radius_nw_km', 'gale_radii_measured'];
  const rows = d.track.map(p => [p.time, p.lat, p.lon, p.wind_kt ?? '', kmh(p.wind_kt) ?? '', p.pressure_hpa ?? '', p.grade ?? '',
    p.speed_kmh ?? '', p.dir_deg ?? '', p.dist2land_km ?? '', ...(p.gale_km || ['', '', '', '']), p.gale_measured ? 'yes' : 'no']);
  const csv = [head, ...rows].map(r => r.join(',')).join('\n');
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  a.download = `${(d.name || d.id).toString().replace(/\W+/g, '_')}_${d.season}_track.csv`;
  a.click();
  URL.revokeObjectURL(a.href);
}

export default function StormPage() {
  const { id } = useParams();
  const { lang } = useData();
  const [d, setD] = useState(undefined);
  const [fcGeo, setFcGeo] = useState(null);
  const [sel, setSel] = useState(0);
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setD(undefined);
    setFcGeo(null);
    api.getStormProfile(id, lang).then(p => {
      if (cancelled) return;
      setD(p);
      if (p) {
        const peakIdx = p.track.reduce((b, x, i) => ((x.wind_kt ?? -1) > (p.track[b].wind_kt ?? -1) ? i : b), 0);
        setSel(p.kind === 'active' ? p.track.length - 1 : peakIdx);
        document.title = `${p.name || t(lang, 'storm.unnamed')} (${p.season}) · Cyclo-Nexus`;
      }
    }).catch(() => !cancelled && setD(null));
    if (!/^\d{7}[NS]\d{5}$/.test(id)) api.getCycloneForecast(id).then(g => !cancelled && setFcGeo(g)).catch(() => {});
    return () => { cancelled = true; document.title = 'Cyclo-Nexus — AI for Safer Coasts'; };
  }, [id, lang]);

  const fcSeries = useMemo(() => {
    if (!d?.forecasts) return [];
    const src = Object.keys(d.forecasts).find(s => s.startsWith('OFFICIAL_'));
    const base = new Date(d.observation_time).getTime();
    return (d.forecasts[src] || []).map(f => ({ ms: base + f.hour * 3600e3, wind_kmh: f.wind_kmh }));
  }, [d]);

  const point = d?.track?.[sel];
  const galeArea = useMemo(() => (point?.gale_km && point.gale_km.some(Boolean) ? quadrantArea(point.lat, point.lon, point.gale_km) : null), [point]);

  if (d === undefined) return <div className="site-container page-pad"><p className="empty-note">{t(lang, 'storm.loading')}</p></div>;
  if (d === null) {
    return (
      <div className="site-container page-pad">
        <p className="empty-note">{t(lang, 'storm.notFound')}</p>
        <Link className="btn-ghost" to="/history"><ArrowLeft size={16} /> {t(lang, 'storm.back')}</Link>
      </div>
    );
  }

  const L = d.life;
  const active = d.kind === 'active';
  const name = d.name || t(lang, 'storm.unnamed');
  const basinName = t(lang, `storm.basin.${d.basin}`);
  const landfall = L.landfalls[0];
  const officialSrc = d.forecasts ? Object.keys(d.forecasts).find(s => s.startsWith('OFFICIAL_')) : null;
  const ai = d.forecasts?.AI_CONSENSUS;
  const adv = d.advisory;
  const advColor = ALERT_COLORS[adv?.alert_level] || '#7c3aed';
  const navItems = [['track', 'track'], ['intensity', 'intensity'], ['impact', 'impact'],
    ...(active && d.forecasts ? [['forecast', 'forecast']] : []), ['positions', 'positions'], ['similar', 'similar']];
  const peakGrade = active ? d.now?.grade : L.peak_grade;

  return (
    <div className="storm-page">
      {/* ── Header ─────────────────────────────────────────── */}
      <header className="storm-hero" style={{ '--cat': IMD_COLORS[peakGrade] || '#94a3b8' }}>
        <div className="site-container">
          <Link className="back-link" to={active ? '/' : '/history'}><ArrowLeft size={16} /> {t(lang, active ? 'storm.backLive' : 'storm.back')}</Link>
          <div className="storm-chips">
            <span className={`chip ${active ? 'live' : ''}`}>{active && <i className="live-dot" />}{t(lang, active ? 'storm.active' : 'storm.past')}</span>
            {active && <span className="chip">{t(lang, String(d.source).startsWith('OFFICIAL_') ? 'storm.official' : 'storm.aiWatch')}</span>}
            {d.is_demo && <span className="chip demo">{t(lang, 'storm.demo')}</span>}
            <span className="chip">{basinName}</span>
          </div>
          <div className="storm-title">
            <h1>{name} <span>{d.season}</span></h1>
            <CatBadge grade={peakGrade} big />
          </div>
          <p className="storm-dates">
            {fill(t(lang, 'storm.lifetime'), { start: fmtDate(L.start, lang), end: active ? fmtDT(d.observation_time, lang) : fmtDate(L.end, lang) })}
            {d.context && <> · {fill(t(lang, 'storm.rankText'), { rank: d.context.rank_in_basin, n: d.context.storms_in_basin, basin: basinName })}</>}
          </p>

          <div className="kpi-grid">
            <Kpi icon={Wind} label={t(lang, active ? 'storm.kpi.nowWind' : 'storm.kpi.peakWind')}
              value={`${active ? d.now.wind_kmh : L.peak?.wind_kmh ?? '—'} km/h`}
              sub={active ? (d.now.movement ? `${t(lang, 'storm.kpi.movement')} ${d.now.movement.dir} · ${d.now.movement.speed} km/h` : null) : (L.peak ? fmtDT(L.peak.time, lang) : null)} />
            <Kpi icon={Gauge} label={t(lang, active ? 'storm.kpi.nowPressure' : 'storm.kpi.minPressure')}
              value={active ? `${Math.round(d.now.pressure_hpa)} hPa` : L.min_pressure ? `${Math.round(L.min_pressure.hpa)} hPa` : '—'} />
            <Kpi icon={Award} label={t(lang, active ? 'storm.kpi.nowCat' : 'storm.kpi.peakCat')} value={peakGrade || '—'} sub={catLabel(peakGrade)} />
            <Kpi icon={Clock} label={t(lang, 'storm.kpi.duration')}
              value={L.duration_h >= 48 ? `${Math.round(L.duration_h / 24 * 10) / 10} ${t(lang, 'storm.kpi.days')}` : `${L.duration_h} ${t(lang, 'storm.kpi.hours')}`} />
            <Kpi icon={RouteIcon} label={t(lang, 'storm.kpi.distance')} value={`${L.distance_km.toLocaleString(loc(lang))} km`}
              sub={L.mean_speed_kmh ? `~${L.mean_speed_kmh} km/h` : null} />
            <Kpi icon={MapPin} label={active ? t(lang, 'storm.point.position') : t(lang, 'storm.kpi.landfall')}
              value={active ? (d.now.place?.name || `${d.now.lat.toFixed(1)}°N`) : landfall ? landfall.place?.name || '—' : t(lang, 'storm.kpi.noLandfall')}
              sub={active ? placeText(d.now.place) : landfall ? `${fmtDT(landfall.time, lang)} · ${kmh(landfall.wind_kt)} km/h` : null} />
          </div>
        </div>
      </header>

      <nav className="storm-nav">
        <div className="site-container">
          {navItems.map(([k, a]) => <a key={k} href={`#${a}`}>{t(lang, `storm.nav.${k}`)}</a>)}
        </div>
      </nav>

      {/* ── Track ─────────────────────────────────────────── */}
      <Section id="track" title={t(lang, 'storm.map.title')} sub={t(lang, 'storm.map.hint')}>
        <div className="track-grid">
          <div className="map-card">
            <StormMap points={d.track} forecastGeo={fcGeo} selected={sel} onSelect={setSel} galeArea={galeArea}
              landfalls={L.landfalls} lang={lang} />
            <div className="scrubber">
              <input type="range" min="0" max={d.track.length - 1} value={sel} onChange={e => setSel(Number(e.target.value))}
                aria-label={t(lang, 'storm.map.at')} />
              <span>{point ? fmtDT(point.time, lang) : ''}</span>
            </div>
            <ul className="map-key">
              <li><i className="k-track" />{t(lang, 'storm.map.observed')}</li>
              {fcGeo && <li><i className="k-fc" />{t(lang, 'storm.map.officialFc')}</li>}
              {ai && <li><i className="k-ai" />{t(lang, 'storm.map.aiFc')}</li>}
              {fcGeo && <li><i className="k-cone" />{t(lang, 'storm.map.cone')}</li>}
              <li><i className="k-gale" />{t(lang, 'storm.map.gale')}</li>
            </ul>
          </div>
          <div className="track-side">
            <PointCard p={point} lang={lang} />
            <div className="card story">
              <h3>{t(lang, 'storm.story.title')}</h3>
              <ul>
                <li><span className="st-ico"><MapPin size={14} /></span>{fill(t(lang, 'storm.story.genesis'), { when: fmtDate(L.genesis.time, lang), place: placeText(L.genesis.place, L.genesis) })}</li>
                {L.peak && <li><span className="st-ico"><Wind size={14} /></span>{fill(t(lang, 'storm.story.peak'), { wind: L.peak.wind_kmh, cat: L.peak_grade || '—', when: fmtDT(L.peak.time, lang), place: placeText(L.peak.place, L.peak) })}</li>}
                {L.rapid_intensification
                  ? <li className="hl"><span className="st-ico"><Zap size={14} /></span>{fill(t(lang, 'storm.story.ri'), { kt: L.rapid_intensification.kt, kmh: kmh(L.rapid_intensification.kt), when: fmtDT(L.rapid_intensification.from, lang) })}</li>
                  : L.max_24h_intensification_kt > 0 && <li><span className="st-ico"><Zap size={14} /></span>{fill(t(lang, 'storm.story.noRi'), { kt: L.max_24h_intensification_kt, kmh: kmh(L.max_24h_intensification_kt) })}</li>}
                {L.landfalls.map(l => (
                  <li key={l.time} className="hl"><span className="st-ico"><Landmark size={14} /></span>{fill(t(lang, 'storm.story.landfall'), { when: fmtDT(l.time, lang), place: placeText(l.place), wind: kmh(l.wind_kt), cat: l.grade || '—' })}</li>
                ))}
                <li><span className="st-ico"><RouteIcon size={14} /></span>{fill(t(lang, 'storm.story.speed'), { km: L.distance_km.toLocaleString(loc(lang)), speed: L.mean_speed_kmh ?? '—' })}</li>
                {L.max_gale_radius_km && <li><span className="st-ico"><Wind size={14} /></span>{fill(t(lang, 'storm.story.size'), { km: L.max_gale_radius_km })}</li>}
                <li title={t(lang, 'storm.story.aceHelp')}><span className="st-ico"><Info size={14} /></span>{fill(t(lang, 'storm.story.ace'), { ace: L.ace })}</li>
              </ul>
            </div>
          </div>
        </div>
      </Section>

      {/* ── Intensity ─────────────────────────────────────── */}
      <Section id="intensity" title={t(lang, 'storm.nav.intensity')} sub={t(lang, 'storm.chart.hover')} tone="soft">
        <div className="card chart-card">
          <IntensityCharts points={d.track} forecast={fcSeries} landfalls={L.landfalls}
            nowTime={active ? new Date(d.observation_time).getTime() : null} active={sel} onActive={setSel} lang={lang} />
        </div>
        <div className="card">
          <h3>{t(lang, 'storm.grades.title')}</h3>
          <GradeTimeline hours={L.grade_hours} lang={lang} />
        </div>
      </Section>

      {/* ── Impact ────────────────────────────────────────── */}
      <Section id="impact" title={t(lang, 'storm.impact.title')} sub={t(lang, active ? 'storm.impact.subtitleActive' : 'storm.impact.subtitle')}>
        {active && d.exposure_forecast
          ? <><h3 className="sub-h">{t(lang, 'storm.impact.alongForecast')}</h3><Exposure exp={d.exposure_forecast} lang={lang} /></>
          : <Exposure exp={d.exposure} lang={lang} />}

        {d.recorded && (
          <div className="card recorded">
            <h3>{t(lang, 'storm.impact.recorded')}</h3>
            <div className="rec-grid">
              <div><HeartCrack size={18} /><strong>{Number(d.recorded.deaths).toLocaleString(loc(lang))}</strong><span>{t(lang, 'storm.impact.deaths')}</span></div>
              <div><IndianRupee size={18} /><strong>{inr(d.recorded.damage_inr, lang)}</strong><span>{t(lang, 'storm.impact.damage')}</span></div>
            </div>
            <p className="muted-small">{d.recorded.deaths_note ? `${d.recorded.deaths_note}. ` : ''}
              <a href={d.recorded.source} target="_blank" rel="noopener noreferrer">{t(lang, 'storm.impact.source')} <ExternalLink size={12} /></a></p>
          </div>
        )}
        {d.analogs && (
          <div className="card recorded">
            <h3>{t(lang, 'storm.impact.analogs')}</h3>
            <p className="muted-small">{t(lang, 'storm.impact.analogsText')}</p>
            <div className="rec-grid">
              <div><HeartCrack size={18} /><strong>{compact(d.analogs.deaths_median, lang)}</strong><span>{t(lang, 'storm.impact.deaths')}</span></div>
              <div><IndianRupee size={18} /><strong>{inr(d.analogs.damage_inr_median, lang)}</strong><span>{t(lang, 'storm.impact.damage')}</span></div>
            </div>
            <p className="muted-small">{d.analogs.storms.map(s => `${s.name} (${s.season})`).join(' · ')}</p>
          </div>
        )}
        <details className="method">
          <summary><Info size={14} /> {t(lang, 'storm.impact.method')}</summary>
          <p>{t(lang, 'storm.impact.methodText')}</p>
          <p className="muted-small">{(active ? d.exposure_forecast || d.exposure : d.exposure)?.radii_source}</p>
        </details>
      </Section>

      {/* ── Forecast + advisory (active) ───────────────────── */}
      {active && d.forecasts && (
        <Section id="forecast" title={t(lang, 'storm.fc.title')} tone="soft">
          {adv && (
            <div className="card advisory-strip" style={{ '--alert': advColor }}>
              <div className="as-head">
                <span className="as-level">{adv.alert_level || t(lang, 'alertsX.watchTitle')}</span>
                <p>{adv.threat_summary}</p>
              </div>
              {adv.directives_fishermen && (
                <div className="as-grid">
                  <div><Anchor size={16} /><b>{t(lang, 'storm.advisory.fishermen')}</b><span>{adv.directives_fishermen}</span></div>
                  <div><Users size={16} /><b>{t(lang, 'storm.advisory.public')}</b><span>{adv.directives_public}</span></div>
                  <div><Building2 size={16} /><b>{t(lang, 'storm.advisory.admin')}</b><span>{adv.directives_administration}</span></div>
                </div>
              )}
            </div>
          )}
          <div className="fc-grid">
            {officialSrc && (
              <div>
                <h3 className="sub-h">{fill(t(lang, 'storm.fc.officialSub'), { src: officialSrc.replace('OFFICIAL_', '') })}</h3>
                <ForecastTable list={d.forecasts[officialSrc]} lang={lang} />
              </div>
            )}
            {ai && (
              <div>
                <h3 className="sub-h">{t(lang, 'storm.fc.aiSub')}</h3>
                <ForecastTable list={ai} lang={lang} ai />
                <p className="fc-note">{fill(t(lang, 'storm.fc.aiNote'), {
                  run: ai[0]?.init_time ? fmtDT(ai[0].init_time, lang) : '—',
                  models: (ai[0]?.members || []).join(', '),
                })}</p>
              </div>
            )}
          </div>
        </Section>
      )}

      {/* ── Positions ─────────────────────────────────────── */}
      <Section id="positions" title={t(lang, 'storm.positions.title')} sub={fill(t(lang, 'storm.positions.count'), { n: d.track.length })}
        tone={active && d.forecasts ? undefined : 'soft'}>
        <div className="card">
          <div className="table-actions">
            <button type="button" className="btn-ghost sm" onClick={() => setShowAll(v => !v)}>
              <ChevronDown size={16} className={showAll ? 'flip' : ''} /> {t(lang, showAll ? 'storm.positions.hide' : 'storm.positions.show')}
            </button>
            <button type="button" className="btn-ghost sm" onClick={() => downloadCsv(d)}><Download size={16} /> {t(lang, 'storm.positions.download')}</button>
          </div>
          <div className="table-scroll">
            <table className="clean-table positions">
              <thead><tr>
                <th>{t(lang, 'storm.point.time')}</th><th>{t(lang, 'storm.point.position')}</th><th>{t(lang, 'storm.point.wind')}</th>
                <th>{t(lang, 'storm.point.pressure')}</th><th>{t(lang, 'storm.point.category')}</th><th>{t(lang, 'storm.point.motion')}</th>
                <th>{t(lang, 'storm.point.gale')}</th><th>{t(lang, 'storm.point.land')}</th>
              </tr></thead>
              <tbody>
                {(showAll ? d.track : d.track.filter((_, i) => i % Math.max(1, Math.ceil(d.track.length / 12)) === 0 || i === sel)).map(p => {
                  const i = d.track.indexOf(p);
                  return (
                    <tr key={p.time} className={i === sel ? 'selected' : ''} onClick={() => { setSel(i); document.getElementById('track')?.scrollIntoView({ behavior: 'smooth' }); }}>
                      <td>{fmtDT(p.time, lang)}</td>
                      <td>{p.lat.toFixed(1)}°N {p.lon.toFixed(1)}°E</td>
                      <td>{p.wind_kt != null ? `${kmh(p.wind_kt)} km/h` : '—'}</td>
                      <td>{p.pressure_hpa != null ? `${Math.round(p.pressure_hpa)}` : '—'}</td>
                      <td>{p.grade ? <CatBadge grade={p.grade} /> : '—'}</td>
                      <td>{p.speed_kmh != null ? `${p.speed_kmh} km/h` : '—'}</td>
                      <td>{p.gale_km ? `${Math.round(p.gale_km.reduce((a, b) => a + b, 0) / 4)} km${p.gale_measured ? '' : '*'}` : '—'}</td>
                      <td>{p.dist2land_km != null ? `${Math.round(p.dist2land_km)} km` : '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="muted-small">* {t(lang, 'storm.map.radiiTypical')}</p>
        </div>
      </Section>

      {/* ── Similar storms ────────────────────────────────── */}
      <Section id="similar" title={t(lang, 'storm.similar.title')} sub={t(lang, 'storm.similar.subtitle')}
        tone={active && d.forecasts ? 'soft' : undefined}>
        {d.context?.similar?.length ? (
          <div className="similar-grid">
            {d.context.similar.map(s => (
              <Link key={s.sid} to={`/storm/${s.sid}`} className="similar-card" style={{ '--cat': IMD_COLORS[s.peak_grade] }}>
                <span className="sc-bar" />
                <strong>{s.name || t(lang, 'storm.similar.unnamed')} <em>{s.season}</em></strong>
                <span>{kmh(s.peak_kt)} km/h · {s.peak_grade}{s.min_pressure_hpa ? ` · ${Math.round(s.min_pressure_hpa)} hPa` : ''}</span>
                {s.recorded && <span className="sc-loss"><HeartCrack size={13} /> {Number(s.recorded.deaths).toLocaleString(loc(lang))} · {inr(s.recorded.damage_inr, lang)}</span>}
              </Link>
            ))}
          </div>
        ) : <p className="muted-small">{t(lang, 'storm.similar.none')}</p>}
        <p className="muted-small sources">{t(lang, 'storm.sources')}</p>
      </Section>
    </div>
  );
}
