/*
  A move-in shows on the calendar on the day it was completed.

  Nov 2026: Betty Smith moved in at The Goldton at Venice. The move-in was
  marked complete that afternoon and the email went out, but the calendar had
  nothing on that day: it only placed a move-in on its planned date, which was
  still Oct 12. Gabriel: the calendar should show that it closed today.

  This runs the real renderCalendar() from dashboard.html in jsdom.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');
const start = html.indexOf('let calendarMonth = null;');
const end = html.indexOf('// Compact month mini-calendar');
if (start < 0 || end < start) { console.log('  FAIL could not find the calendar code'); process.exit(1); }
const calendarCode = html.slice(start, end);

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

async function render(moveins, year, month, day) {
  const dom = new JSDOM('<!doctype html><body><div id="gallery"></div></body>', { runScripts: 'outside-only' });
  const w = dom.window;
  w.eval(`
    var moveInsRaw = [], allSubmissions = [], regions = [], communityData = [];
    async function loadMoveInsRaw() {}
    function escapeHtml(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, c => '&#' + c.charCodeAt(0) + ';'); }
    function scoreColor() { return '#000'; }
    function calculateCommunityScore() { return null; }
    function maybeStartCalendarTour() {}
    ${calendarCode}
    window.__set = (m, y, mo, d) => { moveInsRaw = m; calendarMonth = new Date(y, mo, 1); calSelectedDay = _calKey(new Date(y, mo, d)); };
    window.__render = renderCalendar;
  `);
  w.__set(moveins, year, month, day);
  await w.__render();
  return w.document.getElementById('gallery');
}

const betty = {
  id: 'mv_1', resident_name: 'Betty Smith', community: 'The Goldton at Venice, Venice',
  target_date: '2026-10-12', status: 'completed', completed_at: '2026-11-07T17:08:00+00:00',
};

console.log('\nCompleted move-in on the calendar');
let g = await render([betty], 2026, 10, 7);
const nov7 = [...g.querySelectorAll('.cal-cell')].find(c => (c.querySelector('.cal-daynum') || {}).textContent === '7');
ok(nov7 && /1 completed/.test(nov7.textContent), 'the day it was completed carries a "completed" badge');
ok(/Move-in completed/.test(g.querySelector('.cal-detail').textContent)
   && /Betty Smith/.test(g.querySelector('.cal-detail').textContent),
   'that day\'s detail lists the move-in as completed');
ok(/planned 2026-10-12/.test(g.querySelector('.cal-detail').textContent), 'and says which day it was planned for');

g = await render([betty], 2026, 9, 12);
ok(/1 move-in/.test(g.textContent), 'the planned day still shows the move-in');
ok(!/completed/.test(g.querySelector('.cal-grid:not(.cal-weekhead)').textContent), 'and no completion in October');

g = await render([{ ...betty, status: 'active' }], 2026, 10, 7);
ok(!/completed/.test(g.querySelector('.cal-grid:not(.cal-weekhead)').textContent), 'a reopened move-in is no longer shown as completed');

g = await render([{ ...betty, completed_at: undefined }], 2026, 10, 7);
ok(!/completed/.test(g.querySelector('.cal-grid:not(.cal-weekhead)').textContent), 'one completed before the date was recorded shows nothing new');

if (failures) { console.log(`\n${failures} failure(s)`); process.exit(1); }
console.log('\nAll checks passed');
