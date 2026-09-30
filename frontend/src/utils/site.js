import { useEffect, useState } from 'react';
import { t } from '../i18n/translations';
import { fill } from '../i18n/strings_site';
import { api } from '../services/api';
import { isOfficial, isWatch } from '../types/cyclone';

const ALERT_RANK = { RED: 3, ORANGE: 2, YELLOW: 1 };
const DIRS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];

export const isActiveOfficial = s => isOfficial(s) && !isWatch(s);

/**
 * Rows inserted by backend/scripts/demo_cyclone.js (presentation scenario, not real data).
 * They are labelled "Demo scenario" unless VITE_HIDE_DEMO_BADGE=true.
 */
export const isDemo = s => s?.external_id === 'DEMO';
export const showDemoBadge = s => isDemo(s) && import.meta.env.VITE_HIDE_DEMO_BADGE !== 'true';

/** "12 min ago" / "3 h ago" in the current language. */
export function ago(iso, lang) {
  if (!iso) return '—';
  const min = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (min < 2) return t(lang, 'site.ago.now');
  if (min < 90) return fill(t(lang, 'site.ago.min'), { n: min });
  return fill(t(lang, 'site.ago.hour'), { n: Math.round(min / 60) });
}

export const seaName = (s, lang) => t(lang, `site.sea.${s?.basin || 'NIO'}`);
export const catName = (s, lang) => t(lang, `site.cat.${s?.imd_category}`) || s?.imd_category;

export function haversineKm(lat1, lon1, lat2, lon2) {
  const r = Math.PI / 180;
  const a = Math.sin(((lat2 - lat1) * r) / 2) ** 2
    + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(((lon2 - lon1) * r) / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(a));
}

/** 8-point compass direction from point 1 towards point 2. */
export function compass(lat1, lon1, lat2, lon2) {
  const r = Math.PI / 180;
  const y = Math.sin((lon2 - lon1) * r) * Math.cos(lat2 * r);
  const x = Math.cos(lat1 * r) * Math.sin(lat2 * r) - Math.sin(lat1 * r) * Math.cos(lat2 * r) * Math.cos((lon2 - lon1) * r);
  const deg = (Math.atan2(y, x) / r + 360) % 360;
  return DIRS[Math.round(deg / 45) % 8];
}

/** Official systems strongest-alert first, then satellite watch areas. */
export function rankSystems(systems) {
  return [...systems].sort((a, b) => {
    const oa = isActiveOfficial(a) ? 1 : 0; const ob = isActiveOfficial(b) ? 1 : 0;
    if (oa !== ob) return ob - oa;
    const ra = ALERT_RANK[a.alert_level] || 0; const rb = ALERT_RANK[b.alert_level] || 0;
    if (ra !== rb) return rb - ra;
    return (Number(b.sustained_wind_kmh) || 0) - (Number(a.sustained_wind_kmh) || 0);
  });
}

/**
 * Indicative chance of cyclone formation at a point, from current conditions (Open-Meteo) and
 * nearby satellite watch areas. A transparent checklist, not a forecast — the detailed readings are
 * in the expert panel's point inspector. Returns { level: 'none'|'low'|'medium'|'high', score, max }.
 * Warm sea (SST ≥ 26.5 °C) is required; it is normal for the NIO most of the year, so on its own
 * it gives "low". The level rises only with signs of an organising system:
 *   low pressure      MSLP < 1005 hPa       (+1)  (monsoon-season lows of 1006–1009 hPa are normal)
 *   strong wind       10 m wind > 45 km/h   (+1)
 *   satellite watch area within 500 km      (+2)
 * medium: score ≥ 1, high: score ≥ 3.
 */
export function formationChance(cond, lat, lon, systems = []) {
  if (!cond || cond.sstC == null) return { level: 'none', score: 0, max: 4 };
  if (cond.sstC < 26.5) return { level: 'low', score: 0, max: 4 };
  let score = 0;
  if (cond.mslpHpa != null && cond.mslpHpa < 1005) score += 1;
  if (cond.windKmh != null && cond.windKmh > 45) score += 1;
  if (systems.some(s => isWatch(s) && haversineKm(lat, lon, Number(s.current_lat), Number(s.current_lon)) < 500)) score += 2;
  const level = score >= 3 ? 'high' : score >= 1 ? 'medium' : 'low';
  return { level, score, max: 4 };
}

/** Nearest system to a point, with distance in km, or null. */
export function nearestSystem(systems, lat, lon) {
  let best = null;
  for (const s of systems) {
    const km = haversineKm(lat, lon, Number(s.current_lat), Number(s.current_lon));
    if (!best || km < best.km) best = { s, km };
  }
  return best;
}

/** Forecast GeoJSON for a system, refetched when it or its observation time changes. */
export function useForecast(system) {
  const [geojson, setGeojson] = useState(null);
  useEffect(() => {
    let cancelled = false;
    if (!system) {
      setGeojson(null);
      return undefined;
    }
    api.getCycloneForecast(system.cyclone_id)
      .then(g => { if (!cancelled) setGeojson(g); })
      .catch(() => { /* keep last track on transient errors */ });
    return () => { cancelled = true; };
  }, [system?.cyclone_id, system?.observation_time]); // eslint-disable-line react-hooks/exhaustive-deps
  return geojson;
}

/** Indian number words: 430,000 → "4.3 lakh", 26,000,000 → "2.6 crore" (Hindi: "4.3 लाख", "2.6 करोड़"). */
export function compact(n, lang) {
  if (n == null) return '—';
  const hi = lang === 'hi';
  const r = x => (Math.round(x * 10) / 10).toLocaleString(hi ? 'hi-IN' : 'en-IN');
  if (n >= 1e7) return `${r(n / 1e7)} ${hi ? 'करोड़' : 'crore'}`;
  if (n >= 1e5) return `${r(n / 1e5)} ${hi ? 'लाख' : 'lakh'}`;
  return Math.round(n).toLocaleString(hi ? 'hi-IN' : 'en-IN');
}

/** Rupees in Indian units: 1.015e12 → "₹1.02 lakh crore", 5.3e10 → "₹5,301 crore". */
export function inr(n, lang) {
  if (n == null) return '—';
  const hi = lang === 'hi';
  const loc = hi ? 'hi-IN' : 'en-IN';
  if (n >= 1e12) return `₹${(Math.round(n / 1e10) / 100).toLocaleString(loc)} ${hi ? 'लाख करोड़' : 'lakh crore'}`;
  if (n >= 1e7) return `₹${Math.round(n / 1e7).toLocaleString(loc)} ${hi ? 'करोड़' : 'crore'}`;
  return `₹${Math.round(n).toLocaleString(loc)}`;
}

export const ktToKmh = kt => (kt == null ? null : Math.round(kt * 1.852));
