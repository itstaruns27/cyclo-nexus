import { Sun, CloudSun, Cloud, CloudFog, CloudDrizzle, CloudRain, CloudLightning, CloudSnow } from 'lucide-react';
import { fill } from '../i18n/strings_site';
import { t } from '../i18n/translations';

/** WMO weather interpretation codes (as used by Open-Meteo) → icon + label key. */
const GROUPS = [
  { codes: [0], icon: Sun, key: 'clear' },
  { codes: [1, 2], icon: CloudSun, key: 'partly' },
  { codes: [3], icon: Cloud, key: 'overcast' },
  { codes: [45, 48], icon: CloudFog, key: 'fog' },
  { codes: [51, 53, 55, 56, 57], icon: CloudDrizzle, key: 'drizzle' },
  { codes: [61, 63, 66, 80, 81], icon: CloudRain, key: 'rain' },
  { codes: [65, 67, 82], icon: CloudRain, key: 'heavyRain' },
  { codes: [71, 73, 75, 77, 85, 86], icon: CloudSnow, key: 'snow' },
  { codes: [95, 96, 99], icon: CloudLightning, key: 'thunder' },
];

export function weatherInfo(code, lang) {
  const g = GROUPS.find(x => x.codes.includes(code)) || { icon: Cloud, key: 'unknown' };
  return { Icon: g.icon, label: t(lang, `wx.code.${g.key}`) };
}

const COUNTRIES = { IN: 'India', BD: 'Bangladesh', MM: 'Myanmar', LK: 'Sri Lanka', PK: 'Pakistan', OM: 'Oman', YE: 'Yemen', MV: 'Maldives', TH: 'Thailand', MY: 'Malaysia', ID: 'Indonesia', SO: 'Somalia', IR: 'Iran', AE: 'UAE', NP: 'Nepal', BT: 'Bhutan', CN: 'China' };

/** Rough sea name for a point at sea (NIO only). */
export function seaAt(lat, lon, lang) {
  if (lat < 5) return t(lang, 'site.sea.NIO');
  return t(lang, lon < 77.5 ? 'site.sea.AS' : 'site.sea.BOB');
}

/**
 * Human label for any point: "Puri, India" when close to a town, "32 km NE of Puri, India" further
 * inland, "Bay of Bengal · 180 km SE of Puri" at sea. place = backend /weather/place result.
 */
export function placeLabel(place, lat, lon, atSea, lang) {
  if (!place) return atSea ? seaAt(lat, lon, lang) : `${lat.toFixed(2)}° N, ${lon.toFixed(2)}° E`;
  const town = `${place.name}, ${COUNTRIES[place.country] || place.country}`;
  if (atSea) return `${seaAt(lat, lon, lang)} · ${fill(t(lang, 'wx.fromTown'), { km: place.distance_km, dir: place.direction, town })}`;
  if (place.distance_km <= 10) return town;
  return fill(t(lang, 'wx.fromTown'), { km: place.distance_km, dir: place.direction, town });
}
