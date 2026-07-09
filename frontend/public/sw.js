/**
 * Hotel PMS service worker (iter 387).
 * Strategy:
 *   • Precache the app shell (index.html + core assets + offline.html)
 *   • Stale-while-revalidate for /static/* build assets
 *   • GET /api/*: network-first with 5s timeout → on success cache a copy,
 *     on failure serve the last cached copy (X-Served-From: sw-cache header)
 *     so reception/housekeeping keep working with last-loaded data offline.
 *   • Offline navigation → cached index.html (SPA boots) → offline.html fallback
 */
const VERSION = "v2-2026-07";
const APP_SHELL = "app-shell-" + VERSION;
const STATIC_CACHE = "static-" + VERSION;
const API_CACHE = "api-" + VERSION;
const API_CACHE_MAX = 300;
const SHELL_ASSETS = [
  "/",
  "/index.html",
  "/offline.html",
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
          .filter((k) => k !== APP_SHELL && k !== STATIC_CACHE && k !== API_CACHE)
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

async function trimCache(cacheName, max) {
  const cache = await caches.open(cacheName);
  const keys = await cache.keys();
  if (keys.length > max) {
    await Promise.all(keys.slice(0, keys.length - max).map((k) => cache.delete(k)));
  }
}

// Never cache these API paths (auth/payment/live-signal sensitive)
const API_NO_CACHE = ["/api/auth/", "/api/payments", "/api/stripe", "/api/ab/", "/api/booking-widget/social-proof"];

async function apiNetworkFirst(req) {
  const cache = await caches.open(API_CACHE);
  try {
    const response = await timedFetch(req, 5000);
    if (response && response.status === 200) {
      cache.put(req, response.clone());
      trimCache(API_CACHE, API_CACHE_MAX);
    }
    return response;
  } catch (e) {
    const cached = await cache.match(req);
    if (cached) {
      const headers = new Headers(cached.headers);
      headers.set("X-Served-From", "sw-cache");
      const body = await cached.blob();
      return new Response(body, { status: 200, headers });
    }
    return new Response(
      JSON.stringify({ offline: true, message: "Bağlantı yok. Tekrar deneyin." }),
      { status: 503, headers: { "Content-Type": "application/json" } }
    );
  }
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Skip cross-origin + non-GET
  if (req.method !== "GET") return;
  if (url.origin !== location.origin) return;

  // API GET: network-first, cache fallback (except sensitive paths)
  if (url.pathname.startsWith("/api/")) {
    if (API_NO_CACHE.some((p) => url.pathname.startsWith(p))) {
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
    event.respondWith(apiNetworkFirst(req));
    return;
  }

  // Navigation requests — cached shell → offline page
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).catch(async () => {
        const shell = await caches.match("/index.html");
        if (shell) return shell;
        const off = await caches.match("/offline.html");
        return off || Response.error();
      })
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
