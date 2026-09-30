import React, { useEffect, useState } from 'react';
import {
  MapPin, LocateFixed, Navigation, History, Users, Tornado,
} from 'lucide-react';
import { t } from '../../i18n/translations';
import { fill } from '../../i18n/strings_site';
import { fetchPointConditions } from '../../services/weatherService';
import { api } from '../../services/api';
import { catName, compact, compass, formationChance, isActiveOfficial, ktToKmh, nearestSystem } from '../../utils/site';
import { placeLabel } from '../../utils/weatherCodes';
import WeatherReport from './WeatherReport';

export const CITIES = [
  { name: 'Kolkata', lat: 22.57, lon: 88.36 }, { name: 'Digha', lat: 21.63, lon: 87.51 },
  { name: 'Bhubaneswar', lat: 20.30, lon: 85.82 }, { name: 'Puri', lat: 19.81, lon: 85.83 },
  { name: 'Visakhapatnam', lat: 17.69, lon: 83.22 }, { name: 'Kakinada', lat: 16.99, lon: 82.25 },
  { name: 'Nellore', lat: 14.44, lon: 79.99 }, { name: 'Chennai', lat: 13.08, lon: 80.27 },
  { name: 'Puducherry', lat: 11.93, lon: 79.83 }, { name: 'Port Blair', lat: 11.62, lon: 92.73 },
  { name: 'Thiruvananthapuram', lat: 8.52, lon: 76.94 }, { name: 'Kochi', lat: 9.93, lon: 76.27 },
  { name: 'Mangaluru', lat: 12.91, lon: 74.86 }, { name: 'Panaji (Goa)', lat: 15.49, lon: 73.83 },
  { name: 'Mumbai', lat: 19.08, lon: 72.88 }, { name: 'Veraval', lat: 20.91, lon: 70.37 },
  { name: 'Porbandar', lat: 21.64, lon: 69.61 }, { name: 'Kandla', lat: 23.03, lon: 70.22 },
];


/**
 * "Check your area": everything specific to one place — risk from active storms, live weather and a
 * 3-day outlook (Open-Meteo), the place's own cyclone history since 1980 and the population around it
 * (backend /impact/near: IBTrACS + GeoNames).
 */
export default function AreaCheck({ systems, lang }) {
  const [place, setPlace] = useState(null);
  const [cond, setCond] = useState(null);
  const [near, setNear] = useState(null);
  const [placeInfo, setPlaceInfo] = useState(null);
  const [status, setStatus] = useState('idle'); // idle | locating | loading | ready | error | locError

  useEffect(() => {
    if (!place) return undefined;
    let cancelled = false;
    setStatus('loading');
    setCond(null);
    setNear(null);
    setPlaceInfo(null);
    api.getPlace(place.lat, place.lon).then(p => { if (!cancelled) setPlaceInfo(p); }).catch(() => {});
    fetchPointConditions(place.lat, place.lon)
      .then(c => { if (!cancelled) { setCond(c); setStatus('ready'); } })
      .catch(() => { if (!cancelled) setStatus('error'); });
    api.getNear(place.lat, place.lon).then(n => { if (!cancelled) setNear(n); }).catch(() => {});
    return () => { cancelled = true; };
  }, [place]);

  const locate = () => {
    if (!navigator.geolocation) { setStatus('locError'); return; }
    setStatus('locating');
    navigator.geolocation.getCurrentPosition(
      p => setPlace({ name: t(lang, 'home.myLocation'), mine: true, lat: p.coords.latitude, lon: p.coords.longitude }),
      () => setStatus('locError'),
      { timeout: 10000 },
    );
  };

  const nearest = place ? nearestSystem(systems, place.lat, place.lon) : null;
  let risk = 'none';
  if (nearest) {
    if (!isActiveOfficial(nearest.s)) risk = 'far';
    else if (nearest.km < 300) risk = 'near';
    else if (nearest.km < 800) risk = 'watch';
    else risk = 'far';
  }
  const chance = cond && cond.sstC != null ? formationChance(cond, place.lat, place.lon, systems) : null;
  const stormName = s => s?.name || `${t(lang, 'historicalPage.unnamed')} (${s?.season})`;

  return (
    <div className="area-card">
      <div className="area-controls">
        <select className="field" value={CITIES.findIndex(c => c.name === place?.name)}
          onChange={e => setPlace(CITIES[Number(e.target.value)] || null)} aria-label={t(lang, 'home.chooseCity')}>
          <option value={-1}>{t(lang, 'home.chooseCity')}</option>
          {CITIES.map((c, i) => <option key={c.name} value={i}>{c.name}</option>)}
        </select>
        <button className="btn-ghost" onClick={locate}><LocateFixed size={16} /> {t(lang, 'home.useLocation')}</button>
      </div>

      {status === 'idle' && <p className="area-note">{t(lang, 'area.pick')}</p>}
      {status === 'locating' && <p className="area-note">{t(lang, 'home.locating')}</p>}
      {status === 'locError' && <p className="area-note">{t(lang, 'home.locError')}</p>}
      {status === 'error' && <p className="area-note">{t(lang, 'env.unavailable')}</p>}

      {place && (status === 'ready' || status === 'loading') && (
        <>
          <div className="area-title">
            <h3><MapPin size={18} /> {place.mine && placeInfo ? placeLabel(placeInfo, place.lat, place.lon, cond?.sstC != null && placeInfo.distance_km > 10, lang) : place.name}</h3>
            <span>{place.mine ? `${t(lang, 'home.myLocation')} · ` : ''}{place.lat.toFixed(4)}° N, {place.lon.toFixed(4)}° E</span>
          </div>

          <div className="area-result">
            <div className={`area-risk risk-${risk}`}>
              <span className="area-kicker">{t(lang, 'area.now')}</span>
              <p className="area-risk-text">{t(lang, `home.risk.${risk}`)}</p>
              <div className="area-nearest">
                <Navigation size={16} />
                <span>{t(lang, 'home.nearest')}:</span>
                <strong>
                  {nearest
                    ? `${nearest.s.cyclone_name || (isActiveOfficial(nearest.s) ? catName(nearest.s, lang) : t(lang, 'warn.watchLabel'))} · ${fill(t(lang, 'home.distance'), {
                      km: Math.round(nearest.km).toLocaleString(lang),
                      dir: compass(place.lat, place.lon, Number(nearest.s.current_lat), Number(nearest.s.current_lon)),
                    })}`
                    : t(lang, 'home.noStorm')}
                </strong>
              </div>
              {chance && (
                <div className="area-chance">
                  <Tornado size={16} />
                  <span>{t(lang, 'area.chanceSea')}:</span>
                  <strong className={`lvl-${chance.level}`}>{t(lang, `pin.level.${chance.level}`)}</strong>
                </div>
              )}
            </div>

            <div className="area-weather">
              <span className="area-kicker">{t(lang, 'wx.title')}</span>
              {cond ? <WeatherReport cond={cond} lang={lang} /> : <p className="area-note">{t(lang, 'inspector.loading')}</p>}
            </div>
          </div>

          {near && (
            <div className="area-block">
              <span className="area-kicker"><History size={14} /> {fill(t(lang, 'area.historyTitle'), { since: near.since, km: near.radius_km })}</span>
              <div className="history-grid">
                <div><strong>{near.storms}</strong><span>{t(lang, 'area.systems')}</span></div>
                <div><strong>{near.cyclonic_storms}</strong><span>{t(lang, 'area.cyclones')}</span></div>
                <div>
                  <strong>{near.last ? stormName(near.last) : '—'}</strong>
                  <span>{t(lang, 'area.last')}{near.last ? ` · ${near.last.season}` : ''}</span>
                </div>
                <div>
                  <strong>{near.strongest?.max_wind_kt ? stormName(near.strongest) : '—'}</strong>
                  <span>{t(lang, 'area.strongest')}{near.strongest?.max_wind_kt ? ` · ${ktToKmh(near.strongest.max_wind_kt)} km/h` : ''}</span>
                </div>
              </div>
              <p className="area-people"><Users size={14} /> {fill(t(lang, 'area.people'), { n: compact(near.people_within_50km, lang) })}</p>
            </div>
          )}
        </>
      )}
      <p className="area-disclaimer">{t(lang, 'home.guidance')}</p>
    </div>
  );
}
