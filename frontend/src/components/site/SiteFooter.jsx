import React from 'react';
import { Link } from 'react-router-dom';
import { t } from '../../i18n/translations';
import { useData } from '../../context/DataContext';
import { Logo } from './TopNav';

const OFFICIAL = [
  { name: 'India Meteorological Department', url: 'https://mausam.imd.gov.in' },
  { name: 'NDMA', url: 'https://ndma.gov.in' },
  { name: 'INCOIS', url: 'https://incois.gov.in' },
];
const DATA = [
  { name: 'ISRO MOSDAC (INSAT-3DS)', url: 'https://mosdac.gov.in' },
  { name: 'NASA GPM IMERG', url: 'https://gpm.nasa.gov/data/imerg' },
  { name: 'JTWC', url: 'https://www.metoc.navy.mil/jtwc/jtwc.html' },
  { name: 'NOAA IBTrACS', url: 'https://www.ncei.noaa.gov/products/international-best-track-archive' },
  { name: 'Open-Meteo', url: 'https://open-meteo.com' },
];

export default function SiteFooter() {
  const { lang } = useData();
  const ext = list => list.map(l => (
    <li key={l.name}><a href={l.url} target="_blank" rel="noopener noreferrer">{l.name}</a></li>
  ));
  return (
    <footer className="site-footer">
      <div className="site-container footer-grid">
        <div className="footer-about">
          <div className="brand"><Logo /><span>{t(lang, 'brand')}</span></div>
          <p>{t(lang, 'siteFooter.about')}</p>
        </div>
        <div>
          <h4>{t(lang, 'siteFooter.explore')}</h4>
          <ul>
            <li><Link to="/">{t(lang, 'site.nav.home')}</Link></li>
            <li><Link to="/alerts">{t(lang, 'site.nav.alerts')}</Link></li>
            <li><Link to="/history">{t(lang, 'site.nav.history')}</Link></li>
            <li><Link to="/expert">{t(lang, 'site.nav.expert')}</Link></li>
          </ul>
        </div>
        <div><h4>{t(lang, 'siteFooter.official')}</h4><ul>{ext(OFFICIAL)}</ul></div>
        <div><h4>{t(lang, 'siteFooter.data')}</h4><ul>{ext(DATA)}</ul></div>
      </div>
      <div className="site-container footer-bottom">{t(lang, 'siteFooter.disclaimer')}</div>
    </footer>
  );
}
