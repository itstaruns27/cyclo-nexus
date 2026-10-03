import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { t } from '../../i18n/translations';
import { fill } from '../../i18n/strings_site';
import { api } from '../../services/api';
import { compact, inr } from '../../utils/site';

/** Recorded toll of major past cyclones — plain, low-emphasis reference block on the home page. */
export default function PastImpact({ lang }) {
  const [major, setMajor] = useState(null);
  useEffect(() => { api.getMajorImpacts().then(setMajor).catch(() => {}); }, []);
  if (!major) return null;
  return (
    <div className="past-impact">
      <p className="past-totals">
        <strong>{compact(major.totals.deaths, lang)}</strong> {fill(t(lang, 'impact.totalDeaths'), { n: major.storms.length })}
        <span aria-hidden="true"> · </span>
        <strong>{inr(major.totals.damage_inr, lang)}</strong> {t(lang, 'impact.totalLoss')}
      </p>
      <div className="grid-3 impact-cards">
        {major.storms.slice(0, 6).map(s => (
          <Link key={s.sid} to={`/storm/${s.sid}`} className="impact-card">
            <header><h4>{s.name}</h4><span>{s.season} · {s.countries.join(', ')}</span></header>
            <dl>
              <div><dt>{t(lang, 'impact.deaths')}</dt><dd>{s.deaths?.toLocaleString(lang) ?? '—'}</dd></div>
              <div><dt>{t(lang, 'impact.loss')}</dt><dd>{inr(s.damage_inr, lang)}</dd></div>
              <div><dt>{t(lang, 'impact.people')}</dt><dd>{compact(s.people_storm_zone ?? s.people_gale_zone, lang)}</dd></div>
            </dl>
          </Link>
        ))}
      </div>
      <p className="impact-note">{t(lang, 'impact.note')}</p>
    </div>
  );
}
