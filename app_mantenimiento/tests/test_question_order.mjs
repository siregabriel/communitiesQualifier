/*
  Moving a standard up or down on the Standards page, run in the page's code.

  Greg Crutcher asked to change the order of the questions (Nov 2026). The
  page used to sort them newest first itself, so even a server that kept an
  order would have been overruled here. Now it shows the server's order, and
  the arrows send the whole list back with two neighbours swapped. With a
  survey type filter on, the swap is with the next question you can see,
  leaving the hidden ones where they were. Server side: test_question_order.py.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(new URL('../templates/question_manager.html', import.meta.url), 'utf8');

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

// Server order on purpose NOT newest first, so a page that re-sorts shows it.
const SERVER = [
  { id: 'q_a', text: 'Exits lit', created_at: '2026-01-01T00:00:00', survey_types: [] },
  { id: 'q_b', text: 'Sales binder', created_at: '2026-03-01T00:00:00', survey_types: ['sales'] },
  { id: 'q_c', text: 'Kitchen clean', created_at: '2026-02-01T00:00:00', survey_types: ['clinical'] },
  { id: 'q_d', text: 'Model room', created_at: '2026-04-01T00:00:00', survey_types: ['sales'] },
];

function boot() {
  const dom = new JSDOM(`<!doctype html><body>
    <select id="surveyTypeFilter"><option value="">All</option><option value="sales">Sales</option></select>
    <table><tbody id="questionsBody"></tbody></table>
    <input type="checkbox" id="selectAllRows"></body>`,
    // The arrows are inline onclick handlers, as on the page; jsdom only
    // runs those in this mode. Clicking them is the point of the test.
    { runScripts: 'dangerously' });
  const w = dom.window;
  let server = SERVER.map(q => ({ ...q }));
  const posted = [];
  w.fetch = async (url, opts) => {
    if (url === '/api/questions/order') {
      const ids = JSON.parse(opts.body).ids;
      posted.push(ids);
      server = ids.map(id => server.find(q => q.id === id));
      return { ok: true, json: async () => ({ status: 'success', ids }) };
    }
    return { ok: true, json: async () => ({ status: 'success', questions: server.map(q => ({ ...q })) }) };
  };
  w.alert = () => {};
  w.eval(`
    let questions = [];
    let surveyTypes = [];
    let allQuestions = [];
    ${grab('escapeHtml')}
    ${grab('decodeEntities')}
    ${grab('getSurveyTypeBadges')}
    ${grab('renderQuestions')}
    ${grab('filterQuestions')}
    ${grab('loadQuestions')}
    ${grab('moveQuestion')}
    function updateBulkActions() {}
    function checkEmptySurveyTypes() {}
    window.state = () => ({ questions, allQuestions });
  `);
  return { w, posted };
}

const rowsText = (w) => [...w.document.querySelectorAll('#questionsBody .q-text')].map(td => td.textContent);
const settle = () => new Promise(r => setTimeout(r, 0));

console.log('\nThe page shows the server\'s order, not newest first');
{
  const { w } = boot();
  await w.loadQuestions();
  ok(JSON.stringify(rowsText(w)) === JSON.stringify(['Exits lit', 'Sales binder', 'Kitchen clean', 'Model room']),
     `as sent (${rowsText(w).join(', ')})`);
  const rows = w.document.querySelectorAll('#questionsBody tr');
  ok(rows[0].querySelector('.q-move button[aria-label="Move up"]').disabled, 'the first cannot move up');
  ok(rows[3].querySelector('.q-move button[aria-label="Move down"]').disabled, 'the last cannot move down');
  ok(!rows[1].querySelector('.q-move button[aria-label="Move up"]').disabled, 'the others can');
}

console.log('\nMoving one down');
{
  const { w, posted } = boot();
  await w.loadQuestions();
  w.document.querySelectorAll('#questionsBody tr')[0].querySelector('button[aria-label="Move down"]').click();
  await settle(); await settle();
  ok(JSON.stringify(posted[0]) === JSON.stringify(['q_b', 'q_a', 'q_c', 'q_d']),
     'the whole list is sent with the two swapped');
  ok(JSON.stringify(rowsText(w)) === JSON.stringify(['Sales binder', 'Exits lit', 'Kitchen clean', 'Model room']),
     'and the page shows the new order');
}

console.log('\nWith a survey type filter on');
{
  const { w, posted } = boot();
  await w.loadQuestions();
  w.document.getElementById('surveyTypeFilter').value = 'sales';
  w.filterQuestions();
  ok(JSON.stringify(rowsText(w)) === JSON.stringify(['Exits lit', 'Sales binder', 'Model room']),
     'only that type, in the one order');
  // Move "Model room" up: past "Sales binder", the next one visible.
  const rows = w.document.querySelectorAll('#questionsBody tr');
  rows[2].querySelector('button[aria-label="Move up"]').click();
  await settle(); await settle();
  ok(JSON.stringify(posted[0]) === JSON.stringify(['q_a', 'q_d', 'q_c', 'q_b']),
     'it swaps with the visible neighbour; the hidden one keeps its place');
  ok(w.document.getElementById('surveyTypeFilter').value === 'sales'
     && JSON.stringify(rowsText(w)) === JSON.stringify(['Exits lit', 'Model room', 'Sales binder']),
     'and the filter is still on afterwards');
}

console.log(failures ? `\n${failures} failure(s)` : '\nStandards can be put in order.');
process.exit(failures ? 1 : 0);
