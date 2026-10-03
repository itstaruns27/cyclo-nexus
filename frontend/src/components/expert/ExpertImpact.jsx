import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { t } from '../../i18n/translations';
import { useData } from '../../context/DataContext';
import { api } from '../../services/api';
import { compact, isActiveOfficial, ktToKmh, inr } from '../../utils/site';

const nf = (n, lang) => (n == null ? '—' : Number(n).toLocaleString(lang === 'hi' ? 'hi-IN' : 'en-IN'));

function ExposureTable({ now, forecast, lang }) {
  const rows = [['impact.x.now', now], ['impact.x.forecast', forecast]].filter(([, e]) => e);
  return (
    <div className="table-scroll">
      <table className="data-table">
        <thead>
          <tr><th /><th>{t(lang, 'impact.x.peopleGale')}</th><th>{t(lang, 'impact.x.peopleCore')}</th>
            <th>{t(lang, 'impact.x.townsGale')}</th><th>{t(lang, 'impact.x.townsCore')}</th><th>{t(lang, 'impact.x.byCountry')}</th></tr>
        </thead>
        <tbody>
          {rows.map(([k, e]) => (
            <tr key={k}>
              <td><strong>{t(lang, k)}</strong></td>
              <td>{nf(e.people_gale_zone, lang)}</td><td>{nf(e.people_core, lang)}</td>
              <td>{nf(e.towns_gale_zone, lang)}</td><td>{nf(e.towns_core, lang)}</td>
              <td className="wrap">{Object.entries(e.by_country).sort((a, b) => b[1] - a[1])
                .map(([c, n]) => `${c} ${compact(n, lang)}`).join(' · ') || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Expert impact assessment: selected active system + major recorded cyclones, with method notes. */
export default function ExpertImpact() {
  const { lang, selected } = useData();
  const active = selected && isActiveOfficial(selected) ? selected : null;
  const [storm, setStorm] = useState(null);
  const [major, setMajor] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setStorm(null);
    if (active) api.getCycloneImpact(active.cyclone_id).then(d => { if (!cancelled) setStorm(d); }).catch(() => {});
    return () => { cancelled = true; };
  }, [active?.cyclone_id, active?.observation_time]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { api.getMajorImpacts().then(setMajor).catch(() => {}); }, []);

  const towns = (storm?.exposure_forecast || storm?.exposure_now)?.largest_towns || [];

  return (
    <div className="page">
      <h2 className="page-title">{t(lang, 'impact.x.title')}</h2>

      <div className="panel">
        <div className="panel-header">
          <h3>{active ? `${active.cyclone_name || active.cyclone_id} · ${t(lang, 'impact.x.exposure')}` : t(lang, 'impact.x.exposure')}</h3>
          {storm && <span className="muted-small">{t(lang, 'impact.x.forecastSource')}: {storm.forecast_source || '—'} · +{storm.forecast_hours} h</span>}
        </div>
        {!active && <p className="empty-note">{t(lang, 'impact.x.noActive')}</p>}
        {active && !storm && <p className="empty-note">…</p>}
        {storm && <ExposureTable now={storm.exposure_now} forecast={storm.exposure_forecast} lang={lang} />}

        {towns.length > 0 && (
          <>
            <h4 className="sub-title">{t(lang, 'impact.x.largestTowns')}</h4>
            <div className="table-scroll">
              <table className="data-table">
                <thead><tr><th>{t(lang, 'impact.x.town')}</th><th>{t(lang, 'impact.x.country')}</th><th>{t(lang, 'impact.x.population')}</th>
                  <th>{t(lang, 'impact.x.zone')}</th><th>{t(lang, 'impact.x.distance')}</th></tr></thead>
                <tbody>
                  {towns.map(tn => (
                    <tr key={`${tn.name}-${tn.country}-${tn.min_distance_km}`}>
                      <td>{tn.name}</td><td>{tn.country}</td><td>{nf(tn.population, lang)}</td>
                      <td><span className={`zone-chip ${tn.zone}`}>{t(lang, `impact.x.${tn.zone}`)}</span></td>
                      <td>{tn.min_distance_km} km</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {storm?.analogs && (
          <>
            <h4 className="sub-title">{t(lang, 'impact.x.analogs')} ({storm.peak_wind_kt} kt ± 20)</h4>
            <p className="muted-small">
              {t(lang, 'impact.pastDeaths')}: {t(lang, 'impact.x.median')} {nf(storm.analogs.deaths_median, lang)}
              {' '}({storm.analogs.deaths_range.map(n => nf(n, lang)).join(' – ')}) ·{' '}
              {t(lang, 'impact.pastLoss')}: {t(lang, 'impact.x.median')} {inr(storm.analogs.damage_inr_median, lang)}
              {' '}({storm.analogs.damage_inr_range.map(n => inr(n, lang)).join(' – ')}) ·{' '}
              {storm.analogs.storms.map(s => `${s.name} ${s.season}`).join(', ')}
            </p>
          </>
        )}
      </div>

      {major && (
        <div className="panel">
          <div className="panel-header"><h3>{t(lang, 'impact.x.majorTitle')}</h3></div>
          <div className="table-scroll">
            <table className="data-table">
              <thead><tr><th>{t(lang, 'impact.x.storm')}</th><th>{t(lang, 'impact.x.season')}</th><th>{t(lang, 'impact.x.peak')}</th>
                <th>{t(lang, 'impact.deaths')}</th><th>{t(lang, 'impact.loss')}</th><th>{t(lang, 'impact.x.peopleGale')}</th><th>{t(lang, 'impact.x.source')}</th></tr></thead>
              <tbody>
                {major.storms.map(s => (
                  <tr key={s.sid}>
                    <td><Link className="storm-link" to={`/storm/${s.sid}`}>{s.name}</Link><div className="muted-small">{s.countries.join(', ')}</div></td>
                    <td>{s.season}</td>
                    <td>{s.peak_grade || '—'} · {ktToKmh(s.peak_wind_kt) ?? '—'} km/h</td>
                    <td>{nf(s.deaths, lang)}{s.deaths_note ? ' *' : ''}</td>
                    <td>{inr(s.damage_inr, lang)}</td>
                    <td>{nf(s.people_gale_zone, lang)}</td>
                    <td><a href={s.source} target="_blank" rel="noopener noreferrer">Link</a></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted-small method-note">{major.note}</p>
        </div>
      )}

      <div className="panel method">
        <h4 className="sub-title">{t(lang, 'impact.x.method')}</h4>
        <ul>{(t(lang, 'impact.x.methodItems') || []).map(m => <li key={m}>{m}</li>)}</ul>
      </div>
    </div>
  );
}
