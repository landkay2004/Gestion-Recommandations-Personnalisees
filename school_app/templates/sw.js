{% load static %}
/* ═══════════════════════════════════════════════════════════
   SGN — Service Worker
   Cache : assets statiques uniquement (CSS, JS, images, fonts)
   Jamais en cache : notes, bulletins, résultats, données perso
   ═══════════════════════════════════════════════════════════ */

const CACHE_NAME = 'sgn-static-v2';
const OFFLINE_URL = '{% static "offline.html" %}';

const PRECACHE_ASSETS = [
  '{% static "css/style.css" %}',
  '{% static "offline.html" %}',
  '{% static "icons/icon-192.png" %}',
  '{% static "icons/icon-512.png" %}',
];

const CDN_HOSTS = ['cdn.jsdelivr.net'];

const NEVER_CACHE_PATTERNS = [
  /\/portail\/resultats\//,
  /\/bulletin\//,
  /\/grades\//,
  /\/reports\//,
  /\/admin\//,
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(PRECACHE_ASSETS).catch(() => {}))
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
  const { request } = event;
  const url = new URL(request.url);

  if (request.method !== 'GET') return;
  if (NEVER_CACHE_PATTERNS.some((re) => re.test(url.pathname))) return;

  if (CDN_HOSTS.includes(url.hostname)) {
    event.respondWith(staleWhileRevalidate(request));
    return;
  }

  if (url.pathname.startsWith('/static/')) {
    event.respondWith(cacheFirst(request));
    return;
  }

  if (request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(networkFirstWithOfflineFallback(request));
    return;
  }
});

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch { return new Response('', { status: 503 }); }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);
  const fetchPromise = fetch(request).then((r) => {
    if (r.ok) cache.put(request, r.clone());
    return r;
  }).catch(() => null);
  return cached || (await fetchPromise) || new Response('', { status: 503 });
}

async function networkFirstWithOfflineFallback(request) {
  try {
    return await fetch(request);
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    const offline = await caches.match(OFFLINE_URL);
    return offline || new Response('<h1>Hors ligne</h1>', { headers: { 'Content-Type': 'text/html' } });
  }
}

/* ── Architecture FCM (préparée, non active) ─────────────────
self.addEventListener('push', (event) => {
  const data = event.data?.json() ?? {};
  self.registration.showNotification(data.title ?? 'SGN', {
    body: data.body ?? '',
    icon: '{% static "icons/icon-192.png" %}',
    badge: '{% static "icons/icon-96.png" %}',
    data: { url: data.url ?? '/' },
  });
});
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.url));
});
─────────────────────────────────────────────────────────── */
