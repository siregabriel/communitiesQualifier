/*
  What a card says about a community nobody has been to.

  It said "Oviedo · visited No visits yet". The cause is worth more than the
  symptom: the field that holds the date of the last visit was being set to
  the words "No visits yet" when there wasn't one. A sentence in a date's slot
  is truthy, so

      community.lastVisit ? `visited ${text}` : text

  took the first branch and glued the label onto the excuse. The reliable
  signal for "never" was next to it the whole time — lastVisitTs, which is 0 —
  and two other readers in the same file already used it.

  So the fix is the field, not the sentence: it holds a date or nothing, and
  each place decides its own words.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

/* Render the card's subtitle the way the template does, from the same two
   expressions, so this checks the wording rather than a copy of it. */
const cardDate = (() => {
  const i = html.indexOf('<div class="card-date">');
  const line = html.slice(i, html.indexOf('</div>', i));
  return line.replace('<div class="card-date">', '');
})();
const lastVisitText = (() => {
  const i = html.indexOf('const lastVisitText =');
  return html.slice(i, html.indexOf(';', i));
})();

const subtitle = (community, place) => {
  const w = new JSDOM('', { runScripts: 'outside-only' }).window;
  w.community = community;
  w.escapeHtml = (s) => String(s == null ? '' : s);
  w.where = { place };
  return w.eval(`${lastVisitText}; \`${cardDate}\``).trim();
};

console.log('\nA community nobody has been to');
{
  const never = { name: 'The Georgian Lakeside', lastVisit: '', lastVisitTs: 0 };
  const out = subtitle(never, '');
  ok(out === 'No visits yet', `it just says so — "${out}"`);
  ok(!/visited No visits/.test(out), 'and not "visited No visits yet"');
}

console.log('\nWith a town in its name');
{
  const never = { name: 'Madison at Oviedo', lastVisit: '', lastVisitTs: 0 };
  const out = subtitle(never, 'Oviedo');
  ok(out === 'Oviedo · No visits yet', `the town, then the fact — "${out}"`);
}

console.log('\nOne that has been visited');
{
  const been = { name: 'Madison at Ocoee', lastVisit: '9/18/2026',
                 lastVisitTs: 1789000000000 };
  ok(subtitle(been, 'Ocoee') === 'Ocoee · visited 9/18/2026',
     `reads as before — "${subtitle(been, 'Ocoee')}"`);
  ok(subtitle(been, '') === 'visited 9/18/2026',
     'and without a town, just the date');
}

console.log('\nThe field holds a date or nothing');
{
  /* The whole point. A sentence stored here is what made the bug possible,
     and it would make it possible again the next time somebody writes
     `lastVisit ? ... : ...` without knowing. */
  const i = html.indexOf('lastVisitTs: 0,');
  const block = html.slice(i - 700, i + 100);
  ok(/lastVisit: '',/.test(block),
     'the never-visited case stores an empty string, not a sentence');
  ok(!/lastVisit: 'No visits yet'/.test(html),
     'and the sentence is nowhere in a data field');
}

console.log('\nEvery reader asks the date, not the words');
{
  /* A community reader that branches on lastVisit's truthiness is this bug
     again. Narrowed to the community objects on purpose: the leaderboard keeps
     a performerMap whose lastVisit is a timestamp rather than a formatted
     date, and branching on that one is correct. An earlier version of this
     check flagged it, which is a test complaining about a different field that
     happens to share a name. */
  const bad = [...html.matchAll(/\b(community|c)\.lastVisit \?/g)].map(m => m[0]);
  ok(bad.length === 0, `no community reader branches on the text (${bad.join(', ') || 'none'})`);
  ok(/p\.lastVisit \? new Date\(p\.lastVisit\)/.test(html),
     'while the leaderboard, whose lastVisit really is a timestamp, still does');

  const i = html.indexOf('Last visit: ${escapeHtml(c.lastVisit)}');
  ok(i > 0, 'the dashboard row still shows the date when there is one');
  ok(/c\.lastVisitTs\s*\n?\s*\?/.test(html.slice(i - 200, i)),
     'and asks lastVisitTs first, so it cannot print "Last visit: " with nothing after it');
}

console.log(failures ? `\n${failures} failure(s)` : '\nNever visited reads as never visited.');
process.exit(failures ? 1 : 0);
