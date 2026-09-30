/**
 * CYCLO-NEXUS Service Worker
 * ══════════════════════════
 * Owner: Agent ECHO | Task 21
 *
 * Caches the app shell, translation catalogs, and offline vector tiles
 * so the app boots reliably during zero-network field conditions.
 *
 * STUB — Agent ECHO will implement full caching strategy.
 */

const CACHE_NAME = 'cyclonexus-v1';
const SHELL_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});
