const CACHE_NAME = 'adventure-lab-v1';
const TILES_CACHE_NAME = 'adventure-tiles-cache';
const STATIC_CACHE_NAME = 'adventure-static-cache';

// Recursos estáticos base para poder iniciar offline
const STATIC_ASSETS = [
    '/adventure/',
    '/adventure/mis-rutas/',
    'https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.js',
    'https://unpkg.com/maplibre-gl@3.6.2/dist/maplibre-gl.css',
    'https://unpkg.com/maplibre-gl@3.3.1/dist/maplibre-gl.js',
    'https://unpkg.com/maplibre-gl@3.3.1/dist/maplibre-gl.css',
    'https://cdn.jsdelivr.net/npm/@turf/turf@6/turf.min.js',
    'https://unpkg.com/exifr/dist/full.umd.js',
    'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            console.log('sw: precacheando caparazón estático...');
            return cache.addAll(STATIC_ASSETS);
        }).then(() => self.skipWaiting())
    );
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys => {
            return Promise.all(
                keys.map(key => {
                    if (key !== CACHE_NAME && key !== TILES_CACHE_NAME && key !== STATIC_CACHE_NAME) {
                        console.log('sw: limpiando caché antigua:', key);
                        return caches.delete(key);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', event => {
    const url = new URL(event.request.url);

    // 1. ESTRATEGIA DE CACHE-FIRST PARA TILES DE MAPAS (Esri, Google, CartoDB, Terrarium)
    if (
        url.hostname.includes('arcgisonline.com') ||
        url.hostname.includes('basemaps.cartocdn.com') ||
        url.hostname.includes('mt1.google.com') ||
        url.hostname.includes('amazonaws.com') ||
        url.pathname.includes('/tile/') ||
        url.pathname.includes('/rastertiles/')
    ) {
        event.respondWith(
            caches.open(TILES_CACHE_NAME).then(cache => {
                return cache.match(event.request).then(cachedResponse => {
                    if (cachedResponse) {
                        return cachedResponse;
                    }
                    return fetch(event.request).then(networkResponse => {
                        if (networkResponse.status === 200) {
                            cache.put(event.request, networkResponse.clone());
                        }
                        return networkResponse;
                    }).catch(() => {
                        // Pixel transparente de fallback si no hay red y no está en caché (evita íconos rotos)
                        return new Response(
                            'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7',
                            { headers: { 'Content-Type': 'image/gif' } }
                        );
                    });
                });
            })
        );
        return;
    }

    // 2. CACHE-FIRST DINÁMICO PARA RECURSOS ESTÁTICOS LOCALES Y ESTRATÉGICOS (Fuentes, CSS, JS, Favicon)
    const isLocalStatic = url.pathname.includes('/static/') && (
        url.pathname.endsWith('.woff2') ||
        url.pathname.endsWith('.woff') ||
        url.pathname.endsWith('.ttf') ||
        url.pathname.endsWith('.css') ||
        url.pathname.endsWith('.js') ||
        url.pathname.endsWith('.png') ||
        url.pathname.endsWith('.jpg') ||
        url.pathname.endsWith('.jpeg') ||
        url.pathname.endsWith('.svg') ||
        url.pathname.endsWith('.ico')
    );

    const isStrategicAsset = STATIC_ASSETS.some(asset => event.request.url.includes(asset));

    if (isLocalStatic || isStrategicAsset) {
        event.respondWith(
            caches.open(STATIC_CACHE_NAME).then(cache => {
                return cache.match(event.request).then(cachedResponse => {
                    if (cachedResponse) {
                        return cachedResponse;
                    }
                    return fetch(event.request).then(networkResponse => {
                        if (networkResponse.status === 200) {
                            cache.put(event.request, networkResponse.clone());
                        }
                        return networkResponse;
                    });
                });
            })
        );
        return;
    }

    // 3. STALE-WHILE-REVALIDATE PARA NAVEGACIÓN Y PÁGINAS DE LA EXPEDICIÓN
    if (event.request.mode === 'navigate' || url.pathname.startsWith('/adventure/')) {
        event.respondWith(
            fetch(event.request)
                .then(response => {
                    const responseClone = response.clone();
                    caches.open(CACHE_NAME).then(cache => {
                        cache.put(event.request, responseClone);
                    });
                    return response;
                })
                .catch(() => {
                    return caches.match(event.request).then(cachedResponse => {
                        // Si no hay red, carga la página guardada, de lo contrario la página principal del dashboard
                        return cachedResponse || caches.match('/adventure/mis-rutas/');
                    });
                })
        );
        return;
    }
});
