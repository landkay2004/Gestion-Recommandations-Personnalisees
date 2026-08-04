/* ═══════════════════════════════════════════════════════════
   SGN — Service Worker
   Cache : assets statiques uniquement (CSS, JS, images, fonts)
   Jamais en cache : notes, bulletins, résultats, données perso
   ═══════════════════════════════════════════════════════════ */

const CACHE_NAME = 'sgn-static-v1';
const OFFLINE_URL = '/static/offline.html';

// Assets à mettre en cache immédiatement à l'installation
const PRECACHE_ASSETS = [
  '/static/css/style.css',
  '/static/offline.html',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  // Bootstrap & Bootstrap Icons (CDN) — mis en cache à la première visite
];

// Domaines CDN à mettre en cache (stratégie stale-while-revalidate)
const CDN_HOSTS = [
  'cdn.jsdelivr.net',
];

// URLs Django à NE JAMAIS mettre en cache
const NEVER_CACHE_PATTERNS = [
  /\/portail\/resultats\//,
  /\/bulletin\//,
  /\/grades\//,
  /\/reports\//,
  /\/api\//,
  /\/admin\//,
  /\?/,           // toute URL avec paramètres GET
  /\.sqlite3$/,
];

// ── Installation ──────────────────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      cache.addAll(PRECACHE_ASSETS).catch(() => {})
    )
  );
  self.skipWaiting();
});

// ── Activation : nettoyage ancien cache ───────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// ── Fetch : stratégie par type de ressource ───────────────
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Ne gérer que GET
  if (request.method !== 'GET') return;

  // Ne jamais intercepter les données sensibles
  if (NEVER_CACHE_PATTERNS.some((re) => re.test(url.pathname + url.search))) return;

  // ── CDN : stale-while-revalidate ──
  if (CDN_HOSTS.includes(url.hostname)) {
    event.respondWith(staleWhileRevalidate(request));
    return;
  }

  // ── Assets statiques locaux (/static/) : cache-first ──
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // ── Pages HTML Django : network-first, offline fallback ──
  if (request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(networkFirstWithOfflineFallback(request));
    return;
  }

  // Tout le reste : network uniquement
});

// ── Stratégies ────────────────────────────────────────────

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
  } catch {
    return new Response('', { status: 503 });
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);
  const fetchPromise = fetch(request).then((response) => {
    if (response.ok) cache.put(request, response.clone());
    return response;
  }).catch(() => null);
  return cached || (await fetchPromise) || new Response('', { status: 503 });
}

async function networkFirstWithOfflineFallback(request) {
  try {
    const response = await fetch(request);
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    const offlinePage = await caches.match(OFFLINE_URL);
    return offlinePage || new Response('<h1>Hors ligne</h1>', {
      headers: { 'Content-Type': 'text/html' }
    });
  }
}

// ── Architecture FCM (préparée, non active) ───────────────
// Pour activer Firebase Cloud Messaging plus tard :
// 1. Importer le script Firebase ici
// 2. Initialiser avec votre firebaseConfig
// 3. Gérer l'événement 'push' ci-dessous

/* self.addEventListener('push', (event) => {
  const data = event.data?.json() ?? {};
  self.registration.showNotification(data.title ?? 'SGN', {
    body: data.body ?? '',
    icon: '/static/icons/icon-192.png',
    badge: '/static/icons/icon-96.png',
    data: { url: data.url ?? '/' },
  });
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.url));
}); */
