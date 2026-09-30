import React, { useEffect, useRef } from 'react';
import { api } from '../services/api';

/**
 * Wind particle overlay (demo build): speed-coloured particles with soft glowing trails.
 * Particles live in lon/lat and are advected with bilinear u/v. The grid's `unit` ('m/s' from the
 * backend) is converted to km/h for colouring and speed. Particles fade out towards the grid edges
 * so the layer never shows a hard rectangle. The animation keeps running while the map moves.
 */
const DESKTOP_PARTICLES = 6000;
const MOBILE_PARTICLES = 2200;
const MAX_AGE = 110;
const SPEED_Z4 = 0.0075; // degrees per (km/h · frame) at zoom 4, scaled by 2^(4 − zoom)

// Speed ramp (km/h) → colour, calm blue → gale yellow → storm red/magenta
const RAMP = [
  [0, '#7dd3fc'], [15, '#38bdf8'], [30, '#22d3ee'], [45, '#4ade80'],
  [65, '#facc15'], [90, '#fb923c'], [120, '#f43f5e'], [160, '#e879f9'],
];
const bucketOf = s => {
  let i = 0;
  while (i < RAMP.length - 1 && s >= RAMP[i + 1][0]) i++;
  return i;
};

function sampler(grid) {
  const { bbox, step_deg: step, nx, ny } = grid;
  const k = grid.unit === 'm/s' ? 3.6 : 1; // → km/h
  const u = grid.u.map(x => x * k);
  const v = grid.v.map(x => x * k);
  return (lon, lat) => {
    const fx = (lon - bbox.minLon) / step;
    const fy = (bbox.maxLat - lat) / step; // row 0 = north
    if (fx < 0 || fy < 0 || fx > nx - 1 || fy > ny - 1) return null;
    const x0 = Math.floor(fx); const y0 = Math.floor(fy);
    const x1 = Math.min(x0 + 1, nx - 1); const y1 = Math.min(y0 + 1, ny - 1);
    const dx = fx - x0; const dy = fy - y0;
    const at = (arr, x, y) => arr[y * nx + x];
    const lerp = arr => (at(arr, x0, y0) * (1 - dx) + at(arr, x1, y0) * dx) * (1 - dy)
      + (at(arr, x0, y1) * (1 - dx) + at(arr, x1, y1) * dx) * dy;
    return [lerp(u), lerp(v)];
  };
}

export default function WindParticleCanvas({ map, active }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!map || !active) return undefined;
    let grid = null;
    let sample = null;
    let particles = [];
    let frame = null;
    let cancelled = false;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const count = window.matchMedia('(max-width: 768px)').matches ? MOBILE_PARTICLES : DESKTOP_PARTICLES;
    const paths = RAMP.map(() => []);

    const resize = () => {
      const c = map.getCanvas();
      canvas.width = c.clientWidth * window.devicePixelRatio;
      canvas.height = c.clientHeight * window.devicePixelRatio;
      canvas.style.width = `${c.clientWidth}px`;
      canvas.style.height = `${c.clientHeight}px`;
      ctx.setTransform(window.devicePixelRatio, 0, 0, window.devicePixelRatio, 0, 0);
    };

    // Spawn inside the visible part of the grid so density stays even at any zoom
    const spawn = () => {
      const b = grid.bbox;
      const vb = map.getBounds();
      const minLon = Math.max(b.minLon, vb.getWest()); const maxLon = Math.min(b.maxLon, vb.getEast());
      const minLat = Math.max(b.minLat, vb.getSouth()); const maxLat = Math.min(b.maxLat, vb.getNorth());
      const ok = maxLon > minLon && maxLat > minLat;
      return {
        lon: ok ? minLon + Math.random() * (maxLon - minLon) : b.minLon + Math.random() * (b.maxLon - b.minLon),
        lat: ok ? minLat + Math.random() * (maxLat - minLat) : b.minLat + Math.random() * (b.maxLat - b.minLat),
        age: Math.floor(Math.random() * MAX_AGE),
      };
    };

    const step = () => {
      const speed = SPEED_Z4 * Math.pow(2, 4 - map.getZoom());
      ctx.globalCompositeOperation = 'destination-in';
      ctx.fillStyle = 'rgba(0, 0, 0, 0.93)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.globalCompositeOperation = 'lighter';

      for (const p of paths) p.length = 0;
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        const uv = sample(p.lon, p.lat);
        if (!uv || p.age++ > MAX_AGE) { particles[i] = spawn(); continue; }
        const a = map.project([p.lon, p.lat]);
        p.lon += uv[0] * speed / Math.max(0.2, Math.cos((p.lat * Math.PI) / 180));
        p.lat += uv[1] * speed;
        const b = map.project([p.lon, p.lat]);
        paths[bucketOf(Math.hypot(uv[0], uv[1]))].push(a.x, a.y, b.x, b.y);
      }
      paths.forEach((segs, k) => {
        if (!segs.length) return;
        ctx.strokeStyle = RAMP[k][1];
        ctx.globalAlpha = 0.55 + k * 0.05;
        ctx.lineWidth = 1 + k * 0.22;
        ctx.beginPath();
        for (let j = 0; j < segs.length; j += 4) {
          ctx.moveTo(segs[j], segs[j + 1]);
          ctx.lineTo(segs[j + 2], segs[j + 3]);
        }
        ctx.stroke();
      });
      ctx.globalAlpha = 1;
      fadeEdges();
      frame = requestAnimationFrame(step);
    };

    // Soften the four edges of the data box (projected to screen) so it never reads as a square
    const fadeEdges = () => {
      const b = grid.bbox;
      const nw = map.project([b.minLon, b.maxLat]);
      const se = map.project([b.maxLon, b.minLat]);
      const f = Math.max(40, (se.x - nw.x) * 0.06);
      ctx.globalCompositeOperation = 'destination-out';
      const edge = (x0, y0, x1, y1, rx, ry, rw, rh) => {
        const g = ctx.createLinearGradient(x0, y0, x1, y1);
        g.addColorStop(0, 'rgba(0,0,0,0.35)');
        g.addColorStop(1, 'rgba(0,0,0,0)');
        ctx.fillStyle = g;
        ctx.fillRect(rx, ry, rw, rh);
      };
      const w = se.x - nw.x; const h = se.y - nw.y;
      edge(nw.x, 0, nw.x + f, 0, nw.x, nw.y, f, h);
      edge(se.x, 0, se.x - f, 0, se.x - f, nw.y, f, h);
      edge(0, nw.y, 0, nw.y + f, nw.x, nw.y, w, f);
      edge(0, se.y, 0, se.y - f, nw.x, se.y - f, w, f);
      ctx.globalCompositeOperation = 'source-over';
    };

    const clear = () => ctx.clearRect(0, 0, canvas.width, canvas.height);

    api.getWindGrid().then(g => {
      if (cancelled || !g) return;
      grid = g;
      sample = sampler(g);
      resize();
      particles = Array.from({ length: count }, spawn);
      frame = requestAnimationFrame(step);
    }).catch(() => { /* layer simply stays empty if the grid is unavailable */ });

    const reseed = () => { if (grid) particles = Array.from({ length: count }, spawn); };
    map.on('move', clear);
    map.on('moveend', reseed);
    map.on('resize', resize);
    return () => {
      cancelled = true;
      if (frame) cancelAnimationFrame(frame);
      clear();
      map.off('move', clear);
      map.off('moveend', reseed);
      map.off('resize', resize);
    };
  }, [map, active]);

  return (
    <>
      <canvas ref={canvasRef} className="wind-canvas" style={{ display: active ? 'block' : 'none' }} />
      {active && (
        <div className="wind-scale" aria-hidden="true">
          <span>Calm</span>
          <div className="wind-scale-bar" />
          <span>Storm</span>
        </div>
      )}
    </>
  );
}
