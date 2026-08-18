/* Business OS service worker — safe offline cache */
const CACHE = 'bos-v3';

async function putBestEffort(cache, request, response) {
  try {
    await cache.put(request, response);
    return true;
  } catch (_) {
    // Storage quota/private-mode failures must never break a network response.
    return false;
  }
}

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    const indexResponse = await fetch('/index.html', { cache: 'reload' });
    if (!indexResponse.ok) throw new Error('App shell index could not be fetched');
    const html = await indexResponse.clone().text();
    const indexCached = await putBestEffort(cache, '/index.html', indexResponse.clone());
    if (!indexCached) throw new Error('App shell index could not be cached');

    // Vite production index contains hashed /assets/*.js and *.css. Precache
    // them during install so first-load Safari works offline even if
    // WindowClient.navigate() is unsupported and runtime fetches were missed.
    const assetUrls = [...new Set(
      [...html.matchAll(/(?:src|href)=["'](\/assets\/[^"']+)["']/g)].map((match) => match[1])
    )];
    await Promise.all(assetUrls.map(async (assetUrl) => {
      const response = await fetch(assetUrl, { cache: 'reload' });
      if (!isValidAssetResponse(new URL(assetUrl, self.location.origin), response)) {
        throw new Error(`Invalid app shell asset: ${assetUrl}`);
      }
      const cached = await putBestEffort(cache, assetUrl, response.clone());
      if (!cached) throw new Error(`App shell asset could not be cached: ${assetUrl}`);
    }));

    try {
      const manifest = await fetch('/manifest.webmanifest', { cache: 'reload' });
      if (manifest.ok) await putBestEffort(cache, '/manifest.webmanifest', manifest.clone());
    } catch (_) {
      // Manifest is non-critical for app startup.
    }
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)));
    await self.clients.claim();
  })());
});

function isValidAssetResponse(url, response) {
  if (!response.ok || response.type === 'opaque') return false;
  const contentType = (response.headers.get('content-type') || '').toLowerCase();
  if (contentType.includes('text/html')) return false;
  if (url.pathname.endsWith('.js')) return contentType.includes('javascript');
  if (url.pathname.endsWith('.css')) return contentType.includes('text/css');
  return true;
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Financial/API data must always be live.
  if (url.pathname.startsWith('/api/')) return;

  // Vite dev/HMR modules must NEVER be cached. Caching these causes Safari to
  // mix old and new ESM modules and display a blank page after a deploy.
  const devPath = url.pathname.startsWith('/src/')
    || url.pathname.startsWith('/@vite/')
    || url.pathname.startsWith('/@react-refresh')
    || url.pathname.startsWith('/node_modules/.vite/');
  if (devPath) return;

  // Page navigation is network-first. Never store arbitrary navigation output
  // as /index.html (e.g. /docs, /redoc or /openapi.json). The app shell is
  // precached during install and used only as an offline fallback.
  if (request.mode === 'navigate') {
    event.respondWith(fetch(request).catch(() => caches.match('/index.html')));
    return;
  }

  // Hashed production bundles are immutable and safe to cache-first, but only
  // after MIME validation. Await cache.put so Safari cannot terminate the write.
  if (url.pathname.startsWith('/assets/')) {
    event.respondWith((async () => {
      const cached = await caches.match(request);
      if (cached) return cached;
      const response = await fetch(request);
      if (isValidAssetResponse(url, response)) {
        const cache = await caches.open(CACHE);
        await putBestEffort(cache, request, response.clone());
      }
      return response;
    })());
    return;
  }

  // Manifest/icons: network-first with a tracked cache write and exact fallback.
  event.respondWith((async () => {
    try {
      const response = await fetch(request);
      if (response.ok && !((response.headers.get('content-type') || '').toLowerCase().includes('text/html'))) {
        const cache = await caches.open(CACHE);
        await putBestEffort(cache, request, response.clone());
      }
      return response;
    } catch (_) {
      return caches.match(request);
    }
  })());
});
