const CACHE_NAME = 'joyhotels-v1.1';

// Assets to precache immediately on install
const PRECACHE_ASSETS = [
  '/',
  '/static/lodgify_theme.css',
  '/static/dashboard.css',
  '/static/logo.png',
  '/static/icon-192.png',
  '/static/icon-512.png',
  'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap'
];

// Install Event: cache precache assets
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Pre-caching core assets');
        return cache.addAll(PRECACHE_ASSETS);
      })
      .then(() => self.skipWaiting())
  );
});

// Activate Event: clean up old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cache => {
          if (cache !== CACHE_NAME) {
            console.log('Clearing old cache:', cache);
            return caches.delete(cache);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch Event: apply caching strategy
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Exclude API requests and POST submissions from service worker cache
  if (event.request.method !== 'GET' || url.pathname.startsWith('/api/') || url.pathname.startsWith('/auth/')) {
    return;
  }

  // Caching Strategy:
  // For static assets (CSS, JS, PNG, Fonts), use Cache-First / Stale-While-Revalidate
  if (
    url.pathname.startsWith('/static/') ||
    url.hostname.includes('fonts.gstatic.com') ||
    url.hostname.includes('fonts.googleapis.com')
  ) {
    event.respondWith(
      caches.match(event.request).then(cachedResponse => {
        const fetchPromise = fetch(event.request).then(networkResponse => {
          if (networkResponse && networkResponse.status === 200) {
            const cacheCopy = networkResponse.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, cacheCopy));
          }
          return networkResponse;
        }).catch(err => console.log('Fetch failed for static asset:', err));

        return cachedResponse || fetchPromise;
      })
    );
  } else {
    // For HTML routes (dynamic dashboard, room status, KDS, calendars), use Network-First
    // This guarantees the user ALWAYS sees the absolute latest real-time database state.
    event.respondWith(
      fetch(event.request)
        .then(networkResponse => {
          if (networkResponse && networkResponse.status === 200) {
            const cacheCopy = networkResponse.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, cacheCopy));
          }
          return networkResponse;
        })
        .catch(() => {
          // If offline/network fails, try to return from cache
          return caches.match(event.request);
        })
    );
  }
});
