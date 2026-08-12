/*
 * Dashboard render tests.
 *
 * The dashboard's JavaScript lives inline in templates/dashboard.html, so this
 * pulls the script out of the template and runs it in a real DOM. Checking the
 * syntax is not enough: the mistakes that have actually reached production here
 * were undefined variables and functions that only blow up when called. This
 * calls them.
 *
 * The script is injected as a genuine <script> element so its top-level
 * declarations land in the global lexical scope — that is what lets the checks
 * below read and set the same variables the render functions close over.
 *
 *   cd app_mantenimiento && npm install --no-save jsdom
 *   node tests/test_dashboard_render.mjs
 */
import { JSDOM } from 'jsdom';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const TEMPLATE = path.join(HERE, '..', 'templates', 'dashboard.html');

// The template holds several <script> blocks; the app's own code is the big one.
const html_src = fs.readFileSync(TEMPLATE, 'utf8');
const blocks = [...html_src.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
const js = blocks.reduce((a, b) => (b.length > a.length ? b : a), '');
if (js.length < 10000) {
  console.error('Could not find the dashboard script in the template.');
  process.exit(1);
}
const dom = new JSDOM(`<!doctype html><html><body>
  <div id="gallery"></div><div id="userInfo"></div><div id="userName"></div>
  <div id="attentionStrip"></div>
</body></html>`, { runScripts: 'dangerously', url: 'http://localhost/' });
const w = dom.window;

// The page wires up dozens of elements at load. Rather than rebuild the whole
// document, hand back a throwaway element for anything it can't find — the
// point is to exercise the render functions, not the markup around them.
const realGet = w.document.getElementById.bind(w.document);
const realQS = w.document.querySelector.bind(w.document);
w.document.getElementById = id => realGet(id) || w.document.createElement('div');
w.document.querySelector = sel => realQS(sel) || w.document.createElement('div');

w.fetch = async () => ({ ok: true, status: 200, json: async () => ({}) });
w.Chart = function () { return { destroy() {} }; };

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

const el = w.document.createElement('script');
el.textContent = js;
try { w.document.body.appendChild(el); } catch (e) {
  console.log('  FAIL  the script threw on load: ' + e.message); failures++;
}
const run = code => w.eval(code);

const strip = realGet('attentionStrip');
const gallery = realGet('gallery');

console.log('\nNeeds you — nothing pending');
run(`_attnData = { role: 'regional', cadence_days: 30, groups: [], total: 0 }; renderAttention();`);
ok(strip.innerHTML === '', 'the strip renders nothing at all when there is nothing to do');

console.log('\nNeeds you — a regional with work');
const data = {
  role: 'regional', cadence_days: 30, total: 9,
  groups: [
    { key: 'verify', tone: 'act', title: 'Fixes waiting on your confirmation',
      note: 'A community says these are done.', total: 5,
      items: Array.from({ length: 5 }, (_, i) => ({
        community: "O'Brien Place, Athens", title: 'Standard ' + i,
        detail: 'Reported fixed by Carol', days: i, submission_id: 's1',
        question_id: 'q' + i, view: 'action-items' })) },
    { key: 'overdue', tone: 'plan', title: 'Due for a visit', note: 'Target is every 30 days.',
      total: 4, items: [{ community: 'Kelley Place', title: 'Kelley Place',
        detail: 'No visit on record', days: null, never: true, view: 'communities' }] },
  ],
};
run(`_attnData = ${JSON.stringify(data)}; renderAttention();`);
const html = strip.innerHTML;
ok(html.includes('Needs you'), 'the strip renders');
ok(html.includes('9 items'), 'the header counts everything, not just what is shown');
ok((html.match(/attn-item/g) || []).length === 4, 'each group shows at most three rows (3 + 1)');
ok(html.includes('Show 2 more'), 'the rest sit behind a "show more"');
// Rows are wired by index, so a name with an apostrophe never has to survive
// being quoted into an attribute — which is exactly how this used to break.
ok(!/onclick="[^"]*O'Brien/.test(html), 'a community name never reaches an onclick attribute');
ok(html.includes("O'Brien Place, Athens"), 'and still reads correctly as text');

console.log('\nNeeds you — expanding a group');
run(`expandAttention('verify');`);
ok((strip.innerHTML.match(/attn-item/g) || []).length === 6, 'expanding shows all five, plus the other group');
ok(!strip.innerHTML.includes('Show '), 'nothing left to expand once everything is shown');

console.log('\nNeeds you — more than the server sent');
// The server caps each group, so a long queue has to hand off to the full view
// rather than pretend "show more" can reach the rest.
const capped = { role: 'regional', cadence_days: 30, total: 30, groups: [{
  key: 'verify', tone: 'act', title: 'Fixes waiting on your confirmation', note: '', total: 30,
  items: Array.from({ length: 6 }, (_, i) => ({ community: 'C', title: 'S' + i,
    detail: 'd', days: i, submission_id: 's', question_id: 'q' + i, view: 'action-items' })) }] };
run(`_attnExpanded = {}; _attnData = ${JSON.stringify(capped)}; renderAttention();`);
ok(strip.innerHTML.includes('Show 3 more'), 'first it offers the rest of what it has');
run(`expandAttention('verify');`);
ok(strip.innerHTML.includes('See all 30'), 'then it hands off to the full view');

console.log('\nNeeds you — clicking through');
run(`_attnExpanded = {}; _attnData = ${JSON.stringify(data)}; renderAttention();`);
run(`openSlidePanel = c => { window.__opened = c; };
     openActivityTarget = (s, q) => { window.__target = [s, q]; };
     showView = v => { window.__view = v; };`);
run(`openAttentionItem('overdue', 0);`);
ok(w.__opened === 'Kelley Place', 'a community row opens that community');
run(`openAttentionItem('verify', 2);`);
ok(w.__target && w.__target[1] === 'q2', 'a standard row opens that exact standard');
run(`openAttentionGroup('overdue');`);
ok(w.__view === 'communities', 'the overdue group leads to Communities');
run(`openAttentionGroup('verify');`);
ok(w.__view === 'action-items', 'the others lead to Action Items');

console.log('\nVisit cadence — the rules');
const day = 86400000;
const mk = (name, daysAgo) => ({
  name, score: 80, actionItems: 0, photoUrl: '#', lastVisit: 'x', visitScore: null,
  lastVisitTs: daysAgo === null ? null : new Date(Date.now() - daysAgo * day).toISOString(),
});
run('visitCadenceDays = 30;');
const call = (fn, arg) => run(`(${fn})(${JSON.stringify(arg)})`);
ok(call('daysSinceVisit', mk('a', 45)) === 45, 'days since a visit are counted');
ok(call('daysSinceVisit', mk('a', null)) === null, 'never visited has no count');
ok(call('isDueForVisit', mk('a', null)) === true, 'never visited always counts as due');
ok(call('isDueForVisit', mk('a', 31)) === true, 'past the target is due');
ok(call('isDueForVisit', mk('a', 29)) === false, 'inside the target is not');
ok(call('visitAgeBadge', mk('a', 10)) === '', 'no chip while a community is on schedule');
ok(call('visitAgeBadge', mk('a', 40)).includes('age-chip-due'), 'a chip once it slips');
ok(call('visitAgeBadge', mk('a', 70)).includes('age-chip-late'), 'a louder chip when it is far past');
ok(call('visitAgeBadge', mk('a', null)).includes('Never visited'), 'and a distinct one for never visited');

console.log('\nSorting by longest since a visit');
const list = [mk('recent', 2), mk('never', null), mk('old', 90), mk('mid', 40)];
const sorted = run(`communitySort = 'stale'; sortCommunities(${JSON.stringify(list)}).map(c => c.name).join(',')`);
ok(sorted === 'never,old,mid,recent', 'never visited first, then oldest to newest');

console.log('\nRendering the cards');
run(`getCommunitySlug = n => n.toLowerCase();
     getCommunityRegionName = () => 'Coastal';
     communityCovers = {}; regions = []; isAdmin = false;
     currentConditionFilter = 'all'; communitySort = 'stale'; onlyDueForVisit = false;
     communityData = ${JSON.stringify([mk('Alpha', 2), mk('Beta', 90), mk('Gamma', null)])};
     renderCommunityCards();`);
const cards = gallery.innerHTML;
ok(cards.includes('2 due for a visit'), 'the toolbar counts the ones behind');
ok(cards.includes('Longest since a visit'), 'the new sort is offered');
ok((cards.match(/class="age-chip /g) || []).length === 2, 'only the two behind get a chip');
ok(cards.indexOf('Gamma') < cards.indexOf('Beta'), 'never visited is drawn first');

run(`onlyDueForVisit = true; renderCommunityCards();`);
const only = gallery.innerHTML;
ok(!only.includes('>Alpha<'), 'filtering to due only hides the on-schedule community');
ok(only.includes('Gamma') && only.includes('Beta'), 'and keeps both that are behind');
ok(only.includes('Showing due only'), 'the toggle shows it is on');

run(`communityData = ${JSON.stringify([mk('Alpha', 2)])}; renderCommunityCards();`);
ok(gallery.innerHTML.includes('Every community has been visited'),
   'due-only with nothing behind says so, and offers a way back');

console.log('');
console.log(failures ? `${failures} failure(s)` : 'The dashboard renders as intended.');
process.exit(failures ? 1 : 0);
