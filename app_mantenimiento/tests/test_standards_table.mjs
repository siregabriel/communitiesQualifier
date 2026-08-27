/*
  The Standards manager table, after quieting it down.

  Greg edits standards here, so the structure was deliberately left alone:
  same columns in the same order, same buttons in the same places, same click
  to expand the community list. Only the visual weight changed — which is easy
  to undo by accident, hence these.

  The rule being held down: mark the exception, not the norm. A badge that says
  the same thing on every row is noise, and here it was the loudest thing on
  the page.
*/

import fs from 'fs';
import { JSDOM } from 'jsdom';

const html = fs.readFileSync(new URL('../templates/question_manager.html', import.meta.url), 'utf8');

let failures = 0;
const ok = (c, m) => { console.log((c ? '  ok   ' : '  FAIL ') + m); if (!c) failures++; };

/* Run the real renderQuestions() against a stub page. */
function render(questions, communityCount) {
  const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
  const js = scripts.reduce((a, b) => (b.length > a.length ? b : a), '');
  const dom = new JSDOM(`<!doctype html><html><body>
    <table><tbody id="questionsBody"></tbody></table>
    ${'<input class="community-checkbox">'.repeat(communityCount)}
  </body></html>`, { runScripts: 'outside-only', url: 'http://localhost/' });
  const w = dom.window;
  w.escapeHtml = (t) => String(t).replace(/[&<>"]/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  w.getSurveyTypeBadges = () => '<span class="survey-type-label">Standards</span>';
  w.updateBulkActions = () => {};
  w.toggleCommunityList = () => {};
  w.questions = questions;
  const body = js.slice(js.indexOf('function renderQuestions()'),
                        js.indexOf('function openEditModal'));
  w.eval(body + '\nrenderQuestions();');
  return w.document.getElementById('questionsBody');
}

const ALL = Array.from({ length: 39 }, (_, i) => `Community ${i + 1}`);
const q = (over) => Object.assign({
  id: 'q1', text: 'Month 4 — Regional sales and marketing director responsibilities',
  photo_required: false, communities: ALL, created_at: '2026-08-24T10:00:00',
}, over || {});

console.log('\nThe wording of the standard carries the row');
{
  const body = render([q()], 39);
  const cell = body.querySelector('td.q-text');
  ok(!!cell, 'the question text has a class of its own to be weighted by');
  ok(cell.textContent.includes('Regional sales'), 'and holds the standard');
  const css = html.slice(html.indexOf('td.q-text {'), html.indexOf('}', html.indexOf('td.q-text {')));
  ok(/font-size:\s*14\.5px/.test(css), 'set larger than the row around it');
  ok(/font-weight:\s*600/.test(css), 'and heavier');
  ok(/max-width:\s*460px/.test(css),
     'with room to sit on one line instead of wrapping to three');
}

console.log('\nThe default stops shouting');
{
  const body = render([q()], 39);
  const btn = body.querySelector('.community-count');
  ok(!!btn, 'the community control is still a button');
  ok(btn.getAttribute('onclick').includes('toggleCommunityList'),
     'and still opens the same list — the behaviour is untouched');
  ok(!btn.className.includes('is-partial'),
     'covering every community is the norm, so it is styled quietly');
  ok(!/🏘️/.test(html), 'the house emoji is gone with it');

  const css = html.slice(html.indexOf('.community-count {'), html.indexOf('.community-count:hover'));
  ok(/background:\s*none/.test(css), 'no saturated blue fill');
  ok(/border-bottom:\s*1px dotted/.test(css), 'a dotted underline shows it still opens');
}

console.log('\nThe exception is what stands out');
{
  const body = render([q({ communities: ALL.slice(0, 6) })], 39);
  const btn = body.querySelector('.community-count');
  ok(btn.className.includes('is-partial'),
     'a standard that covers only some communities is marked');
  ok(btn.textContent.includes('6 communities'), 'and says how many');
  const css = html.slice(html.indexOf('.community-count.is-partial {'),
                         html.indexOf('}', html.indexOf('.community-count.is-partial {')));
  ok(/#fff4e3/.test(css), 'in amber, so it reads as the unusual one');
}

console.log('\nPhoto required marks the exception too');
{
  const off = render([q()], 39);
  ok(!!off.querySelector('.photo-none'), 'not required shows a dash');
  ok(off.querySelector('.photo-none').textContent.trim() === '—', 'and nothing else');
  ok(!/badge-no/.test(off.innerHTML), 'no badge announcing the absence of a requirement');

  const on = render([q({ photo_required: true })], 39);
  ok(!!on.querySelector('i.photo-yes'), 'required shows a camera');
  ok(on.querySelector('i.photo-yes').getAttribute('title') === 'Photo required',
     'and says what it means on hover');
}

console.log('\nNothing about the structure moved');
{
  const body = render([q()], 39);
  const cells = [...body.querySelectorAll('tr:first-child > td')];
  ok(cells.length === 7, `the row still has its seven columns (${cells.length})`);
  ok(!!cells[0].querySelector('input.row-select'), 'select checkbox first, as before');
  ok(cells[1].classList.contains('q-text'), 'then the question text');
  ok(!!cells[6].querySelector('.action-buttons'), 'and the edit/delete buttons last');
  ok(/Aug 24, 2026/.test(cells[5].textContent), 'the created date is still there, just quieter');
}

console.log('\nStandards looks like the rest of the app');
{
  /* It is a separate template with its own styles, so it never had the page's
     ambient background and read as a different product. The definition lives
     in theme.css now — one copy, keyed on .main-content, which only the
     dashboard and this page use. Two copies would drift. */
  const theme = fs.readFileSync(new URL('../static/theme.css', import.meta.url), 'utf8');
  const dash = fs.readFileSync(new URL('../templates/dashboard.html', import.meta.url), 'utf8');

  ok(/@keyframes ambientDrift/.test(theme) && /@keyframes ambientTint/.test(theme),
     'the animation is defined in the shared stylesheet');
  ok(!/@keyframes ambientDrift/.test(dash),
     'and not also in the dashboard — one definition, not two');
  ok(/\.main-content::before/.test(theme), 'the colour layer is shared');
  ok(/\.main-content > \.container/.test(theme),
     "and this page's content is lifted above it, like the dashboard's");

  const users = ['dashboard.html', 'question_manager.html', 'reporte.html', 'login.html'];
  const withIt = users.filter(f =>
    /class="main-content"/.test(fs.readFileSync(new URL('../templates/' + f, import.meta.url), 'utf8')));
  ok(withIt.length === 2 && withIt.includes('question_manager.html'),
     `only the two pages that should have it do (${withIt.join(', ')})`);

  ok(/prefers-reduced-motion[\s\S]{0,160}animation: none/.test(theme),
     'and it still stops for anyone who asked for less movement');
}

console.log(failures ? `\n${failures} failure(s)` : '\nSame table, with the volume where it belongs.');
process.exit(failures ? 1 : 0);
