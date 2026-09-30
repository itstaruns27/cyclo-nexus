import React, { useEffect, useState } from 'react';
import { t } from '../../i18n/translations';
import { useData } from '../../context/DataContext';
import { api } from '../../services/api';

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const STRENGTH = [['D', '#60a5fa'], ['CS', '#fbbf24'], ['SCS', '#fb923c'], ['VSCS', '#ef4444']];

// From docs/validation_report.md (physics_dav_v1, 30 Sep 2026)
const VALIDATION = [
  ['clim.v.threshold', '0.95'], ['clim.v.pod', '8 / 14 (57%)'], ['clim.v.far', '0 / 6'], ['clim.v.error', '101–463 km (median ≈ 330)'],
];

function Bars({ values, labels, highlight }) {
  const max = Math.max(...values, 1);
  return (
    <div className="bars">
      {values.map((v, i) => (
        <div key={labels[i]} className={`bar${highlight === i ? ' now' : ''}`}>
          <span className="bar-val">{v}</span>
          <span className="bar-fill" style={{ height: `${(v / max) * 100}%` }} />
          <span className="bar-lab">{labels[i]}</span>
        </div>
      ))}
    </div>
  );
}

/** IBTrACS climatology (1980–present) + satellite detector validation. */
export default function Climatology() {
  const { lang } = useData();
  const [c, setC] = useState(null);
  useEffect(() => { api.getClimatology().then(setC).catch(() => {}); }, []);
  if (!c) return null;
  const decades = Object.entries(c.by_decade).sort();
  const total = Object.values(c.by_strength).reduce((a, b) => a + b, 0);

  return (
    <div className="page">
      <h2 className="page-title">{t(lang, 'clim.title')}</h2>
      <div className="clim-grid">
        <div className="panel">
          <div className="panel-header"><h3>{t(lang, 'clim.byMonth')}</h3><span className="muted-small">{c.storms} {t(lang, 'clim.systems')} · {c.per_year}/{t(lang, 'clim.year')}</span></div>
          <Bars values={c.by_month} labels={MONTHS} highlight={new Date().getUTCMonth()} />
        </div>
        <div className="panel">
          <div className="panel-header"><h3>{t(lang, 'clim.byDecade')}</h3></div>
          <Bars values={decades.map(d => d[1])} labels={decades.map(d => d[0])} />
        </div>
        <div className="panel">
          <div className="panel-header"><h3>{t(lang, 'clim.byStrength')}</h3></div>
          <div className="stack">
            {STRENGTH.map(([k, col]) => (
              <span key={k} style={{ flex: c.by_strength[k] || 0.001, background: col }} title={`${k}: ${c.by_strength[k]}`} />
            ))}
          </div>
          <ul className="legend-list">
            {STRENGTH.map(([k, col]) => (
              <li key={k}><i style={{ background: col }} />{t(lang, `clim.s.${k}`)}<b>{c.by_strength[k]} ({Math.round((100 * c.by_strength[k]) / total)}%)</b></li>
            ))}
          </ul>
          <p className="muted-small">{t(lang, 'clim.basins')}: {Object.entries(c.by_basin).map(([b, n]) => `${b} ${n}`).join(' · ')}</p>
        </div>
        <div className="panel">
          <div className="panel-header"><h3>{t(lang, 'clim.validation')}</h3></div>
          <dl className="kv">
            {VALIDATION.map(([k, v]) => <div key={k}><dt>{t(lang, k)}</dt><dd>{v}</dd></div>)}
          </dl>
          <p className="muted-small">{t(lang, 'clim.validationNote')}</p>
        </div>
      </div>
    </div>
  );
}
