// Service worker de ¿QuéCocino?: permite abrir la app y "Mis recetas" sin conexión.
// Las favoritas y el detalle de cada receta guardada viven en localStorage; aquí solo se guarda la "cáscara".
const CACHE = "quecocino-v1";
const CASCARA = ["/", "/static/manifest.json", "/static/icono.svg", "/static/icono-192.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(CASCARA)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  // Red primero: la app siempre muestra lo más nuevo; si no hay conexión, usa la copia guardada.
  e.respondWith(
    fetch(e.request).then((r) => {
      if (r.ok && (CASCARA.includes(url.pathname) || url.pathname === "/opciones")) {
        const copia = r.clone(); caches.open(CACHE).then((c) => c.put(e.request, copia));
      }
      return r;
    }).catch(() => caches.match(e.request))
  );
});
