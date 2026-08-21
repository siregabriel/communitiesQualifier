/*
 * Draft storage tests.
 *
 * An unfinished visit is kept on the device — answers, ad-hoc items and photo
 * blobs — so an inspector can walk away mid-visit and come back. It is the
 * least visible code we run and the most costly to break: a silent failure
 * means somebody loses an hour of work in a building somewhere.
 *
 * These mirror the store in templates/reporte.html: same database name,
 * version, keyPath and the same put/get/cursor calls. If you change the store
 * there, change it here.
 *
 *   cd app_mantenimiento && npm install --no-save fake-indexeddb
 *   node tests/test_drafts.mjs
 */
import 'fake-indexeddb/auto';

const DRAFT_DB = 'atlasDrafts';
const DRAFT_STORE = 'drafts';
const DRAFT_TTL_DAYS = 7;

let _db = null;
const db = () => _db ? Promise.resolve(_db) : new Promise((res, rej) => {
  const r = indexedDB.open(DRAFT_DB, 1);
  r.onupgradeneeded = () => {
    const d = r.result;
    if (!d.objectStoreNames.contains(DRAFT_STORE)) d.createObjectStore(DRAFT_STORE, { keyPath: 'id' });
  };
  r.onsuccess = () => { _db = r.result; res(_db); };
  r.onerror = () => rej(r.error);
});
const tx = mode => db().then(d => d.transaction(DRAFT_STORE, mode).objectStore(DRAFT_STORE));
const put = v => tx('readwrite').then(s => new Promise((res, rej) => {
  const r = s.put(v); r.onsuccess = () => res(); r.onerror = () => rej(r.error);
}));
const get = k => tx('readonly').then(s => new Promise(res => {
  const r = s.get(k); r.onsuccess = () => res(r.result || null); r.onerror = () => res(null);
}));
const del = k => tx('readwrite').then(s => new Promise(res => {
  const r = s.delete(k); r.onsuccess = () => res(); r.onerror = () => res();
}));
const count = () => tx('readonly').then(s => new Promise(res => {
  const r = s.count(); r.onsuccess = () => res(r.result);
}));
const prune = () => tx('readwrite').then(s => new Promise(res => {
  const cutoff = Date.now() - DRAFT_TTL_DAYS * 86400000;
  const r = s.openCursor();
  r.onsuccess = () => {
    const c = r.result;
    if (!c) return res();
    if (!c.value || (c.value.savedAt || 0) < cutoff) c.delete();
    c.continue();
  };
  r.onerror = () => res();
}));

let failures = 0;
const ok = (cond, msg) => {
  console.log((cond ? '  ok   ' : '  FAIL ') + msg);
  if (!cond) failures++;
};

const photoBytes = new Uint8Array([0xFF, 0xD8, 0xFF, 0xE0, 1, 2, 3, 4, 5]);
const draft = (id, community, savedAt) => ({
  id, community, surveyTypeId: 'st1', savedAt,
  responses: {
    q1: { condition: 'Fail', description: 'Sign missing in lobby', routeTo: 'sales' },
    q2: { condition: 'Pass', description: '', routeTo: '' },
  },
  photos: {
    q1: { name: 'lobby.jpg', type: 'image/jpeg', blob: new Blob([photoBytes], { type: 'image/jpeg' }) },
  },
  actionItems: [{ text: 'Replace welcome sign', assigned_to: 'Sales', priority: 'high' }],
  // Notes about the visit as a whole, with their own photo.
  notes: 'Great visit — they had a wonderful event while I was there.',
  notesPhoto: { name: 'event.jpg', type: 'image/jpeg',
                blob: new Blob([photoBytes], { type: 'image/jpeg' }) },
});

console.log('saving and coming back to it');
await put(draft('st1::Wildcat', 'Wildcat Senior Living, Summerville', Date.now()));
const got = await get('st1::Wildcat');
ok(!!got, 'the draft comes back');
ok(got.responses.q1.condition === 'Fail' && got.responses.q1.routeTo === 'sales',
   'answers and routing survive');
ok(got.actionItems[0].priority === 'high', 'ad-hoc items survive');
ok(got.photos.q1.blob instanceof Blob, 'the photo is stored as binary, not text');
ok(got.notes && got.notes.includes('wonderful event'), 'the visit note survives');
ok(got.notesPhoto && got.notesPhoto.blob instanceof Blob, 'and the photo attached to it');

const back = new Uint8Array(await got.photos.q1.blob.arrayBuffer());
ok(back.length === photoBytes.length && back.every((b, i) => b === photoBytes[i]),
   'the photo bytes come back byte for byte');

const file = new File([got.photos.q1.blob], got.photos.q1.name, { type: got.photos.q1.type });
ok(file instanceof File && file.name === 'lobby.jpg' && file.size === photoBytes.length,
   'and rebuild into a File the form can upload');

console.log('one draft per community');
await put(draft('st1::Goldton', 'The Goldton at Venice', Date.now()));
ok(await count() === 2, 'two communities can be in progress at once');
await put(draft('st1::Wildcat', 'Wildcat Senior Living, Summerville', Date.now()));
ok(await count() === 2, 'saving again overwrites rather than duplicating');

console.log('expiry');
await put(draft('st1::Old', 'Somewhere', Date.now() - 8 * 86400000));
ok(await count() === 3, 'a stale draft is there before pruning');
await prune();
ok(await get('st1::Old') === null, 'a draft older than the limit is dropped');
ok(await get('st1::Wildcat') !== null, 'a recent one is kept');

console.log('cleared once the visit is sent');
await del('st1::Wildcat');
ok(await get('st1::Wildcat') === null, 'submitting removes the draft');

console.log('');
console.log(failures ? `${failures} failure(s)` : 'Drafts survive the trip.');
process.exit(failures ? 1 : 0);
