/*
  The visit form keeps a copy of an unfinished visit on the server, and can
  come back from it.

  Greg Crutcher's 33 answers at Greystone existed only in his phone's browser,
  and were lost there. The phone still saves first; every save is now also
  sent to the server (text in one request, each photo on its own), and a form
  that opens with nothing on the phone — another browser, another phone, a
  wiped one — restores from the server instead.

  Runs the page's real script with an in-memory IndexedDB and a fake server.
  The server side has its own tests (test_server_drafts.py).
*/

import fs from 'fs';
import { JSDOM, VirtualConsole } from 'jsdom';
import { IDBFactory } from 'fake-indexeddb';

const html = fs.readFileSync(new URL('../templates/reporte.html', import.meta.url), 'utf8');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

const COMMUNITY = 'Monark Grove Greystone';
const SURVEY = 'sales-marketing';
const KEY = `${SURVEY}::${COMMUNITY}`;
const QUESTIONS = [1, 2, 3, 4].map(n => ({ id: `q${n}`, text: `Standard ${n}`, photo_required: false }));
const PHOTO = new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 9, 9, 9, 9, 9, 9]);

const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)]
  .map((m) => m[1]).reduce((a, b) => (b.length > a.length ? b : a), '')
  .replace(/\{\{\s*survey_type_id\s*\}\}/g, SURVEY)
  .replace(/\{\{\s*departments\s*\|\s*tojson\s*\}\}/g, '[]')
  .replace(/\{\{\s*community_places\s*\|\s*tojson\s*\}\}/g, '[]');

const SERVER_DRAFT = {
  community: COMMUNITY, survey_type_id: SURVEY, total: 4, saved_at: Date.now() - 3600000,
  responses: {
    q1: { condition: 'Pass', description: '', routeTo: '' },
    q2: { condition: 'Fail', description: "Greg's note: brochures out of date", routeTo: '' },
  },
  action_items: [], notes: 'From the server.',
  photos: { q2: { name: 'lobby.jpg', type: 'image/jpeg', size: PHOTO.length } },
};

function idb(factory, value) {
  return new Promise((resolve, reject) => {
    const r = factory.open('atlasDrafts', 1);
    r.onupgradeneeded = () => r.result.createObjectStore('drafts', { keyPath: 'id' });
    r.onsuccess = () => {
      const store = r.result.transaction('drafts', value ? 'readwrite' : 'readonly').objectStore('drafts');
      const q = value ? store.put(value) : store.get(KEY);
      q.onsuccess = () => { r.result.close(); resolve(q.result || null); };
      q.onerror = () => reject(q.error);
    };
    r.onerror = () => reject(r.error);
  });
}

function quiet() {
  const vc = new VirtualConsole();
  vc.forwardTo(console, { jsdomErrors: 'none' });
  return vc;
}

const settle = (ms = 30) => new Promise((r) => setTimeout(r, ms));

async function boot({ local = null, server = null, offline = false } = {}) {
  const factory = new IDBFactory();
  if (local) await idb(factory, local);
  const dom = new JSDOM(`<!doctype html><html><body>
    <div id="userInfo"></div>
    <div class="loading-message" id="loadingMessage"></div>
    <div class="loading-message" id="communityPrompt" style="display:none;"></div>
    <select id="communitySelect"><option value="">—</option><option value="${COMMUNITY}">${COMMUNITY}</option></select>
    <form id="reportForm" style="display:none;">
      <div id="progressContainer"><div id="progressFill"></div><div id="progressMessage"></div></div>
      <div id="draftBanner" style="display:none;"></div>
      <div id="questionsContainer"></div><div id="aiList"></div>
      <textarea id="visitNotes"></textarea><div id="notesCount"></div>
      <button type="submit">Submit Visit</button>
    </form>
    <div id="draftChip"></div><div id="draftStatus"></div>
    </body></html>`,
    { runScripts: 'dangerously', virtualConsole: quiet(),
      url: 'http://localhost/reporte?community=' + encodeURIComponent(COMMUNITY) });
  const w = dom.window;
  w.indexedDB = factory;
  w.localStorage.setItem('atlasFormTourSeen_v1', '1');
  // Every browser has this; jsdom does not. The preview thumbnail is all it is for.
  w.URL.createObjectURL = () => 'blob:preview';
  const calls = [];
  w.fetch = async (url, opts = {}) => {
    url = String(url);
    const method = opts.method || 'GET';
    if (url.startsWith('/api/user-info')) {
      return { ok: true, json: async () => ({ display_name: 'Greg', username: 'greg.crutcher',
        community: null, role: 'regional', is_admin: false }) };
    }
    if (url.startsWith('/api/questions')) {
      return { ok: true, json: async () => ({ status: 'success', questions: QUESTIONS }) };
    }
    if (url.startsWith('/api/drafts')) {
      let body = null;
      if (opts.body && typeof opts.body === 'string') body = JSON.parse(opts.body);
      if (opts.body && typeof opts.body !== 'string') {
        body = Object.fromEntries([...opts.body.entries()].map(([k, v]) => [k, typeof v === 'string' ? v : { name: v.name, size: v.size }]));
      }
      calls.push({ url, method, body });
      if (offline) throw new TypeError('Failed to fetch');
      if (url.startsWith('/api/drafts/content') && method === 'GET') {
        return { ok: true, json: async () => ({ status: 'success', draft: server }) };
      }
      if (url.startsWith('/api/drafts/photo') && method === 'GET') {
        return { ok: true, blob: async () => new w.Blob([PHOTO], { type: 'image/jpeg' }) };
      }
      return { ok: true, json: async () => ({ status: 'success' }) };
    }
    return { ok: true, json: async () => ({}) };
  };
  const el = w.document.createElement('script');
  el.textContent = script;
  w.document.body.appendChild(el);
  await w.loadUserInfo();
  await settle(200);
  return { w, factory, calls };
}

const checked = (w, q) => (w.document.querySelector(`input[name="condition_${q}"]:checked`) || {}).value || '';
const banner = (w) => w.document.getElementById('draftBanner').textContent;

console.log('\nNothing on this phone, a copy on the server: it comes back');
{
  const { w, factory } = await boot({ server: SERVER_DRAFT });
  ok(checked(w, 'q1') === 'Pass' && checked(w, 'q2') === 'Fail', 'the answers are restored');
  ok(w.document.getElementById('description_q2').value === "Greg's note: brochures out of date",
     'with the words as typed');
  ok(w.document.getElementById('visitNotes').value === 'From the server.', 'and the notes');
  ok(/Restored from your account/.test(banner(w)), 'and it says where it came from');
  const file = w.eval('photoFiles.q2');
  ok(!!file && file.size === PHOTO.length, 'the photo is a file again, ready to submit');
  const kept = await idb(factory);
  ok(kept && Object.keys(kept.responses).length === 2, 'and this phone now has its own copy');
}

console.log('\nThe phone is newer than the server: the phone wins');
{
  const local = {
    id: KEY, community: COMMUNITY, surveyTypeId: SURVEY, savedAt: Date.now(),
    responses: { q1: { condition: 'Fail', description: 'newer', routeTo: '' },
                 q2: { condition: 'Pass', description: '', routeTo: '' },
                 q3: { condition: 'Pass', description: '', routeTo: '' } },
    photos: {}, actionItems: [], notes: 'phone', notesPhoto: null,
  };
  const { w, calls } = await boot({ local, server: SERVER_DRAFT });
  ok(checked(w, 'q1') === 'Fail' && checked(w, 'q3') === 'Pass', 'the newer answers are on screen');
  ok(!/Restored from your account/.test(banner(w)), 'from the phone');
  await settle(100);
  const put = calls.filter(c => c.method === 'PUT').pop();
  ok(put && Object.keys(put.body.responses).length === 3,
     'and the server is brought up to date straight away, without waiting for an edit');
}

console.log('\nThe server is newer than the phone: the server wins');
{
  const stale = { id: KEY, community: COMMUNITY, surveyTypeId: SURVEY, savedAt: SERVER_DRAFT.saved_at - 86400000,
    responses: { q1: { condition: 'Fail', description: 'old', routeTo: '' } },
    photos: {}, actionItems: [], notes: '', notesPhoto: null };
  const { w } = await boot({ local: stale, server: SERVER_DRAFT });
  ok(checked(w, 'q2') === 'Fail' && /Restored from your account/.test(banner(w)),
     'the copy made later on another device is the one restored');
}

console.log('\nA photo goes up once, not with every save');
{
  const { w, calls } = await boot({});
  w.eval(`photoFiles.q1 = new File([new Uint8Array([1,2,3,4,5])], 'sign.jpg', { type: 'image/jpeg' });`);
  const tick = w.document.querySelector('input[name="condition_q1"][value="Pass"]');
  tick.checked = true;
  tick.dispatchEvent(new w.Event('change', { bubbles: true }));
  await settle(2700);
  const posts = () => calls.filter(c => c.url.startsWith('/api/drafts/photo') && c.method === 'POST');
  ok(posts().length === 1 && posts()[0].body.slot === 'q1', `the photo is uploaded for its standard (${posts().length})`);
  const t2 = w.document.querySelector('input[name="condition_q2"][value="Pass"]');
  t2.checked = true;
  t2.dispatchEvent(new w.Event('change', { bubbles: true }));
  await settle(2700);
  ok(posts().length === 1, 'and not again on the next save');
  const put = calls.filter(c => c.method === 'PUT').pop();
  ok(put && !JSON.stringify(put.body).includes('sign.jpg'), 'the text request never carries the photo');

  w.eval('delete photoFiles.q1');
  const t3 = w.document.querySelector('input[name="condition_q3"][value="Pass"]');
  t3.checked = true;
  t3.dispatchEvent(new w.Event('change', { bubbles: true }));
  await settle(2700);
  ok(calls.some(c => c.url.startsWith('/api/drafts/photo') && c.method === 'DELETE' && c.body.slot === 'q1'),
     'a removed photo is removed from the server too');
}

console.log('\nPhotos the server already has are not sent again after a restore');
{
  const { w, calls } = await boot({ server: SERVER_DRAFT });
  const t = w.document.querySelector('input[name="condition_q3"][value="Pass"]');
  t.checked = true;
  t.dispatchEvent(new w.Event('change', { bubbles: true }));
  await settle(2700);
  ok(!calls.some(c => c.url.startsWith('/api/drafts/photo') && c.method === 'POST'),
     'the restored photo is not uploaded a second time');
}

console.log('\nNo signal: the phone keeps working');
{
  const local = { id: KEY, community: COMMUNITY, surveyTypeId: SURVEY, savedAt: Date.now(),
    responses: { q1: { condition: 'Pass', description: '', routeTo: '' } },
    photos: {}, actionItems: [], notes: '', notesPhoto: null };
  const { w, factory } = await boot({ local, offline: true });
  ok(checked(w, 'q1') === 'Pass', 'the phone copy is restored');
  const t = w.document.querySelector('input[name="condition_q2"][value="Fail"]');
  t.checked = true;
  t.dispatchEvent(new w.Event('change', { bubbles: true }));
  await settle(1100);
  const kept = await idb(factory);
  ok(kept && Object.keys(kept.responses).length === 2, 'and still saves on the phone');
}

console.log(failures ? `\n${failures} failure(s)` : '\nAn unfinished visit has a second copy.');
process.exit(failures ? 1 : 0);
