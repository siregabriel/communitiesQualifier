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
const KNOWN = ['src', 'alt', 'style', 'onclick', 'onerror', 'class', 'href', 'target', 'title'];
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
  .filter(n => !['class','src','alt','style','onclick','onerror'].includes(n));
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

console.log('\nRaised by the community');
const raised = [
  { id: 'r1', community: "O'Brien Place", text: 'Living room furniture is "worn" and needs replacing',
    priority: 'high', photo: 'x/sofa.jpg', raised_by_name: 'Jazmyn Frazier',
    raised_at: new Date().toISOString(), resolved: false },
  { id: 'r2', community: "O'Brien Place", text: 'Fire extinguisher tag is out of date',
    priority: 'medium', photo: '', raised_by_name: 'Jazmyn Frazier',
    raised_at: new Date().toISOString(), resolved: false },
  { id: 'r3', community: "O'Brien Place", text: 'Already handled', priority: 'low',
    photo: '', raised_by_name: 'Jazmyn Frazier', raised_at: new Date().toISOString(), resolved: true },
];
run(`raisedItems = ${JSON.stringify(raised)};`);
const ri = run('raisedItemsHtml()');
ok(ri.includes('Raised by the community'), 'the section renders');
ok((ri.match(/ri-card/g) || []).length === 2, 'resolved ones are not shown');
ok(ri.includes('>2<'), 'the count matches what is open');
ok(ri.includes('no score changed'), 'it says plainly that this is not a finding');
ok(ri.includes('Jazmyn Frazier'), 'it names who raised it');

// The quoting trap again — parse it rather than trusting the string.
const box = w.document.createElement('div');
box.innerHTML = ri;
const riPhoto = box.querySelector('.ri-photo');
ok(!!riPhoto, 'a photo is shown when there is one');
const stray = [...riPhoto.attributes].map(a => a.name)
  .filter(n => !['class','src','alt','style','onclick','onerror'].includes(n));
ok(stray.length === 0, `quotes in the text do not break out of the attribute (${stray.join(', ')})`);
ok(box.querySelector('.ri-text').textContent.includes('"worn"'), 'and the text reads correctly');

run('raisedItems = [];');
ok(run('raisedItemsHtml()') === '', 'nothing raised, nothing rendered');
run(`raisedItems = ${JSON.stringify([raised[2]])};`);
ok(run('raisedItemsHtml()') === '', 'only resolved ones is the same as nothing');

console.log('');
console.log(failures ? `${failures} failure(s)` : 'The dashboard renders as intended.');
process.exit(failures ? 1 : 0);
