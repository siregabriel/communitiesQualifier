/*
  The service worker, exercised rather than read.

  It used to cache every response it saw. That kept a signed-in dashboard on
  disk, and made a server-rendered menu change look like it had never deployed.
  These checks run the real file against a fake ServiceWorkerGlobalScope and
  watch what it actually decides to store.
*/

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = fs.readFileSync(path.join(HERE, '..', 'static', 'service-worker.js'), 'utf8');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };
const section = (t) => console.log('\n' + t);

/* A minimal Cache/CacheStorage, so we can see exactly what gets written. */
function makeEnv({ offline = false } = {}) {
  const stored = new Map();
  const deleted = [];
  let cacheNames = ['inspections-v1', 'atlas-static-v2'];

  const cache = {
    addAll: async () => {},
    put: async (req, res) => { stored.set(req.url, res); },
    match: async (req) => stored.get(req.url) || undefined,
  };
  const caches = {
    open: async () => cache,
    keys: async () => cacheNames.slice(),
    delete: async (n) => { deleted.push(n); cacheNames = cacheNames.filter(x => x !== n); return true; },
    match: async (req) => stored.get(req.url) || undefined,
  };

  const listeners = {};
  const self = {
    location: { origin: 'https://standards.atlasseniorliving.net' },
    addEventListener: (name, fn) => { listeners[name] = fn; },
    skipWaiting: () => {},
    clients: { claim: async () => {} },
  };

  const fetchCalls = [];
  const fetchImpl = async (req) => {
    fetchCalls.push(req.url);
    if (offline) throw new Error('offline');
    return {
      ok: true, type: 'basic', clone() { return { body: 'copy of ' + req.url }; },
      body: 'fresh ' + req.url,
    };
  };

  const fn = new Function('self', 'caches', 'fetch', 'URL', SRC + '\n');
  fn(self, caches, fetchImpl, URL);
  return { listeners, stored, deleted, fetchCalls, self, caches };
}

/* Dispatch a fetch event and return what the worker chose to respond with,
   or the string 'not-intercepted' when it let the request through. */
async function request(env, url, method = 'GET') {
  let responded = 'not-intercepted';
  const waits = [];
  env.listeners.fetch({
    request: { url, method },
    respondWith: (p) => { responded = p; },
    waitUntil: (p) => waits.push(p),
  });
  await Promise.all(waits);
  return responded === 'not-intercepted' ? responded : await responded;
}

const ORIGIN = 'https://standards.atlasseniorliving.net';

section('Pages and API replies are left alone');
{
  const env = makeEnv();
  for (const url of ['/dashboard', '/dashboard?view=communities', '/login',
                     '/api/user-info', '/api/attention', '/']) {
    const r = await request(env, ORIGIN + url);
    ok(r === 'not-intercepted', `${url} goes straight to the network`);
  }
  ok(env.stored.size === 0, 'and nothing about them is written to the cache');
}

section('A signed-in page is never answered from cache');
{
  const env = makeEnv();
  // Pretend an older version had already stored a dashboard.
  (await env.caches.open()).put({ url: ORIGIN + '/dashboard' }, { body: 'yesterday' });
  const r = await request(env, ORIGIN + '/dashboard');
  ok(r === 'not-intercepted',
     'even with a copy sitting in the cache, the worker does not serve it');
}

section('Static assets are cached, network first');
{
  const env = makeEnv();
  const r = await request(env, ORIGIN + '/static/theme.css');
  ok(r && r.body === 'fresh ' + ORIGIN + '/static/theme.css',
     'a new stylesheet is picked up the moment it deploys');
  ok(env.stored.has(ORIGIN + '/static/theme.css'), 'and kept for going offline');
}

section('Offline falls back to the cached asset');
{
  const env = makeEnv();
  await request(env, ORIGIN + '/static/theme.css');       // warm it
  const off = makeEnv({ offline: true });
  (await off.caches.open()).put({ url: ORIGIN + '/static/theme.css' }, { body: 'cached css' });
  const r = await request(off, ORIGIN + '/static/theme.css');
  ok(r && r.body === 'cached css', 'the stylesheet still loads with no network');
}

section('Requests that cannot be reused safely are not cached');
{
  const env = makeEnv();
  ok(await request(env, ORIGIN + '/static/x.css', 'POST') === 'not-intercepted',
     'a POST is never cached');
  ok(await request(env, 'https://s3.amazonaws.com/uploads/a/b.jpg') === 'not-intercepted',
     'another origin is not ours to cache');
  ok(env.stored.size === 0, 'neither left anything behind');
}

section('Activating clears what the old version stored');
{
  const env = makeEnv();
  const waits = [];
  env.listeners.activate({ waitUntil: (p) => waits.push(p) });
  await Promise.all(waits);
  ok(env.deleted.includes('inspections-v1'),
     'the old cache — full of signed-in pages — is deleted on upgrade');
  ok(!env.deleted.includes('atlas-static-v2'), 'the current one is kept');
}

console.log(failures ? `\n${failures} failure(s)` : '\nThe service worker caches only what is safe to.');
process.exit(failures ? 1 : 0);
