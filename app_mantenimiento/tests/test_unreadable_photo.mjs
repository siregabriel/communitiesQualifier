/*
  A photo the phone can no longer read must not hold a visit hostage.

  Shannon Cook (Nov 2026) could not send a visit. The server log showed her
  draft text arriving every few seconds from the same phone, while every
  upload carrying two particular photos — the draft photo saves and the
  submission itself — was cut off before it reached the app (nginx: 400, zero
  bytes). The browser held those two photos but could not read them, so it
  dropped each upload part way, and the form told her she had a weak signal.
  Retrying could never work.

  Now a photo is copied into memory when it is chosen and read again before
  anything sends it. These boot the real form and give it a photo whose bytes
  cannot be read, then check it is taken off its standard, the person is told
  where, and the rest of the visit still goes.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(new URL('../templates/reporte.html', import.meta.url), 'utf8');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

const COMMUNITY = 'The Goldton at Southaven, Southaven';
const QUESTIONS = [
  { id: 'q1', text: 'Lobby clean', photo_required: false },
  { id: 'q2', text: 'Cooler seals', photo_required: false },
];

function boot({ confirmAnswer = true } = {}) {
  const script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)]
    .map((m) => m[1]).reduce((a, b) => (b.length > a.length ? b : a), '')
    .replace(/\{\{\s*survey_type_id\s*\}\}/g, 'standards')
    .replace(/\{\{\s*departments\s*\|\s*tojson\s*\}\}/g, '[]')
    .replace(/\{\{\s*community_places\s*\|\s*tojson\s*\}\}/g, '[]');
  const dom = new JSDOM(`<!doctype html><html><body>
    <div id="userInfo"></div>
    <div class="loading-message" id="loadingMessage"></div>
    <div class="loading-message" id="communityPrompt" style="display:none;"></div>
    <select id="communitySelect"><option value="">—</option><option value="${COMMUNITY}">${COMMUNITY}</option></select>
    <form id="reportForm" style="display:none;"><button type="submit">Submit Visit</button></form>
    <div id="questionsContainer"></div>
    <div id="progressContainer"><div id="progressFill"></div><div id="progressMessage"></div></div>
    <div id="draftChip"></div><div id="draftBanner"></div><div id="draftStatus"></div>
    <textarea id="visitNotes"></textarea><div id="notesCount"></div>
    <div id="successScreen"><p id="successText"></p><p id="successSummary"></p></div>
    </body></html>`, { runScripts: 'dangerously', url: 'http://localhost/reporte?community=' + encodeURIComponent(COMMUNITY) });
  const w = dom.window;
  const alerts = [], confirms = [], posts = [];
  w.alert = (m) => alerts.push(String(m));
  w.confirm = (m) => { confirms.push(String(m)); return confirmAnswer; };
  w.console.error = () => {};
  w.console.warn = () => {};
  w.Element.prototype.scrollIntoView = function () {};
  w.scrollTo = function () {};
  w.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
  w.fetch = async (url, opts = {}) => {
    const u = String(url);
    if (opts.method === 'POST') posts.push({ url: u, body: opts.body });
    if (u.startsWith('/api/user-info')) return { ok: true, json: async () => ({ display_name: 'Shannon Cook',
      username: 'shannon.cook', community: null, role: 'regional', is_admin: false }) };
    if (u.startsWith('/api/questions')) return { ok: true, json: async () => ({ status: 'success', questions: QUESTIONS }) };
    return { ok: true, json: async () => ({ status: 'success' }) };
  };
  const xhrs = [];
  w.XMLHttpRequest = class {
    constructor() { this.upload = {}; xhrs.push(this); }
    open(method, url) { this.method = method; this.url = url; }
    send(body) { this.body = body; }
  };
  const el = w.document.createElement('script');
  el.textContent = script;
  w.document.body.appendChild(el);
  return { w, xhrs, alerts, confirms, posts };
}

const settle = () => new Promise((r) => setTimeout(r, 30));
const good = (w, name = 'IMG_1.jpg') => new w.File(['jpeg bytes'], name, { type: 'image/jpeg' });
// What Shannon's phone held: a photo with a name and a size whose bytes cannot be read.
const broken = (w, name = 'IMG_2.jpg') => {
  const f = new w.File(['jpeg bytes'], name, { type: 'image/jpeg' });
  f.arrayBuffer = () => Promise.reject(new w.DOMException('The file could not be read', 'NotReadableError'));
  return f;
};
function mark(w, qid, value, text) {
  const input = w.document.querySelector(`input[name="condition_${qid}"][value="${value}"]`);
  input.checked = true;
  input.dispatchEvent(new w.Event('change', { bubbles: true }));
  if (text !== undefined) w.document.getElementById(`description_${qid}`).value = text;
}
async function visitWithPhotos(opts) {
  const ctx = boot(opts);
  await ctx.w.loadUserInfo();
  await settle();
  mark(ctx.w, 'q1', 'Pass');
  mark(ctx.w, 'q2', 'Fail', 'Door seal torn');
  ctx.w.__good = good(ctx.w);
  ctx.w.__broken = broken(ctx.w);
  ctx.w.eval('photoFiles.q1 = window.__good; photoFiles.q2 = window.__broken;');
  ctx.w.document.getElementById('reportForm').dispatchEvent(new ctx.w.Event('submit', { cancelable: true }));
  await settle();
  return ctx;
}

console.log('\nAn unreadable photo is taken off, and the visit still goes');
{
  const { w, xhrs, confirms } = await visitWithPhotos();
  ok(confirms.some(c => /1 photo on this visit could not be read/.test(c)), 'the person is asked, naming one photo');
  ok(xhrs.length === 1, 'the visit is sent');
  const fd = xhrs[0] && xhrs[0].body;
  ok(fd && fd.has('photo_q_q1'), 'with the readable photo');
  ok(fd && !fd.has('photo_q_q2'), 'without the unreadable one, which would have cut the upload off');
  ok(fd && fd.get('photo_q_q1') !== w.__good, 'the readable photo goes as a fresh copy, not the stored reference');
  const name = w.document.getElementById('fileName_q2');
  ok(/could not be read/.test(name.textContent) && name.classList.contains('photo-lost'),
     `the standard says where the photo was lost (${name.textContent})`);
}

console.log('\nCancel: nothing is sent, the photo is marked to take again');
{
  const { w, xhrs } = await visitWithPhotos({ confirmAnswer: false });
  ok(xhrs.length === 0, 'nothing is posted');
  ok(w.eval('!photoFiles.q2'), 'the unreadable photo is off the standard');
  ok(w.eval('!!photoFiles.q1'), 'the readable one stays');
}

console.log('\nThe draft copy: an unreadable photo is not uploaded on every save');
{
  const { w, posts } = boot();
  await w.loadUserInfo();
  await settle();
  w.__good = good(w);
  w.__broken = broken(w);
  w.eval('photoFiles.q1 = window.__good; photoFiles.q2 = window.__broken;');
  await w.eval(`serverSyncPhotos({ community: ${JSON.stringify(COMMUNITY)}, surveyTypeId: 'standards',
    photos: { q1: { name: 'IMG_1.jpg', blob: window.__good }, q2: { name: 'IMG_2.jpg', blob: window.__broken } } })`);
  const slots = posts.filter(p => p.url === '/api/drafts/photo').map(p => p.body.get('slot'));
  ok(slots.includes('q1'), 'the readable photo is saved to the server');
  ok(!slots.includes('q2'), 'the unreadable one is not attempted');
  ok(w.document.getElementById('fileName_q2').classList.contains('photo-lost'), 'and is marked on the form');
}

console.log('\nChoosing a photo the browser cannot read says so at once');
{
  const { w, alerts } = boot();
  await w.loadUserInfo();
  await settle();
  const pick = broken(w);
  // Small enough that shrinkPhoto hands back the same file; the read is what fails.
  await w.handlePhotoChange({ target: { files: [pick], value: 'x' } }, 'q1');
  ok(w.eval('!photoFiles.q1'), 'the photo is not kept');
  ok(alerts.some(a => /could not be read/.test(a) && /take it again/.test(a)), 'and the person is told to take it again');
}

console.log(failures ? `\n${failures} failed` : '\nall passed');
process.exit(failures ? 1 : 0);
