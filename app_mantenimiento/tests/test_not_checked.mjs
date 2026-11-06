/*
  "Not checked" on the visit form, run in the page's own code.

  Greg Crutcher asked for a way to skip a standard he could not check that
  day (kitchen closed, room locked) without passing or failing it. It is left
  out of the score, so it needs a reason: without one it is an easy way to
  turn a Fail into a better number. This boots reporte.html, marks answers the
  way a regional would, and submits. The server side is test_not_checked.py.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(new URL('../templates/reporte.html', import.meta.url), 'utf8');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

const COMMUNITY = 'Kelley Place, Enterprise';
const QUESTIONS = [
  { id: 'q1', text: 'Fire extinguisher tags are current', photo_required: false },
  { id: 'q2', text: 'Walk-in cooler seals fully', photo_required: false },
  { id: 'q3', text: 'Dining room set for service', photo_required: false },
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
    <div id="successScreen"></div>
    </body></html>`, { runScripts: 'dangerously', url: 'http://localhost/reporte?community=' + encodeURIComponent(COMMUNITY) });

  const w = dom.window;
  const sent = [];
  const alerts = [];
  w.alert = (m) => alerts.push(String(m));
  const confirms = [];
  w.confirm = (m) => { confirms.push(String(m)); return true; };
  w.Element.prototype.scrollIntoView = function () {};
  w.scrollTo = function () {};
  // jsdom has neither; the page asks both while sending.
  w.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
  w.fetch = async (url, opts) => {
    const u = String(url);
    if (u.startsWith('/api/user-info')) {
      return { ok: true, json: async () => ({ display_name: 'Marissa Scott', username: 'marissa',
        community: null, role: 'regional', is_admin: false }) };
    }
    if (u.startsWith('/api/questions')) {
      return { ok: true, json: async () => ({ status: 'success', questions: QUESTIONS }) };
    }
    if (u.startsWith('/api/inspections') && opts && opts.method === 'POST') {
      sent.push(opts.body);
      return { ok: true, status: 201, json: async () => ({ status: 'success', submission: { id: 's1' } }) };
    }
    return { ok: true, json: async () => ({}) };
  };
  const el = w.document.createElement('script');
  el.textContent = script;
  w.document.body.appendChild(el);
  return { w, sent, alerts, confirms };
}

const settle = () => new Promise((r) => setTimeout(r, 30));

function mark(w, qid, value, text) {
  const input = w.document.querySelector(`input[name="condition_${qid}"][value="${value}"]`);
  input.checked = true;
  input.dispatchEvent(new w.Event('change', { bubbles: true }));
  if (text !== undefined) w.document.getElementById(`description_${qid}`).value = text;
  return input;
}

async function submit(w) {
  w.document.getElementById('reportForm').dispatchEvent(new w.Event('submit', { cancelable: true }));
  await settle();
}

async function ready() {
  const ctx = boot();
  await ctx.w.loadUserInfo();
  await settle();
  return ctx;
}

console.log('\nEvery standard offers it, next to Pass and Fail');
{
  const { w } = await ready();
  for (const q of QUESTIONS) {
    const values = [...w.document.querySelectorAll(`input[name="condition_${q.id}"]`)].map(i => i.value);
    ok(JSON.stringify(values) === JSON.stringify(['Pass', 'Fail', 'Not checked']),
       `${q.id}: Pass, Fail, Not checked (${values.join(', ')})`);
  }
}

console.log('\nOn a phone it gets its own row (the rule, not the look)');
{
  // jsdom has no layout and no media queries, so this cannot show that it
  // fits; a screenshot on a real phone does. What it can hold down is that
  // the rule exists, is for phones, and is aimed at the button that has it.
  const { w } = await ready();
  const label = w.document.querySelector('input[name="condition_q1"][value="Not checked"]').closest('label');
  ok(label.classList.contains('rb-notchecked'), 'the Not checked button carries the class the rule targets');
  const style = [...html.matchAll(/<style>([\s\S]*?)<\/style>/g)].map(m => m[1]).join('\n');
  const sheet = new w.CSSStyleSheet();
  sheet.replaceSync(style);
  const phone = [...sheet.cssRules].filter(r => r.media && /max-width:\s*480px/.test(r.media.mediaText));
  const wraps = phone.some(m => [...m.cssRules].some(r => r.selectorText === '.condition-rating' && r.style.flexWrap === 'wrap'));
  const ownRow = phone.some(m => [...m.cssRules].some(r => r.selectorText === '.radio-button.rb-notchecked' && /100%/.test(r.style.flex)));
  ok(wraps, 'on a phone the row may wrap');
  ok(ownRow, 'and Not checked takes the whole second row');
}

console.log('\nThe chosen answer is filled, light and dark (computed from the real CSS)');
{
  // In dark mode an !important rule painted every segment the same, so a
  // picked Pass or Fail had no fill — only a small icon said which it was.
  const css = [...html.matchAll(/<style>([\s\S]*?)<\/style>/g)].map(m => m[1]).join('\n');
  const rgb = (c) => (c.match(/\d+(\.\d+)?/g) || []).slice(0, 3).map(Number);
  const lum = ([r, g, b]) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const contrast = (a, b) => { const [x, y] = [lum(rgb(a)), lum(rgb(b))].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };
  const seg = (v, cls, on) => `<label class="radio-button${cls === 'notchecked' ? ' rb-notchecked' : ''}"><input type="radio" name="${v}" ${on ? 'checked' : ''}><span class="radio-label ${cls}">${v}</span></label>`;
  for (const dark of [false, true]) {
    const mode = dark ? 'dark' : 'light';
    const dom = new JSDOM(`<!doctype html><html ${dark ? 'data-theme="dark"' : ''}><head><style>${css}</style></head><body>
      <div class="condition-rating">${seg('Pass', 'pass', 1)}${seg('Fail', 'fail', 1)}${seg('Not checked', 'notchecked', 1)}${seg('Idle', 'pass', 0)}</div></body></html>`);
    const w = dom.window;
    const [pass, fail, nc, idle] = [...w.document.querySelectorAll('.radio-label')].map(l => w.getComputedStyle(l));
    const fills = { Pass: [pass, [14, 130, 89]], Fail: [fail, [209, 50, 18]], 'Not checked': [nc, [91, 107, 133]] };
    for (const [name, [st, want]] of Object.entries(fills)) {
      ok(rgb(st.backgroundColor).join() === want.join(), `${mode}: a chosen ${name} is filled with its own colour (${st.backgroundColor})`);
      ok(contrast(st.color, st.backgroundColor) >= 4.5, `${mode}: and its label reads on it (${contrast(st.color, st.backgroundColor).toFixed(1)}:1)`);
    }
    ok(rgb(idle.backgroundColor).join() !== rgb(pass.backgroundColor).join(), `${mode}: one not chosen is not filled`);
  }
}

console.log('\nPicking it asks for a reason');
{
  const { w } = await ready();
  mark(w, 'q2', 'Not checked');
  const req = w.document.getElementById('commentsReq_q2');
  ok(req.classList.contains('show'), 'the "required" mark appears');
  ok(/Reason required/.test(req.textContent), `and says a reason is needed (${req.textContent})`);
  ok(/Why couldn't it be checked/.test(w.document.getElementById('description_q2').placeholder),
     'the box asks why');
  mark(w, 'q2', 'Fail');
  ok(/Required for a Fail/.test(req.textContent), 'switching to Fail asks for the finding instead');
  mark(w, 'q2', 'Pass');
  ok(!req.classList.contains('show'), 'and a Pass needs nothing');
}

console.log('\nWithout a reason it does not send');
{
  const { w, sent, alerts } = await ready();
  mark(w, 'q1', 'Pass');
  mark(w, 'q2', 'Not checked', '   ');
  mark(w, 'q3', 'Pass');
  await submit(w);
  ok(sent.length === 0, 'nothing reaches the server');
  ok(alerts.some(a => /say why "Walk-in cooler seals fully" could not be checked/.test(a)),
     `and it says which one needs a reason (${alerts[0] || 'no alert'})`);
  ok(w.document.getElementById('description_q2').classList.contains('comments-invalid'), 'the box is flagged');
}

console.log('\nWith a reason it is sent as Not checked, reason and all');
{
  const { w, sent, alerts } = await ready();
  mark(w, 'q1', 'Pass');
  mark(w, 'q2', 'Not checked', 'Kitchen closed for deep cleaning');
  mark(w, 'q3', 'Fail', 'Two tables not set');
  await submit(w);
  ok(sent.length === 1, 'it is sent');
  ok(!alerts.length, `with nothing to complain about (${alerts.join(' | ')})`);
  ok(w.document.getElementById('successScreen').classList.contains('show'), 'and the visit is confirmed');
  const responses = sent[0] ? JSON.parse(sent[0].get('responses')) : [];
  const q2 = responses.find(r => r.question_id === 'q2');
  ok(q2 && q2.condition === 'Not checked', 'as Not checked');
  ok(q2 && q2.description === 'Kitchen closed for deep cleaning', 'with its reason');
  ok(responses.length === 3, 'all three answered, so the visit is not partial');
}

console.log('\nA visit with a blank as well: the warning counts only what is scored');
{
  const { w, confirms } = await ready();
  mark(w, 'q1', 'Pass');
  mark(w, 'q2', 'Not checked', 'Locked');
  await submit(w);
  const m = confirms[0] || '';
  ok(/1 of 3 standards has no answer yet/.test(m), 'the blank one is what makes it partial');
  ok(/cover the 1 you did pass or fail/.test(m), `and the score covers the one passed, not two (${m.split('\n')[2] || m})`);
}

console.log('\nThe running score leaves it out');
{
  const { w } = await ready();
  mark(w, 'q1', 'Pass');
  mark(w, 'q2', 'Not checked', 'Locked');
  mark(w, 'q3', 'Pass');
  const shown = w.document.getElementById('progressFill').textContent;
  ok(shown === '100%', `two of two checked passed reads 100%, not 67% (${shown})`);
}

console.log('\nAn unfinished visit brings it back');
{
  const { w } = await ready();
  w.draftApply({ responses: { q2: { condition: 'Not checked', description: 'Locked', routeTo: '' } } });
  const picked = w.document.querySelector('input[name="condition_q2"]:checked');
  ok(picked && picked.value === 'Not checked', 'the choice is restored');
  ok(w.document.getElementById('commentsReq_q2').classList.contains('show'), 'with the reason still required');
  const saved = w.draftCollect().responses.q2;
  ok(saved && saved.condition === 'Not checked' && saved.description === 'Locked', 'and saved again as it was');
}

console.log(failures ? `\n${failures} failure(s)` : '\nNot checked works on the form.');
process.exit(failures ? 1 : 0);
