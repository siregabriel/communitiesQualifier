/*
  Offline support for the static shell — and nothing else.

  The previous version cached every response it saw, including /dashboard and
  every /api/ reply. Two problems came out of that:

    * A page built on the server for one account sat in the cache afterwards.
      Sign-in state, someone's community list and a whole visit's findings were
      being written to disk and kept there past sign-out.

    * The menu is rendered server-side, so a deploy that changed it looked like
      it had never landed: the browser had a copy of yesterday's HTML and was
      happy to keep using it.

  So: only /static/ is cached now. Pages and API replies always go to the
  network, and if the network is down they fail honestly rather than showing
  stale data as if it were current. The app is useless offline anyway — every
  screen is server data — so a cached shell would only be a convincing lie.

  Bumping CACHE_NAME clears whatever the old version left behind; the activate
  handler below deletes every cache that isn't the current one.
*/

const CACHE_NAME = 'atlas-static-v2';

// Only things that are the same for everyone, signed in or not.
const PRECACHE = [
    '/static/manifest.json',
];


function isCacheable(request) {
    // A cache entry is only safe when the answer cannot depend on who is asking.
    if (request.method !== 'GET') return false;
    let url;
    try {
        url = new URL(request.url);
    } catch (e) {
        return false;
    }
    if (url.origin !== self.location.origin) return false;
    return url.pathname.startsWith('/static/');
}


self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => cache.addAll(PRECACHE))
            .catch(() => { /* a missing asset must not block activation */ })
    );
    self.skipWaiting();
});


self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys()
            .then((names) => Promise.all(
                names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n))
            ))
            .then(() => self.clients.claim())
    );
});


self.addEventListener('fetch', (event) => {
    // Anything that isn't a static asset is left entirely alone — not
    // intercepted, not stored, not served from cache.
    if (!isCacheable(event.request)) return;

    // Network first, so a deploy's new stylesheet is picked up straight away.
    // The cache is the fallback for being offline, not the default answer.
    event.respondWith(
        fetch(event.request)
            .then((response) => {
                if (response && response.ok && response.type === 'basic') {
                    const copy = response.clone();
                    caches.open(CACHE_NAME)
                        .then((cache) => cache.put(event.request, copy))
                        .catch(() => { /* a full disk must not break the page */ });
                }
                return response;
            })
            .catch(() => caches.match(event.request))
    );
});
