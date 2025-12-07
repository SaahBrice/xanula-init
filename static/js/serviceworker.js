/**
 * Xanula Service Worker
 * Per Architecture Document Section 12 (Offline Capability)
 * 
 * Caching strategies:
 * - Shell (essential UI): Cache-first
 * - Static assets: Cache-first
 * - API responses: Network-first with cache fallback
 * - Book files: Cache-only when downloaded
 */

const CACHE_VERSION = 'v1.1.0';
const STATIC_CACHE = `xanula-static-${CACHE_VERSION}`;
const DYNAMIC_CACHE = `xanula-dynamic-${CACHE_VERSION}`;
const BOOK_CACHE = 'xanula-books';

// Essential files to cache on install
const SHELL_FILES = [
    '/',
    '/library/',
    '/offline/',
    '/static/css/main.css',
];

// Files to cache on first visit
const CACHE_ON_DEMAND = [
    '/books/',
    '/wishlist/',
];

// Install event - cache shell files but wait for activation
self.addEventListener('install', (event) => {
    console.log('[SW] Installing service worker v' + CACHE_VERSION);
    event.waitUntil(
        caches.open(STATIC_CACHE)
            .then(cache => {
                console.log('[SW] Caching shell files');
                return cache.addAll(SHELL_FILES).catch(err => {
                    console.log('[SW] Some shell files failed to cache:', err);
                });
            })
        // Don't skipWaiting - wait for user to confirm update
    );
});

// Activate event - clean up old caches and notify clients
self.addEventListener('activate', (event) => {
    console.log('[SW] Activating service worker v' + CACHE_VERSION);
    event.waitUntil(
        caches.keys()
            .then(cacheNames => {
                return Promise.all(
                    cacheNames
                        .filter(name => name.startsWith('xanula-') &&
                            name !== STATIC_CACHE &&
                            name !== DYNAMIC_CACHE &&
                            name !== BOOK_CACHE)
                        .map(name => {
                            console.log('[SW] Deleting old cache:', name);
                            return caches.delete(name);
                        })
                );
            })
            .then(() => self.clients.claim())
            .then(() => {
                // Notify all clients that update is complete
                self.clients.matchAll().then(clients => {
                    clients.forEach(client => {
                        client.postMessage({ type: 'SW_UPDATED', version: CACHE_VERSION });
                    });
                });
            })
    );
});

// Fetch event - handle requests with caching strategies
self.addEventListener('fetch', (event) => {
    const { request } = event;
    const url = new URL(request.url);

    // Skip non-GET requests
    if (request.method !== 'GET') return;

    // Skip external requests
    if (!url.origin.includes(self.location.origin)) return;

    // Handle different request types
    if (isBookFile(url)) {
        // Book files: Cache-only (must be explicitly downloaded)
        event.respondWith(cacheOnly(request));
    } else if (isStaticAsset(url)) {
        // Static assets: Cache-first
        event.respondWith(cacheFirst(request, STATIC_CACHE));
    } else if (isApiRequest(url)) {
        // API requests: Network-first
        event.respondWith(networkFirst(request));
    } else {
        // HTML pages: Network-first with offline fallback
        event.respondWith(networkFirstWithOfflineFallback(request));
    }
});

// Check if URL is a book file (ebook or audiobook)
function isBookFile(url) {
    return url.pathname.includes('/media/ebooks/') ||
        url.pathname.includes('/media/audiobooks/');
}

// Check if URL is a static asset
function isStaticAsset(url) {
    return url.pathname.startsWith('/static/') ||
        url.pathname.includes('.css') ||
        url.pathname.includes('.js') ||
        url.pathname.includes('.woff') ||
        url.pathname.includes('.png') ||
        url.pathname.includes('.jpg') ||
        url.pathname.includes('.svg');
}

// Check if URL is an API request
function isApiRequest(url) {
    return url.pathname.startsWith('/api/') ||
        url.pathname.includes('/json');
}

// Cache-first strategy
async function cacheFirst(request, cacheName) {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
        return cachedResponse;
    }

    try {
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            const cache = await caches.open(cacheName);
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    } catch (error) {
        console.log('[SW] Network error for:', request.url);
        return new Response('Network error', { status: 408 });
    }
}

// Network-first strategy
async function networkFirst(request) {
    try {
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            const cache = await caches.open(DYNAMIC_CACHE);
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    } catch (error) {
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        return new Response(JSON.stringify({ error: 'Offline' }), {
            headers: { 'Content-Type': 'application/json' },
            status: 503
        });
    }
}

// Network-first with offline fallback for HTML pages
async function networkFirstWithOfflineFallback(request) {
    try {
        const networkResponse = await fetch(request);
        if (networkResponse.ok) {
            const cache = await caches.open(DYNAMIC_CACHE);
            cache.put(request, networkResponse.clone());
        }
        return networkResponse;
    } catch (error) {
        const cachedResponse = await caches.match(request);
        if (cachedResponse) {
            return cachedResponse;
        }
        // Return offline page
        return caches.match('/offline/');
    }
}

// Cache-only for downloaded books
async function cacheOnly(request) {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
        return cachedResponse;
    }

    // If not cached, try network (for streaming)
    try {
        return await fetch(request);
    } catch (error) {
        console.log('[SW] Book not cached and offline:', request.url);
        return new Response('Book not downloaded for offline use', { status: 404 });
    }
}

// Message handler for download operations
self.addEventListener('message', (event) => {
    const { type, payload } = event.data;

    switch (type) {
        case 'DOWNLOAD_BOOK':
            downloadBook(payload, event.source);
            break;
        case 'REMOVE_BOOK':
            removeBook(payload, event.source);
            break;
        case 'GET_CACHE_SIZE':
            getCacheSize(event.source);
            break;
        case 'CLEAR_ALL_DOWNLOADS':
            clearAllDownloads(event.source);
            break;
        case 'SKIP_WAITING':
            self.skipWaiting();
            break;
    }
});

// Download book files to cache
async function downloadBook(payload, client) {
    const { bookId, ebookUrl, audiobookUrl, coverUrl } = payload;

    try {
        const cache = await caches.open(BOOK_CACHE);
        const filesToCache = [];
        let totalSize = 0;

        // Download ebook if available
        if (ebookUrl) {
            try {
                const response = await fetch(ebookUrl);
                if (response.ok) {
                    const blob = await response.blob();
                    totalSize += blob.size;
                    await cache.put(ebookUrl, new Response(blob));
                    filesToCache.push({ type: 'ebook', url: ebookUrl, size: blob.size });
                }
            } catch (e) {
                console.log('[SW] Failed to cache ebook:', e);
            }
        }

        // Download audiobook if available
        if (audiobookUrl) {
            try {
                const response = await fetch(audiobookUrl);
                if (response.ok) {
                    const blob = await response.blob();
                    totalSize += blob.size;
                    await cache.put(audiobookUrl, new Response(blob));
                    filesToCache.push({ type: 'audiobook', url: audiobookUrl, size: blob.size });
                }
            } catch (e) {
                console.log('[SW] Failed to cache audiobook:', e);
            }
        }

        // Download cover image
        if (coverUrl) {
            try {
                const response = await fetch(coverUrl);
                if (response.ok) {
                    await cache.put(coverUrl, response.clone());
                }
            } catch (e) {
                console.log('[SW] Failed to cache cover:', e);
            }
        }

        client.postMessage({
            type: 'DOWNLOAD_COMPLETE',
            payload: { bookId, files: filesToCache, totalSize }
        });

    } catch (error) {
        client.postMessage({
            type: 'DOWNLOAD_ERROR',
            payload: { bookId, error: error.message }
        });
    }
}

// Remove book files from cache
async function removeBook(payload, client) {
    const { bookId, ebookUrl, audiobookUrl, coverUrl } = payload;

    try {
        const cache = await caches.open(BOOK_CACHE);

        if (ebookUrl) await cache.delete(ebookUrl);
        if (audiobookUrl) await cache.delete(audiobookUrl);
        if (coverUrl) await cache.delete(coverUrl);

        client.postMessage({
            type: 'REMOVE_COMPLETE',
            payload: { bookId }
        });
    } catch (error) {
        client.postMessage({
            type: 'REMOVE_ERROR',
            payload: { bookId, error: error.message }
        });
    }
}

// Get total cache size
async function getCacheSize(client) {
    try {
        const cache = await caches.open(BOOK_CACHE);
        const keys = await cache.keys();
        let totalSize = 0;

        for (const request of keys) {
            const response = await cache.match(request);
            if (response) {
                const blob = await response.blob();
                totalSize += blob.size;
            }
        }

        client.postMessage({
            type: 'CACHE_SIZE',
            payload: { size: totalSize, count: keys.length }
        });
    } catch (error) {
        client.postMessage({
            type: 'CACHE_SIZE',
            payload: { size: 0, count: 0 }
        });
    }
}

// Clear all downloads
async function clearAllDownloads(client) {
    try {
        await caches.delete(BOOK_CACHE);
        client.postMessage({
            type: 'CLEAR_COMPLETE',
            payload: { success: true }
        });
    } catch (error) {
        client.postMessage({
            type: 'CLEAR_ERROR',
            payload: { error: error.message }
        });
    }
}

// Background sync for progress updates
self.addEventListener('sync', (event) => {
    if (event.tag === 'sync-progress') {
        event.waitUntil(syncProgress());
    }
});

async function syncProgress() {
    console.log('[SW] Syncing progress...');
    // Get queued progress updates from IndexedDB
    // This will be implemented with the main app
}

console.log('[SW] Service worker loaded');
