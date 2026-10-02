/**
 * Cyclo-Nexus service worker — offline-first safety information
 * ═════════════════════════════════════════════════════════════
 * Coastal networks fail exactly when a cyclone arrives, so the last advisory must stay readable.
 *   - pages (navigations): network first, cached app shell when offline
 *   - /assets/* (content-hashed build files): cache first
 *   - API GETs (/api/v1/…, any origin): network first; when offline the last saved response is
 *     returned with header X-Cyclonexus-Saved = when it was saved, so the site can say
 *     "offline — showing information saved at …" instead of presenting it as live
 *   - map tiles and other third-party requests: not cached (too large; always fetched)
 * Never cache-first for data: a stale storm position presented as current is dangerous.
 */

const VERSION = 'v2';
const SHELL = `cyclonexus-shell-${VERSION}`;
const ASSETS = `cyclonexus-assets-${VERSION}`;
const DATA = `cyclonexus-data-${VERSION}`;
const SHELL_URLS = ['/', '/manifest.json', '/favicon.svg', '/icons/icon-192.png'];
const SAVED_HEADER = 'X-Cyclonexus-Saved';
const MAX_DATA_ENTRIES = 80;

self.addEventListener('install', event => {
  event.waitUntil(caches.open(SHELL).then(c => c.addAll(SHELL_URLS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  const keep = new Set([SHELL, ASSETS, DATA]);
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => !keep.has(k)).map(k => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

async function trim(cacheName, max) {
  const cache = await caches.open(cacheName);
  const keys = await cache.keys();
  await Promise.all(keys.slice(0, Math.max(0, keys.length - max)).map(k => cache.delete(k)));
}

// Server-side failures that mean "API unreachable" (proxy/host down) rather than a real answer.
// /health is exempt: its 503 is a meaningful "data not ready" reply the site interprets.
function isGatewayFailure(res, url) {
  return [500, 502, 503, 504].includes(res.status) && !url.pathname.startsWith('/api/v1/health');
}

async function networkFirstData(request) {
  const cache = await caches.open(DATA);
  try {
    const res = await fetch(request);
    if (isGatewayFailure(res, new URL(request.url))) {
      const saved = await cache.match(request);
      if (saved) return saved;
    }
    if (res.ok) {
      const headers = new Headers(res.headers);
      headers.set(SAVED_HEADER, new Date().toISOString());
      const body = await res.clone().blob();
      await cache.put(request, new Response(body, { status: res.status, statusText: res.statusText, headers }));
      trim(DATA, MAX_DATA_ENTRIES);
    }
    return res;
  } catch (err) {
    const saved = await cache.match(request);
    if (saved) return saved;
    throw err;
  }
}

async function networkFirstPage(request) {
  try {
    const res = await fetch(request);
    if (res.ok) (await caches.open(SHELL)).put('/', res.clone());
    return res;
  } catch (err) {
    return (await caches.match('/')) || Promise.reject(err);
  }
}

async function cacheFirstAsset(request) {
  const hit = await caches.match(request);
  if (hit) return hit;
  const res = await fetch(request);
  if (res.ok) (await caches.open(ASSETS)).put(request, res.clone());
  return res;
}

self.addEventListener('fetch', event => {
  const { request } = event;
  if (request.method !== 'GET') return;
  const url = new URL(request.url);

  if (url.pathname.startsWith('/api/v1/') && !url.pathname.startsWith('/api/v1/webhook')
      && !url.pathname.startsWith('/api/v1/internal')) {
    event.respondWith(networkFirstData(request));
  } else if (url.origin !== self.location.origin) {
    // third-party (tiles, fonts, GIBS): browser default
  } else if (request.mode === 'navigate') {
    event.respondWith(networkFirstPage(request));
  } else if (url.pathname.startsWith('/assets/') || SHELL_URLS.includes(url.pathname)) {
    event.respondWith(cacheFirstAsset(request));
  }
});
