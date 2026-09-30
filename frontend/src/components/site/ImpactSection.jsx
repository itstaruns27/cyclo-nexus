import React, { useEffect, useState } from 'react';
import { Users, AlertOctagon, Building2, HeartCrack, IndianRupee } from 'lucide-react';
import { t } from '../../i18n/translations';
import { fill } from '../../i18n/strings_site';
import { api } from '../../services/api';
import { compact, isActiveOfficial, inr } from '../../utils/site';

/**
 * Home-page impact module (plain language).
 * Active official storm → people living in its path (now + forecast) and what similar past storms caused.
 * Otherwise → recorded toll of major past cyclones.
 */
export default function ImpactSection({ lead, lang }) {
  const active = lead && isActiveOfficial(lead) ? lead : null;
  const [storm, setStorm] = useState(null);
  const [major, setMajor] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setStorm(null);
    if (active) api.getCycloneImpact(active.cyclone_id).then(d => { if (!cancelled) setStorm(d); }).catch(() => {});
    return () => { cancelled = true; };
  }, [active?.cyclone_id, active?.observation_time]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    api.getMajorImpacts().then(setMajor).catch(() => {});
  }, []);

  const exp = storm?.exposure_forecast || storm?.exposure_now;

  return (
    <>
      {active && exp && (
        <div className="impact-now">
          <div className="grid-4">
            <div className="impact-stat danger">
              <Users size={20} />
              <strong>{compact(exp.people_gale_zone, lang)}</strong>
              <span>{fill(t(lang, 'impact.inPath'), { h: storm.forecast_hours || 0 })}</span>
            </div>
            <div className="impact-stat danger">
              <AlertOctagon size={20} />
              <strong>{compact(exp.people_core, lang)}</strong>
              <span>{t(lang, 'impact.inCore')}</span>
            </div>
            <div className="impact-stat">
              <HeartCrack size={20} />
              <strong>{storm.analogs ? compact(storm.analogs.deaths_median, lang) : '—'}</strong>
              <span>{t(lang, 'impact.pastDeaths')}</span>
            </div>
            <div className="impact-stat">
              <IndianRupee size={20} />
              <strong>{storm.analogs ? inr(storm.analogs.damage_inr_median, lang) : '—'}</strong>
              <span>{t(lang, 'impact.pastLoss')}</span>
            </div>
          </div>
          {exp.largest_towns?.length > 0 && (
            <div className="impact-towns">
              <span><Building2 size={14} /> {t(lang, 'impact.towns')}:</span>
              {exp.largest_towns.slice(0, 8).map(tn => (
                <span key={`${tn.name}-${tn.country}`} className={`town-chip ${tn.zone}`}>{tn.name}</span>
              ))}
            </div>
          )}
          {storm.analogs && (
            <p className="impact-analogs">
              {fill(t(lang, 'impact.analogs'), { list: storm.analogs.storms.map(s => `${s.name} (${s.season})`).join(', ') })}
            </p>
          )}
        </div>
      )}

      {major && (
        <>
          {active && <h3 className="impact-sub">{t(lang, 'impact.pastTitle')}</h3>}
          <div className="impact-totals">
            <div><strong>{compact(major.totals.deaths, lang)}</strong><span>{fill(t(lang, 'impact.totalDeaths'), { n: major.storms.length })}</span></div>
            <div><strong>{inr(major.totals.damage_inr, lang)}</strong><span>{t(lang, 'impact.totalLoss')}</span></div>
          </div>
          <div className="grid-3 impact-cards">
            {major.storms.slice(0, 6).map(s => (
              <article key={s.sid} className="impact-card">
                <header><h4>{s.name}</h4><span>{s.season} · {s.countries.join(', ')}</span></header>
                <dl>
                  <div><dt>{t(lang, 'impact.deaths')}</dt><dd>{s.deaths?.toLocaleString(lang) ?? '—'}</dd></div>
                  <div><dt>{t(lang, 'impact.loss')}</dt><dd>{inr(s.damage_inr, lang)}</dd></div>
                  <div><dt>{t(lang, 'impact.people')}</dt><dd>{compact(s.people_gale_zone, lang)}</dd></div>
                </dl>
              </article>
            ))}
          </div>
          <p className="impact-note">{t(lang, 'impact.note')}</p>
        </>
      )}
    </>
  );
}
