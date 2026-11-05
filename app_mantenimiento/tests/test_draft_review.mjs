/*
  An administrator opening somebody's unfinished visit — run rather than read.

  The read-only review, its Remind button, and Send on their behalf, which
  asks first and says what will happen: how much is answered, that it will be
  partial, that a Fail with no comment will say so, and that it reads "Sent by
  Excellence Administrator on behalf of …". The server side is
  test_draft_admin.py.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

const grab = (name) => {
  let i = html.indexOf(`function ${name}(`);
  if (i < 0) throw new Error(`no such function: ${name}`);
  if (html.slice(i - 6, i) === 'async ') i -= 6;
  let depth = 0;
  for (let k = html.indexOf('{', i); k < html.length; k++) {
    if (html[k] === '{') depth++;
    else if (html[k] === '}' && --depth === 0) return html.slice(i, k + 1);
  }
  throw new Error(`unbalanced braces in ${name}`);
};

const DRAFT = {
  username: 'greg.crutcher', owner: 'Greg Crutcher', community: "Monark Grove Greystone",
  survey_type_id: 'sales-marketing', survey_name: 'Sales and Marketing',
  updated_at: '2026-11-03T11:49:00', answered: 3, total: 5, fails_without_comment: 1,
  notes: 'Good tour', notes_photo: false,
  action_items: [{ text: 'Order brochures', assigned_to: 'Sales' }],
  items: [
    { question_id: 'q1', text: 'Lobby clean', condition: 'Pass', description: '', has_photo: false },
    { question_id: 'q2', text: 'Brochures current', condition: 'Fail', description: 'Out of date', has_photo: true },
    { question_id: 'q3', text: '<b>Signage</b>', condition: 'Fail', description: '', has_photo: false },
    { question_id: 'q4', text: 'Model staged', condition: '', description: '', has_photo: false },
    { question_id: 'q5', text: 'Tour route', condition: '', description: '', has_photo: false },
  ],
};

async function world({ confirmAnswer = true } = {}) {
  const dom = new JSDOM(`<!doctype html><body>
    <div id="personModal"><div id="personModalBody"></div></div></body>`, { runScripts: 'outside-only' });
  const w = dom.window;
  w.eval(`
    var calls = [], asked = [], closed = 0;
    function escapeHtml(s) { return String(s == null ? '' : s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }
    function timeAgo() { return '2 days ago'; }
    function closePersonModal() { closed++; }
    function confirm(t) { asked.push(t); return ${confirmAnswer}; }
    function fetch(url, opts) {
      calls.push({ url: String(url), method: (opts && opts.method) || 'GET',
                   body: opts && opts.body ? JSON.parse(opts.body) : null });
      if (String(url).startsWith('/api/drafts/review?')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'success', draft: ${JSON.stringify(DRAFT)} }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'success', message: 'Reminder sent.' }) });
    }
    ${grab('draftReviewQuery')}
    ${grab('openDraftReview')}
    ${grab('draftReviewHtml')}
    ${grab('wireDraftReview')}
  `);
  await w.openDraftReview('greg.crutcher', 'Monark Grove Greystone', 'sales-marketing');
  return w;
}

const tick = () => new Promise(r => setTimeout(r, 0));
const body = (w) => w.document.getElementById('personModalBody');

console.log('\nThe review');
{
  const w = await world();
  const t = body(w).textContent.replace(/\s+/g, ' ');
  ok(/Greg Crutcher · Monark Grove Greystone · Sales and Marketing/.test(t), 'who, where and which visit');
  ok(/3 of 5 answered · 2 not answered · 1 Fail without a comment/.test(t), `the counts (${t.match(/\d of \d[^·]*·[^·]*·[^·]*/)})`);
  ok(/Read-only/.test(t), 'it says it is read-only');
  ok(body(w).querySelectorAll('.drv-item').length === 5, 'every standard, answered or not');
  ok(body(w).querySelectorAll('.drv-blank').length === 2, 'the unanswered ones greyed');
  ok(/No comment yet/.test(body(w).querySelectorAll('.drv-item')[2].textContent), 'a Fail with no comment is flagged');
  const img = body(w).querySelector('.drv-photo');
  ok(img && /\/api\/drafts\/review\/photo\?.*slot=q2/.test(img.getAttribute('src')), 'photos come from the admin route');
  ok(/Good tour/.test(t) && /Order brochures/.test(t), 'notes and action items too');
  ok(!body(w).querySelector('.drv-text b'), 'a standard with markup in it is shown as text');
  ok(!body(w).querySelector('input, textarea, select'), 'and nothing can be edited');
}

console.log('\nRemind');
{
  const w = await world();
  await w.document.getElementById('drvRemind').onclick();
  const c = w.calls.find(x => x.url === '/api/drafts/remind');
  ok(c && c.method === 'POST' && c.body.username === 'greg.crutcher' && c.body.survey_type_id === 'sales-marketing',
     'posts who and which visit');
  ok(/Reminder sent/.test(w.document.getElementById('drvMsg').textContent), 'and says it went');
}

console.log('\nSend on their behalf, after a clear question');
{
  const w = await world();
  await w.document.getElementById('drvSend').onclick();
  const q = w.asked[0] || '';
  ok(/Send Greg Crutcher's visit to Monark Grove Greystone on their behalf\?/.test(q), 'it asks first');
  ok(/3 of 5 standards answered\. It will be marked as a partial visit\./.test(q), 'says how much, and that it is partial');
  ok(/1 Fail without a comment will say none was written/.test(q), 'and what happens to a Fail with no comment');
  ok(/Sent by Excellence Administrator on behalf of Greg Crutcher/.test(q), 'and how it will read — no admin name');
  ok(/Greg Crutcher will be emailed/.test(q), 'and that he is told');
  const c = w.calls.find(x => x.url === '/api/drafts/send-on-behalf');
  ok(c && c.body.confirm === true && c.body.username === 'greg.crutcher', 'then sends, confirmed');
}

console.log('\nCancel sends nothing');
{
  const w = await world({ confirmAnswer: false });
  await w.document.getElementById('drvSend').onclick();
  ok(!w.calls.some(x => x.url === '/api/drafts/send-on-behalf'), 'nothing posted');
}

console.log('\nThe list row opens it, by delegation');
{
  const i = html.indexOf("const row = e.target.closest('.dn-row.is-reviewable[data-draft-user]');");
  ok(i > 0 && /openDraftReview\(row\.dataset\.draftUser, row\.dataset\.draftCommunity, row\.dataset\.draftType\)/
       .test(html.slice(i, i + 200)), 'a click on the row opens the review with its data');
}

console.log(failures ? `\n${failures} failure(s)` : '\nAn admin can read, remind, and send.');
process.exit(failures ? 1 : 0);
