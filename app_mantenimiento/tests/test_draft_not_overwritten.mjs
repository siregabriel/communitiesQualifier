/*
  A saved visit cannot be overwritten before it is back on screen.

  Greg Crutcher answered 33 of 35 standards at Monark Grove Greystone and left
  to do a phone shop. Four days later his dashboard still said "33 of 35
  answered" at 6:48 a.m. He tapped it, the form opened, and at 6:49 the server
  was told "1 of 35". The answers were gone from his phone.

  The form offered the saved visit behind a Resume button, but autosave was
  already switched on while that banner was showing. Any tap saved the
  near-empty page over the stored visit; switching apps saved an empty page,
  which deletes it. Now the saved visit is put back on screen first, and
  autosave starts after.

  This runs the page's real script against an in-memory IndexedDB, seeds a
  saved visit, and does what Greg did.
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

const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)]
  .map((m) => m[1]).reduce((a, b) => (b.length > a.length ? b : a), '')
  .replace(/\{\{\s*survey_type_id\s*\}\}/g, SURVEY)
  .replace(/\{\{\s*departments\s*\|\s*tojson\s*\}\}/g, '[]')
  .replace(/\{\{\s*community_places\s*\|\s*tojson\s*\}\}/g, '[]');

const SAVED = {
  id: KEY, community: COMMUNITY, surveyTypeId: SURVEY,
  savedAt: Date.now() - 4 * 86400000 + 3600000,   // four days ago, inside the 7-day keep
  responses: {
    q1: { condition: 'Pass', description: '', routeTo: '' },
    q2: { condition: 'Fail', description: 'Brochures out of date in the lobby', routeTo: '' },
    q3: { condition: 'Pass', description: '', routeTo: '' },
  },
  photos: {}, actionItems: [], notes: 'Great tour with the ED.', notesPhoto: null,
};

function idb(factory, fn) {
  return new Promise((resolve, reject) => {
    const r = factory.open('atlasDrafts', 1);
    r.onupgradeneeded = () => r.result.createObjectStore('drafts', { keyPath: 'id' });
    r.onsuccess = () => {
      const store = r.result.transaction('drafts', fn ? 'readwrite' : 'readonly').objectStore('drafts');
      const q = fn ? store.put(fn) : store.get(KEY);
      q.onsuccess = () => { r.result.close(); resolve(q.result || null); };
      q.onerror = () => reject(q.error);
    };
    r.onerror = () => reject(r.error);
  });
}

async function boot({ seed = true } = {}) {
  const factory = new IDBFactory();
  if (seed) await idb(factory, SAVED);
  const dom = new JSDOM(`<!doctype html><html><body>
    <div id="userInfo"></div>
    <div class="loading-message" id="loadingMessage"></div>
    <div class="loading-message" id="communityPrompt" style="display:none;"></div>
    <div id="nearbySuggest" hidden></div><button id="nearbyFind" hidden></button>
    <select id="communitySelect">
      <option value="">—</option><option value="${COMMUNITY}">${COMMUNITY}</option>
    </select>
    <form id="reportForm" style="display:none;">
      <div id="progressContainer"><div id="progressFill"></div><div id="progressMessage"></div></div>
      <div id="draftBanner" style="display:none;"></div>
      <div id="questionsContainer"></div>
      <div id="aiList"></div>
      <textarea id="visitNotes"></textarea><div id="notesCount"></div>
      <button type="submit">Submit Visit</button>
    </form>
    <div id="draftChip"></div><div id="draftStatus"></div>
    </body></html>`,
    { runScripts: 'dangerously', virtualConsole: quiet(), url: 'http://localhost/reporte?community=' + encodeURIComponent(COMMUNITY) });
  const w = dom.window;
  w.indexedDB = factory;
  // A returning user: the first-visit tour would otherwise start on a timer
  // and point at elements this page does not have.
  w.localStorage.setItem('atlasFormTourSeen_v1', '1');
  const notices = [];
  w.confirm = () => true;
  w.fetch = async (url, opts) => {
    url = String(url);
    if (url.startsWith('/api/user-info')) {
      return { ok: true, json: async () => ({ display_name: 'Greg Crutcher', username: 'greg.crutcher',
        community: null, role: 'regional', is_admin: false }) };
    }
    if (url.startsWith('/api/questions')) {
      return { ok: true, json: async () => ({ status: 'success', questions: QUESTIONS }) };
    }
    if (url.startsWith('/api/drafts')) {
      if (opts && opts.body) notices.push({ method: opts.method, ...JSON.parse(opts.body) });
      return { ok: true, json: async () => ({ status: 'success' }) };
    }
    return { ok: true, json: async () => ({}) };
  };
  const el = w.document.createElement('script');
  el.textContent = script;
  w.document.body.appendChild(el);
  await w.loadUserInfo();
  await settle(150);
  return { w, factory, notices };
}

// jsdom cannot navigate, so Start fresh's reload logs "not implemented".
// Everything else still reaches the terminal.
function quiet() {
  const vc = new VirtualConsole();
  vc.forwardTo(console, { jsdomErrors: "none" });
  return vc;
}

const settle = (ms = 30) => new Promise((r) => setTimeout(r, ms));
const checked = (w, q) => (w.document.querySelector(`input[name="condition_${q}"]:checked`) || {}).value || '';
const hide = async (w) => {
  Object.defineProperty(w.document, 'hidden', { configurable: true, get: () => true });
  w.document.dispatchEvent(new w.Event('visibilitychange'));
  await settle(80);
};

console.log('\nThe saved visit is on screen as soon as the form opens');
{
  const { w } = await boot();
  ok(checked(w, 'q1') === 'Pass' && checked(w, 'q2') === 'Fail' && checked(w, 'q3') === 'Pass',
     `the three answers are back without pressing anything (${['q1','q2','q3'].map(q => checked(w, q)).join(', ')})`);
  ok(w.document.getElementById('description_q2').value === 'Brochures out of date in the lobby',
     'with what was written');
  ok(w.document.getElementById('visitNotes').value === 'Great tour with the ED.', 'and the visit notes');
  const banner = w.document.getElementById('draftBanner');
  ok(banner.style.display !== 'none' && /Picked up where you left off/.test(banner.textContent),
     'the banner says it was restored');
  ok(/3 items answered/.test(banner.textContent), 'and how much');
  ok(!/>\s*Resume\s*</.test(banner.innerHTML), 'there is no Resume button left to miss');
}

console.log('\nWhat Greg did: answer one more before anything else');
{
  const { w, factory, notices } = await boot();
  const q4 = w.document.querySelector('input[name="condition_q4"][value="Pass"]');
  q4.checked = true;
  q4.dispatchEvent(new w.Event('change', { bubbles: true }));
  await settle(1100);   // past the 900 ms autosave delay
  const stored = await idb(factory);
  const n = Object.keys((stored && stored.responses) || {}).length;
  ok(n === 4, `the saved visit now has 4 answers, not 1 (${n})`);
  ok(stored && stored.responses.q2 && stored.responses.q2.description === 'Brochures out of date in the lobby',
     'and the earlier ones are intact');
  await settle(1700);   // the server copy follows 1.5 s after the phone's
  const last = notices.filter(x => x.method === 'PUT').pop();
  const sent = last ? Object.keys(last.responses || {}).length : undefined;
  ok(sent === 4, `the server is sent 4 answers, not 1 (${sent})`);
}

console.log('\nOr switch apps the moment it opens');
{
  const { w, factory, notices } = await boot();
  await hide(w);
  const stored = await idb(factory);
  ok(stored !== null, 'the saved visit is not deleted');
  ok(stored && Object.keys(stored.responses).length === 3, 'and still has its 3 answers');
  ok(!notices.some(x => x.method === 'DELETE'), 'and the dashboard is not told it is gone');
}

console.log('\nStart fresh still works, and asks first');
{
  const { w, factory } = await boot();
  let asked = 0;
  w.confirm = () => { asked++; return true; };
  const btn = w.document.getElementById('draftFreshBtn');
  ok(!!btn, 'the banner offers it');
  await btn.onclick();
  await settle(50);
  ok(asked === 1, 'it asks before throwing anything away');
  ok((await idb(factory)) === null, 'and then the saved visit is gone');
}

console.log('\nAnd saying no to it keeps everything');
{
  const { w, factory } = await boot();
  w.confirm = () => false;
  await w.document.getElementById('draftFreshBtn').onclick();
  await settle(50);
  const stored = await idb(factory);
  ok(stored && Object.keys(stored.responses).length === 3, 'nothing is discarded');
}

console.log('\nNo saved visit: nothing restored, nothing announced');
{
  const { w } = await boot({ seed: false });
  ok(checked(w, 'q1') === '', 'the form is empty');
  ok(w.document.getElementById('draftBanner').style.display === 'none', 'and there is no banner');
}

console.log(failures ? `\n${failures} failure(s)` : '\nA saved visit cannot be lost by opening it.');
process.exit(failures ? 1 : 0);
