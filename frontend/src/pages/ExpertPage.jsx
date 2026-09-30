import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import StatCards from '../components/StatCards';
import CycloneMap from '../components/CycloneMap';
import CycloneDetails from '../components/CycloneDetails';
import BottomPanels from '../components/BottomPanels';
import FreshnessBanner from '../components/FreshnessBanner';
import ForecastPage from './ForecastPage';
import AlertsPage from './AlertsPage';
import StatusPage from './StatusPage';
import ExpertImpact from '../components/expert/ExpertImpact';
import Climatology from '../components/expert/Climatology';
import { t } from '../i18n/translations';
import { useData } from '../context/DataContext';
import { useForecast } from '../utils/site';

const SECTIONS = ['overview', 'map', 'forecast', 'impact', 'advisories', 'climatology', 'health'];

/**
 * Technical view for authorities and experts: every number the platform has, with sources,
 * official vs experimental labels, full advisories (fishermen / administration) and system health.
 */
export default function ExpertPage() {
  const { lang, systems, selected } = useData();
  const forecast = useForecast(selected);

  return (
    <div className="expert">
      <div className="expert-head">
        <div className="site-container">
          <span className="eyebrow">Cyclo-Nexus · SIH26070</span>
          <h1>{t(lang, 'expert.title')}</h1>
          <p>{t(lang, 'expert.subtitle')}</p>
        </div>
      </div>

      <nav className="subnav" aria-label={t(lang, 'expert.title')}>
        <div className="site-container subnav-inner">
          {SECTIONS.map(s => <a key={s} href={`#${s}`}>{t(lang, `expert.nav.${s}`)}</a>)}
          <Link to="/history" className="subnav-extra">{t(lang, 'expert.history')} <ArrowRight size={14} /></Link>
        </div>
      </nav>

      <div className="site-container expert-body">
        <FreshnessBanner />

        <section id="overview" className="expert-section">
          <h2 className="page-title">{t(lang, 'expert.nav.overview')}</h2>
          <StatCards />
        </section>

        <section id="map" className="expert-section">
          <h2 className="page-title">{t(lang, 'expert.nav.map')}</h2>
          <div className="dashboard-grid">
            <CycloneMap forecastGeoJSON={forecast} systems={systems} selected={selected} />
            <CycloneDetails />
          </div>
          <BottomPanels cyclone={selected} forecastGeoJSON={forecast} />
        </section>

        <section id="forecast" className="expert-section"><ForecastPage /></section>
        <section id="impact" className="expert-section"><ExpertImpact /></section>
        <section id="advisories" className="expert-section"><AlertsPage /></section>
        <section id="climatology" className="expert-section"><Climatology /></section>
        <section id="health" className="expert-section"><StatusPage /></section>
      </div>
    </div>
  );
}
