/*
  "Share this note with the community's staff", run in the pages' own code.

  Lauren Hamilton asked whether a community's whole team could read the notes
  a visitor writes to the Executive Director. They could. Now a note is
  private unless the visitor ticks a box under it. This holds down that the
  box starts unticked, that only a ticked box sends the flag, that the choice
  survives an unfinished visit on the phone and on the server, and that the
  panel says who a note reaches. Server side: test_private_notes.py.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const form = fs.readFileSync(new URL('../templates/reporte.html', import.meta.url), 'utf8');
const dash = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

const grab = (src, name) => {
  let i = src.indexOf(`function ${name}(`);
  if (i < 0) throw new Error('not found: ' + name);
  if (src.slice(i - 6, i) === 'async ') i -= 6;
  let depth = 0;
  for (let k = src.indexOf('{', i); k < src.length; k++) {
    if (src[k] === '{') depth++;
    else if (src[k] === '}' && --depth === 0) return src.slice(i, k + 1);
  }
  throw new Error('unbalanced braces in ' + name);
};

const COMMUNITY = 'The Goldton at Venice, Venice';

// The notes section exactly as the page has it, so the test reads the real
// markup rather than a copy that could drift.
const section = (() => {
  const start = form.indexOf('<div class="notes-section" id="visitNotesSection">');
  let depth = 0;
  const tag = /<(\/?)div\b[^>]*>/g;
  tag.lastIndex = start;
  let m;
  while ((m = tag.exec(form))) {
    depth += m[1] ? -1 : 1;
    if (depth === 0) return form.slice(start, m.index + m[0].length);
  }
  throw new Error('notes section not balanced');
})();

function bootForm() {
  const script = [...form.matchAll(/<script>([\s\S]*?)<\/script>/g)]
    .map((m) => m[1]).reduce((a, b) => (b.length > a.length ? b : a), '')
    .replace(/\{\{\s*survey_type_id\s*\}\}/g, 'standards')
    .replace(/\{\{\s*departments\s*\|\s*tojson\s*\}\}/g, '[]')
    .replace(/\{\{\s*community_places\s*\|\s*tojson\s*\}\}/g, '[]');
  const dom = new JSDOM(`<!doctype html><html><body>
    <div id="userInfo"></div><div id="loadingMessage"></div><div id="communityPrompt"></div>
    <select id="communitySelect"><option value="">—</option><option value="${COMMUNITY}">${COMMUNITY}</option></select>
    <form id="reportForm" style="display:none;">${section}<button type="submit">Submit Visit</button></form>
    <div id="questionsContainer"></div>
    <div id="progressContainer"><div id="progressFill"></div><div id="progressMessage"></div></div>
    <div id="draftChip"></div><div id="draftBanner"></div><div id="draftStatus"></div>
    <div id="successScreen"></div>
    </body></html>`, { runScripts: 'dangerously', url: 'http://localhost/reporte?community=' + encodeURIComponent(COMMUNITY) });
  const w = dom.window;
  const sent = [];
  w.alert = () => {};
  w.confirm = () => true;
  w.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} });
  w.Element.prototype.scrollIntoView = function () {};
  w.scrollTo = function () {};
  w.fetch = async (url, opts) => {
    const u = String(url);
    if (u.startsWith('/api/user-info')) {
      return { ok: true, json: async () => ({ display_name: 'Lauren Hamilton', username: 'lauren',
        community: null, role: 'regional', is_admin: false }) };
    }
    if (u.startsWith('/api/questions')) {
      return { ok: true, json: async () => ({ status: 'success', questions: [
        { id: 'q1', text: 'Lobby clean', photo_required: false }] }) };
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
  return { w, sent };
}

const settle = () => new Promise((r) => setTimeout(r, 30));

async function submitWith(shared) {
  const { w, sent } = bootForm();
  await w.loadUserInfo();
  await settle();
  const pass = w.document.querySelector('input[name="condition_q1"][value="Pass"]');
  pass.checked = true;
  w.document.getElementById('visitNotes').value = 'Talk to Laura about the sales numbers.';
  if (shared) w.document.getElementById('visitNotesShared').checked = true;
  w.document.getElementById('reportForm').dispatchEvent(new w.Event('submit', { cancelable: true }));
  await settle();
  return { w, body: sent[0] };
}

console.log('\nThe box under the note');
{
  const { w } = bootForm();
  await w.loadUserInfo();
  await settle();
  const box = w.document.getElementById('visitNotesShared');
  ok(box && box.type === 'checkbox', 'there is a checkbox');
  ok(box && !box.checked, 'and it starts unticked: private unless chosen');
  const label = box && box.closest('label');
  ok(label && /Share this note with the community's staff/.test(label.textContent), 'it says what it does');
  ok(label && /only the Executive Director and leadership/.test(label.textContent), 'and what unticked means');
  ok(label && /Staff always see the findings/.test(label.textContent), 'and that the findings are not affected');
}

console.log('\nWhat is sent');
{
  const off = await submitWith(false);
  ok(off.body && off.body.get('visit_notes'), 'the note is sent');
  ok(off.body && off.body.get('visit_notes_shared') === null, 'unticked: no share flag at all');
  const on = await submitWith(true);
  ok(on.body && on.body.get('visit_notes_shared') === '1', 'ticked: shared');
}

console.log('\nAn unfinished visit keeps the choice');
{
  const { w } = bootForm();
  await w.loadUserInfo();
  await settle();
  w.document.getElementById('visitNotesShared').checked = true;
  const saved = w.draftCollect();
  ok(saved.notesShared === true, 'saved on the phone');
  ok(w.draftServerBody(saved).notes_shared === true, 'and sent to the server copy');
  w.document.getElementById('visitNotesShared').checked = false;
  w.draftApply({ responses: {}, notes: 'x', notesShared: true });
  ok(w.document.getElementById('visitNotesShared').checked, 'restored ticked');
  w.draftApply({ responses: {}, notes: 'x' });
  ok(!w.document.getElementById('visitNotesShared').checked, 'and an older draft with no choice comes back private');
  const remote = await w.draftFromRemote({ responses: {}, notes: 'x', notes_shared: true, photos: {} }, 'k');
  ok(remote.draft.notesShared === true, "the server's copy carries it back to the phone");
}

console.log('\nThe panel and the history say who a note reaches');
{
  const dom = new JSDOM('<!doctype html><body></body>', { runScripts: 'outside-only' });
  const w = dom.window;
  w.eval(`
    ${grab(dash, 'escapeHtml')}
    ${grab(dash, 'decodeEntities')}
    ${grab(dash, 'escapeHtmlForAttr')}
    ${grab(dash, 'visitNoteAudience')}
    ${grab(dash, 'renderVisitNote')}
    ${grab(dash, 'visitTalkPanel')}
    function photoUrl(p) { return p; }
    function commentThreadHtml() { return ''; }
    function formatDate(s) { return s; }
  `);
  const box = w.document.createElement('div');
  box.innerHTML = w.renderVisitNote('A note', '', false);
  ok(/Private · Executive Director and leadership/.test(box.querySelector('.vnote-who').textContent),
     'a private note says it is private');
  box.innerHTML = w.renderVisitNote('A note', '', true);
  ok(/Shared with the community's staff/.test(box.querySelector('.vnote-who').textContent),
     'a shared one says it is shared');
  box.innerHTML = w.visitTalkPanel({ id: 'v1', notes: 'A note', notes_shared: false, comment_list: [] });
  ok(box.querySelector('.vnote-who') && /Private/.test(box.querySelector('.vnote-who').textContent),
     'and the history says the same');
  const call = dash.match(/renderVisitNote\(data\.notes, data\.notesPhoto, ([^)]+)\)/);
  ok(call && call[1] === 'data.notesShared', 'the panel passes the visit\'s own choice in');
  ok(/notesShared: !!chosen\.notes_shared/.test(dash), 'read from the visit the server sent');
}

console.log('\nHow it reads, light and dark (computed from the page\'s real CSS)');
{
  // Gabriel's screenshot: the share box came out in spaced capitals, because
  // the page's bare `label` rule (meant for field captions) reaches every
  // <label>. Checking that rule then showed worse: the notes section had no
  // dark style, so it stayed white while the dark `label` rule turned label
  // text near-white — "Add a photo" and the share box, white on white.
  // jsdom resolves the cascade, !important included; it does not lay out.
  const css = [...form.matchAll(/<style>([\s\S]*?)<\/style>/g)].map(m => m[1]).join('\n');
  const rgb = (c) => (c.match(/\d+(\.\d+)?/g) || []).slice(0, 3).map(Number);
  const lum = ([r, g, b]) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const contrast = (a, b) => { const [x, y] = [lum(rgb(a)), lum(rgb(b))].sort((m, n) => n - m); return (x + 0.05) / (y + 0.05); };
  for (const dark of [false, true]) {
    const mode = dark ? 'dark' : 'light';
    const dom = new JSDOM(`<!doctype html><html ${dark ? 'data-theme="dark"' : ''}><head><style>${css}</style></head><body>${section}</body></html>`);
    const w = dom.window, d = w.document, cs = (el) => w.getComputedStyle(el);
    const share = d.querySelector('.notes-share'), photo = d.querySelector('.notes-photo');
    const bg = cs(d.querySelector('.notes-section')).backgroundColor;
    ok(cs(share).textTransform === 'none' && cs(share).letterSpacing === 'normal',
       `${mode}: the share box is a sentence, not spaced capitals`);
    ok(cs(photo).textTransform === 'none', `${mode}: "Add a photo" is not in capitals either`);
    const pairs = [['the share box heading', share.querySelector('b'), bg],
                   ['its explanation', share.querySelector('small'), bg],
                   ['"Add a photo"', photo, cs(photo).backgroundColor]];
    for (const [name, el, behind] of pairs) {
      const c = contrast(cs(el).color, behind);
      ok(c >= 4.5, `${mode}: ${name} is readable (${c.toFixed(1)}:1)`);
    }
    if (dark) ok(rgb(bg).every(v => v < 60), `dark: the section itself is dark (${bg})`);
  }
}

console.log(failures ? `\n${failures} failure(s)` : '\nNotes are private unless shared.');
process.exit(failures ? 1 : 0);
