/*
  Clicking a visit opens that visit.

  Two visits landed at The Oscar at Georgetown on the same day — Lauren's
  Sales Quick Visit at 92%, Carol's Operational Quick Visit at 100%. The
  dashboard drew a row for each, with the right inspector and the right
  score on each. Clicking either one opened Carol's.

  The rows passed only the community name, and the panel answered the only
  question it could be asked: show me the most recent visit of this place.
  It had been that way from the start and stayed invisible for as long as
  the visit somebody clicked happened to be the newest, which it nearly
  always is.

  So these run the real openSlidePanel over two visits of one community and
  check which one it picks — and the real renderPanelContent to check the
  header stops calling an old visit the last one.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

/* Pull a function out of the template by matching its braces. Reading the
   source for "openSlidePanel(community, id)" would only prove a string is
   present; this runs the thing. */
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

// Lauren's and Carol's, as they sit in the data: same community, same day,
// hers first. Carol's is the newest, so it is what the old code always showed.
const DATA = {
  status: 'success',
  submissions: [
    {
      id: 'v-lauren', community: 'The Oscar at Georgetown',
      submitted_at: '2026-09-18T14:02:00', inspector_name: 'Lauren Hamilton',
      survey_type_id: 'sales', notes: 'Sales walk',
      responses: [{ question_id: 'q1', condition: 'Fail' },
                  { question_id: 'q2', condition: 'Pass' }],
    },
    {
      id: 'v-carol', community: 'The Oscar at Georgetown',
      submitted_at: '2026-09-18T19:40:00', inspector_name: 'Carol Brinegar',
      survey_type_id: 'ops', notes: 'All passed',
      responses: [{ question_id: 'q1', condition: 'Pass' }],
    },
    {
      id: 'v-elsewhere', community: 'The Goldton At Lake Nona',
      submitted_at: '2026-09-18T21:00:00', inspector_name: 'Jennifer Oscar',
      responses: [{ question_id: 'q1', condition: 'Pass' }],
    },
  ],
};

const dom = new JSDOM('<!doctype html><body></body>', { runScripts: 'outside-only' });
const w = dom.window;
w.DATA = DATA;
w.eval(`
  ${grab('openSlidePanel')}
  var captured = null, emptied = null, opened = 0;
  function fetchInspectionsCached() { return Promise.resolve(DATA); }
  function renderEmptyState(m) { emptied = m; }
  function showPanel() { opened++; }
  function showOverlay() {}
  function scoreBoth(r) { return { current: 1, visit: 2, fixed: 3 }; }
  function countActionItems() { return 0; }
  function groupResponsesByCondition(r, id) { return { forVisit: id, n: r.length }; }
  function extractPhotos() { return []; }
  function partialInfo(s) { return null; }
  function renderPanelContent(d) { captured = d; }
`);

const open = async (community, id) => {
  w.captured = null;
  await w.openSlidePanel(community, id);
  return w.captured;
};

console.log('\nWhich visit the panel opens');
{
  const latest = await open('The Oscar at Georgetown');
  ok(latest && latest.inspectorName === 'Carol Brinegar',
     `no id named, so the community's latest — ${latest && latest.inspectorName}`);

  const older = await open('The Oscar at Georgetown', 'v-lauren');
  ok(older && older.inspectorName === 'Lauren Hamilton',
     `Lauren's row opens Lauren's visit — ${older && older.inspectorName}`);
  ok(older.notes === 'Sales walk', 'with her notes, not the other visit\'s');
  ok(older.totalResponses === 2, `and her two answers (${older.totalResponses})`);
  ok(older.responses.forVisit === 'v-lauren',
     'and the responses are grouped under her id, so comments land on hers');

  const newer = await open('The Oscar at Georgetown', 'v-carol');
  ok(newer.inspectorName === 'Carol Brinegar', 'and Carol\'s row still opens Carol\'s');
}

console.log('\nAn id that names nothing here');
{
  // Stale links exist: a deleted visit, an old bookmark, a feed entry from
  // before ids were recorded. Opening the community beats opening nothing.
  const gone = await open('The Oscar at Georgetown', 'v-deleted-long-ago');
  ok(gone && gone.inspectorName === 'Carol Brinegar',
     'falls back to the latest rather than refusing to open');

  const foreign = await open('The Oscar at Georgetown', 'v-elsewhere');
  ok(foreign && foreign.communityName === 'The Oscar at Georgetown',
     'an id from another community does not drag that community in');
  ok(foreign.inspectorName === 'Carol Brinegar',
     "and does not show Jennifer's visit under Georgetown's name");
}

console.log('\nWhat it still does for callers that mean the community');
{
  // The community card, the ranking, a person's profile: their subject is the
  // place, not one walk through it. They pass no id and must be untouched.
  const card = await open('The Oscar at Georgetown');
  ok(card.isLatest === true, 'the panel knows it is showing the latest');
  ok(card.score === 1 && card.visitScore === 2 && card.fixedSinceVisit === 3,
     'and the stats still come from scoreBoth as before');

  w.emptied = null;
  await w.openSlidePanel('A Community With No Visits');
  ok(/No visit data/.test(w.emptied || ''), 'a place with no visits still says so');

  w.captured = null;
  // It warns on the way out, which is right — and it is expected here, so it
  // is swallowed rather than left to masquerade as this suite's last word.
  const warn = console.warn;
  console.warn = () => {};
  await w.openSlidePanel('');
  console.warn = warn;
  ok(w.captured === null, 'and an empty name still opens nothing');
}

console.log('\nThe header stops calling an old visit the last one');
{
  const hdom = new JSDOM(`<!doctype html><body>
    <h2 id="slidePanelTitle"></h2>
    <p id="slidePanelSubtitle">Last visit: N/A</p>
    <div id="slidePanelBody"></div></body>`, { runScripts: 'outside-only' });
  const h = hdom.window;
  h.eval(`
    ${grab('renderPanelContent')}
    var currentPanelCommunity = null;
    function escapeHtml(s) { return String(s); }
    function inspectorAvatarHtml(n) { return ''; }
    function panelCoverHtml() { return ''; }
    function renderStats() { return ''; }
    function renderVisitNote() { return ''; }
    function renderResponses() { return ''; }
    function renderPhotos() { return ''; }
    function loadCommunityHistory() {}
    function loadCommunityRaised() {}
  `);
  const sub = () => h.document.getElementById('slidePanelSubtitle').textContent;
  const base = { communityName: 'The Oscar at Georgetown', lastVisitDate: '9/18/2026',
                 inspectorName: 'Lauren Hamilton', responses: {}, photos: [] };

  h.renderPanelContent({ ...base, isLatest: true, inspectorName: 'Carol Brinegar' });
  ok(/^Last visit: 9\/18\/2026/.test(sub()), `the newest still reads "Last visit" — ${sub()}`);

  h.renderPanelContent({ ...base, isLatest: false });
  ok(/^Visit: 9\/18\/2026/.test(sub()), `an older one does not — ${sub()}`);
  ok(!/Last visit/.test(sub()), 'the claim is gone, not just reworded');
  ok(/Lauren Hamilton/.test(sub()), 'and it is still attributed to who did it');

  // Callers outside this change pass no isLatest at all.
  h.renderPanelContent({ ...base });
  ok(/^Last visit/.test(sub()), 'an old caller that says nothing keeps the old wording');
}

console.log('\nEvery list that draws one visit names it');
{
  /* Counted against the source, because the failure this guards against is
     silent: a list added later that passes only the community reads the wrong
     visit and says nothing about it. Matching on parentheses rather than a
     regex — several of these calls have .replace(/'/g, "\\'") inside them, and
     a lazy /\([^)]*\)/ stops at the paren in the middle of that. */
  const calls = [];
  for (let i = 0; (i = html.indexOf('openSlidePanel(', i)) >= 0;) {
    if (html.slice(Math.max(0, i - 9), i).includes('function ')) { i += 15; continue; }
    let depth = 0, k = html.indexOf('(', i), start = k + 1, commas = 0;
    for (; k < html.length; k++) {
      const c = html[k];
      if ('(' === c || '{' === c || '[' === c) depth++;
      else if (')' === c || '}' === c || ']' === c) { if (--depth === 0 && c === ')') break; }
      else if (c === ',' && depth === 1) commas++;
    }
    calls.push({ line: html.slice(0, i).split('\n').length, named: commas > 0 });
    i = k;
  }

  const named = calls.filter(c => c.named);
  const place = calls.filter(c => !c.named);

  ok(calls.length === 14, `every call accounted for (${calls.length})`);
  ok(named.length === 6,
     `six lists open the visit they drew (${named.length}: lines ${named.map(c => c.line).join(', ')})`);
  ok(place.length === 8,
     `eight callers mean the community itself (${place.length}: lines ${place.map(c => c.line).join(', ')})`);

  // Named individually too, so the counts above can't be satisfied by the
  // wrong six.
  const namesVisit = (anchor, label) => {
    const i = html.indexOf(anchor);
    ok(i >= 0, `${label}: still there`);
    if (i < 0) return;
    const j = html.indexOf('openSlidePanel(', i);
    ok(named.some(c => c.line === html.slice(0, j).split('\n').length),
       `${label}: names its visit`);
  };
  namesVisit('// --- Recent activity ---', 'Recent activity');
  namesVisit('class="visit-row" onclick=', 'Visits');
  namesVisit('class="cal-row" onclick=', 'Calendar');
  namesVisit('ev.meta && ev.meta.submission_id', 'Profile feed');
  namesVisit('e.raised_item_id', 'Live activity');
  ok(/openSlidePanel\(s\.community, s\.id\)/.test(html), 'Search: names its visit');

  // And the ones whose subject really is the community keep their one argument.
  ok(/open: \(\) => openSlidePanel\(c\.name\)/.test(html),
     'the community list still opens the community');
  ok(/openSlidePanel\(communityName\);/.test(html),
     'and the deep link still opens the community');

  /* The map pin was the first new caller after this test was written, and it
     is the reason the count is checked rather than the six being listed: it
     forced the question out loud. A pin stands for the place, and the score
     printed on it is the latest visit's, which is what an id-less call
     opens — so it passes none, like the community card. */
  ok(/el\.onclick = \(\) => openSlidePanel\(c\.community\);/.test(html),
     'the map pin opens the community, not one visit of it');
}

console.log('\nThe id reaches the feed in the first place');
{
  const py = fs.readFileSync(new URL('../app.py', import.meta.url), 'utf8');
  const i = py.indexOf("activity_service.log(username, 'inspection_submitted'");
  ok(i >= 0, 'a submitted visit is still recorded');
  ok(/submission_id/.test(py.slice(i, i + 320)),
     'and records its id, or the feed row has nothing to name');
}

console.log(failures ? `\n${failures} failure(s)` : '\nA row opens the visit it is a row for.');
process.exit(failures ? 1 : 0);
