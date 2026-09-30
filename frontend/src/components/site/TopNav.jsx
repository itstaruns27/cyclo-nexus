import React, { useEffect, useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import { t, LANGUAGES } from '../../i18n/translations';
import { useData } from '../../context/DataContext';

const LINKS = [
  { to: '/', key: 'home', end: true },
  { to: '/alerts', key: 'alerts' },
  { to: '/history', key: 'history' },
  { to: '/expert', key: 'expert' },
];

export function Logo() {
  return (
    <svg className="logo-mark" viewBox="0 0 32 32" aria-hidden="true">
      <circle cx="16" cy="16" r="15" fill="currentColor" />
      <path d="M16 16c0-5 3.5-8.5 9-8-4 .6-6.6 3.4-7 8z M16 16c0 5-3.5 8.5-9 8 4-.6 6.6-3.4 7-8z
        M16 16c-5 0-8.5-3.5-8-9 .6 4 3.4 6.6 8 7z M16 16c5 0 8.5 3.5 8 9-.6-4-3.4-6.6-8-7z" fill="#fff" />
      <circle cx="16" cy="16" r="2.6" fill="currentColor" stroke="#fff" strokeWidth="1.6" />
    </svg>
  );
}

export default function TopNav() {
  const { lang, setLang, systems } = useData();
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  const alerts = systems.filter(s => s.alert_level).length;

  useEffect(() => { setOpen(false); }, [pathname]);

  return (
    <header className="topnav">
      <div className="site-container topnav-inner">
        <Link to="/" className="brand" aria-label={t(lang, 'brand')}>
          <Logo />
          <span>{t(lang, 'brand')}</span>
        </Link>

        <nav className={`topnav-links${open ? ' open' : ''}`} aria-label="Main">
          {LINKS.map(l => (
            <NavLink key={l.key} to={l.to} end={l.end} className={({ isActive }) => `topnav-link${isActive ? ' active' : ''}`}>
              {t(lang, `site.nav.${l.key}`)}
              {l.key === 'alerts' && alerts > 0 && <span className="nav-dot" aria-label={`${alerts}`} />}
            </NavLink>
          ))}
        </nav>

        <div className="topnav-actions">
          <select className="lang-pill" value={lang} onChange={e => setLang(e.target.value)} aria-label="Language">
            {LANGUAGES.map(l => <option key={l.code} value={l.code}>{l.native}</option>)}
          </select>
          <button className="menu-toggle" onClick={() => setOpen(o => !o)} aria-label={t(lang, 'menu')} aria-expanded={open}>
            {open ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>
    </header>
  );
}
