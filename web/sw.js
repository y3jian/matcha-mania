const CACHE_NAME = "matcha-mania-v2"; // bumped: v1 cached price/harvest data cache-first, which could show stale data
const APP_SHELL = [
  "./harvest_map.html",
  "./data/harvest_seasons.js",
  "./data/matcha_prices.js",
  "./manifest.json",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
  );
  self.clients.claim();
});

// same-origin GET requests: network-first, cache only as an offline fallback.
// (Cache-first would serve stale price/harvest data right after a fresh scrape or a
// newly-tracked product — this site's whole point is showing current data, so freshness
// wins over the marginal speed of serving a cached copy first.)
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET" || new URL(event.request.url).origin !== self.location.origin) return;
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok) caches.open(CACHE_NAME).then((cache) => cache.put(event.request, response.clone()));
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
