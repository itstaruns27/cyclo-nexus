import React, { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { IMD_COLORS, IMD_SCALE } from '../../types/cyclone';
import { t } from '../../i18n/translations';

/**
 * Wind and pressure through the storm's life — two charts on one shared time axis (never a dual
 * axis). Wind sits on the IMD category bands; a shared crosshair + tooltip follows the pointer and
 * is synced with the map slider through `active` / `onActive` (index into `points`).
 */
const KMH = 1.852;
const PAD = { l: 44, r: 16, t: 12, b: 26 };

function useWidth(ref) {
  const [w, setW] = useState(720);
  useLayoutEffect(() => {
    if (!ref.current) return undefined;
    const ro = new ResizeObserver(([e]) => setW(Math.max(280, Math.round(e.contentRect.width))));
    ro.observe(ref.current);
    return () => ro.disconnect();
  }, [ref]);
  return w;
}

const fmtDay = (ms, lang) => new Date(ms).toLocaleDateString(lang === 'hi' ? 'hi-IN' : 'en-IN', { day: 'numeric', month: 'short', timeZone: 'UTC' });
const fmtTime = (ms, lang) => new Date(ms).toLocaleString(lang === 'hi' ? 'hi-IN' : 'en-IN',
  { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'UTC', hour12: false }) + ' UTC';

function niceMax(v, step) {
  return Math.ceil(v / step) * step;
}

export default function IntensityCharts({ points, forecast = [], landfalls = [], nowTime = null, active, onActive, lang }) {
  const box = useRef(null);
  const width = useWidth(box);
  const series = useMemo(() => points.map((p, i) => ({
    i, ms: new Date(p.time).getTime(), wind: p.wind_kt == null ? null : p.wind_kt * KMH, pres: p.pressure_hpa, grade: p.grade,
  })), [points]);
  const fc = useMemo(() => forecast.map(f => ({ ms: f.ms, wind: f.wind_kmh })), [forecast]);

  const all = [...series.map(s => s.ms), ...fc.map(f => f.ms)];
  const x0 = Math.min(...all); const x1 = Math.max(...all);
  const innerW = width - PAD.l - PAD.r;
  const x = ms => PAD.l + ((ms - x0) / Math.max(1, x1 - x0)) * innerW;

  const windMax = niceMax(Math.max(130, ...series.map(s => s.wind || 0), ...fc.map(f => f.wind || 0)) + 10, 50);
  const presVals = series.map(s => s.pres).filter(v => v != null);
  const pMin = presVals.length ? Math.floor((Math.min(...presVals) - 4) / 10) * 10 : 950;
  const pMax = presVals.length ? Math.ceil((Math.max(...presVals) + 2) / 5) * 5 : 1010;

  const WH = 230; const PH = 130;
  const yW = v => PAD.t + (1 - v / windMax) * (WH - PAD.t - PAD.b);
  const yP = v => PAD.t + (1 - (v - pMin) / Math.max(1, pMax - pMin)) * (PH - PAD.t - PAD.b);

  const path = (arr, key, y) => {
    let d = ''; let pen = false;
    for (const s of arr) {
      if (s[key] == null) { pen = false; continue; }
      d += `${pen ? 'L' : 'M'}${x(s.ms).toFixed(1)},${y(s[key]).toFixed(1)}`;
      pen = true;
    }
    return d;
  };

  // Day ticks (≤ 8)
  const days = [];
  const dayMs = 86400e3;
  const stepDays = Math.max(1, Math.ceil((x1 - x0) / dayMs / 8));
  for (let d = Math.ceil(x0 / dayMs) * dayMs; d <= x1; d += stepDays * dayMs) days.push(d);

  const pick = clientX => {
    const r = box.current.getBoundingClientRect();
    const ms = x0 + ((clientX - r.left - PAD.l) / innerW) * (x1 - x0);
    let best = 0;
    series.forEach((s, i) => { if (Math.abs(s.ms - ms) < Math.abs(series[best].ms - ms)) best = i; });
    onActive(best);
  };

  const cur = active != null ? series[active] : null;
  const peak = series.reduce((a, s) => (s.wind != null && (!a || s.wind > a.wind) ? s : a), null);
  const lastObs = series[series.length - 1];
  const fcPath = fc.length && lastObs?.wind != null
    ? `M${x(lastObs.ms)},${yW(lastObs.wind)}` + fc.map(f => `L${x(f.ms)},${yW(f.wind)}`).join('')
    : '';

  const Axis = ({ h }) => (
    <g className="ch-axis">
      <line x1={PAD.l} x2={width - PAD.r} y1={h - PAD.b} y2={h - PAD.b} />
      {days.map(d => (
        <text key={d} x={x(d)} y={h - 8} textAnchor="middle">{fmtDay(d, lang)}</text>
      ))}
    </g>
  );

  const Cross = ({ h }) => (cur ? <line className="ch-cross" x1={x(cur.ms)} x2={x(cur.ms)} y1={PAD.t} y2={h - PAD.b} /> : null);

  return (
    <div className="intensity-charts" ref={box}
      onPointerMove={e => pick(e.clientX)} onPointerDown={e => pick(e.clientX)}>
      <div className="ch-title">{t(lang, 'storm.chart.wind')}</div>
      <svg width={width} height={WH} role="img" aria-label={t(lang, 'storm.chart.wind')}>
        {/* IMD category bands */}
        {IMD_SCALE.map(c => {
          const top = Math.min(windMax, c.maxWindKmh); const bot = c.minWindKmh;
          if (bot >= windMax) return null;
          return (
            <g key={c.category}>
              <rect x={PAD.l} width={innerW} y={yW(top)} height={Math.max(0, yW(bot) - yW(top))} fill={IMD_COLORS[c.category]} opacity="0.10" />
              <text className="ch-band" x={width - PAD.r - 4} y={yW(top) + 12} textAnchor="end">{c.category}</text>
            </g>
          );
        })}
        <g className="ch-grid">
          {[0, 50, 100, 150, 200, 250, 300].filter(v => v <= windMax).map(v => (
            <g key={v}><line x1={PAD.l} x2={width - PAD.r} y1={yW(v)} y2={yW(v)} /><text x={PAD.l - 6} y={yW(v) + 4} textAnchor="end">{v}</text></g>
          ))}
        </g>
        {landfalls.map(l => {
          const ms = new Date(l.time).getTime();
          return (
            <g key={l.time} className="ch-mark">
              <line x1={x(ms)} x2={x(ms)} y1={PAD.t} y2={WH - PAD.b} />
              <text x={x(ms) + 4} y={PAD.t + 10}>{t(lang, 'storm.chart.landfall')}</text>
            </g>
          );
        })}
        {nowTime && (
          <g className="ch-mark now">
            <line x1={x(nowTime)} x2={x(nowTime)} y1={PAD.t} y2={WH - PAD.b} />
            <text x={x(nowTime) + 4} y={PAD.t + 10}>{t(lang, 'storm.chart.now')}</text>
          </g>
        )}
        <path className="ch-line" d={path(series, 'wind', yW)} />
        {fcPath && <path className="ch-line fc" d={fcPath} />}
        {peak && (
          <g>
            <circle className="ch-dot" cx={x(peak.ms)} cy={yW(peak.wind)} r="4.5" />
            <text className="ch-label" x={x(peak.ms)} y={yW(peak.wind) - 10} textAnchor="middle">{Math.round(peak.wind)} km/h</text>
          </g>
        )}
        <Cross h={WH} />
        {cur?.wind != null && <circle className="ch-dot hover" cx={x(cur.ms)} cy={yW(cur.wind)} r="5" />}
        <Axis h={WH} />
      </svg>

      {presVals.length > 1 && (
        <>
          <div className="ch-title">{t(lang, 'storm.chart.pressure')}</div>
          <svg width={width} height={PH} role="img" aria-label={t(lang, 'storm.chart.pressure')}>
            <g className="ch-grid">
              {[0, 0.5, 1].map(f => {
                const v = Math.round(pMin + f * (pMax - pMin));
                return <g key={f}><line x1={PAD.l} x2={width - PAD.r} y1={yP(v)} y2={yP(v)} /><text x={PAD.l - 6} y={yP(v) + 4} textAnchor="end">{v}</text></g>;
              })}
            </g>
            <path className="ch-line pres" d={path(series, 'pres', yP)} />
            <Cross h={PH} />
            {cur?.pres != null && <circle className="ch-dot hover pres" cx={x(cur.ms)} cy={yP(cur.pres)} r="5" />}
            <Axis h={PH} />
          </svg>
        </>
      )}

      {cur && (
        <div className="ch-tip" style={{ left: Math.min(Math.max(x(cur.ms), 90), width - 90) }}>
          <strong>{fmtTime(cur.ms, lang)}</strong>
          <span>{cur.wind != null ? `${Math.round(cur.wind)} km/h` : '—'}{cur.grade ? ` · ${cur.grade}` : ''}</span>
          {cur.pres != null && <span>{Math.round(cur.pres)} hPa</span>}
        </div>
      )}
    </div>
  );
}

/** Stacked bar: hours in each IMD grade, in scale order, 2 px surface gaps, legend with values. */
export function GradeTimeline({ hours, lang }) {
  const order = IMD_SCALE.map(c => c.category).filter(g => hours[g] > 0);
  const total = order.reduce((s, g) => s + hours[g], 0);
  if (!total) return <p className="muted-small">{t(lang, 'storm.grades.none')}</p>;
  return (
    <div className="grade-timeline">
      <div className="gt-bar" role="img" aria-label={t(lang, 'storm.grades.title')}>
        {order.map(g => (
          <span key={g} style={{ flex: hours[g], background: IMD_COLORS[g] }} title={`${g}: ${hours[g]} h`} />
        ))}
      </div>
      <ul className="gt-legend">
        {order.map(g => (
          <li key={g}><i style={{ background: IMD_COLORS[g] }} />{g}<b>{hours[g] >= 48 ? `${Math.round(hours[g] / 24 * 10) / 10} d` : `${hours[g]} h`}</b></li>
        ))}
      </ul>
    </div>
  );
}
