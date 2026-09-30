import React from 'react';
import { Link } from 'react-router-dom';
import { WifiOff, Clock } from 'lucide-react';
import { t } from '../i18n/translations';
import { useData } from '../context/DataContext';

/** Warns when the API is unreachable or a data component is stale (from /api/v1/health). */
export default function FreshnessBanner() {
  const { lang, health, offline } = useData();

  if (offline) {
    return (
      <div className="freshness-banner error" role="alert">
        <WifiOff size={16} /> {t(lang, 'banner.offline')}
      </div>
    );
  }
  const stale = (health?.components || []).filter(c => c.stale);
  if (!stale.length) return null;
  return (
    <div className="freshness-banner warn" role="status">
      <Clock size={16} />
      {t(lang, 'banner.stale')} {stale.map(c => t(lang, `banner.${c.component}`)).join(', ')}.
      <Link to="/status">{t(lang, 'nav.status')} →</Link>
    </div>
  );
}
