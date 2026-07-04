/**
 * Minimal Hotel PMS service worker (iter 362).
 * Strategy:
 *   • Precache the app shell (index.html + core assets)
 *   • Stale-while-revalidate for /static/* build assets
 *   • Network-first with 5s timeout for /api/* — falls back to nothing
 *     (we don't cache API responses — they must be fresh)
 *   • Offline navigation → serve cached index.html so the SPA still boots
 *
 * Kept intentionally small and framework-free so it can be replaced by
 * Workbox later without disturbing the shell.
 */
const VERSION = "v1-2026-07";
const APP_SHELL = "app-shell-" + VERSION;
const STATIC_CACHE = "static-" + VERSION;
const SHELL_ASSETS = [
  "/",
  "/index.html",
  "/manifest.json",
  "/favicon.ico",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(APP_SHELL).then((c) => c.addAll(SHELL_ASSETS)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys
          .filter((k) => k !== APP_SHELL && k !== STATIC_CACHE)
          .map((k) => caches.delete(k))
      );
      await self.clients.claim();
    })()
  );
});

async function timedFetch(request, ms) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("timeout")), ms);
    fetch(request).then(
      (r) => { clearTimeout(timer); resolve(r); },
      (e) => { clearTimeout(timer); reject(e); }
    );
  });
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Skip cross-origin + non-GET
  if (req.method !== "GET") return;
  if (url.origin !== location.origin) return;

  // API: network-first with 5s timeout, no caching of responses
  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      timedFetch(req, 5000).catch(() =>
        new Response(
          JSON.stringify({ offline: true, message: "Bağlantı yok. Tekrar deneyin." }),
          { status: 503, headers: { "Content-Type": "application/json" } }
        )
      )
    );
    return;
  }

  // Navigation requests — serve cached shell if offline
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).catch(() => caches.match("/index.html").then((r) => r || Response.error()))
    );
    return;
  }

  // Static assets — stale-while-revalidate
  if (url.pathname.startsWith("/static/") || url.pathname.endsWith(".css") || url.pathname.endsWith(".js")) {
    event.respondWith(
      caches.open(STATIC_CACHE).then((cache) =>
        cache.match(req).then((cached) => {
          const fetchPromise = fetch(req)
            .then((response) => {
              if (response && response.status === 200) cache.put(req, response.clone());
              return response;
            })
            .catch(() => cached);
          return cached || fetchPromise;
        })
      )
    );
    return;
  }
});
