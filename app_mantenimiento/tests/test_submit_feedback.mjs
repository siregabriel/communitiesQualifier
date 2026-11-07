/*
  Sending a visit: what the person sees while it goes, and after.

  Pressing Submit used to change the button to "Submitting..." and nothing
  else, for however long a weak signal and a few photos took — the server
  also sends the emails before it answers. A regional once read a dropped
  upload as lost work. Gabriel asked for the real progress in the button:
  how much has gone up, then the server's part. The confirmation also says
  in one line what was sent. This boots the real form with an upload that
  the test drives step by step, then checks a refused send and a dropped
  connection still end with the button back and the draft promise made.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(new URL('../templates/reporte.html', import.meta.url), 'utf8');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

const COMMUNITY = 'Kelley Place, Enterprise';
const QUESTIONS = [
  { id: 'q1', text: 'Lobby clean', photo_required: false },
  { id: 'q2', text: 'Cooler seals', photo_required: false },
  { id: 'q3', text: 'Kitchen', photo_required: false },
];

function boot() {
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
  const alerts = [];
  w.alert = (m) => alerts.push(String(m));
  w.confirm = () => true;
  w.console.error = () => {};   // the page logs a dropped connection; expected here
  w.Element.prototype.scrollIntoView = function () {};
  w.scrollTo = function () {};
  w.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
  w.fetch = async (url) => {
    const u = String(url);
    if (u.startsWith('/api/user-info')) return { ok: true, json: async () => ({ display_name: 'Marissa Scott',
      username: 'marissa', community: null, role: 'regional', is_admin: false }) };
    if (u.startsWith('/api/questions')) return { ok: true, json: async () => ({ status: 'success', questions: QUESTIONS }) };
    return { ok: true, json: async () => ({}) };
  };
  // An upload the test moves along by hand.
  const xhrs = [];
  w.XMLHttpRequest = class {
    constructor() { this.upload = {}; xhrs.push(this); }
    open(method, url) { this.method = method; this.url = url; }
    send(body) { this.body = body; }
    progress(part) { this.upload.onprogress({ lengthComputable: true, loaded: part * 1000, total: 1000 }); }
    finish(status, json) { this.status = status; this.responseText = JSON.stringify(json); this.onload(); }
    drop() { this.onerror(); }
  };
  const el = w.document.createElement('script');
  el.textContent = script;
  w.document.body.appendChild(el);
  return { w, xhrs, alerts };
}

const settle = () => new Promise((r) => setTimeout(r, 30));
function mark(w, qid, value, text) {
  const input = w.document.querySelector(`input[name="condition_${qid}"][value="${value}"]`);
  input.checked = true;
  input.dispatchEvent(new w.Event('change', { bubbles: true }));
  if (text !== undefined) w.document.getElementById(`description_${qid}`).value = text;
}
async function readyAndSubmit() {
  const ctx = boot();
  await ctx.w.loadUserInfo();
  await settle();
  mark(ctx.w, 'q1', 'Pass');
  mark(ctx.w, 'q2', 'Fail', 'Door seal torn');
  mark(ctx.w, 'q3', 'Not checked', 'Kitchen closed');
  ctx.w.document.getElementById('reportForm').dispatchEvent(new ctx.w.Event('submit', { cancelable: true }));
  await settle();
  return ctx;
}
const btn = (w) => w.document.querySelector('button[type="submit"]');

console.log('\nWhile it goes up, the button says how far');
{
  const { w, xhrs } = await readyAndSubmit();
  ok(xhrs.length === 1 && xhrs[0].method === 'POST' && xhrs[0].url === '/api/inspections', 'the visit is posted once, to the same place');
  ok(btn(w).disabled && /^Sending…/.test(btn(w).textContent), `the button says it is sending (${btn(w).textContent})`);
  xhrs[0].progress(0.62);
  ok(btn(w).textContent === 'Sending… 62%', `with the real share sent (${btn(w).textContent})`);
  ok(btn(w).style.getPropertyValue('--sent') === '62%', 'and fills to match');
  xhrs[0].progress(1);
  ok(/notifying the team/.test(btn(w).textContent), `then says what the server is doing (${btn(w).textContent})`);
  xhrs[0].finish(201, { status: 'success', submission: { id: 's1' } });
  await settle();
  ok(w.document.getElementById('successScreen').classList.contains('show'), 'the confirmation shows');
  ok(w.document.getElementById('successSummary').textContent === '1 pass · 1 fail · 1 not checked',
     `with what was sent, in one line (${w.document.getElementById('successSummary').textContent})`);
  ok(btn(w).textContent === 'Submit Visit' && !btn(w).disabled && !btn(w).style.getPropertyValue('--sent'),
     'and the button is put back');
}

console.log('\nA visit the server refuses: the button comes back, the draft is promised');
{
  const { w, xhrs, alerts } = await readyAndSubmit();
  xhrs[0].progress(1);
  xhrs[0].finish(413, { status: 'error' });
  await settle();
  ok(alerts.some(a => /too big to send/.test(a) && /nothing is lost/.test(a)), 'too big: it says so, and that nothing is lost');
  ok(btn(w).textContent === 'Submit Visit' && !btn(w).disabled, 'and Submit is ready again');
  ok(!w.document.getElementById('successScreen').classList.contains('show'), 'no confirmation');
}

console.log('\nA dropped connection, as before');
{
  const { w, xhrs, alerts } = await readyAndSubmit();
  xhrs[0].progress(0.3);
  xhrs[0].drop();
  await settle();
  ok(alerts.some(a => /Couldn't reach the server/.test(a) && /Your draft is saved/.test(a)),
     'it explains the dropped connection and that the draft is safe');
  ok(btn(w).textContent === 'Submit Visit' && !btn(w).style.getPropertyValue('--sent'), 'and the button is put back, unfilled');
}

console.log(failures ? `\n${failures} failed` : '\nall passed');
process.exit(failures ? 1 : 0);
