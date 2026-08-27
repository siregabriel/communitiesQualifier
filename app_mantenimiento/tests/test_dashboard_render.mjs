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
// Some checks need the page's own markup rather than a stub — the search
// palette in particular, since half of what it does is manipulate those
// elements. Lift the real element out of the template by walking its tags, so
// that if it is ever restructured this fails loudly instead of quietly testing
// a placeholder.
function elementFromTemplate(id) {
  const start = html_src.indexOf(`<div id="${id}"`);
  if (start === -1) throw new Error(`#${id} is no longer in the template`);
  let depth = 0, i = start;
  const tag = /<(\/?)div\b[^>]*?(\/?)>/g;
  tag.lastIndex = start;
  let m;
  while ((m = tag.exec(html_src))) {
    if (m[2] === '/') continue;          // self-closing, ignore
    depth += m[1] === '/' ? -1 : 1;
    i = m.index + m[0].length;
    if (depth === 0) return html_src.slice(start, i);
  }
  throw new Error(`#${id} is not balanced in the template`);
}

const searchMarkup = elementFromTemplate('searchOverlay');
const lightboxMarkup = elementFromTemplate('photoLightbox');
for (const needed of ['searchInput', 'searchResults']) {
  if (!searchMarkup.includes(needed)) {
    console.error(`The search markup no longer contains #${needed}.`);
    process.exit(1);
  }
}

const dom = new JSDOM(`<!doctype html><html><body>
  <div id="gallery"></div><div id="userInfo"></div><div id="userName"></div>
  <div id="attentionStrip"></div>
  ${searchMarkup}
  ${lightboxMarkup}
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
// jsdom has no layout, so it implements neither of these. Browsers do.
w.Element.prototype.scrollIntoView = function () {};
w.HTMLElement.prototype.scrollTo = function () {};

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
run(`window.__real = { openSlidePanel, openActivityTarget, showView };
     openSlidePanel = c => { window.__opened = c; };
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

console.log('\nTrend — reading the direction');
const dir = t => run(`JSON.stringify(trendDirection(${JSON.stringify(t)}))`);
ok(dir([]) === undefined || JSON.parse(dir([]) || 'null') === null, 'no visits, no direction');
ok(JSON.parse(dir([80]) || 'null') === null, 'one visit is not a trend');
ok(JSON.parse(dir([70, 85])).dir === 'up', 'a real rise reads as up');
ok(JSON.parse(dir([85, 70])).dir === 'down', 'a real fall reads as down');
ok(JSON.parse(dir([80, 82])).dir === 'flat', 'two points of movement is noise, not a direction');
ok(JSON.parse(dir([80, 80])).dir === 'flat', 'no change is flat');

console.log('Trend — drawing it');
const spark = t => run(`sparklineSvg(${JSON.stringify(t)})`);
ok(spark([80]) === '', 'nothing is drawn for a single visit');
const flat = spark([80, 80, 80]);
ok(flat.includes('<polyline'), 'a flat run still draws a line rather than dividing by zero');
ok(!/NaN|Infinity/.test(flat), 'and produces no NaN coordinates');
const rising = spark([40, 60, 90]);
ok(!/NaN|Infinity/.test(rising) && rising.includes('#0f8a5f'), 'a rising line is drawn in green');
ok(spark([90, 60, 40]).includes('#d13212'), 'a falling one in red');
const block = run(`trendBlock(${JSON.stringify({ trend: [70, 85] })})`);
ok(block.includes('+15 points'), 'the reading spells out the change');
ok(run(`trendBlock(${JSON.stringify({ trend: [70] })})`) === '', 'and says nothing with one visit');

console.log('\nAction Items — collapsing a long thread');
const mkItem = (n) => ({
  submissionId: 's1',
  comments: Array.from({ length: n }, (_, i) => ({
    id: 'c' + i, username: 'someone', author: 'Someone', text: 'Comment ' + i,
    at: new Date().toISOString(),
  })),
});
const ui = n => run(`commentsUi(${JSON.stringify(mkItem(n))}, 'q1', '')`);
ok(!ui(2).includes('cm-toggle'), 'a short thread is left alone');
const long = ui(5);
ok(long.includes('cm-toggle') && long.includes('Show 4 earlier comments'), 'a long one collapses');
ok(long.includes('is-collapsed'), 'and starts collapsed');
ok((long.match(/class="cm"/g) || []).length === 5,
   'every comment is still in the DOM, so expanding needs no re-render');
ok(long.includes('cm-add'), 'and posting a new comment is still offered');

console.log('Action Items — the toggle itself');
const threadHost = w.document.createElement('div');
threadHost.innerHTML = long;
w.document.body.appendChild(threadHost);
const thread = threadHost.querySelector('.cm-list');
const btn = threadHost.querySelector('.cm-toggle');
run(`toggleThread('${thread.id}', document.getElementById('${thread.id}').parentNode.querySelector('.cm-toggle'))`);
ok(!thread.classList.contains('is-collapsed'), 'clicking it expands the thread');
ok(btn.textContent.includes('Hide'), 'and the button says how to undo that');
run(`toggleThread('${thread.id}', document.getElementById('${thread.id}').parentNode.querySelector('.cm-toggle'))`);
ok(thread.classList.contains('is-collapsed') && btn.textContent.includes('Show 4'), 'and back again');

console.log('\nSearch');
run(`communityData = ${JSON.stringify([
  { name: 'Kelley Place, Enterprise', score: 67, lastVisit: 'Jun 20, 2026',
    lastVisitTs: Date.now(), actionItems: 3, trend: [] },
  { name: 'The Goldton at Venice', score: null, lastVisit: 'No visits yet',
    lastVisitTs: 0, actionItems: 0, trend: [] },
])};
regions = [{ id: 'magnolia', name: 'Magnolia', communities: ['Kelley Place, Enterprise'],
             leadership: [{ name: 'June Carter', username: 'june', title: 'Regional' },
                          { name: 'Open', username: '' }] }];
allSubmissions = [{ id: 'v1', community: 'Kelley Place, Enterprise',
                    inspector_name: 'June Carter', submitted_at: '2026-06-20T20:18:27' }];`);

const results = q => JSON.parse(run(
  `runSearch(${JSON.stringify(q)}); JSON.stringify(_srResults.map(r => r.kind + ': ' + r.title))`));
ok(results('kelley').length >= 2, 'a community name finds the community and its visits');
ok(results('kelley')[0].startsWith('Community'), 'and the community itself comes first');
ok(results('june').some(r => r.startsWith('Person')), 'a person is found by name');
ok(!results('open').some(r => r === 'Person: Open'), 'an unfilled leadership slot is not a person');
ok(results('kelley june').length === 1, 'words can be combined, in any order');
ok(results('zzzz').length === 0, 'and nonsense finds nothing');
ok(w.document.getElementById('searchResults').innerHTML.includes('Nothing matches'),
   'which is said out loud rather than left blank');

console.log('Search — keyboard and opening');
run(`openSearch();`);
ok(w.document.getElementById('searchOverlay').classList.contains('show'), 'it opens');
run(`runSearch('kelley');`);
run(`searchKey({ key: 'ArrowDown', preventDefault(){} });`);
ok(run('_srActive') === 1, 'arrow keys move down the list');
run(`searchKey({ key: 'ArrowUp', preventDefault(){} }); searchKey({ key: 'ArrowUp', preventDefault(){} });`);
ok(run('_srActive') === run('_srResults.length') - 1, 'and wrap around the ends');
run(`window.__opened = null; searchPick(0);`);
ok(w.__opened === 'Kelley Place, Enterprise', 'picking a community opens it');
ok(!w.document.getElementById('searchOverlay').classList.contains('show'), 'and closes the search');

console.log('\nPartial visits');
const sub = (conds, total) => ({
  standards_total: total,
  responses: conds.map((c, i) => ({ question_id: 'q' + i, condition: c })),
});
const info = s => JSON.parse(run(`JSON.stringify(partialInfo(${JSON.stringify(s)}))`) || 'null');
ok(info(sub(['Pass', 'Pass', 'Pass'], 8)).answered === 3, 'three of eight is partial');
ok(info(sub(['Pass', 'Pass', 'Pass'], 8)).missing === 5, 'and it knows how many are missing');
ok(info(sub(['Pass', 'Fail', 'Pass'], 3)) === null, 'a complete visit is not partial');
ok(info(sub(['Pass'], null)) === null, 'a visit with no recorded total is left alone');
ok(info(sub(['Pass'], undefined)) === null, 'and so is an older one missing the field entirely');
// Unanswered standards are never stored, but a stray row with no verdict
// must not be counted as answered either.
ok(info({ standards_total: 4, responses: [
  { question_id: 'a', condition: 'Pass' }, { question_id: 'b' }] }).answered === 1,
  'a row with no verdict does not count as answered');

const chip = s => run(`partialChip(partialInfo(${JSON.stringify(s)}))`);
ok(chip(sub(['Pass'], 8)).includes('1 of 8 standards'), 'the chip says what it covers');
ok(chip(sub(['Pass', 'Pass'], 2)) === '', 'and stays away from a complete visit');
ok(run(`partialChip(null)`) === '', 'nothing is drawn without an info object');
ok(run(`partialChip(partialInfo(${JSON.stringify(sub(['Pass'], 8))}), true)`).includes('1/8'),
   'the compact form is just the ratio');

console.log('Partial visits — on the card');
run(`communityData = ${JSON.stringify([
  { name: 'Halfway House', score: 100, actionItems: 0, photoUrl: '#',
    lastVisit: 'Aug 1, 2026', lastVisitTs: Date.now(), trend: [],
    partial: { answered: 3, total: 8, missing: 5 } },
  { name: 'Whole House', score: 100, actionItems: 0, photoUrl: '#',
    lastVisit: 'Aug 1, 2026', lastVisitTs: Date.now(), trend: [], partial: null },
])}; onlyDueForVisit = false; communitySort = 'az'; renderCommunityCards();`);
const cardsHtml = gallery.innerHTML;
ok((cardsHtml.match(/partial-chip/g) || []).length === 1,
   'only the partial visit is labelled, though both show 100%');
ok(cardsHtml.includes('3 of 8 standards'), 'and it says what the number is based on');

console.log('\nPhoto viewer');
const lb = realGet('photoLightbox');
const lbImg = realGet('plbImg');
ok(!!lb && !!lbImg, 'the viewer markup is in the page');
ok(!lb.classList.contains('show'), 'it starts closed');

run(`openPhoto('/static/uploads/x/hallway.jpg', 'Tour Path is show time ready');`);
ok(lb.classList.contains('show'), 'opening a photo shows it');
ok(lbImg.getAttribute('src').endsWith('hallway.jpg'), 'and loads that photo');
ok(realGet('plbCap').textContent.includes('Tour Path'), 'the caption says which standard');
ok(w.document.body.style.overflow === 'hidden', 'the page behind stops scrolling');

console.log('Photo viewer — dismissing');
run(`closePhoto({ target: { id: 'plbImg' } });`);
ok(lb.classList.contains('show'), 'clicking the photo itself does not close it');
run(`closePhoto({ target: { id: 'photoLightbox' } });`);
ok(!lb.classList.contains('show'), 'clicking the backdrop closes it');
ok(w.document.body.style.overflow === '', 'and scrolling is given back');
ok(lbImg.getAttribute('src') === '', 'the image is released');

console.log('Photo viewer — Escape order');
run(`window.__panelClosed = false; closeSlidePanel = () => { window.__panelClosed = true; };`);
run(`openPhoto('/static/uploads/x/a.jpg', 'a');`);
const esc = new w.KeyboardEvent('keydown', { key: 'Escape', bubbles: true });
w.document.dispatchEvent(esc);
ok(!lb.classList.contains('show'), 'Escape closes the photo');
ok(w.__panelClosed === false,
   'and leaves the panel underneath open — otherwise you lose your place');

run(`openPhoto('', 'nothing');`);
ok(!lb.classList.contains('show'), 'an empty path opens nothing at all');

console.log('\nPhoto viewer — the markup actually survives being parsed');
// A caption was being written straight into the onclick with JSON.stringify.
// Its double quotes closed the attribute, so the handler was cut in half and
// the click did nothing — while the zoom cursor still appeared, which is what
// made it look like the click was being swallowed by something else.
// Checking the string is not enough; the browser has to parse it.
const shots = [
  { name: 'action item card',
    html: run(`renderActionItemCardPhotoForTest()`) },
];
function attrsOf(html) {
  const d = w.document.createElement('div');
  d.innerHTML = html;
  const img = d.querySelector('img') || d.querySelector('a');
  return img ? [...img.attributes].map(a => a.name) : [];
}
const KNOWN = ['src', 'alt', 'style', 'onclick', 'onerror', 'class', 'href', 'target', 'title', 'data-path'];
for (const shot of shots) {
  if (!shot.html) continue;
  const stray = attrsOf(shot.html).filter(n => !KNOWN.includes(n));
  ok(stray.length === 0,
     `${shot.name}: no stray attributes from a broken quote (${stray.join(', ')})`);
  const d = w.document.createElement('div');
  d.innerHTML = shot.html;
  const el = d.querySelector('img');
  const handler = el && el.getAttribute('onclick');
  ok(handler && handler.includes('openPhoto') && /\)\s*$/.test(handler.trim()),
     `${shot.name}: the click handler is whole, not truncated`);
}

console.log('\nHistory — reading what was said, in place');
const visit = {
  id: 'v_1', submitted_at: '2026-08-21T09:00:00', inspector: 'Greg Crutcher',
  survey_type: 'Operational Quick Visit', visit_score: 78, current_score: 92,
  passed: 5, failed: 1, fixed: 0, action_items: 1, comments: 3,
  notes: 'Great visit "wonderful event" while I was there.',
  notes_photo: 'x/event.jpg',
  comment_list: [
    { standard: '30 Second Commercial', author: 'Carol Ramirez',
      text: 'Team retrained this week.', at: '2026-08-20T10:00:00', photo: '' },
    { standard: '30 Second Commercial', author: 'Greg Crutcher',
      text: 'Thanks - will check next visit.', at: '2026-08-20T11:00:00', photo: '' },
    { standard: 'Common Area TVs Display', author: 'Carol Ramirez',
      text: 'TV replaced.', at: '2026-08-20T12:00:00', photo: 'x/tv.jpg' },
  ],
};
const panel = run(`visitTalkPanel(${JSON.stringify(visit)})`);
ok(panel.includes('Team retrained'), 'the comment text is there, not just a count');
ok(panel.includes('TV replaced'), 'every comment is included');
ok((panel.match(/talk-thread/g) || []).length === 2,
   'comments are grouped by standard, so a back-and-forth reads as one thread');
ok(panel.includes('Great visit'), 'the visit note is in the same panel');
ok(panel.indexOf('Great visit') < panel.indexOf('Team retrained'),
   'the note leads, as it does everywhere else');
ok(panel.includes('hidden'), 'it starts collapsed');

// The same quoting trap that broke the photo click. Parse it, do not trust it.
const holder = w.document.createElement('div');
holder.innerHTML = panel;
const shot = holder.querySelector('.talk-photo');
ok(!!shot, 'a comment photo is shown');
const strayAttrs = [...shot.attributes].map(a => a.name)
  .filter(n => !['class','src','alt','style','onclick','onerror','data-path'].includes(n));
ok(strayAttrs.length === 0, `no attribute broke out of its quotes (${strayAttrs.join(', ')})`);
ok(holder.querySelector('.talk-text').textContent.includes('"wonderful event"'),
   'quotes inside a note survive intact');

console.log('History — the toggle');
w.document.body.appendChild(holder);
const talk = holder.querySelector('.talk');
ok(talk.hidden === true, 'collapsed to begin with');
run(`toggleVisitTalk('v_1');`);
ok(talk.hidden === false, 'clicking the count opens it');
run(`toggleVisitTalk('v_1');`);
ok(talk.hidden === true, 'and closes it again');

ok(run(`visitTalkPanel({ id: 'v_2', comments: 0, comment_list: [], notes: '' })`) === '',
   'a visit with nothing said renders no panel at all');

/* Ahora todo pasa por renderActionItems: las peticiones viven dentro de la
   misma lista agrupada, no en un bloque aparte. Se maneja la vista real y se
   lee el DOM que sale, no una cadena. */
function aiRender(state) {
  run(`
    allInspections = ${JSON.stringify(state.inspections || [])};
    raisedItems = ${JSON.stringify(state.raised || [])};
    raisedCategories = ${JSON.stringify(state.categories || [])};
    raisedCategoryFilter = ${JSON.stringify(state.categoryFilter || '')};
    aiScope = ${JSON.stringify(state.scope || 'open')};
    currentSurveyTypeFilter = 'all';
    canVerifyFixes = ${state.canVerify === false ? 'false' : 'true'};
    _aiCollapsed.clear(); _aiOpenRows.clear();
    renderActionItems();
  `);
  return gallery;
}

const NOW = new Date().toISOString();
const finding = (over) => Object.assign({
  community: 'Kelley Place, Enterprise', condition: 'Fail',
  questionText: 'Fire extinguisher tags are current',
  description: 'Two tags expired in hall B',
  submissionId: 's1', questionId: 'q1', username: 'june',
  submittedAt: NOW, timestamp: 'Aug 18, 2026', addressed: false,
  comments: [], photoPath: '',
}, over || {});
const ask = (over) => Object.assign({
  id: 'r1', community: 'Kelley Place, Enterprise',
  text: 'Living room furniture is "worn" and needs replacing',
  priority: 'high', photo: 'x/sofa.jpg', category: 'capex',
  category_name: 'CapEx', raised_by_name: 'Jazmyn Frazier',
  raised_at: NOW, resolved: false,
}, over || {});
const CATS = [{ id: 'capex', name: 'CapEx', active: true },
              { id: 'clinical', name: 'Clinical', active: true }];

console.log('\nAction Items — a queue, not a photo wall');
{
  const g = aiRender({ inspections: [finding()], raised: [ask()], categories: CATS });
  ok(!g.classList.contains('gallery-compact'),
     'the grid is gone — a to-do list is read top to bottom, not in a zigzag');
  ok(g.querySelectorAll('.ail-group').length === 1, 'work is grouped by community');
  ok(g.querySelector('.ail-where').textContent.includes('Kelley Place'), 'the group names it');
  ok(g.querySelectorAll('.ail-row').length === 2,
     'the finding and the request are in the same list');
  ok(!g.querySelector('.card-image'),
     'no 120px photo on top of every item');
  ok(g.querySelectorAll('.ail-thumb').length === 2, 'a thumbnail instead');
}

console.log('\nAction Items — the fake priority badge is gone');
{
  const g = aiRender({ inspections: [finding()], raised: [], categories: CATS });
  ok(!/HIGH PRIORITY/i.test(g.innerHTML),
     'a failed standard no longer stamps HIGH PRIORITY on itself; it was hard-coded on every one');
  ok(g.querySelector('.ail-tag-fail').textContent.trim() === 'Fail',
     'it carries the condition it actually has');
}

console.log('\nAction Items — findings and requests are told apart');
{
  const g = aiRender({ inspections: [finding()], raised: [ask()], categories: CATS });
  const rows = [...g.querySelectorAll('.ail-row')];
  const askRow = rows.find(r => r.classList.contains('ail-row-ask'));
  ok(!!askRow, 'a request is marked apart from a finding');
  ok(askRow.querySelector('.ail-tag').textContent.trim() === 'Asked for', 'and says so');
  ok(askRow.querySelector('.ail-cat').textContent.trim() === 'CapEx', 'with its category');
  ok(askRow.querySelector('.ail-title').textContent.includes('"worn"'),
     'quotes in the text survive');
  const strayAttrs = [...askRow.querySelector('.ail-thumb img').attributes].map(a => a.name)
    .filter(n => !['src','data-path','alt','onclick','onerror'].includes(n));
  ok(strayAttrs.length === 0, `nothing broke out of an attribute (${strayAttrs.join(', ')})`);
}

console.log('\nAction Items — one filter bar, not two');
{
  const g = aiRender({ inspections: [finding()], raised: [ask()], categories: CATS });
  ok(g.querySelectorAll('.ai-bar').length === 1, 'a single bar holds both filters');
  ok(g.querySelectorAll('.ai-chiprow').length === 2,
     'scope on one line, the categories under it');
  ok(/Needs attention/.test(g.innerHTML) && /CapEx/.test(g.innerHTML), 'both are present');
}

console.log('\nAction Items — a category filter really filters');
{
  const g = aiRender({ inspections: [finding()], raised: [ask(), ask({ id: 'r2', category: 'clinical', category_name: 'Clinical', text: 'Med cart' })],
                       categories: CATS, categoryFilter: 'clinical' });
  const titles = () => [...gallery.querySelectorAll('.ail-title')].map(t => t.textContent.trim());
  ok(titles().some(t => /Med cart/.test(t)), 'the chosen category is shown');
  ok(!titles().some(t => /furniture/.test(t)), 'another category is filtered out');

  // Keeping the findings on screen made "CapEx" look like a filter that does
  // nothing. They step aside — but the list says so rather than going quiet.
  ok(!titles().some(t => /Fire extinguisher/.test(t)),
     'and so are the findings, which never had a category to choose');
  const note = g.querySelector('.ai-hidden');
  ok(!!note && /1 visit finding hidden — it carries no category/.test(note.textContent),
     `the list says what it took out, and says it in the singular (${
        note ? note.textContent.trim().replace(/\s+/g, ' ').slice(0, 55) : 'no note'})`);

  run('aiKeepFindings(true)');
  ok(titles().some(t => /Fire extinguisher/.test(t)), 'and offers them back');
  ok(/shown alongside/.test(gallery.querySelector('.ai-hidden').textContent),
     'saying plainly that they are back');

  run(`setRaisedCategoryFilter('capex')`);
  ok(run('_aiKeepFindings') === false,
     'choosing a different category asks the question again rather than carrying the last answer');

  run(`setRaisedCategoryFilter('capex')`);
  ok(!gallery.querySelector('.ai-hidden'),
     'and with no category chosen there is nothing to explain');
}

console.log('\nAction Items — the detail opens in place');
{
  const g = aiRender({ inspections: [finding()], raised: [], categories: CATS });
  const row = g.querySelector('.ail-row');
  ok(!row.classList.contains('is-open'), 'a row starts closed, so the list stays scannable');
  ok(/Two tags expired/.test(row.querySelector('.ail-detail').textContent),
     'the description is in the detail, not on the line');
  run(`aiToggleRow('${row.id}')`);
  ok(gallery.querySelector('#' + row.id).classList.contains('is-open'), 'tapping it opens it');
  run(`aiToggleRow('${row.id}')`);
  ok(!gallery.querySelector('#' + row.id).classList.contains('is-open'), 'and closes it again');
}

console.log('\nAction Items — closed work reads as closed');
{
  const g = aiRender({ scope: 'done', inspections: [finding({ addressed: true, addressedBy: 'Marissa' })],
                       raised: [ask({ resolved: true, resolved_by: 'Marissa' })], categories: CATS });
  ok(g.querySelectorAll('.ail-row.is-done').length === 2, 'both are marked done');
  ok(g.querySelector('.ail-count.is-clear'),
     'a community with nothing open shows a tick rather than a red zero');
}

console.log('\nAction Items — an ED is not offered the close button');
{
  const g = aiRender({ inspections: [finding()], raised: [], categories: CATS, canVerify: false });
  ok(!g.querySelector('.ai-resolve-btn'), 'they cannot close a finding');
  ok(/A regional will review/.test(g.innerHTML), 'and are told who does');
}

console.log('\nAction Items — nothing to do says so');
{
  const g = aiRender({ inspections: [], raised: [], categories: CATS });
  ok(!!g.querySelector('.empty-state'), 'an empty queue renders an empty state');
  ok(!g.querySelector('.ail-group'), 'and no stray group headers');
}

console.log('');
/* ---- Descarga sellada: la ruta llega hasta el visor ------------------- */
/* El visor solo recibia la URL firmada de S3, que caduca y no dice de que
   comunidad es. Sin la ruta guardada el servidor no puede poner el pie. */
console.log('\nPhoto download — the stored path reaches the viewer');
{
  const tpl = html_src;
  const calls = [...tpl.matchAll(/openPhoto\(([^)]*)\)/g)].map(m => m[1]);
  const opens = calls.filter(c => !c.startsWith('src'));   // fuera la definicion
  ok(opens.length >= 10, `every photo in the app opens the viewer (${opens.length} places)`);
  const noPath = opens.filter(c => !/dataset\.path/.test(c));
  ok(noPath.length === 0,
     `each one hands over the stored path, or the download has nothing to caption (${noPath.join(' | ')})`);

  const imgs = [...tpl.matchAll(/data-path="\$\{escapeHtmlForAttr\(([^)]+)\)\}"/g)];
  ok(imgs.length >= 10, `and the path is escaped on the way into the attribute (${imgs.length})`);

  ok(/id="plbDownload"[\s\S]{0,240}?download/.test(tpl), 'the viewer has a download control');
  ok(/\/api\/photo\/download\?path=' \+ encodeURIComponent\(path\)/.test(tpl),
     'it points at the app, not straight at the file');
  ok(/dl\.style\.display = 'none'/.test(tpl),
     'and hides itself when there is no path to caption');
  // Segundo boton, sobre la esquina de la foto dentro de la visita.
  ok(/class="rp-dl"[\s\S]{0,200}?\/api\/photo\/download\?path=\$\{encodeURIComponent\(response\.photoPath\)\}/.test(tpl),
     'the photo inside a visit has its own download on the corner');
  ok(/class="rp-wrap"/.test(tpl),
     'wrapped so the button lands on the photo, not on the whole card');
  ok(/onerror="this\.closest\('\.response-photo'\)\.style\.display='none'"/.test(tpl),
     'a broken photo takes its download button with it');

}

/* ---- La ficha de comunidad ------------------------------------------- */
console.log('\nCommunity card — the score rides on the photo');
{
  run(`
    communityData = [{
      name: 'Legacy Reserve at Old Town, Columbus',
      lastVisit: 'Aug 18, 2026', lastVisitTs: Date.now(),
      score: 55, visitScore: 48, fixedSinceVisit: 3,
      actionItems: 5, trend: [], partial: null, photoUrl: '#eee'
    }, {
      name: 'The Oscar at Georgetown',
      lastVisit: null, lastVisitTs: 0,
      score: null, actionItems: 0, trend: [], partial: null, photoUrl: '#eee'
    }];
    communitySort = 'name'; onlyDueForVisit = false;
    renderCommunityCards();
  `);
  const cards = gallery.querySelectorAll('.community-card');
  ok(cards.length === 2, `both communities render (${cards.length})`);

  const first = cards[0];
  ok(!!first.querySelector('.card-image .cc-medal'),
     'the score hangs off the cover photo instead of filling the card');
  ok(first.querySelector('.cc-medal').classList.contains('warning'),
     'a 55% wears the amber halo, not the green one');
  ok(first.querySelector('.cc-medal .progress-value').textContent.trim() === '55%',
     'and still reads the current score');
  ok(first.querySelectorAll('.cc-medal circle').length === 3,
     'two arcs plus the track, so recovered points are visible at a glance');

  ok(first.querySelector('.card-title').textContent.trim() === 'Legacy Reserve at Old Town',
     'the title drops the city, which was forcing a second line');
  ok(/Columbus/.test(first.querySelector('.card-date').textContent),
     'the city moves down beside the date');

  ok(first.dataset.community === 'Legacy Reserve at Old Town, Columbus',
     'the whole name is kept on the card, or opening it would find nothing');
  ok(!first.querySelector('.view-details-btn'),
     'the full-width button is gone — the card itself is the target');

  const stats = first.querySelectorAll('.cc-stat-v');
  ok(stats.length === 3 && stats[0].textContent.trim() === '48%'
     && stats[1].textContent.trim() === '3' && stats[2].textContent.trim() === '5',
     'at the visit, fixed since, and open — all three were buried before');

  const never = cards[1];
  ok(never.querySelector('.cc-medal').classList.contains('na'),
     'and a community never visited wears the neutral one');
  ok(never.classList.contains('cc-nodata'), 'a community with no visit is marked');
  ok(never.querySelectorAll('.cc-stat').length === 0,
     'and shows no stat boxes, which would all be zero');
  ok(!never.querySelector('.cc-go'), 'nor invites you into an empty panel');
}

console.log('\nCommunity card — clicking it opens the right community');
{
  let opened = null;
  run(`window.__realOpen = openSlidePanel; openSlidePanel = n => { window.__opened = n; };`);
  const card = gallery.querySelector('.community-card');
  card.querySelector('.card-title').dispatchEvent(new w.Event('click', { bubbles: true }));
  await new Promise(r => setTimeout(r, 300));
  opened = w.__opened;
  ok(opened === 'Legacy Reserve at Old Town, Columbus',
     `the stored name is what gets opened, city included (${opened})`);

  w.__opened = null;
  const dead = gallery.querySelectorAll('.community-card')[1];
  dead.querySelector('.card-title').dispatchEvent(new w.Event('click', { bubbles: true }));
  await new Promise(r => setTimeout(r, 300));
  ok(w.__opened === null, 'a community with no visit does not open an empty panel');
  run(`openSlidePanel = window.__realOpen;`);
}

console.log('\nCommunity card — names with and without a city');
{
  const split = n => run(`JSON.stringify(splitCommunityName(${JSON.stringify(n)}))`);
  const a = JSON.parse(split('Legacy Reserve at Old Town, Columbus'));
  ok(a.name === 'Legacy Reserve at Old Town' && a.place === 'Columbus', 'one comma splits cleanly');
  const b = JSON.parse(split('The Oscar at Georgetown'));
  ok(b.name === 'The Oscar at Georgetown' && b.place === '', 'no comma, nothing invented');
  const c = JSON.parse(split('The Enclave at Round Rock Senior Living, Round Rock, TX'));
  ok(c.name === 'The Enclave at Round Rock Senior Living' && c.place === 'Round Rock, TX',
     'the first comma splits, so the state does not become the whole place');
}

/* jsdom no calcula diseño, así que las trampas de CSS se comprueban leyendo la
   hoja. Ésta en concreto ya me mordió: el medallón cuelga del borde inferior de
   la foto, y un overflow:hidden en la foto lo recorta sin avisar. */
console.log('\nCommunity card — the medal is not clipped away');
{
  const css = html_src.slice(html_src.indexOf('.community-card .card-image {'),
                             html_src.indexOf('.community-card .card-image img {'));
  // Not "no hidden here" — that passed while the medal was being sliced in
  // half, because dropping the declaration handed the decision back to the
  // base .card-image rule, which clips. It has to say visible out loud.
  ok(/overflow:\s*visible/.test(css),
     'the cover photo declares overflow visible, beating the base rule that clips');
  ok(/height:\s*168px/.test(css), 'and the photo is shorter than the 200px it was');

  const medal = html_src.slice(html_src.indexOf('.cc-medal {'), html_src.indexOf('.cc-chips'));
  ok(/bottom:\s*-\d+px/.test(medal), 'the medal sits below the photo edge');
  const medalZ = Number((medal.match(/z-index:\s*(\d+)/) || [])[1]);
  const coverZ = Number((html_src.slice(html_src.indexOf('.cover-actions {'))
                                 .match(/z-index:\s*(\d+)/) || [])[1]);
  ok(medalZ > coverZ, `the medal sits above the cover controls (${medalZ} > ${coverZ})`);

  for (const state of ['warning', 'danger', 'na']) {
    ok(new RegExp('\\.cc-medal\\.' + state + ' \\{').test(html_src),
       `a ${state} score gets its own halo colour`);
  }
  ok(/\.cc-medal \{[^}]*rgba\(16, 185, 129/.test(html_src),
     'and a passing score glows green by default');

  // The card itself must keep clipping: it is what holds the cover photo's
  // top corners exactly on the card's curve. Letting the photo round itself
  // left a pixel of card showing at each corner, because the 1px border makes
  // the card's inner radius 17px against the photo's 18px.
  const theme = fs.readFileSync(new URL('../static/theme.css', import.meta.url), 'utf8');
  const cardRule = theme.slice(theme.indexOf('/* A vivid top accent rail'),
                               theme.indexOf('/* Region badge overlaid'));
  ok(/\.community-card \{[^}]*overflow:\s*hidden/.test(cardRule),
     'the card clips, which is what keeps the photo corners true');
  ok(!/\.community-card \.card-image \{[^}]*border-radius/.test(cardRule),
     'and the photo does not fight it with a radius of its own');

  // So the halo has to fit inside the card rather than escape it. Measured,
  // not eyeballed — this is the whole reason the corners broke last time.
  const geom = html_src.slice(html_src.indexOf('.cc-medal {'), html_src.indexOf('.cc-medal.warning'));
  const right = Number((geom.match(/right:\s*(\d+)px/) || [])[1]);
  const glow = geom.match(/0 0 (\d+)px (\d+)px rgba/);
  const reach = Number(glow[1]) + Number(glow[2]);
  ok(right - reach > 1,
     `the halo stops ${right - reach}px short of the card edge, so nothing clips it`);

  ok(/@media \(max-width: 600px\) \{\s*\.cc-stats \{ display: none/.test(html_src),
     'the three stat boxes stand down on a phone, where they do not fit');

  const title = html_src.slice(html_src.indexOf('.community-card .card-title {'),
                               html_src.indexOf('.community-card .card-date {'));
  ok(/padding-right:\s*\d+px/.test(title),
     'the title reserves room so a long name never runs under the medal');
}

console.log('\nCommunity card — each region wears its own mark');
{
  // An earlier section pinned getCommunityRegionName to a single region;
  // put a real lookup back before asking what each card shows.
  run(`regions = [{ name: 'Innovia', communities: ['Legacy Reserve at Old Town, Columbus'] },
                 { name: 'DMV', communities: ['Tribute at The Glen'] },
                 { name: 'Unassigned', communities: ['The Oscar at Georgetown'] }];
       getCommunityRegionName = n => (regions.find(r => r.communities.includes(n)) || {}).name || null;
       communityData = [
         { name: 'Legacy Reserve at Old Town, Columbus', lastVisit: 'Aug 18, 2026', lastVisitTs: 2,
           score: 55, visitScore: 48, fixedSinceVisit: 3, actionItems: 5, trend: [], partial: null, photoUrl: '#eee' },
         { name: 'Tribute at The Glen', lastVisit: 'Aug 12, 2026', lastVisitTs: 1,
           score: 89, actionItems: 0, trend: [], partial: null, photoUrl: '#eee' },
         { name: 'The Oscar at Georgetown', lastVisit: 'Aug 20, 2026', lastVisitTs: 3,
           score: 92, actionItems: 0, trend: [], partial: null, photoUrl: '#eee' }];
       communitySort = 'name'; onlyDueForVisit = false; renderCommunityCards();`);

  const badges = [...gallery.querySelectorAll('.card-region-badge')];
  ok(badges.length === 3, `every card still names its region (${badges.length})`);

  const src = n => badges.find(b => b.textContent.trim() === n)?.querySelector('.rb-icon')?.getAttribute('src');
  ok(src('Innovia') === '/static/region-innovia.svg', 'Innovia gets its own mark');
  ok(src('DMV') === '/static/region-dmv.svg', 'and DMV, lowercased into a filename');

  // Unassigned has no file. jsdom does not fire onerror for a missing image,
  // so check the fallback the way the page would take it.
  const un = badges.find(b => b.textContent.trim() === 'Unassigned');
  ok(/replaceWith/.test(un.querySelector('.rb-icon').getAttribute('onerror')),
     'a region with no mark falls back instead of showing a broken image');
  ok(run(`regionIconHtml('')`) === '<i class="fas fa-sitemap"></i>',
     'and no region at all asks for no file at all');

  // The mark is an <img> inside the cover photo, so the photo's own rule —
  // position:absolute, inset:0 — matches it too and lifted it out of the pill
  // onto the region name. It has to opt back into the flex row explicitly.
  const themeCss = fs.readFileSync(new URL('../static/theme.css', import.meta.url), 'utf8');
  const iconRule = themeCss.slice(themeCss.indexOf('.community-card .card-region-badge .rb-icon {'),
                                  themeCss.indexOf('}', themeCss.indexOf('.community-card .card-region-badge .rb-icon {')));
  ok(/position:\s*static/.test(iconRule),
     'the mark stays in the pill instead of being absolutely positioned onto the name');
  ok(/inset:\s*auto/.test(iconRule), 'and is not pinned to the pill corner');
  ok(/width:\s*14px/.test(iconRule) && /height:\s*14px/.test(iconRule),
     'at a badge size, not the photo size the cover rule would give it');

  const files = fs.readdirSync(new URL('../static/', import.meta.url))
                  .filter(f => f.startsWith('region-') && f.endsWith('.svg'));
  for (const f of files) {
    const slug = f.slice('region-'.length, -'.svg'.length);
    ok(/^[a-z0-9-]+$/.test(slug), `${f} is named the way the card asks for it`);
  }
}

console.log('\nRaised items — the form requires a category');
{
  const tpl = html_src;
  ok(/id="riCategory"/.test(tpl), 'the raise form has a category dropdown');
  ok(/Pick a category\./.test(tpl), 'and refuses to send without one');
  ok(/fd\.append\('category', category\)/.test(tpl), 'sending the chosen id, not the label');
  ok(/if \(!\(raisedCategories \|\| \[\]\)\.length\) await loadRaisedCategories\(\)/.test(tpl),
     'and loads the list first, so a required field is never a dead end');
}

console.log('\nActivity feed — a row opens the exact item it is about');
{
  // An earlier section replaced these with spies. Left in place they would
  // make this whole section a test of the spy — which is what happened the
  // first time it was written.
  // openActivityTarget itself is the real one — it is what widens the scope,
  // clears the filter and marks the row to reveal. Only showView is stood in
  // for: the real one wipes the page for a skeleton and reloads from the
  // server, which here would just erase the fixture. What it does once the
  // data is in hand is render the view, so that is what the stand-in does.
  run(`openActivityTarget = window.__real.openActivityTarget;
       openSlidePanel = window.__real.openSlidePanel;
       showView = v => { window.__view = v; if (v === 'action-items') renderActionItems(); };`);
  // The feed has linked into Action Items for a while. The list rewrite gave
  // rows a closed state and groups a folded one, which quietly turned those
  // links into a scroll to something with no height.
  const many = [];
  for (let i = 0; i < 5; i++) {
    many.push(finding({ community: 'Community ' + i, submissionId: 's' + i, questionId: 'q' + i,
                        questionText: 'Standard ' + i, addressed: true }));
  }
  many.push(finding({ community: 'Target Place', submissionId: 'sX', questionId: 'qX',
                      questionText: 'The one being linked to', addressed: true,
                      comments: [{ id: 'c1', author: 'Marissa Scott', at: NOW, text: 'Vendor comes Friday' }] }));
  aiRender({ inspections: many, raised: [], categories: CATS, scope: 'all' });

  ok(gallery.querySelectorAll('.ail-group').length === 6, 'enough groups that folding kicks in');
  const folded = [...gallery.querySelectorAll('.ail-group.is-folded')].length;
  ok(folded > 0, `groups with nothing open start folded (${folded})`);

  run(`openActivityTarget('sX','qX','')`);
  const row = gallery.querySelector('#ai_sX_qX');
  ok(!!row, 'the linked row is rendered');
  ok(!row.closest('.ail-group').classList.contains('is-folded'),
     'its group is unfolded, or the link lands on something with no height');
  ok(row.classList.contains('is-open'), 'and the row itself is open');
  ok(/Vendor comes Friday/.test(row.querySelector('.ail-detail').textContent),
     'so the comment they clicked through to read is actually on screen');
}

console.log('\nActivity feed — a filter left on cannot hide the target');
{
  aiRender({ inspections: [finding({ submissionId: 'sY', questionId: 'qY' })],
             raised: [ask()], categories: CATS, categoryFilter: 'clinical', scope: 'open' });
  run(`openActivityTarget('sY','qY','')`);
  ok(run('raisedCategoryFilter') === '', 'the category filter is cleared on the way in');
  ok(run('aiScope') === 'all', 'and the scope widens, in case the item is closed or from an earlier visit');
  ok(!!gallery.querySelector('#ai_sY_qY'), 'the target is on screen');
}

console.log('\nActivity feed — one definition of a row key');
{
  // Drawing a row with one formula and linking to it with another is how a
  // deep link starts landing on nothing.
  const tpl = html_src;
  const built = tpl.match(/'ai_' \+ [A-Za-z]+/g) || [];
  ok(built.length === 2,
     `the key is built in two places only — the row helper and the link that resolves one (${built.length})`);
  ok(/const key = aiRowKey\(r\)/.test(tpl), 'the finding row uses the helper');
  ok(/aiRowKey\(\{ kind: 'raised'/.test(tpl), 'and so does a request row');
}

console.log('\nRaised items — the same conversation a finding has');
{
  // Every Executive Director was told they can comment back and forth on
  // these. Until now there was no thread on a raised item at all.
  run(`currentUserCommunities = ['Kelley Place, Enterprise']; currentUsername = 'jaz'; isAdmin = false;`);
  const withThread = ask({
    community: 'Kelley Place, Enterprise',
    comments: [
      { id: 'c1', username: 'jaz', author: 'Jazmyn Frazier', text: 'Quotes attached', at: NOW },
      { id: 'c2', username: 'marissa', author: 'Marissa Scott', text: 'Approved', at: NOW },
    ],
  });
  const g = aiRender({ inspections: [], raised: [withThread], categories: CATS });
  const row = g.querySelector('.ail-row-ask');

  ok(/Quotes attached/.test(row.textContent) && /Approved/.test(row.textContent),
     'both sides of the thread are on the item');
  ok(/Marissa Scott/.test(row.textContent), 'each reply is attributed');
  ok(!!row.querySelector('.cm-add'), 'and there is a way to add one');
  ok(/openRaisedCommentBox/.test(row.querySelector('.cm-add').getAttribute('onclick')),
     'which posts against the raised item, not against a visit');
  ok(/2/.test(row.querySelector('.ail-meta').textContent),
     'the line shows how many replies there are without opening it');

  const del = [...row.querySelectorAll('.cm-del')];
  ok(del.length === 1, 'you can delete your own comment and not the other one');
  ok(/deleteRaisedComment\('r1','c1'\)/.test(del[0].getAttribute('onclick')),
     'and it targets that exact comment');
}

console.log('\nRaised items — who closes it');
{
  run(`currentUserCommunities = ['Kelley Place, Enterprise']; isAdmin = false;`);
  const mine = aiRender({ inspections: [], raised: [ask({ community: 'Kelley Place, Enterprise' })],
                          categories: CATS });
  ok(!!mine.querySelector('.ail-row-ask .ai-resolve-btn'),
     'the community that raised it can mark it done');

  // A regional sees the same item in their queue and must not close it.
  run(`currentUserCommunities = []; isAdmin = false;`);
  const theirs = aiRender({ inspections: [], raised: [ask({ community: 'Kelley Place, Enterprise' })],
                            categories: CATS });
  ok(!theirs.querySelector('.ail-row-ask .ai-resolve-btn'),
     'a regional is not offered the close button');
  ok(/The community closes this one out/.test(theirs.querySelector('.ail-row-ask').textContent),
     'and is told what to do instead');
  ok(!!theirs.querySelector('.ail-row-ask .cm-add'), 'they can still reply');
}

console.log('\nRaised items — one thread renderer, not two');
{
  // A finding and a request are different things, but the conversation is the
  // same conversation. Two copies would drift apart.
  const tpl = html_src;
  ok((tpl.match(/class="cm-wrap"/g) || []).length === 1,
     'the thread markup exists once');
  ok(/function commentsUi[\s\S]{0,400}commentThreadHtml\(/.test(tpl),
     'a finding renders through it');
  ok(/function raisedCommentsUi[\s\S]{0,400}commentThreadHtml\(/.test(tpl),
     'and so does a request');
}

console.log('\nActivity feed — a raised item is reachable too');
{
  run(`openActivityTarget = window.__real.openActivityTarget;
       openSlidePanel = window.__real.openSlidePanel;
       showView = v => { window.__view = v; if (v === 'action-items') renderActionItems(); };`);
  aiRender({ inspections: [], raised: [ask({ id: 'rZ', community: 'Kelley Place, Enterprise' })],
             categories: CATS });
  run(`openRaisedTarget('rZ')`);
  const row = gallery.querySelector('#ask_rZ');
  ok(!!row, 'the row the feed points at is rendered');
  ok(row.classList.contains('is-open'),
     'and opened, so the reply that was just posted is on screen');
  ok(!row.closest('.ail-group').classList.contains('is-folded'), 'with its group unfolded');
}

console.log(failures ? `${failures} failure(s)` : 'The dashboard renders as intended.');
process.exit(failures ? 1 : 0);
