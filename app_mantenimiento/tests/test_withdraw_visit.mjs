/*
  "Withdraw this visit" in the visit panel, run in the page's own code.

  Katie Beattie filed a visit wrong and asked how to restart it; there was no
  way short of editing the server's files. The panel now offers to withdraw a
  visit to whoever the server says may (can_withdraw), asks why, and can hand
  the answers back as an unfinished visit. This holds down that the offer
  appears only when the server made it, that it posts what was typed to the
  visit it is about, that a name cannot inject markup, and that nothing keeps
  drawing the withdrawn visit from a cached copy. Server side:
  test_withdraw_visit.py.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

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

function boot(me, reply = { status: 200, body: { status: 'success', redo: 'created' } }) {
  const dom = new JSDOM(`<!doctype html><body><div id="slidePanelBody"></div></body>`,
                        { runScripts: 'outside-only' });
  const w = dom.window;
  w.posted = [];
  w.reply = reply;
  w.eval(`
    var currentUsername = ${JSON.stringify(me)};
    var inspectionsCache = { data: { stale: true }, timestamp: Date.now() };
    function escapeHtml(s) {
      return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
    var closed = 0, reloaded = 0;
    function closeSlidePanel() { closed++; }
    async function loadInspections() { reloaded++; }
    async function fetch(url, opts) {
      posted.push({ url, body: JSON.parse(opts.body) });
      return { ok: reply.status === 200, json: async () => reply.body };
    }
    ${grab(dash, 'renderWithdrawSection')}
    ${grab(dash, 'wireWithdrawSection')}
  `);
  w.show = (wd) => {
    w.document.getElementById('slidePanelBody').innerHTML = w.renderWithdrawSection(wd);
    w.wireWithdrawSection(wd);
  };
  return w;
}

const KATIES = { id: 'insp_1793754642997_4261', owner: 'katie.beattie',
                 inspector: 'Katie Beattie', workedOn: false };
const $ = (w, id) => w.document.getElementById(id);
const tick = () => new Promise((r) => setTimeout(r, 0));

console.log('Offered only where the server offered it');
{
  const w = boot('carol.brinegar');
  w.show(null);
  ok(!$(w, 'withdrawOpen'), 'no can_withdraw from the server, no button');
}

console.log('\nKatie, on her own visit');
{
  const w = boot('katie.beattie');
  w.show(KATIES);
  ok(!!$(w, 'withdrawOpen'), 'the button is there');
  ok($(w, 'withdrawForm').hidden, 'and the form waits behind it');
  ok(/Start it again with these answers/.test($(w, 'withdrawForm').textContent),
     'the redo is worded for the person who filed it');
  ok($(w, 'withdrawRedo').checked, 'and starts ticked: she asked to redo it');
  ok(!/already followed/.test($(w, 'withdrawForm').textContent), 'no follow-up warning when there was none');
  ok(/Withdraw & redo this visit/.test($(w, 'withdrawOpen').textContent), 'the button says it can be redone');
  ok(/24 hours/.test(($(w, 'withdrawHint') || {}).textContent || ''), 'and she is told how long she has');

  $(w, 'withdrawOpen').click();
  ok(!$(w, 'withdrawForm').hidden && $(w, 'withdrawOpen').hidden, 'opening shows the form');
  ok($(w, 'withdrawHint').hidden, 'and puts the hint away with the button');

  $(w, 'withdrawGo').click();
  await tick();
  ok(w.posted.length === 0, 'no reason, nothing sent');
  ok(/why/i.test($(w, 'withdrawMsg').textContent), `and it says so — "${$(w, 'withdrawMsg').textContent}"`);

  $(w, 'withdrawReason').value = '  I did this review incorrectly  ';
  $(w, 'withdrawGo').click();
  await tick(); await tick();
  const p = w.posted[0] || {};
  ok(p.url === '/api/inspections/insp_1793754642997_4261/withdraw', `posted to her visit — ${p.url}`);
  ok(p.body && p.body.reason === 'I did this review incorrectly' && p.body.redo === true,
     `with the reason and the redo — ${JSON.stringify(p.body)}`);
  ok(/unfinished visits/.test($(w, 'withdrawMsg').textContent), 'tells her where her answers went');
  ok(w.eval('inspectionsCache.data') === null, 'the cached visits are dropped, so the panel cannot redraw it');
}

console.log('\nUnticked, no redo is asked for');
{
  const w = boot('katie.beattie', { status: 200, body: { status: 'success', redo: null } });
  w.show(KATIES);
  $(w, 'withdrawOpen').click();
  $(w, 'withdrawRedo').checked = false;
  $(w, 'withdrawReason').value = 'Wrong community';
  $(w, 'withdrawGo').click();
  await tick(); await tick();
  ok(w.posted[0].body.redo === false, 'redo: false');
}

console.log('\nWhen the answers could not come back, it says so');
{
  const w = boot('katie.beattie', { status: 200, body: { status: 'success', redo: 'unavailable' } });
  w.show(KATIES);
  $(w, 'withdrawOpen').click();
  $(w, 'withdrawReason').value = 'Wrong';
  $(w, 'withdrawGo').click();
  await tick(); await tick();
  ok(/could not be brought back/.test($(w, 'withdrawMsg').textContent),
     `not a silent "Withdrawn." — ${$(w, 'withdrawMsg').textContent}`);
}

console.log('\nAn administrator, on a visit somebody already followed up');
{
  const w = boot('gabriel');
  w.show({ ...KATIES, workedOn: true });
  ok(/Give Katie Beattie an unfinished visit/.test($(w, 'withdrawForm').textContent),
     'the redo names who it goes to');
  ok(/already followed this visit up/.test($(w, 'withdrawForm').textContent), 'and warns what goes with it');
  ok(!$(w, 'withdrawHint'), 'no 24-hour hint: an administrator has no limit');
}

console.log('\nA refusal is shown, and nothing is dropped');
{
  const w = boot('katie.beattie', { status: 403, body: { status: 'error', message: 'Ask an administrator.' } });
  w.show(KATIES);
  $(w, 'withdrawOpen').click();
  $(w, 'withdrawReason').value = 'Wrong';
  $(w, 'withdrawGo').click();
  await tick(); await tick();
  ok($(w, 'withdrawMsg').textContent === 'Ask an administrator.', 'the server\'s reason');
  ok(!$(w, 'withdrawGo').disabled, 'and the button works again');
  ok(w.eval('inspectionsCache.data') !== null, 'the cache is kept: the visit is still there');
}

console.log('\nA name cannot become markup');
{
  const w = boot('gabriel');
  w.show({ ...KATIES, inspector: '<img src=x onerror=alert(1)>' });
  ok(!w.document.querySelector('#slidePanelBody img'), 'no element made from the inspector name');
}

if (failures) { console.log(`\n${failures} failed`); process.exit(1); }
console.log('\nAll passed.');
