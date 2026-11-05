/*
  People, grouped by community or by role — run rather than read.

  One long list was fine at thirty people. With Staff (six per community,
  starting with Laura Blakeman's team at The Goldton at Venice) it heads past
  two hundred, and Gabriel found it long and tiring to read. It now groups:
  by community (each community's ED and Staff, its region and regional, and a
  warning where there is no ED), or by role (collapsible sections), in compact
  cards three to a row.

  Cards are wired by delegation from a data-user attribute — never an onclick
  string around a name (CLAUDE.md: escapeHtmlForAttr turns ' into &#39;, which
  the parser decodes back into code).
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
const constant = (name) => {
  const i = html.indexOf(`const ${name} =`);
  if (i < 0) throw new Error(`no const ${name}`);
  let depth = 0, k = html.indexOf('=', i) + 1;
  for (; k < html.length; k++) {
    const ch = html[k];
    if (ch === '{' || ch === '[' || ch === '(') depth++;
    else if (ch === '}' || ch === ']' || ch === ')') depth--;
    else if (ch === ';' && depth === 0) break;
  }
  return html.slice(i, k + 1);
};

const VENICE = 'The Goldton at Venice, Venice';
const OSCAR = 'The Oscar at Georgetown';
const CANOPY = 'The Canopy At Beacon Woods';

const DATA = {
  status: 'success',
  communities: [VENICE, OSCAR, CANOPY],
  regions: [
    { id: 'gulf', name: 'Gulf', communities: [VENICE, CANOPY] },
    { id: 'texas', name: 'Texas', communities: [OSCAR] },
  ],
  counts: { admin: 1, corporate: 1, regional: 1, staff: 2, team: 2 },
  people: [
    { username: 'admin', name: 'Administrator', role: 'admin', scope: 'All communities', last_login: '2026-11-01' },
    { username: 'abbey.isbell', name: 'Abbey Isbell', role: 'corporate', title: 'Chief of Staff', scope: 'All communities', last_login: '2026-11-01' },
    { username: 'lauren.hamilton', name: 'Lauren Hamilton', role: 'regional', region_id: 'gulf', scope: 'Gulf', last_login: '2026-11-01' },
    { username: 'laura.blakeman', name: 'Laura Blakeman', role: 'staff', communities: [VENICE], scope: VENICE, last_login: '2026-11-01', online: true },
    { username: 'amy.bollier', name: 'Amy Bollier', role: 'staff', communities: [OSCAR], scope: OSCAR, last_login: '2026-11-01' },
    { username: "cait.o'whelan", name: "Caitlin O'Whelan", role: 'team', title: 'Executive Chef', communities: [VENICE], scope: VENICE },
    { username: 'antoninette', name: '<b>Antoninette</b>', role: 'team', title: 'Business Office Director', communities: [VENICE], scope: VENICE, last_login: '2026-11-02', must_change: true },
  ],
};

function world(view) {
  const dom = new JSDOM(`<!doctype html><body><div id="gallery"></div></body>`,
                        { runScripts: 'outside-only', url: 'https://x.example/' });
  const w = dom.window;
  if (view) w.localStorage.setItem('atlasPeopleView', view);
  w.eval(`
    var opened = [], resets = [], viewAs = [], added = 0;
    function escapeHtml(s) { return String(s == null ? '' : s).replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }
    function avatarColor() { return '#334155'; }
    function profileInitials(n) { return String(n).slice(0, 2).toUpperCase(); }
    function timeAgo() { return '2 days ago'; }
    function openPersonEdit(u) { opened.push(u); }
    function peopleResetPassword(u) { resets.push(u); }
    function startViewAs(u) { viewAs.push(u); }
    function openAddPerson() { added++; }
    var peopleData = ${JSON.stringify(DATA)};
    var peopleFilter = { q: '', role: 'all' };
    ${constant('PEOPLE_VIEW_KEY')}
    ${constant('PEOPLE_ROLE_META')}
    ${(html.match(/let peopleCollapsed = [^;]+;/) || ['/* missing */'])[0].replace('let ', 'var ')}
    ${['peopleSetRole', 'peopleSearch', 'peopleView', 'setPeopleView', 'peopleMatches', 'peopleStatus',
       'peopleAvatar', 'peopleCard', 'peopleSection', 'peopleByRoleHtml', 'peopleCommunityRow',
       'peopleByCommunityHtml', 'drawPeopleBody', 'drawPeople', 'wirePeople'].map(grab).join('\n')}
  `);
  w.drawPeople();
  return w;
}

const $ = (w, sel) => w.document.querySelector(sel);
const $$ = (w, sel) => [...w.document.querySelectorAll(sel)];
const comm = (w, name) => $$(w, '.pp-comm').find(c => $(w, '.pp-comm-name') && c.querySelector('.pp-comm-name').textContent === name);
const click = (w, el) => el.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));

console.log('\nBy community is the default');
{
  const w = world();
  ok($(w, '[data-view="community"]').classList.contains('on'), 'the community view is selected');
  const venice = comm(w, VENICE);
  ok(!!venice, 'Venice has a card');
  const rows = [...venice.querySelectorAll('.pp-row')];
  ok(rows.length === 3, `its ED and two Staff (${rows.length})`);
  ok(/Laura Blakeman/.test(rows[0].textContent) && /ED/.test(rows[0].textContent), 'the ED first, marked ED');
  ok(/Executive Chef/.test(venice.textContent), 'Staff show their position');
  ok(/Gulf · Lauren Hamilton/.test(venice.querySelector('.pp-comm-sub').textContent), 'with the region and its regional');
}

console.log('\nThe gaps show');
{
  const w = world();
  const canopy = comm(w, CANOPY);
  ok(canopy.classList.contains('pp-gap'), 'a community with no ED is marked');
  ok(/No Executive Director/.test(canopy.textContent) && /reach nobody/.test(canopy.textContent), 'and says what that costs');
  ok(!comm(w, VENICE).classList.contains('pp-gap'), 'one with an ED is not');
  ok(/No staff yet/.test(comm(w, OSCAR).textContent), 'and a community with no Staff says so');
}

console.log('\nFiltering to Staff does not invent a missing ED');
{
  const w = world();
  click(w, $(w, '[data-role="team"]'));
  const venice = comm(w, VENICE);
  ok(venice && !venice.classList.contains('pp-gap') && !/No Executive Director/.test(venice.textContent),
     'Venice has an ED even when only Staff are being shown');
  ok(comm(w, CANOPY) === undefined, 'and a community with nobody matching is left out');
}

console.log('\nLeadership has its own section');
{
  const w = world();
  const names = $$(w, '.pp-card .pp-name').map(n => n.textContent);
  ok(names.includes('Abbey Isbell') && names.includes('Lauren Hamilton') && names.includes('Administrator'),
     'admins, corporate and regionals, as cards');
  ok(!names.includes('Laura Blakeman'), 'and EDs are not repeated there');
}

console.log('\nSearch');
{
  const w = world();
  const input = $(w, '#pplSearch');
  input.value = 'chef';
  input.dispatchEvent(new w.Event('input'));
  ok($(w, '#pplSearch') === input, 'the search box is the same element, so the cursor stays in it');
  ok($$(w, '.pp-comm').length === 1 && comm(w, VENICE), 'only the community with a match is left');
  ok(comm(w, VENICE).querySelectorAll('.pp-row').length === 1, 'showing only the person who matches');
  ok($$(w, '.pp-card').length === 0, 'and leadership with no match is not shown');

  input.value = 'canopy';
  input.dispatchEvent(new w.Event('input'));
  ok(comm(w, CANOPY), 'a community found by its own name, even with nobody in it');
}

console.log('\nBy role');
{
  const w = world();
  click(w, $(w, '[data-view="role"]'));
  ok(w.localStorage.getItem('atlasPeopleView') === 'role', 'the choice is remembered');
  ok($(w, '[data-view="role"]').classList.contains('on'), 'and shown as selected');
  const heads = $$(w, '.pp-sec-head').map(h => h.textContent.replace(/\s+/g, ' ').trim());
  ok(heads.length === 3, `three sections (${heads.join(' | ')})`);
  ok(/Staff/.test(heads[2]) && $(w, '[data-sec="team"]').getAttribute('aria-expanded') === 'false',
     'Staff, the long one, starts folded');
  ok(!$$(w, '.pp-card .pp-name').some(n => /O'Whelan/.test(n.textContent)), 'so its people are not drawn');
  click(w, $(w, '[data-sec="team"]'));
  ok($$(w, '.pp-card .pp-name').some(n => /O'Whelan/.test(n.textContent)), 'opening it shows them');

  const w2 = world('role');
  const input = $(w2, '#pplSearch');
  input.value = 'whelan';
  input.dispatchEvent(new w2.Event('input'));
  ok($$(w2, '.pp-card .pp-name').some(n => /O'Whelan/.test(n.textContent)),
     'a search opens every section, so a match is never hidden in a fold');
}

console.log('\nThe role chips still filter');
{
  const w = world('role');
  click(w, $(w, '[data-role="staff"]'));
  const names = $$(w, '.pp-card .pp-name').map(n => n.textContent);
  ok(names.length === 2 && names.every(n => /Laura|Amy/.test(n)), `Directors only (${names.join(', ')})`);
}

console.log('\nClicking');
{
  const w = world('role');
  click(w, $(w, '[data-sec="team"]'));
  const card = $$(w, '.pp-card').find(c => /O'Whelan/.test(c.textContent));
  click(w, card);
  ok(w.opened[0] === "cait.o'whelan", `a card opens that person, apostrophe and all (${w.opened[0]})`);
  click(w, card.querySelector('[data-act="reset"]'));
  ok(w.resets[0] === "cait.o'whelan" && w.opened.length === 1, 'the key resets the password, and opens nothing');
  ok(!card.querySelector('[data-act="viewas"]'), 'Staff have no "view as"');
  const ed = $$(w, '.pp-card').find(c => /Laura Blakeman/.test(c.textContent));
  click(w, ed.querySelector('[data-act="viewas"]'));
  ok(w.viewAs[0] === 'laura.blakeman', 'an ED card offers "view as"');

  const wc = world();
  click(wc, comm(wc, VENICE).querySelector('.pp-row'));
  ok(wc.opened[0] === 'laura.blakeman', 'a row in a community card opens that person too');
  click(wc, comm(wc, VENICE).querySelector('.pp-row [data-act="reset"]'));
  ok(wc.resets[0] === 'laura.blakeman' && wc.opened.length === 1,
     'and its key resets the password without switching views');
  click(wc, $(wc, '#pplAdd'));
  ok(wc.added === 1, 'Add person still works');
  ok(!/onclick=/.test($(wc, '#pplBody').innerHTML), 'and no handler is written into the markup');
}

console.log('\nStatus, and names as text');
{
  const w = world('role');
  click(w, $(w, '[data-sec="team"]'));
  const dots = Object.fromEntries($$(w, '.pp-card').map(c => [c.dataset.user, c.querySelector('.pp-dot')]));
  ok(dots['laura.blakeman'].classList.contains('pp-on'), 'in the app now: green');
  ok(dots["cait.o'whelan"].classList.contains('pp-warn') && /Never signed in/.test(dots["cait.o'whelan"].title),
     'never signed in: amber, and the tooltip says so');
  ok(dots['antoninette'].classList.contains('pp-warn'), 'must set a new password: amber too');
  ok(!$(w, '#pplBody b'), 'a name with markup in it is shown as text');
}

console.log(failures ? `\n${failures} failure(s)` : '\nPeople read by community, or by role.');
process.exit(failures ? 1 : 0);
