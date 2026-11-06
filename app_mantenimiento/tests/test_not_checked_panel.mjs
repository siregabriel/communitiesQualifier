/*
  "Not checked" wherever a visit is read back: the visit panel, the history
  under a community, and an admin's review of an unfinished visit.

  It is left out of the score, which is only fair if everyone can see it was
  used and why. A Not checked shown as a Pass (the panel's fallback badge), or
  a history row saying "All passed" over three of them, would hide exactly
  what Greg Crutcher asked to be made visible. The form side is
  test_not_checked.mjs, the server side test_not_checked.py.
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
  throw new Error('unbalanced braces in ' + name);
};

function boot(fetchReply) {
  const dom = new JSDOM(`<!doctype html><body><div id="panelHistory"></div></body>`,
                        { runScripts: 'outside-only' });
  const w = dom.window;
  w.fetch = async () => ({ ok: true, json: async () => fetchReply });
  w.eval(`
    ${grab('escapeHtml')}
    ${grab('decodeEntities')}
    ${grab('escapeHtmlForAttr')}
    ${grab('getBadgeClass')}
    ${grab('getBadgeIcon')}
    ${grab('groupResponsesByCondition')}
    ${grab('renderResponses')}
    ${grab('loadCommunityHistory')}
    ${grab('draftReviewHtml')}
    ${grab('partialInfo')}
    function standardFor() { return null; }
    function photoUrl(p) { return p; }
    function formatDate(s) { return s; }
    function scoreColor() { return '#000'; }
    function visitTalkPanel() { return ''; }
    // The trend line and stats above the list: real ones, they only draw.
    ${grab('trendDirection')}
    ${grab('sparklineSvg')}
    function renderOnBehalfNote() {}
    function renderStats() { return ''; }
    function timeAgo() { return 'today'; }
    function draftReviewQuery() { return ''; }
  `);
  return w;
}

console.log('\nThe visit panel');
{
  const w = boot({});
  const grouped = w.groupResponsesByCondition([
    { question_text: 'Dining room set', condition: 'Pass' },
    { question_text: 'Walk-in cooler seals', condition: 'Not checked', description: 'Kitchen closed for deep cleaning' },
    { question_text: 'Exit signs lit', condition: 'Fail', description: 'East corridor out' },
  ], 's1');
  ok(grouped.map(r => r.condition).join(',') === 'Fail,Not checked,Pass',
     'sorted Fail, then Not checked, then Pass');
  const nc = grouped.find(r => r.condition === 'Not checked');
  ok(nc.conditionClass === 'badge-notchecked', `its own badge, not the Pass fallback (${nc.conditionClass})`);

  const host = w.document.createElement('div');
  host.innerHTML = w.renderResponses(grouped);
  const card = [...host.querySelectorAll('.response-card')]
    .find(c => c.textContent.includes('Walk-in cooler seals'));
  ok(card && card.querySelector('.badge-notchecked') && /Not checked/.test(card.querySelector('.response-condition').textContent),
     'the card says Not checked');
  ok(card && /Why:\s*Kitchen closed for deep cleaning/.test(card.querySelector('.response-description').textContent),
     'and gives the reason, labelled as the reason');
  const fail = [...host.querySelectorAll('.response-card')].find(c => c.textContent.includes('Exit signs'));
  ok(fail && !/Why:/.test(fail.textContent), 'a Fail comment is not labelled as a reason');
}

console.log('\nThe history under a community');
{
  const visit = (extra) => ({ id: 'v1', submitted_at: '2026-11-06', inspector: 'Greg Crutcher', survey_type: '',
    visit_score: 100, current_score: 100, passed: 4, failed: 0, fixed: 0, action_items: 0, comments: 0,
    partial: false, answered: 6, standards_total: 6, notes: '', ...extra });
  let w = boot({ status: 'success', visits: [visit({ not_checked: 2 })],
                 standards: [{ question_text: 'Exit signs lit', fails: 1, seen: 1,
                               results: ['not_checked', 'fail'] }] });
  await w.loadCommunityHistory('Kelley Place');
  const host = w.document.getElementById('panelHistory');
  ok(/2 not checked/.test(host.textContent), 'the visit row says how many were not checked');
  ok(!/All passed/.test(host.textContent), 'and does not claim everything passed');
  ok(/No fails/.test(host.textContent), 'only that nothing failed');
  const dot = host.querySelector('.trk-dots .dot-nc');
  ok(dot && /Not checked/.test(dot.title), 'the timeline marks that visit as not checked');
  ok(host.querySelector('.trk-legend .dot-nc'), 'and the legend explains the mark');

  w = boot({ status: 'success', visits: [visit({ not_checked: 0 })], standards: [] });
  await w.loadCommunityHistory('Kelley Place');
  ok(/All passed/.test(w.document.getElementById('panelHistory').textContent), 'with none, it is still "All passed"');
}

console.log('\nAn admin reviewing an unfinished visit');
{
  const w = boot({});
  const host = w.document.createElement('div');
  host.innerHTML = w.draftReviewHtml({
    owner: 'Greg Crutcher', community: 'Greystone', survey_name: '', total: 3, updated_at: '',
    fails_without_comment: 0, not_checked_without_reason: 1, action_items: [], notes: '',
    items: [
      { question_id: 'q1', text: 'Brochures current', condition: 'Pass', description: '' },
      { question_id: 'q2', text: 'Model room ready', condition: 'Not checked', description: '' },
      { question_id: 'q3', text: 'Signage', condition: '', description: '' },
    ],
  });
  ok(/2 of 3 answered/.test(host.textContent), 'Not checked counts as answered');
  ok(host.querySelector('.drv-nc') && /Not checked/.test(host.querySelector('.drv-nc').textContent),
     'and shows as Not checked, not "Not answered"');
  ok(/No reason yet/.test(host.textContent), 'a missing reason is pointed out');
  ok(/1 Not checked without a reason/.test(host.textContent), 'and counted in the summary');
}

console.log('\nA community card does not call it partial');
{
  // The server already counted it as answered; the card worked it out again
  // from Pass and Fail only, and would have shown "3/4" over a whole visit.
  const w = boot({});
  const whole = { standards_total: 3, responses: [
    { condition: 'Pass' }, { condition: 'Fail' }, { condition: 'Not checked', description: 'Locked' }] };
  ok(w.partialInfo(whole) === null, 'three of three answered is not partial');
  const blank = { standards_total: 4, responses: whole.responses };
  const p = w.partialInfo(blank);
  ok(p && p.answered === 3 && p.missing === 1, 'a blank one still is');
}

console.log(failures ? `\n${failures} failure(s)` : '\nNot checked is visible wherever a visit is read.');
process.exit(failures ? 1 : 0);
