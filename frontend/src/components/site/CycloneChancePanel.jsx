import React, { useEffect, useState } from 'react';
import { X, AlertTriangle, Eye, Mountain, Waves, MapPin } from 'lucide-react';
import { t } from '../../i18n/translations';
import { fill } from '../../i18n/strings_site';
import { useData } from '../../context/DataContext';
import { isWatch, ALERT_COLORS } from '../../types/cyclone';
import { fetchPointConditions } from '../../services/weatherService';
import { api } from '../../services/api';
import { catName, compass, formationChance, isActiveOfficial, nearestSystem } from '../../utils/site';
import { placeLabel } from '../../utils/weatherCodes';
import WeatherReport from './WeatherReport';

const LEVELS = ['low', 'medium', 'high'];

/**
 * Public map-click panel: where is this, what is the weather, and is there (or could there be) a cyclone.
 * Official storm within 500 km → that storm; otherwise the indicative formation chance.
 */
export default function CycloneChancePanel({ lngLat, onClose }) {
  const { lang, systems } = useData();
  const [state, setState] = useState({ loading: true });
  const [place, setPlace] = useState(null);
  const [placeDone, setPlaceDone] = useState(false);
  const { lat, lng: lon } = lngLat;

  useEffect(() => {
    let cancelled = false;
    setState({ loading: true });
    setPlace(null);
    setPlaceDone(false);
    fetchPointConditions(lat, lon)
      .then(cond => { if (!cancelled) setState({ cond }); })
      .catch(() => { if (!cancelled) setState({ error: true }); });
    api.getPlace(lat, lon).then(p => { if (!cancelled) setPlace(p); }).catch(() => {})
      .finally(() => { if (!cancelled) setPlaceDone(true); });
    return () => { cancelled = true; };
  }, [lat, lon]);

  const near = nearestSystem(systems, lat, lon);
  const storm = near && isActiveOfficial(near.s) && near.km < 500 ? near : null;
  const watch = !storm && near && isWatch(near.s) && near.km < 500 ? near : null;
  const chance = state.cond ? formationChance(state.cond, lat, lon, systems) : null;
  const atSea = state.cond ? state.cond.sstC != null : false;

  return (
    <div className="chance-panel" role="dialog" aria-label={t(lang, 'pin.title')}>
      <div className="chance-head">
        <div>
          <strong className="chance-place"><MapPin size={14} /> {state.loading && !placeDone ? '…' : placeLabel(place, lat, lon, atSea, lang)}</strong>
          <span>{lat.toFixed(2)}° N, {lon.toFixed(2)}° E</span>
        </div>
        <button onClick={onClose} aria-label="Close"><X size={16} /></button>
      </div>

      {state.loading && <p className="chance-note">{t(lang, 'inspector.loading')}</p>}
      {state.error && <p className="chance-note">{t(lang, 'inspector.error')}</p>}
      {state.cond && <WeatherReport cond={state.cond} lang={lang} compact />}

      <div className="chance-status">
        {storm && (
          <div className="chance-hero chance-storm" style={{ '--c': ALERT_COLORS[storm.s.alert_level] || ALERT_COLORS.YELLOW }}>
            <AlertTriangle size={22} />
            <div>
              <strong>{fill(t(lang, 'pin.stormNear'), { name: storm.s.cyclone_name || catName(storm.s, lang) })}</strong>
              <span>{fill(t(lang, 'pin.stormDist'), {
                km: Math.round(storm.km), dir: compass(lat, lon, Number(storm.s.current_lat), Number(storm.s.current_lon), lang),
                cat: catName(storm.s, lang),
              })}</span>
            </div>
          </div>
        )}

        {!storm && state.cond && !atSea && (
          <div className="chance-hero chance-land">
            <Mountain size={22} />
            <div><strong>{t(lang, 'pin.noCyclone')}</strong><span>{t(lang, 'pin.land')}</span></div>
          </div>
        )}

        {!storm && chance && atSea && (
          <>
            <div className="chance-hero">
              {watch ? <Eye size={22} /> : <Waves size={22} />}
              <div>
                <strong>{t(lang, 'pin.noCyclone')}</strong>
                <span>{watch ? t(lang, 'pin.watchNear') : t(lang, 'pin.chanceLabel')}</span>
              </div>
            </div>
            <div className={`chance-meter level-${chance.level}`} aria-label={t(lang, `pin.level.${chance.level}`)}>
              {LEVELS.map(l => <span key={l} className={LEVELS.indexOf(l) <= LEVELS.indexOf(chance.level) ? 'on' : ''} />)}
            </div>
            <div className="chance-level">{t(lang, 'pin.chance')}: <strong>{t(lang, `pin.level.${chance.level}`)}</strong></div>
          </>
        )}
      </div>
      <p className="chance-foot">{t(lang, 'pin.foot')}</p>
    </div>
  );
}
