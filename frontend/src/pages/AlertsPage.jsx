import React, { useEffect, useState } from 'react';
import { Anchor, Users, Building2, AlertOctagon, Satellite } from 'lucide-react';
import { t } from '../i18n/translations';
import { useData } from '../context/DataContext';
import { api } from '../services/api';
import { ALERT_COLORS, isOfficial, isWatch } from '../types/cyclone';

function AdvisoryCard({ adv, lang }) {
  const color = ALERT_COLORS[adv.alert_level] || '#a855f7';
  return (
    <div className="panel advisory-card" style={{ borderLeft: `4px solid ${color}` }}>
      <div className="panel-header">
        <h3 style={{ color }}>
          {adv.type === 'watch' ? <Satellite size={16} /> : <AlertOctagon size={16} />}{' '}
          {adv.alert_level || t(lang, 'source.watch')}
        </h3>
        <span className="muted-small">{new Date(adv.observation_time).toISOString().slice(0, 16).replace('T', ' ')} UTC</span>
      </div>
      {adv.fallback && <p className="muted-small">{t(lang, 'alertsPage.englishOnly')}</p>}
      <p className="advisory-summary">{adv.threat_summary}</p>
      {adv.directives_fishermen && (
        <ul className="advisory-directives">
          <li><Anchor size={14} /> <strong>{t(lang, 'alertsPage.fishermen')}:</strong> {adv.directives_fishermen}</li>
          <li><Users size={14} /> <strong>{t(lang, 'alertsPage.public')}:</strong> {adv.directives_public}</li>
          <li><Building2 size={14} /> <strong>{t(lang, 'alertsPage.administration')}:</strong> {adv.directives_administration}</li>
        </ul>
      )}
      <p className="advisory-disclaimer">
        {adv.disclaimer}
        {adv.source_url && <> · <a href={adv.source_url} target="_blank" rel="noopener noreferrer">{t(lang, 'panel.viewSource')}</a></>}
      </p>
    </div>
  );
}

export default function AlertsPage() {
  const { lang, systems } = useData();
  const [advisories, setAdvisories] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setAdvisories(null);
    Promise.all(systems.map(s => api.getAdvisory(s.cyclone_id, lang).catch(() => null)))
      .then(list => { if (!cancelled) setAdvisories(list.filter(Boolean)); });
    return () => { cancelled = true; };
  }, [lang, systems.map(s => `${s.cyclone_id}@${s.observation_time}`).join(',')]); // eslint-disable-line react-hooks/exhaustive-deps

  const official = (advisories || []).filter(a => a.type === 'advisory');
  const watches = (advisories || []).filter(a => a.type === 'watch');
  const noOfficial = !systems.some(s => isOfficial(s) && !isWatch(s));

  return (
    <div className="page">
      <h2 className="page-title">{t(lang, 'alertsPage.title')}</h2>
      {advisories === null && systems.length > 0 && <p className="empty-note">{t(lang, 'alertsPage.loading')}</p>}
      {noOfficial && <div className="panel"><p className="empty-note">{t(lang, 'alertsPage.none')}</p></div>}
      {official.map(a => <AdvisoryCard key={a.cyclone_id} adv={a} lang={lang} />)}
      {watches.length > 0 && (
        <>
          <h3 className="section-title">{t(lang, 'alertsPage.watchTitle')}</h3>
          {watches.map(a => <AdvisoryCard key={a.cyclone_id} adv={a} lang={lang} />)}
        </>
      )}
    </div>
  );
}
