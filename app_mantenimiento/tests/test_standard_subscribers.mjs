/*
  Settings → Visit report subscribers: picking standards, run rather than read.

  A subscriber can ask for only some standards (the server side is
  test_standard_subscribers.py). The row must show the pick it was saved
  with, send what is ticked, and send it even with "All visits" on — the
  standards narrow what they get, not which visits.
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

function world(sub) {
  const dom = new JSDOM(`<!doctype html><body><div id="esSubscribers"></div></body>`,
    { runScripts: 'outside-only' });
  const w = dom.window;
  w.eval(`
    var calls = [];
    var esRegions = [{ id: 'north', name: 'North' }];
    var esInspectors = [];
    var esStandards = [{ id: 'q_social', text: 'Social Media' }, { id: 'q_lobby', text: 'Lobby' }];
    function escapeHtml(s) { return String(s); }
    function fetch(url, opts) { calls.push({ url, body: JSON.parse(opts.body) });
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ status: 'success' }) }); }
    async function loadEmailSettings() {} async function loadNotificationSummary() {}
    ${grab('subscriberRowHtml')}
    ${grab('filterSubStandards')}
    ${grab('saveSingleSubscriber')}
  `);
  w.document.getElementById('esSubscribers').innerHTML = w.subscriberRowHtml(sub, false);
  return w;
}

const save = async (w) => {
  w.saveSingleSubscriber(w.document.querySelector('.sub-row button.btn-primary'));
  await new Promise(r => setTimeout(r, 0));
  return w.calls[0].body;
};

console.log('standard subscribers');

{
  const w = world({ email: 'social@atlas.com', regions: [], inspectors: [], standards: ['q_social'] });
  const ticked = [...w.document.querySelectorAll('.sub-standard:checked')].map(c => c.value);
  ok(JSON.stringify(ticked) === '["q_social"]', 'a saved pick shows ticked');
  ok(w.document.querySelector('.sub-all').checked, 'and the row still reads "All visits"');
  const body = await save(w);
  ok(JSON.stringify(body.standards) === '["q_social"]', 'sent with "All visits" on');
}

{
  const w = world({ email: 'all@atlas.com', regions: ['north'], inspectors: [] });
  const body = await save(w);
  ok(Array.isArray(body.standards) && body.standards.length === 0,
     'nothing ticked sends none (the whole report)');
}

{
  const w = world({ email: 'x@atlas.com', regions: [], inspectors: [], standards: [] });
  const f = w.document.querySelector('.sub-std-filter');
  f.value = 'social';
  w.filterSubStandards(f);
  const shown = [...w.document.querySelectorAll('.sub-std-item')].filter(l => !l.hidden)
    .map(l => l.textContent.trim());
  ok(JSON.stringify(shown) === '["Social Media"]', 'the filter narrows the list');
}

if (failures) { console.log(`\n${failures} failure(s)`); process.exit(1); }
console.log('\nall passed');
