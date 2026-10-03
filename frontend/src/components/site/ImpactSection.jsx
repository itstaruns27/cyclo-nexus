import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { Users, AlertOctagon, Building2, HeartCrack, IndianRupee } from 'lucide-react';
import { t } from '../../i18n/translations';
import { fill } from '../../i18n/strings_site';
import { api } from '../../services/api';
import { compact, isActiveOfficial, inr } from '../../utils/site';

/**
 * Home-page impact module (plain language).
 * Active official storm → people living in its path (now + forecast) and what similar past storms caused.
 * Shown on the home page only while an official storm is active (past storms live on /history).
 */
export default function ImpactSection({ lead, lang }) {
  const active = lead && isActiveOfficial(lead) ? lead : null;
  const [storm, setStorm] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setStorm(null);
    if (active) api.getCycloneImpact(active.cyclone_id).then(d => { if (!cancelled) setStorm(d); }).catch(() => {});
    return () => { cancelled = true; };
  }, [active?.cyclone_id, active?.observation_time]); // eslint-disable-line react-hooks/exhaustive-deps

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
          <Link className="btn-solid impact-more" to={`/storm/${encodeURIComponent(active.cyclone_id)}#impact`}>{t(lang, 'alertsX.details')} <ArrowRight size={16} /></Link>
        </div>
      )}
    </>
  );
}
