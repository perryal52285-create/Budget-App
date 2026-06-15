// Perry Budget service worker — offline shell only.
// Caches hashed build assets (safe to cache forever) and serves them offline.
// Never caches /api/ (always fresh, and avoids serving stale financial data).
const CACHE = "pb-shell-v1";

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))),
    ).then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.includes("/api/")) return;
  const isAsset = url.pathname.includes("/ui/assets/");
  e.respondWith(
    caches.open(CACHE).then(async (cache) => {
      const cached = await cache.match(e.request);
      const network = fetch(e.request)
        .then((res) => {
          if (res.ok && isAsset) cache.put(e.request, res.clone());
          return res;
        })
        .catch(() => cached);
      // assets: cache-first; everything else: network-first with cache fallback
      return isAsset ? cached || network : network;
    }),
  );
});
