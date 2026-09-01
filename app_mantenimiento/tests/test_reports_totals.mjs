/*
  The numbers at the top of Reports, counted rather than trusted.

  "Total Visits" was reading allInspections.length. That array is built one
  entry per answered standard, plus one per action item raised during a visit —
  so a fortnight of work showed 263 visits where 24 had happened, and the card
  sat directly above a leaderboard saying 24. Nobody could tell which was
  lying.

  This builds submissions of a known shape and checks each card against the
  thing it claims to count.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

const grab = (name) => {
  let i = html.indexOf(`function ${name}(`);
  if (i < 0) throw new Error('not found: ' + name);
  if (html.slice(i - 6, i) === 'async ') i -= 6;
  let depth = 0;
  for (let k = html.indexOf('{', i); k < html.length; k++) {
    if (html[k] === '{') depth++;
    else if (html[k] === '}' && --depth === 0) return html.slice(i, k + 1);
  }
};

/* Three visits: 11 standards each on two of them, 20 on the third, plus two
   action items raised along the way. Matches the real shape — the visits list
   shows 10 pass / 1 fail, 20 pass / 0 fail, 7 pass / 4 fail. */
const VISITS = [
  { id: 's1', username: 'zach', community: 'A', survey_type_id: 'standards',
    submitted_at: '2026-08-27T10:00:00', pass: 10, fail: 1, actions: 1 },
  { id: 's2', username: 'shannon', community: 'A', survey_type_id: 'sales',
    submitted_at: '2026-08-26T10:00:00', pass: 20, fail: 0, actions: 0 },
  { id: 's3', username: 'greg', community: 'B', survey_type_id: 'standards',
    submitted_at: '2026-08-25T10:00:00', pass: 7, fail: 4, actions: 1 },
];

const submissions = VISITS.map(v => ({
  id: v.id, username: v.username, community: v.community,
  survey_type_id: v.survey_type_id, submitted_at: v.submitted_at,
  responses: [
    ...Array.from({ length: v.pass }, (_, i) => ({ question_id: `p${i}`, condition: 'Pass' })),
    ...Array.from({ length: v.fail }, (_, i) => ({ question_id: `f${i}`, condition: 'Fail' })),
  ],
  action_items: Array.from({ length: v.actions }, (_, i) => ({ id: `a${i}`, text: 'Dryer vent' })),
}));

const expected = {
  visits: VISITS.length,
  standards: VISITS.reduce((n, v) => n + v.pass + v.fail, 0),
  pass: VISITS.reduce((n, v) => n + v.pass, 0),
  fail: VISITS.reduce((n, v) => n + v.fail, 0),
  actions: VISITS.reduce((n, v) => n + v.actions, 0),
};

const dom = new JSDOM('<!doctype html><body><div id="gallery"></div></body>',
                      { runScripts: 'outside-only' });
const w = dom.window;

w.eval(`
  ${grab('escapeHtml')}
  ${grab('decodeEntities')}
  ${grab('formatTimestamp')}
  ${grab('renderReports')}
  var allSubmissions = ${JSON.stringify(submissions)};
  var surveyTypes = [
    { id: 'standards', name: 'Standards', color: '#00285c', icon: 'fa-list' },
    { id: 'sales', name: 'Sales Quick Visit', color: '#0f8a5f', icon: 'fa-tag' }];
  var allInspections = [];
  allSubmissions.forEach(s => {
    s.responses.forEach(r => allInspections.push({
      type: 'inspection', condition: r.condition, surveyTypeId: s.survey_type_id }));
    (s.action_items || []).forEach(() => allInspections.push({
      type: 'manual-action', condition: 'Action', surveyTypeId: s.survey_type_id }));
  });
  function renderLeaderboard() {}
  // Other things the Reports view draws, which this test is not about.
  var communityData = [];
  var currentUser = 'admin';
  var isAdmin = true;
  function getCommunityRegionName() { return ''; }
  function loadLeaderboard() {}
  function renderScoreTrend() {}
`);

w.renderReports();

/* Read the cards back off the page: label -> number. */
const cards = {};
for (const box of w.document.querySelectorAll('#gallery div[style*="border-radius: 10px"]')) {
  const kids = box.children;
  if (kids.length === 2 && /^\d+$/.test(kids[1].textContent.trim())) {
    cards[kids[0].textContent.trim()] = Number(kids[1].textContent.trim());
  }
}

console.log('\nWhat each card counts');
ok(cards['Visits'] === expected.visits,
   `Visits is how many visits happened (${cards['Visits']}, expected ${expected.visits})`);
ok(cards['Standards checked'] === expected.standards,
   `Standards checked is every standard answered (${cards['Standards checked']}, expected ${expected.standards})`);
ok(cards['Pass'] === expected.pass, `Pass (${cards['Pass']})`);
ok(cards['Fail'] === expected.fail, `Fail (${cards['Fail']})`);

console.log('\nAnd they add up');
ok(cards['Pass'] + cards['Fail'] === cards['Standards checked'],
   'pass plus fail is every standard checked — action items are not standards and never scored');
ok(cards['Visits'] < cards['Standards checked'],
   'a visit covers many standards, so it can never be the larger number');
ok(!('Total Visits' in cards),
   'and nothing is still labelled "Total Visits" while counting something else');

console.log('\nThe number matches what the leaderboard would say');
{
  // The leaderboard counts submissions server-side. The card is computed here.
  // Those two sitting side by side disagreeing is the bug as it was seen.
  const perPerson = {};
  submissions.forEach(s => { perPerson[s.username] = (perPerson[s.username] || 0) + 1; });
  const leaderboardTotal = Object.values(perPerson).reduce((a, b) => a + b, 0);
  ok(cards['Visits'] === leaderboardTotal,
     `the card and the leaderboard agree (${cards['Visits']} vs ${leaderboardTotal})`);
}

console.log(failures ? `\n${failures} failure(s)` : '\nThe totals count what they say they count.');
process.exit(failures ? 1 : 0);
