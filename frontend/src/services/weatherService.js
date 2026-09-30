/**
 * Point weather from Open-Meteo (free, no key, CORS-enabled) and simplified
 * cyclogenesis indicators (v3 Micro-Task 4.1).
 *
 * The indicators are a transparent checklist, not a forecast:
 *   warm ocean     SST ≥ 26.5 °C
 *   low pressure   ΔP = max(0, 1013 − MSLP) > 0
 *   strong winds   10 m wind > 35 km/h
 */

const FORECAST_URL = 'https://api.open-meteo.com/v1/forecast';
const MARINE_URL = 'https://marine-api.open-meteo.com/v1/marine';

/** Current conditions at a point. SST is null over land. One retry on a transient failure. */
export async function fetchPointConditions(lat, lon) {
  try {
    return await fetchOnce(lat, lon);
  } catch {
    await new Promise(r => setTimeout(r, 800));
    return fetchOnce(lat, lon);
  }
}

async function fetchOnce(lat, lon) {
  const q = `latitude=${lat.toFixed(3)}&longitude=${lon.toFixed(3)}`;
  const [wx, sea] = await Promise.all([
    fetch(`${FORECAST_URL}?${q}&current=temperature_2m,relative_humidity_2m,pressure_msl,wind_speed_10m,wind_direction_10m,precipitation`
      + ',apparent_temperature,weather_code,wind_gusts_10m,cloud_cover'
      + '&daily=precipitation_sum,wind_gusts_10m_max,temperature_2m_max,temperature_2m_min,weather_code,precipitation_probability_max'
      + '&forecast_days=3&timezone=auto').then(r => {
      if (!r.ok) throw new Error(`Open-Meteo HTTP ${r.status}`);
      return r.json();
    }),
    fetch(`${MARINE_URL}?${q}&current=sea_surface_temperature`).then(r => (r.ok ? r.json() : null)).catch(() => null),
  ]);
  const c = wx.current || {};
  return {
    time: c.time || null,
    utcOffsetS: wx.utc_offset_seconds ?? 0,
    temperatureC: c.temperature_2m ?? null,
    humidityPct: c.relative_humidity_2m ?? null,
    mslpHpa: c.pressure_msl ?? null,
    windKmh: c.wind_speed_10m ?? null,
    windDirDeg: c.wind_direction_10m ?? null,
    precipMm: c.precipitation ?? null,
    precipTodayMm: wx.daily?.precipitation_sum?.[0] ?? null,
    sstC: sea?.current?.sea_surface_temperature ?? null,
    feelsLikeC: c.apparent_temperature ?? null,
    weatherCode: c.weather_code ?? null,
    gustKmh: c.wind_gusts_10m ?? null,
    cloudPct: c.cloud_cover ?? null,
    // 3-day outlook: [{ date, rainMm, gustKmh, maxTempC }]
    outlook: (wx.daily?.time || []).map((d, i) => ({
      date: d, rainMm: wx.daily.precipitation_sum?.[i] ?? null,
      gustKmh: wx.daily.wind_gusts_10m_max?.[i] ?? null, maxTempC: wx.daily.temperature_2m_max?.[i] ?? null,
      minTempC: wx.daily.temperature_2m_min?.[i] ?? null, code: wx.daily.weather_code?.[i] ?? null,
      rainChancePct: wx.daily.precipitation_probability_max?.[i] ?? null,
    })),
  };
}

export function genesisIndicators(cond) {
  const checks = [
    { key: 'sst', ok: cond.sstC != null && cond.sstC >= 26.5, value: cond.sstC, unit: '°C', threshold: '≥ 26.5' },
    { key: 'pressure', ok: cond.mslpHpa != null && 1013 - cond.mslpHpa > 0,
      value: cond.mslpHpa != null ? Math.max(0, 1013 - cond.mslpHpa) : null, unit: 'hPa ΔP', threshold: '> 0' },
    { key: 'wind', ok: cond.windKmh != null && cond.windKmh > 35, value: cond.windKmh, unit: 'km/h', threshold: '> 35' },
  ];
  return { checks, met: checks.filter(c => c.ok).length, total: checks.length, overLand: cond.sstC == null };
}
