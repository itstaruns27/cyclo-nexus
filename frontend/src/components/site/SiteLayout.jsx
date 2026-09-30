import React, { useEffect } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import WarningBar from './WarningBar';
import TopNav from './TopNav';
import SiteFooter from './SiteFooter';

export default function SiteLayout() {
  const { pathname, hash } = useLocation();

  // New page → top; "#section" links → that section (after the page has rendered)
  useEffect(() => {
    if (hash) {
      const id = setTimeout(() => document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: 'smooth' }), 60);
      return () => clearTimeout(id);
    }
    window.scrollTo(0, 0);
    return undefined;
  }, [pathname, hash]);

  return (
    <div className="site">
      <WarningBar />
      <TopNav />
      <main className="site-main"><Outlet /></main>
      <SiteFooter />
    </div>
  );
}
