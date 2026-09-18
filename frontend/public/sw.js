const CACHE_VERSION = "sanosync-pwa-v1";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter(
              (key) =>
                key.startsWith("sanosync-pwa-") &&
                key !== CACHE_VERSION,
            )
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

/*
 * SanoSync rimane online-first.
 *
 * Non memorizziamo risposte API, autenticazione,
 * calorie, pasti o dati personali nel service worker.
 */
self.addEventListener("fetch", (event) => {
  if (
    event.request.method !== "GET" ||
    !event.request.url.startsWith(
      self.location.origin,
    )
  ) {
    return;
  }

  event.respondWith(fetch(event.request));
});
