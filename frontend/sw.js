
// Service Worker for StoneBridge Capitals PWA
const CACHE_NAME = 'banking-pwa-v1';
const OFFLINE_URL = '/offline/';

// Assets to cache on install
const ASSETS_TO_CACHE = [
    '/',
    '/login/',
    '/offline/',
    '/static/css/style.css',
    '/static/css/bootstrap.css',
    '/static/js/bootstrap.bundle.min.js',
    '/static/images/logo.png',
    '/static/images/pwa/icon-192x192.png',
    '/static/images/pwa/icon-512x512.png',
    '/static/fonts/icomoon/style.css',
    'https://fonts.googleapis.com/css2?family=Work+Sans:wght@400;600;700&display=swap',
    'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.8.1/font/bootstrap-icons.css'
];

// Install event - cache essential assets
self.addEventListener('install', (event) => {
    console.log('[ServiceWorker] Install');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('[ServiceWorker] Caching app shell');
                return cache.addAll(ASSETS_TO_CACHE);
            })
            .catch((error) => {
                console.log('[ServiceWorker] Cache failed:', error);
            })
    );
    self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
    console.log('[ServiceWorker] Activate');
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('[ServiceWorker] Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

// Fetch event - serve from cache, fall back to network
self.addEventListener('fetch', (event) => {
    // Skip non-GET requests
    if (event.request.method !== 'GET') {
        return;
    }

    // Skip requests to different origins (except for fonts/CDNs)
    const requestUrl = new URL(event.request.url);
    const isExternal = requestUrl.origin !== location.origin;
    const isAllowedExternal = event.request.url.includes('fonts.googleapis.com') ||
                              event.request.url.includes('fonts.gstatic.com') ||
                              event.request.url.includes('cdn.jsdelivr.net');

    if (isExternal && !isAllowedExternal) {
        return;
    }

    // For navigation requests (HTML pages)
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request)
                .then((response) => {
                    // Cache successful responses
                    if (response.status === 200) {
                        const responseClone = response.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            cache.put(event.request, responseClone);
                        });
                    }
                    return response;
                })
                .catch(() => {
                    // Return cached version or offline page
                    return caches.match(event.request)
                        .then((cachedResponse) => {
                            if (cachedResponse) {
                                return cachedResponse;
                            }
                            return caches.match(OFFLINE_URL);
                        });
                })
        );
        return;
    }

    // For other requests (assets) - cache first, then network
    event.respondWith(
        caches.match(event.request)
            .then((cachedResponse) => {
                if (cachedResponse) {
                    // Return cached version and update cache in background
                    fetch(event.request).then((response) => {
                        if (response.status === 200) {
                            caches.open(CACHE_NAME).then((cache) => {
                                cache.put(event.request, response);
                            });
                        }
                    }).catch(() => {});
                    return cachedResponse;
                }

                // Not in cache, fetch from network
                return fetch(event.request)
                    .then((response) => {
                        // Cache successful responses
                        if (response.status === 200) {
                            const responseClone = response.clone();
                            caches.open(CACHE_NAME).then((cache) => {
                                cache.put(event.request, responseClone);
                            });
                        }
                        return response;
                    });
            })
    );
});

// Handle push notifications
self.addEventListener('push', (event) => {
    console.log('[ServiceWorker] Push received');

    let data = {};
    let title = 'StoneBridge Capitals';
    let options = {
        body: 'You have a new notification',
        icon: '/static/images/pwa/icon-192x192.png',
        badge: '/static/images/pwa/icon-72x72.png',
        vibrate: [100, 50, 100],
        requireInteraction: true,
        data: {
            url: '/users/dashboard/',
            timestamp: Date.now()
        }
    };

    if (event.data) {
        try {
            // Try to parse as JSON
            data = event.data.json();
            title = data.title || 'StoneBridge Capitals';
            options.body = data.body || options.body;
            options.icon = data.icon || options.icon;
            options.badge = data.badge || options.badge;
            options.tag = data.tag || undefined;
            options.data = {
                url: data.url || '/users/dashboard/',
                timestamp: data.timestamp || Date.now()
            };
        } catch (e) {
            // If not JSON, use as plain text
            options.body = event.data.text();
        }
    }

    event.waitUntil(
        self.registration.showNotification(title, options)
    );
});

// Handle notification clicks
self.addEventListener('notificationclick', (event) => {
    console.log('[ServiceWorker] Notification clicked');
    event.notification.close();

    const urlToOpen = event.notification.data?.url || '/users/dashboard/';

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then((windowClients) => {
                // Check if there's already an open window
                for (let client of windowClients) {
                    if (client.url.includes(self.location.origin) && 'focus' in client) {
                        client.navigate(urlToOpen);
                        return client.focus();
                    }
                }
                // If no open window, open a new one
                if (clients.openWindow) {
                    return clients.openWindow(urlToOpen);
                }
            })
    );
});

// Handle notification close
self.addEventListener('notificationclose', (event) => {
    console.log('[ServiceWorker] Notification closed');
});

// Handle push subscription change (when subscription expires)
self.addEventListener('pushsubscriptionchange', (event) => {
    console.log('[ServiceWorker] Push subscription changed');
    event.waitUntil(
        self.registration.pushManager.subscribe({ userVisibleOnly: true })
            .then((subscription) => {
                console.log('[ServiceWorker] Resubscribed to push');
                // Note: Would need to send new subscription to server
            })
    );
});

// Log when service worker is activated
console.log('[ServiceWorker] Script loaded');
